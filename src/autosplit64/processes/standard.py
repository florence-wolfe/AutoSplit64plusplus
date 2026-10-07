import time

import cv2
import numpy as np

from autosplit64 import core

from autosplit64.core.resource_utils import resource_path

from autosplit64.core import config
from autosplit64.core.image_utils import is_black, is_white
from autosplit64.core.processing import Process


class ProcessWait(Process):
    def __init__(self,):
        super().__init__()

        self.register_signal("FADEOUT")

    def execute(self):
        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        return self.signals["LOOP"]

    def on_transition(self):
        core.enable_predictions(False)
        core.fps = 10
        super().on_transition()


class _RunStartProcess(Process):
    """ Detects being in game from the star count, also mid-run when that's enabled """

    def __init__(self):
        super().__init__()
        self._star_skip_enabled = config.get("general", "mid_run_start_enabled")
        self._prev_prediction = -1
        self._jump_predictions = 0

    def _in_game_detected(self):
        if core.split_index() > 0:
            prev_split_star = core.route.splits[core.split_index()-1].star_count
        else:
            prev_split_star = core.route.initial_star

        probability_threshold = config.get("thresholds", "probability_threshold")

        if core.prediction_info.prediction == core.star_count and core.prediction_info.probability > probability_threshold:
            core.enable_fade_count(True)
            core.enable_xcam_count(True)
            return True
        elif self._star_skip_enabled and prev_split_star <= core.prediction_info.prediction <= core.current_split().star_count and core.prediction_info.probability > probability_threshold:
            if core.prediction_info.prediction == self._prev_prediction:
                self._jump_predictions += 1
            else:
                self._jump_predictions = 0

            if self._jump_predictions >= 4:
                core.enable_fade_count(True)
                core.enable_xcam_count(True)
                core.set_star_count(core.prediction_info.prediction)
                self._jump_predictions = 0
                self._prev_prediction = -1
                return True

            self._prev_prediction = core.prediction_info.prediction

        return False


class ProcessRunStart(_RunStartProcess):
    def __init__(self):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("START")

    def execute(self):
        if core.fade_status in (core.FADEOUT_COMPLETE, core.FADEOUT_PARTIAL):
            return self.signals["FADEOUT"]
        if self._in_game_detected():
            core.set_in_game(True)
            return self.signals["START"]
        return self.signals["LOOP"]

    def on_transition(self):
        core.enable_fade_count(False)
        core.fps = 6

        super().on_transition()


class ProcessRunStartUpSegment(_RunStartProcess):
    def __init__(self):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("START")

    def execute(self):
        if core.fade_status in (core.FADEOUT_COMPLETE, core.FADEOUT_PARTIAL):
            return self.signals["FADEOUT"]
        if self._in_game_detected():
            return self.signals["START"]
        return self.signals["LOOP"]

    def on_transition(self):
        core.enable_fade_count(False)
        core.fps = 6

        super().on_transition()


class ProcessStarCount(Process):
    def __init__(self):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("FADEIN")

    def execute(self):
        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if core.fade_status in (core.FADEIN_PARTIAL, core.FADEIN_COMPLETE):
            return self.signals["FADEIN"]

        return self.signals["LOOP"]

    def on_transition(self):
        core.fps = config.get("advanced", "star_process_frame_rate")
        core.enable_predictions(True)
        core.enable_xcam_count(True)
        super().on_transition()


class ProcessFadein(Process):
    def __init__(self):
        super().__init__()
        self.register_signal("COMPLETE")

    def execute(self):
        if core.incoming_split() and core.fade_status == core.FADEIN_COMPLETE:
            core.split()

        if core.fade_status == core.FADEIN_PARTIAL:
            return self.signals["LOOP"]
        else:
            # TODO: BUG: Fadein transition oscillation
            # Returns complete signal, transitions to star_count, is still white, transitions back on loop
            return self.signals["COMPLETE"]

    def on_transition(self):
        core.fps = 29.97
        core.enable_predictions(False)

        super().on_transition()


class _FadeoutProcess(Process):
    """ A fadeout, which is a console reset when the SM64 logo shows """

    def __init__(self):
        super().__init__()
        self.register_signal("RESET")
        self.register_signal("COMPLETE")

        self._fps = config.get("advanced", "fadeout_process_frame_rate")
        self._black_threshold = config.get("thresholds", "black_threshold")
        self._undo_threshold = config.get("thresholds", "undo_threshold")

        _, _, reset_width, reset_height = core.get_region_rect(core.RESET_REGION)
        self._reset_template = cv2.resize(cv2.imread(resource_path(config.get("advanced", "reset_frame_one"))), (reset_width, reset_height), interpolation=cv2.INTER_AREA)
        self._reset_template_2 = cv2.resize(cv2.imread(resource_path(config.get("advanced", "reset_frame_two"))), (reset_width, reset_height), interpolation=cv2.INTER_AREA)

    def _split(self, reset_region):
        """ Split during the fadeout if the current split ends with one """

    def execute(self):
        reset_region = core.get_region(core.RESET_REGION)
        self._split(reset_region)

        # Check for a match against the reset templates (SM64 logo)
        if self._is_reset(reset_region, self._reset_template) or self._is_reset(reset_region, self._reset_template_2):
            core.enable_predictions(True)
            self._reset()
            return self.signals["RESET"]

        # If both star count, and life count are still black, reprocess fadeout, otherwise fadeout completed
        if core.fade_status in (core.FADEOUT_COMPLETE, core.FADEOUT_PARTIAL):
            return self.signals["LOOP"]
        else:
            core.enable_predictions(True)
            return self.signals["COMPLETE"]

    def _reset(self):
        if not config.get("general", "srl_mode"):
            if core.current_time - core.last_split < self._undo_threshold:
                core.undo()

            core.reset()
            if core.start_on_reset:
                core.split()

        core.enable_fade_count(False)
        core.enable_xcam_count(False)
        core.set_in_game(False)
        core.star_count = core.route.initial_star

    def _is_reset(self, region, template):
        match = cv2.minMaxLoc(cv2.matchTemplate(region,
                                                template,
                                                cv2.TM_SQDIFF_NORMED))[0]
        return match < config.get("thresholds", "reset_threshold")

    def on_transition(self):
        core.fps = self._fps
        core.enable_predictions(False)
        core.enable_xcam_count(False)
        super().on_transition()


class ProcessFadeout(_FadeoutProcess):
    def _split(self, reset_region):
        # TODO: SWITCH TO USING FADE_STATUS
        # If centre of screen is black, and the current split conditions are met, trigger split
        if is_black(reset_region, self._black_threshold) and core.incoming_split() and core.current_split().split_type == core.SPLIT_NORMAL:
            core.split()


class ProcessFadeoutNoStar(_FadeoutProcess):
    def _split(self, reset_region):
        # TODO: SWITCH TO USING FADE_STATUS
        # If centre of screen is black, and the current split conditions are met, trigger split
        if is_black(reset_region, self._black_threshold) and core.incoming_split(star_count=False) and core.current_split().split_type == core.SPLIT_FADE_ONLY:
            core.split()


class ProcessFadeoutResetOnly(_FadeoutProcess):
    pass


class ProcessPostFadeout(Process):
    def __init__(self):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("FADEIN")
        self.register_signal("FLASH")
        self.register_signal("COMPLETE")

        self.power_lower_bound = [215, 40, 0]
        self.power_upper_bound = [255, 150, 0]
        self._power_found = False

    def execute(self):
        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if core.fade_status in (core.FADEIN_PARTIAL, core.FADEIN_COMPLETE):
            return self.signals["FADEIN"]

        if core.prediction_info.prediction in (121, 122) and self.loop_time() > 1:
            return self.signals["FLASH"]

        if time.time() - core.collection_time > 11:
            self._death_check()

        if core.incoming_split():
            if core.xcam_count == 0 and core.in_xcam:
                core.split()
            elif core.xcam_count == core.current_split().on_xcam:
                core.xcam_count = 0
                core.split()

        if self.loop_time() < 6:
            return self.signals["LOOP"]
        else:
            return self.signals["COMPLETE"]

    def _death_check(self):
        if 2 < self.loop_time() < 3:
            self._power_found = self._power_check()
        elif self.loop_time() >= 3 and self._power_found:
            self._power_found = self._power_check()
            if not self._power_found:
                core.fadeout_count = max(core.fadeout_count - 2, 0)

    def _power_check(self):
        power_region = core.get_region(core.POWER_REGION)

        lower = np.array(self.power_lower_bound, dtype="uint8")
        upper = np.array(self.power_upper_bound, dtype="uint8")

        power_mask = cv2.inRange(power_region, lower, upper)
        output = cv2.bitwise_and(power_region, power_region, mask=power_mask)

        return not is_black(output, 0.1, 0.9)

    def on_transition(self):
        self._power_found = False
        core.enable_predictions(True)
        core.enable_xcam_count(True)
        core.fps = 15

        super().on_transition()


class ProcessFlashCheck(Process):
    def __init__(self):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("FADEIN")
        self.register_signal("COMPLETE")

        self._running_total = 0
        self._prev_prediction = 0
        self._flash_count = 0

    def execute(self):
        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if core.fade_status in (core.FADEIN_PARTIAL, core.FADEIN_COMPLETE):
            return self.signals["FADEIN"]

        if core.prediction_info.prediction in (121, 122):
            normalized_prediction = 1
        else:
            normalized_prediction = -1

        if normalized_prediction == self._prev_prediction * -1:
            self._flash_count += 1

        self._running_total += normalized_prediction
        self._prev_prediction = normalized_prediction

        if -10 < self._running_total < 10 and self._flash_count >= 4:
            print("Flash Detected!")
            print("Running Total:", self._running_total, "Flash Count:", self._flash_count)
            if time.time() - core.collection_time > 15:
                print("Increment Star from Flash!")
                core.set_star_count(core.star_count + 1)

                if core.current_split().star_count == core.star_count:

                    if core.current_split().on_fadeout == 1:
                        core.skip()
                    else:
                        core.fadeout_count += 1

            return self.signals["COMPLETE"]

        if self.loop_time() < 2:
            return self.signals["LOOP"]
        else:
            return self.signals["COMPLETE"]

    def on_transition(self):
        core.fps = 29.97
        core.enable_predictions(True)
        self._running_total = 0
        self._flash_count = 0
        self._prev_prediction = 0

        super().on_transition()


class ProcessReset(Process):
    def __init__(self,):
        super().__init__()
        self.register_signal("RESET")

    def execute(self):
        return self.signals["RESET"]


class ProcessDummy(Process):
    def __init__(self):
        super().__init__()
        self.register_signal("COMPLETE")

    def execute(self):
        return self.signals["COMPLETE"]


class ProcessFileSelectSplit(_RunStartProcess):
    def __init__(self):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("COMPLETE")

        self._restart_split_delay = 1.2012 + (config.get("advanced", "file_select_frame_offset") / 29.97)

    def execute(self):
        region = core.get_region(core.FADEOUT_REGION)

        if core.fade_status in (core.FADEOUT_COMPLETE, core.FADEOUT_PARTIAL):
            return self.signals["FADEOUT"]
        if self._in_game_detected():
            core.set_in_game(True)
            return self.signals["COMPLETE"]

        if core.fadein_count == 2:
            region_int = region.astype(int)
            region_int_b, region_int_g, region_int_r = region_int.transpose(2, 0, 1)
            mask = (np.abs(region_int_r - region_int_g) > 25)

            region[mask] = [0, 0, 0]

            if np.any(region == [0, 0, 0]):
                try:
                    time.sleep(self._restart_split_delay)
                except ValueError:
                    pass
                core.fadein_count = 0
                core.fadeout_count = 0
                core.split()
                core.set_in_game(True)
                return self.signals["COMPLETE"]

        return self.signals["LOOP"]

    def on_transition(self):
        super().on_transition()
        core.fps = 29.97
        core.enable_fade_count(True)
