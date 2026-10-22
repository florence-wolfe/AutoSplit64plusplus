import time
from threading import Thread
import logging

import cv2
import numpy as np

from . import config, detection_model, irises, livesplit, perception
from .game_capture import GameCapture
from .model import Model, PredictionInfo
from .image_utils import convert_to_cv2
from .route_loader import load_or_none as load_route
from .processing import ProcessorSwitch

from .constants import (
    NO_FADE,
    FADEOUT_PARTIAL,
    FADEOUT_COMPLETE,
    FADEIN_PARTIAL,
    FADEIN_COMPLETE,
    STAR_REGION,
    FADEOUT_REGION,
    XCAM_REGION,
    LIVES_REGION,
    SPLIT_INITIAL,
    MODEL_PATH,
    MODEL_PATH_LEGACY,
    MODEL_WIDTH,
    MODEL_HEIGHT,
    CONFIRMATION_MODE,
    INITIAL_STATE
)


# What split detection does and why, in the session log
log = logging.getLogger("detection")
# How long the HUD shows a fade for it to start one between looks: a game frame, give or take the capture's timing
GAME_FRAME = 0.9 / 30
# Seconds of looks the iris matcher needs to judge a fadeout
MIN_LOOKING = 1
# The lives count once the star count model is this sure of the same number this many looks in a row
LIVES_SURE, LIVES_LOOKS = 0.9, 3
# Seconds a capture lost in a run, e.g. by the capture software restarting, is looked for before reporting it, and
# between looks
CAPTURE_RECOVERY_TIME, CAPTURE_RETRY_INTERVAL = 300, 1
# Settings' names for the connection and operation modes
CONNECTION_MODES = ["Named Pipe", "TCP", "LiveSplit One"]
OPERATION_MODES = ["Probability", "X-Cam"]


class SplitDetection(Thread):
    # TODO: Add all error messages to constants with associated error code
    def __init__(self):
        super().__init__()

        # Split detection's state, which each start begins afresh
        for name, value in INITIAL_STATE.items():
            setattr(self, name, value)

        # Load config
        config.load_config()

        # Initialize LiveSplit Connection
        self._ls_socket = None

        # Load Route
        self._route = load_route(config.get("route", "path"))

        # Initialize Game Capture
        # Without a route, starting fails on it, but the capture regions still need a version
        if config.get("game", "override_version") or not self._route:
            version = config.get("game", "version")
        else:
            version = self._route.version

        # Initialize the Game Capture
        self._game_capture = GameCapture(config.get("game", "use_obs"), config.get("game", "vc_fix"), config.get("game", "process_name"), config.get("game", "game_region"), version, config.get("game", "capture_device") if config.get("game", "capture_source") == "device" else None)

        # Initialise Prediction Model
        if config.get("model", "legacy"):
            self._model = Model(MODEL_PATH_LEGACY, MODEL_WIDTH, MODEL_HEIGHT, True)
        else:
            self._model = Model(MODEL_PATH, MODEL_WIDTH, MODEL_HEIGHT, False)

        # Main Loop Toggle
        self._running = False
        # When the game capture was lost, while it's being looked for again
        self._capture_lost_at = None

        # What the detection model does
        self._features = detection_model.FEATURES[detection_model.get()]

        # Operation Mode
        self._operation_mode = CONFIRMATION_MODE

        # Splitter Functionality Flags
        self._count_fades = False
        self._count_xcams = False
        self._make_predictions = True

        # Fadeout
        self._fade_start_time = 0
        # What fade the HUD showed in the last frame captured, on a look or between, and since when
        self._fade_seen = (None, 0.0)
        # Each fade and X-Cam split detection saw so far, which a split is sent on once, and the last split's
        self._fade_number = 0
        self._xcam_number = 0
        self._split_event = None
        self._minimum_fadeout_time = 0.4

        # X-Cam Detection
        self._xcam_found_time = 0
        self._xcam_point_x_ratio = 5/23
        self._xcam_point_y_ratio = 16/23
        _, _, self._xcam_region_width, self._xcam_region_height = self._game_capture.get_region_rect(XCAM_REGION)

        # Initialize ProcessorSwitch
        self._processor_switch = ProcessorSwitch()

        # Star Skip Error Correction
        self._matching_consecutive_predictions = 0
        self._minimum_consecutive_predictions = config.get("error", "minimum_consecutive_prediction")
        self._previous_prediction = self.prediction_info
        self._max_star_skip = config.get("error", "max_star_skip")
        self._star_skip_enabled = config.get("error", "star_skip")

        #
        self._in_game = False
        # Whether the timer ended the run, which leaves it past the last split
        self._run_ended = False

        try:
            self._route_length = len(self._route.splits)
            self._current_split = self._route.splits[0]
        except AttributeError:
            self._route_length = 0
            self._current_split = None

        # Callback Listeners
        self._update_listener = None
        self._error_listener = None

        # Load configuration
        self._black_threshold = config.get("thresholds", "black_threshold")
        self._white_threshold = config.get("thresholds", "white_threshold")
        self._xcam_lower_bound = np.array(config.get("split_xcam", "lower_bound"), dtype="uint8")
        self._xcam_upper_bound = np.array(config.get("split_xcam", "upper_bound"), dtype="uint8")
        self._xcam_threshold = config.get("thresholds", "xcam_pixel_threshold")
        self._xcam_bg_threshold = config.get("thresholds", "xcam_bg_threshold")
        self._xcam_bg_activation = config.get("thresholds", "xcam_bg_activation")
        self._xcam_rg_threshold = config.get("thresholds", "xcam_rg_threshold")
        self._xcam_rg_activation = config.get("thresholds", "xcam_rg_activation")
        self._split_cooldown = config.get("general", "split_cooldown")
        self._probability_threshold = config.get("thresholds", "probability_threshold")
        self._confirmation_threshold = config.get("thresholds", "confirmation_threshold")
        self._prediction_processing_length = config.get("error", "processing_length")
        self._undo_prediction_threshold = config.get("error", "undo_threshold")
        self._minimum_undo_count = config.get("error", "minimum_undo_count")
        self._detailed_output = config.get("advanced", "detailed_console_output")

        # Star Analysis Function
        if config.get("general", "operation_mode") == CONFIRMATION_MODE:
            self.analyze_star_count = self._analyze_star_count_confirmation_mode
        else:
            self.analyze_star_count = self._analyze_star_count_probability_mode

        #
        self._predictions = [PredictionInfo(0, 0)] * self._prediction_processing_length

        self.route = self._route

        try:
            self.route_length = self._route_length
            self.star_count = self._route.initial_star
        except AttributeError:
            pass

        self.logger = logging.getLogger(".log")

        # Whether what the HUD shows where the lives are is lives, which it isn't in Usamune
        self._lives_trusted = True
        self.forget_lives()

    def validity_check(self):

        if not livesplit.check_connection(self._ls_socket):
            self._error_occurred("Could not connect to LiveSplit.\nIs LiveSplit running?\nIf Connection mode is TCP, ensure the LiveSplit Server is started.\nIf Connection mode is LiveSplit One, connect it to ws://localhost:" + str(config.get("connection", "lso_port")) + " via Settings > Connect to Server.")
            return False
        
        try:
            self._game_capture.is_valid()
        except Exception as e:
            self._error_occurred(str(e))
            return False

        try:
            self._game_capture.capture()
        except Exception as e:
            self._error_occurred(str(e))
            return False

        if not self._check_capture_size():
            return False

        if not self._route:
            self._error_occurred("Unable to load route " + config.get("route", "path"))
            return False

        if not self._model.valid():
            self._error_occurred("Unable to load prediction model " + (MODEL_PATH_LEGACY if config.get("model", "legacy") else MODEL_PATH))
            return False

        return True

    def _check_capture_size(self):
        """ Report a capture whose size changed since its regions were configured """
        current_capture_size = self._game_capture.get_capture_size()

        if current_capture_size[0] != config.get("game", "capture_size")[0] or current_capture_size[1] != config.get("game", "capture_size")[1]:
            self._error_occurred("Capture windows dimensions have changed since last configuring coordinates. Please reconfigure capture coordinates and generate reset templates.")
            return False
        return True

    def _capture(self):
        """
        Capture the game. A capture lost in a run is looked for again, keeping what was counted, and reported only
        once it's lost for CAPTURE_RECOVERY_TIME. False while it's lost.
        """
        try:
            if self._capture_lost_at is not None:
                self._game_capture.reconnect()
            self._game_capture.capture()
        except Exception as e:
            now = time.perf_counter()
            if self._capture_lost_at is None:
                log.warning("Lost the game capture, looking for it again: %s", e)
                self._capture_lost_at = now
            elif now - self._capture_lost_at >= CAPTURE_RECOVERY_TIME:
                self._error_occurred(str(e))
                return False
            time.sleep(CAPTURE_RETRY_INTERVAL)
            return False

        if self._capture_lost_at is not None:
            log.info("Got the game capture back after %.0f s", time.perf_counter() - self._capture_lost_at)
            self._capture_lost_at = None
            return self._check_capture_size()
        return True

    def stop(self):
        if self._running:
            log.info("Stopped")
        self._running = False
    	# stop the livesplit connection
        livesplit.disconnect(self._ls_socket)
        # Destruct the shared memory connection
        self._game_capture.close()
        # Unload the model
        self._model.close()

    def run(self):
        try:
            self._running = True
            
            self._ls_socket = livesplit.connect()

            # A failing check reports the error, which also stops split detection
            if not self.validity_check():
                return
            log.info("Started: %s", self._setup())
            log.info("Detection model %s (%s)", detection_model.NAMES[detection_model.get()], detection_model.get())
            self._start_occurred()

            self._processor_switch._current_processor = self._current_split.split_type
            
            while self._running:
                self.current_time = time.perf_counter()
                if not self._capture():
                    continue
                try:
                    self._sync_split_index(livesplit.split_index(self._ls_socket))

                    self.analyze_fade_status()
                    if self._make_predictions:
                        self.analyze_star_count()
                        self.analyze_lives()

                    if self._count_xcams:
                        self.analyze_xcam_status()
                except Exception as e:
                    # Reporting the error stops split detection, so don't run the processes on this frame
                    self._error_occurred(str(e))
                    continue

                try:
                    if self._in_game:
                        self._processor_switch.execute(self._current_split.split_type)
                    else:
                        self._processor_switch.execute(SPLIT_INITIAL)
                except ConnectionAbortedError:
                    self._error_occurred("LiveSplit connection failed")
                
                try:
                    self.execution_time = time.perf_counter() - self.current_time
                    wait = 1 / self.fps - self.execution_time
                    # Sooner for a process's timed look
                    look_at = self._processor_switch.look_at()
                    if look_at is not None:
                        wait = min(wait, look_at - time.perf_counter())
                    self._game_capture.wait(wait, self.look_now if self.has(detection_model.LOOKS_BETWEEN) else None)
                except ValueError:
                    pass
                
        except Exception:
            self.logger.error("Fatal Error", exc_info=True)

    def _sync_split_index(self, ls_index):
        """ Follow the timer's split index. False means the timer didn't answer this time. """
        if ls_index is False:
            return
        ls_index = max(ls_index, 0)
        run_ended = ls_index >= len(self._route.splits)
        if run_ended and not self._run_ended:
            log.info("Timer ended the run")
        self._run_ended = run_ended
        if ls_index != self.split_index():
            self.set_split_index(ls_index)

    def analyze_xcam_status(self):
        xcam = self._game_capture.get_region(XCAM_REGION)

        # Initial threshold mask
        mask = cv2.inRange(xcam, self._xcam_lower_bound, self._xcam_upper_bound)
        output = cv2.bitwise_and(xcam, xcam, mask=mask)

        # Axis relationship mask
        xcam_int = xcam.astype(int)
        xcam_int_b, xcam_int_g, xcam_int_r = xcam_int.transpose(2, 0, 1)
        mask = ((np.abs(xcam_int_g - xcam_int_b) > self._xcam_bg_threshold) & (xcam_int_g > self._xcam_bg_activation)) |\
               ((np.abs(xcam_int_r - xcam_int_g) < self._xcam_rg_threshold) & (xcam_int_g > self._xcam_rg_activation))

        output[mask] = [0, 0, 0]

        non_black_pixels_mask = np.any(output != [0, 0, 0], axis=-1)
        output[non_black_pixels_mask] = [255, 255, 255]

        output_1d = output.flatten()

        self.xcam_percent = np.count_nonzero(output_1d) / output_1d.size

        if self.xcam_percent > self._xcam_threshold and output[int(self._xcam_point_x_ratio*self._xcam_region_width), int(self._xcam_point_y_ratio*self._xcam_region_height), 2] > 20:
            self._xcam_seen()
        else:
            self.in_xcam = False

    def _xcam_seen(self):
        """ An X-Cam is in view, a new one half a second after the last was """
        self.in_xcam = True
        if self.current_time - self._xcam_found_time > 0.5:
            self.xcam_count += 1
            self._xcam_number += 1
        self._xcam_found_time = self.current_time

    def fade_event(self):
        """ The fade split detection saw last, which a split on a fadeout or a fade-in is sent on once """
        return "fade", self._fade_number

    def xcam_event(self):
        """ The X-Cam split detection saw last, which a split on an X-Cam is sent on once """
        return "X-Cam", self._xcam_number

    def analyze_fade_status(self):
        seen = perception.fade(self._game_capture, self._black_threshold, self._white_threshold)
        self._saw_fade(seen)

        # Determine the current fade status
        if seen.hud_black:
            if self.fade_status == NO_FADE:
                self._fade_number += 1
                # Counted or not, a fadeout is where a life can be lost
                self._lives_since["fadeouts"] += 1
            if self.fade_status == NO_FADE and self._count_fades:
                self.fadeout_count += 1
                self.xcam_count = 0
                log.info("Fadeout %d: %s", self.fadeout_count, self._state())

            if seen.centre_black and self.current_time - self._fade_start_time > self._minimum_fadeout_time:
                self.fade_status = FADEOUT_COMPLETE
            else:
                self.fade_status = FADEOUT_PARTIAL
        elif seen.hud_white:
            if self.fade_status == NO_FADE:
                self._fade_number += 1
            if self.fade_status == NO_FADE and self._count_fades:
                self.fadein_count += 1
                self.xcam_count = 0
                log.info("Fade-in %d: %s", self.fadein_count, self._state())

            if not seen.fadein_white:
                self.fade_status = FADEIN_COMPLETE
            else:
                self.fade_status = FADEIN_PARTIAL
        else:
            self.fade_status = NO_FADE
            self._fade_start_time = self.current_time

    def look_now(self):
        """ Whether to look at the frame just captured, between looks: it starts a fade, or a process wants it """
        return self.fade_start() or self._processor_switch.look_now()

    def fade_start(self):
        """
        Whether the frame just captured starts a fade, which split detection then looks at right away, instead of up to
        a look later, or never for a fade shorter than a look. Once the HUD is black or white for a game frame: it can
        flicker across the black threshold as it comes back, within a frame on a 60 fps capture, which isn't a fade.
        """
        kind, since = self._saw_fade(perception.fade(self._game_capture, self._black_threshold, self._white_threshold))
        return kind is not None and self.fade_status == NO_FADE and time.perf_counter() - since >= GAME_FRAME

    def _saw_fade(self, seen):
        """ The fade the HUD shows, on a look or a frame between, and since when it's shown it """
        kind = "black" if seen.hud_black else "white" if seen.hud_white else None
        if kind != self._fade_seen[0]:
            self._fade_seen = (kind, time.perf_counter())
        return self._fade_seen

    def _analyze_star_count_probability_mode(self):
        try:
            resized_image = cv2.resize(
                convert_to_cv2(self._game_capture.get_region(STAR_REGION)), 
                (self._model.width, self._model.height)
            )
            try:
                self.prediction_info = self._model.predict(resized_image)
            except Exception as e:
                self._error_occurred(f"Model prediction failed: {str(e)}")
                return
        except cv2.error:
            self._error_occurred("An error occurred while processing the frame")
            return

        total_predictions = len(self._predictions)

        if self.star_count - 1 <= self.prediction_info.prediction <= self.star_count + 1 or self.prediction_info.prediction > 120:
            self._predictions.append(self.prediction_info)

            # Limit number of predictions
            if total_predictions > self._prediction_processing_length:
                self._predictions.pop(0)

            # Handle Prediction
            prev_two_probabilities = [self._predictions[i].probability for i in range(total_predictions - 2, total_predictions)
                                      if self._predictions[i].prediction == self.star_count + 1]

            try:
                result = next(x for x, val in enumerate(prev_two_probabilities) if val >= self._probability_threshold)

                if prev_two_probabilities[result ^ 1] >= self._confirmation_threshold:
                    self.set_star_count(self.star_count + 1)
                    if self.in_xcam:
                        self.xcam_count = 1
            except (StopIteration, IndexError):
                pass

        self._star_error_check()

    def _analyze_star_count_confirmation_mode(self):
        try:
            resized_image = cv2.resize(
                convert_to_cv2(self._game_capture.get_region(STAR_REGION)), 
                (self._model.width, self._model.height)
            )
            try:
                self.prediction_info = self._model.predict(resized_image)
            except Exception as e:
                self._error_occurred(f"Model prediction failed: {str(e)}")
                return
        except cv2.error:
            self._error_occurred("An error occurred while processing the frame")
            return

        total_predictions = len(self._predictions)

        if self.star_count - 1 <= self.prediction_info.prediction <= self.star_count + 1 or self.prediction_info.prediction > 120:
            self._predictions.append(self.prediction_info)

            # Limit number of predictions
            if total_predictions > self._prediction_processing_length:
                self._predictions.pop(0)

            if self.prediction_info.prediction == self.star_count + 1 and self.prediction_info.probability > self._confirmation_threshold:
                if self.current_time - self._xcam_found_time < 1:
                    self.set_star_count(self.star_count + 1)

        self._star_error_check()

    def _star_error_check(self):
        # Error Check
        # TODO: Handle fadeouts correctly. See below.
        # If split is undone, need to get previous fadeout count, set it to current, and add the fadeout count of the
        # incorrect star
        prev_star_probabilities = [p.probability for p in self._predictions if p.prediction == self.star_count - 1]

        if len(prev_star_probabilities) >= self._minimum_undo_count:
            if sum(prev_star_probabilities) / len(prev_star_probabilities) > self._undo_prediction_threshold:
                self.set_star_count(self.star_count - 1)
                self._undo_if_below_previous_split()

        try:
            # Predictions above 120 mean no star count was readable
            if self._star_skip_enabled and (self.previous_split_initial_star <= self.prediction_info.prediction <= self.next_split_split_star or self.prediction_info.prediction > 120):
                if self.prediction_info.prediction == self._previous_prediction.prediction and self.prediction_info.probability > self._probability_threshold:
                    self._matching_consecutive_predictions += 1
                elif self._matching_consecutive_predictions > 0:
                    self._matching_consecutive_predictions = 0

                if self._matching_consecutive_predictions >= self._minimum_consecutive_predictions and 0 < abs(self.prediction_info.prediction - self.star_count) <= self._max_star_skip and self.prediction_info.prediction <= 120:
                    self.set_star_count(self.prediction_info.prediction)
                    self._undo_if_below_previous_split()
        except AttributeError:
            pass

        self._previous_prediction = self.prediction_info

    def died(self):
        """
        Whether the fadeout ending now was a death, by the iris it closed with: the game closes the screen on a death
        with Bowser's head. A death takes back two fadeouts: its own, and the one that brought Mario into the stage, or
        into the fight, where dying sends him back to the stage.
        """
        if not self.has(detection_model.DEATHS):
            return False
        looks = list(self._game_capture.looks)
        # Too little to judge from, as when split detection has only just started
        if not looks or looks[-1][0] - looks[0][0] < MIN_LOOKING:
            return False
        late = self.has(detection_model.IRISES_ENDING_LATE)
        verdict = irises.classify(looks, early=irises.EARLY if late else irises.SHORT_EARLY)
        log.info("Iris %s: %s", verdict.iris, ", ".join(f"{name} {score:.2f}" for name, score in verdict.scores.items()))
        if verdict.iris != "bowser":
            return False
        # Which fadeout since the lives last changed, as a wrong call mustn't hide a death after it
        self._lives_since["death"] = self._lives_since["fadeouts"]
        fadeouts = self.fadeout_count
        self.fadeout_count = max(fadeouts - 2, 0)
        log.info("Death, Bowser's iris, fadeouts %d -> %d", fadeouts, self.fadeout_count)
        return True

    def forget_lives(self):
        """ Learn the lives afresh, and what happened since """
        self._lives = None
        self._lives_readings = []
        self._lives_since = {"fadeouts": 0, "death": None, "split": None}

    def analyze_lives(self):
        """ Read the lives, which count once the star count model is sure of the same number LIVES_LOOKS looks in a row """
        if not self._lives_trusted or not self.has(detection_model.DEATHS):
            return
        reading = self._read_lives()
        if reading.probability < LIVES_SURE or reading.prediction > 120:
            self._lives_readings = []
            return
        self._lives_readings = (self._lives_readings + [reading.prediction])[-LIVES_LOOKS:]
        if len(self._lives_readings) == LIVES_LOOKS and len(set(self._lives_readings)) == 1:
            if self._lives_readings[0] != self._lives:
                self._lives_changed(self._lives_readings[0])

    def _read_lives(self):
        region = convert_to_cv2(self._game_capture.get_region(LIVES_REGION))
        return self._model.predict(cv2.resize(region, (self._model.width, self._model.height)))

    def _lives_changed(self, lives):
        """
        The lives the HUD shows are now `lives`. One lost after a fadeout is a death, which takes back two fadeouts, as
        died() does, unless Bowser's iris counted it already, on the latest fadeout: deaths it can't see are falls, which close with a circle,
        as doors do, often into the dark. If it split on the death's fadeout, with none since, it undoes the split: a
        split on an earlier fadeout, e.g. leaving the stage before, was right.
        """
        if not self._lives_trusted:
            return
        before, since = self._lives, self._lives_since
        self._lives = lives
        self._lives_since = {"fadeouts": 0, "death": None, "split": None}
        if before is None:
            return
        log.info("Lives %d -> %d", before, lives)
        if lives == before + 1:
            return
        if lives != before - 1 or not since["fadeouts"]:
            # Lives go up or down by one, and down only in a death, which fades out
            self._lives_trusted = False
            log.info("Not following the lives: %d -> %d%s, so what the HUD shows there aren't lives, as in Usamune",
                     before, lives, " with no fadeout" if lives == before - 1 else "")
            return
        # Bowser's iris counted it, on the latest fadeout
        if since["death"] == since["fadeouts"]:
            return
        if since["split"] and since["split"][2] == since["fadeouts"]:
            index, fadeouts, _ = since["split"]
            self.undo()
            self.set_split_index(index)
            self.fadeout_count = max(fadeouts - 2, 0)
            log.info("Death, a life lost after a split, undid it, fadeouts %d -> %d", fadeouts, self.fadeout_count)
            return
        fadeouts = self.fadeout_count
        self.fadeout_count = max(fadeouts - 2, 0)
        log.info("Death, a life lost, fadeouts %d -> %d", fadeouts, self.fadeout_count)

    def _undo_if_below_previous_split(self):
        """ Undo the previous split when the star count is now below the star count it split on """
        index = self.split_index()
        if index > 0 and self.star_count < self._route.splits[index - 1].star_count:
            self.undo()

    def has(self, feature):
        """ Whether the detection model does the feature, as detection_model.FEATURES says """
        return feature in self._features

    def get_region(self, region):
        return self._game_capture.get_region(region)

    def get_region_rect(self, region):
        return self._game_capture.get_region_rect(region)

    def register_split_processor(self, split_type, processor):
        self._processor_switch.register_processor(split_type, processor)

    #
    # TIMER FUNCTIONS
    #

    def split(self, event=None):
        """ Split, once for `event`, the fade or X-Cam it's on, which the looks after see too, if it's on one """
        if event is not None and event == self._split_event:
            log.info("Split not sent, already split on this %s: %s", event[0], self._state())
            return

        # Cool-down period between splits
        if self.has(detection_model.SPLIT_COOLDOWN) and time.perf_counter() - self.last_split < self._split_cooldown:
            log.info("Split not sent, within the split cooldown: %s", self._state())
            return

        # Prevent splitting past the final split
        if self._run_ended:
            log.info("Split not sent, past the last split: %s", self._state())
            return

        log.info("Split: %s", self._state())
        self._split_event = event
        # The split, the fadeouts it split on, and the fadeouts since the lives last changed, to undo it if the lives
        # show it split on a death's fadeout
        self._lives_since["split"] = (self.split_index(), self.fadeout_count, self._lives_since["fadeouts"])
        livesplit.split(self._ls_socket)
        self.last_split = time.perf_counter()

    def reset(self):
        log.info("Reset the timer: %s", self._state())
        livesplit.reset(self._ls_socket)
        self._reset_occured()

    def restart(self):
        log.info("Restarted the timer: %s", self._state())
        livesplit.restart(self._ls_socket)
        self._reset_occured()
    
    def _reset_occured(self):
        self.set_star_count(self._route.initial_star)
        self.xcam_count = 0
        self._in_game = False

    def skip(self):
        log.info("Skipped the split: %s", self._state())
        livesplit.skip(self._ls_socket)

    def undo(self):
        log.info("Undid the split: %s", self._state())
        livesplit.undo(self._ls_socket)

    #
    # INFO FUNCTIONS
    #

    def current_split(self):
        return self._current_split

    def split_index(self):
        """ Return the current split index """
        try:
            return self._route.splits.index(self._current_split)
        except ValueError:
            log.warning("The current split %s isn't in the route", getattr(self._current_split, "title", None))

    def incoming_split(self, star_count=True, fadeout=True, fadein=True):
        if self.star_count != self._current_split.star_count and star_count:
            return False

        # TODO: Make only one fade need to match
        if self.fadeout_count != self._current_split.on_fadeout and fadeout:
            return False

        if self.fadein_count != self._current_split.on_fadein and fadein:
            return False

        return True

    #
    # TRACKING FUNCTIONS
    #

    def enable_predictions(self, enable):
        self._make_predictions = enable

    def enable_fade_count(self, enable):
        self._count_fades = enable
        self._reset_fade_count()

    def enable_xcam_count(self, enable):
        self._count_xcams = enable

    def set_in_game(self, in_game):
        if in_game != self._in_game:
            log.info("In game" if in_game else "Not in game")
        self._in_game = in_game

    def set_star_count(self, star_count):
        if star_count != self.star_count:
            prediction = self.prediction_info
            log.info("Star count %s -> %s, prediction %s", self.star_count, star_count,
                     f"{prediction.prediction} at {prediction.probability:.2f}" if prediction else "none")
        self._reset_fade_count()
        self.xcam_count = 0
        self.star_count = star_count
        self.collection_time = time.perf_counter()
        self._update_occurred()
        self._predictions = [PredictionInfo(0, 0)] * self._prediction_processing_length

    def set_split_index(self, index):
        # #  Check if running
        # if index == -1:
        #     return
        # # Check for reset
        # if index == 0:
        #     self._reset_occured()
        
        try:
            self._current_split = self._route.splits[index]
            log.info("Timer on split %d: %s", index + 1, self._current_split.title)

            self._reset_fade_count()
            self.xcam_count = 0

            # The star count the previous split started from
            if index >= 2:
                self.previous_split_initial_star = self._route.splits[index - 2].star_count
            else:
                self.previous_split_initial_star = self._route.initial_star

            try:
                self.next_split_split_star = self._route.splits[self.split_index() + 1].star_count
            except IndexError:
                pass

            self._update_occurred()
        except IndexError:
            pass

    #
    # HELPER FUNCTIONS
    #
    def set_start_listener(self, listener):
        self._start_listener = listener

    def _start_occurred(self):
        try:
            self._start_listener()
        except AttributeError:
            pass

    def set_update_listener(self, listener):
        self._update_listener = listener

    def set_error_listener(self, listener):
        self._error_listener = listener

    def _error_occurred(self, error):
        log.warning("Error: %s", error)
        try:
            self._error_listener(error)
        except AttributeError:
            pass

        self.stop()

    def _update_occurred(self):
        try:
            self._update_listener(self.split_index(), self.star_count, self.current_split().star_count)
        except AttributeError:
            pass

    def status(self):
        """ What split detection is doing, for the Debug window: the split it's on, what it needs and what's counted """
        split = self._current_split
        # Without a route, e.g. one that failed to load
        if split is None:
            return {"running": self._running, "in_game": self._in_game}
        return {
            "running": self._running, "in_game": self._in_game,
            "split_index": self.split_index(), "split_count": len(self._route.splits),
            "split": split.title, "split_type": split.split_type,
            "needs_stars": split.star_count, "needs_fadeouts": split.on_fadeout, "needs_fadeins": split.on_fadein,
            "needs_xcams": split.on_xcam,
            "stars": self.star_count, "fadeouts": self.fadeout_count, "fadeins": self.fadein_count, "xcams": self.xcam_count,
        }

    def _state(self):
        """ The split detection is on, what it needs and what's counted so far, for the log """
        split = self._current_split
        return (f"split {self.split_index() + 1} of {len(self._route.splits)}, {split.title} "
                f"(needs {split.star_count} stars, fadeout {split.on_fadeout}, fade-in {split.on_fadein}), "
                f"star count {self.star_count}, fadeouts {self.fadeout_count}, fade-ins {self.fadein_count}")

    def _setup(self):
        """ The route and settings split detection runs with, for the log """
        if config.get("game", "use_obs"):
            source = "the OBS Plugin"
        elif config.get("game", "capture_source") == "device":
            source = f"video device {config.get('game', 'capture_device')}"
        else:
            source = f"window of {config.get('game', 'process_name')}"
        route = self._route
        return (f"route {route.title} ({route.version}, {route.timing}, {len(route.splits)} splits), "
                f"capturing the {source}, game region {config.get('game', 'game_region')} "
                f"of {config.get('game', 'capture_size')}, VC fix {config.get('game', 'vc_fix')}, "
                f"connection mode {CONNECTION_MODES[config.get('connection', 'ls_connection_type')]}, "
                f"operation mode {OPERATION_MODES[config.get('general', 'operation_mode')]}, "
                f"SRL mode {config.get('general', 'srl_mode')}")

    def _reset_fade_count(self):
        self.fadeout_count = 0
        self.fadein_count = 0
