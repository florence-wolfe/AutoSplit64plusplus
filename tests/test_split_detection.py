import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from autosplit64.core import split_detection
from autosplit64.core.split_detection import SplitDetection
from autosplit64.core.constants import INITIAL_STATE
from autosplit64.core.model import PredictionInfo
from tests.settings import patch_settings


def make_base(star_counts=(1, 2, 3, 4, 5, 6), current=3):
    """ A SplitDetection with a route of splits with the given star counts, without capture, model or timer """
    b = SplitDetection.__new__(SplitDetection)
    # The AS64++ model's
    b._features = set(split_detection.detection_model.FEATURES[split_detection.detection_model.AS64PP])
    splits = [SimpleNamespace(title=f"Split {s}", star_count=s, on_fadeout=1, on_fadein=0, split_type="Normal")
              for s in star_counts]
    b._route = SimpleNamespace(title="Route", splits=splits, initial_star=0, version="JP", timing="RTA")
    b._current_split = b._route.splits[current]
    b._lives_trusted = True
    b._capture_lost_at = None
    b._model_failing_since = b._model_reloaded_at = None
    b.forget_lives()
    return b


class SyncSplitIndexTest(unittest.TestCase):
    def setUp(self):
        self.base = make_base(current=3)
        self.base.set_split_index = mock.Mock()

    def test_no_answer_from_timer_keeps_split(self):
        self.base._sync_split_index(False)
        self.base.set_split_index.assert_not_called()

    def test_not_running_goes_to_first_split(self):
        self.base._sync_split_index(-1)
        self.base.set_split_index.assert_called_once_with(0)

    def test_follows_timer(self):
        self.base._sync_split_index(5)
        self.base.set_split_index.assert_called_once_with(5)

    def test_same_split_does_nothing(self):
        self.base._sync_split_index(3)
        self.base.set_split_index.assert_not_called()


class ValidityCheckTest(unittest.TestCase):
    def setUp(self):
        self.base = make_base()
        self.base._error_occurred = mock.Mock()
        self.base._ls_socket = None
        size = split_detection.config.get("game", "capture_size")
        self.base._game_capture = mock.Mock(get_capture_size=mock.Mock(return_value=list(size)))
        self.base._model = mock.Mock(valid=mock.Mock(return_value=False))
        patcher = mock.patch.object(split_detection.livesplit, "check_connection", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_model_that_failed_to_load_is_reported(self):
        self.assertFalse(self.base.validity_check())
        message = self.base._error_occurred.call_args.args[0]
        self.assertIn("Unable to load prediction model", message)
        self.assertIn(".onnx", message)



class RunTest(unittest.TestCase):
    def test_failed_start_checks_end_the_run(self):
        b = make_base()
        b._route, b._current_split = None, None
        b._processor_switch = mock.Mock()
        # A failing check reports the error, which also stops split detection
        b.validity_check = mock.Mock(return_value=False)
        b.stop = mock.Mock()
        b._start_listener = mock.Mock()
        # Ends the loop, if the run went on to it
        b._capture = mock.Mock(side_effect=lambda: setattr(b, "_running", False))

        with mock.patch.object(split_detection.livesplit, "connect"), self.assertNoLogs("detection", "ERROR"):
            b.run()

        b._capture.assert_not_called()
        b._start_listener.assert_not_called()
        b.stop.assert_not_called()

    def test_lost_livesplit_connection_is_reported_once(self):
        b = make_base()
        b._current_split.split_type = "NORMAL"
        b._game_capture = mock.Mock()
        b._in_game = True
        b._make_predictions = False
        b._count_xcams = False
        b.analyze_fade_status = mock.Mock()
        # The process would split, which fails too
        b._processor_switch = mock.Mock(execute=mock.Mock(side_effect=ConnectionAbortedError))
        b.validity_check = mock.Mock(return_value=True)
        b._start_listener = mock.Mock()
        b._error_listener = mock.Mock()
        b.stop = mock.Mock(side_effect=lambda: setattr(b, "_running", False))
        b.fps = 30

        with mock.patch.object(split_detection.livesplit, "connect"), \
             mock.patch.object(split_detection.livesplit, "split_index", side_effect=ConnectionAbortedError("LiveSplit connection lost")):
            b.run()

        b._error_listener.assert_called_once_with("LiveSplit connection lost")
        b.stop.assert_called()

    def test_unexpected_error_is_reported(self):
        # Ending the run, which is told rather than leaving split detection seeming to run
        b = make_base()
        b._game_capture = mock.Mock()
        b._in_game = True
        b._make_predictions = False
        b._count_xcams = False
        b.analyze_fade_status = mock.Mock()
        b._processor_switch = mock.Mock(look_at=mock.Mock(side_effect=RuntimeError("a bug")))
        b.validity_check = mock.Mock(return_value=True)
        b._start_listener = mock.Mock()
        b._error_listener = mock.Mock()
        b.stop = mock.Mock(side_effect=lambda: setattr(b, "_running", False))
        b.fps = 30

        with mock.patch.object(split_detection.livesplit, "connect"), \
             mock.patch.object(split_detection.livesplit, "split_index", return_value=3), \
             self.assertLogs("detection", "ERROR") as logs:
            b.run()

        b._error_listener.assert_called_once_with("a bug")
        b.stop.assert_called()
        self.assertIsNotNone(logs.records[0].exc_info)


class CaptureLostTest(unittest.TestCase):
    """ A capture lost in a run, e.g. the capture software restarting, is found again, with what was counted kept """

    def setUp(self):
        b = self.base = make_base()
        b._in_game = True
        b._make_predictions = False
        b._count_xcams = False
        # No process asks for a look at a time
        b._processor_switch = mock.Mock(look_at=mock.Mock(return_value=None))
        b.validity_check = mock.Mock(return_value=True)
        b._start_listener = mock.Mock()
        b._error_listener = mock.Mock()
        b.stop = mock.Mock(side_effect=lambda: setattr(b, "_running", False))
        b.fps = 30
        size = split_detection.config.get("game", "capture_size")
        b._game_capture = mock.Mock(get_capture_size=mock.Mock(return_value=list(size)))
        for patcher in [mock.patch.object(split_detection.livesplit, "connect"),
                        mock.patch.object(split_detection.livesplit, "split_index", return_value=3),
                        mock.patch.object(split_detection.time, "sleep")]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_with_captures(self, *captures):
        """ Run split detection with the capture failing or working at each look """
        capture = self.base._game_capture.capture
        capture.side_effect = list(captures) + [None] * 5
        # Which looks were processed, counting from 1; the run ends once two were
        self.analyzed = []
        def analyze():
            self.analyzed.append(capture.call_count)
            self.base._running = len(self.analyzed) < 2
        self.base.analyze_fade_status = analyze
        self.base.run()

    def test_found_again(self):
        star_count = self.base.star_count = 5
        with self.assertLogs("detection", "INFO") as logs:
            self.run_with_captures(None, Exception("Failed to capture"), Exception("Failed to capture"), None)
        self.base._error_listener.assert_not_called()
        self.base._game_capture.reconnect.assert_called()
        self.assertEqual(self.analyzed, [1, 4])
        self.assertEqual(self.base.star_count, star_count)
        log = "\n".join(logs.output)
        self.assertIn("Lost the game capture", log)
        self.assertIn("Failed to capture", log)
        self.assertIn("Got the game capture back", log)

    def test_frames_while_lost_arent_processed(self):
        self.run_with_captures(Exception("Failed to capture"), None)
        # The look that failed isn't processed, the ones after it are
        self.assertEqual(self.analyzed, [2, 3])

    def test_reported_once_lost_too_long(self):
        with mock.patch.object(split_detection, "CAPTURE_RECOVERY_TIME", 0):
            self.run_with_captures(Exception("Failed to capture"), Exception("Still failing"))
        self.base._error_listener.assert_called_once_with("Still failing")
        self.base.stop.assert_called()

    def test_found_again_at_another_size(self):
        # The capture regions would be off
        self.base._game_capture.get_capture_size.return_value = [1, 1]
        self.run_with_captures(Exception("Failed to capture"), None)
        message = self.base._error_listener.call_args.args[0]
        self.assertIn("dimensions have changed", message)
        self.base.stop.assert_called()


class GameVersionTest(unittest.TestCase):
    """ The version the capture regions are laid out for """

    def version_for(self, route, override=False):
        settings = {("game", "override_version"): override, ("game", "version"): "US", ("route", "path"): "routes/missing.as64"}
        with mock.patch.object(split_detection.config, "load_config"), \
             patch_settings(settings, real=True), \
             mock.patch.object(split_detection, "load_route", return_value=route), \
             mock.patch.object(split_detection, "Model"), \
             mock.patch.object(split_detection, "GameCapture") as game_capture:
            game_capture.return_value.get_region_rect.return_value = [0, 0, 10, 10]
            SplitDetection()
        return game_capture.call_args.args[4]

    def test_route_version(self):
        self.assertEqual(self.version_for(SimpleNamespace(version="JP", splits=[SimpleNamespace(star_count=1)], initial_star=0)), "JP")

    def test_overridden(self):
        self.assertEqual(self.version_for(SimpleNamespace(version="JP", splits=[SimpleNamespace(star_count=1)], initial_star=0), override=True), "US")

    def test_route_that_failed_to_load(self):
        self.assertEqual(self.version_for(None), "US")


class LookingBetweenLooksTest(unittest.TestCase):
    """ Looking at a frame between looks changes when splits happen, by a frame, so only the AS64++ model does it """

    def looks_between(self, model):
        settings = {("route", "path"): "routes/missing.as64", ("model", "detection"): model,
                    ("model", "legacy"): model == "legacy"}
        with mock.patch.object(split_detection.config, "load_config"), \
             patch_settings(settings, real=True), \
             mock.patch.object(split_detection, "Model"), \
             mock.patch.object(split_detection, "GameCapture") as game_capture:
            game_capture.return_value.get_region_rect.return_value = [0, 0, 10, 10]
            return SplitDetection().has(split_detection.detection_model.LOOKS_BETWEEN)

    def test_only_the_as64pp_model(self):
        self.assertTrue(self.looks_between("as64pp"))
        self.assertFalse(self.looks_between("star_predictor"))
        self.assertFalse(self.looks_between("legacy"))


class StateTest(unittest.TestCase):
    """ Split detection's state, which each start begins afresh """

    def setUp(self):
        route = SimpleNamespace(version="JP", splits=[SimpleNamespace(star_count=1)], initial_star=0)
        for patcher in [mock.patch.object(split_detection.config, "load_config"),
                        patch_settings({("route", "path"): "routes/missing.as64"}, real=True),
                        mock.patch.object(split_detection, "load_route", return_value=route), mock.patch.object(split_detection, "Model"),
                        mock.patch.object(split_detection, "GameCapture")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        split_detection.GameCapture.return_value.get_region_rect.return_value = [0, 0, 10, 10]

    def state(self, detection):
        """ Its state, except the route's, which each start sets """
        return {name: getattr(detection, name) for name in INITIAL_STATE if name not in ("route", "route_length", "star_count")}

    def test_the_first_start_begins_with_the_initial_state(self):
        self.assertEqual(self.state(SplitDetection()),
                         {name: value for name, value in INITIAL_STATE.items() if name not in ("route", "route_length", "star_count")})

    def test_a_later_start_begins_afresh(self):
        # Not with what the last start left, like the stale star-skip window or X-Cam count
        first = SplitDetection()
        first.fadeout_count, first.fps, first.prediction_info = 2, 15, PredictionInfo(7, 0.9)
        first.previous_split_initial_star, first.next_split_split_star, first.xcam_count = 8, 12, 3
        second = SplitDetection()
        self.assertEqual(self.state(second), self.state(SplitDetection()))
        self.assertEqual((second.fadeout_count, second.previous_split_initial_star, second.xcam_count), (0, 0, 0))


class DetectionLogTest(unittest.TestCase):
    """ What split detection does and why, in the session log """

    def setUp(self):
        self.livesplit = mock.Mock()
        patcher = mock.patch.object(split_detection, "livesplit", self.livesplit)
        patcher.start()
        self.addCleanup(patcher.stop)
        b = self.base = SplitDetection.__new__(SplitDetection)
        splits = [SimpleNamespace(title=title, star_count=stars, on_fadeout=1, on_fadein=0, split_type="Normal")
                  for title, stars in (("WF 6", 6), ("CCM 8", 8), ("BitDW 9", 9))]
        b._route = SimpleNamespace(title="16 Star", splits=splits, initial_star=0, version="JP", timing="RTA")
        b._current_split = splits[1]
        b._ls_socket = None
        b._split_cooldown = 0.5
        # The default model's, which waits the split cooldown after a split
        b._features = set(split_detection.detection_model.FEATURES[split_detection.detection_model.STAR_PREDICTOR])
        b._split_event = None
        b._in_game = True
        b._run_ended = False
        b._prediction_processing_length = 3
        b._update_occurred = mock.Mock()
        b._lives_trusted = True
        b.forget_lives()
        vars(b).update(star_count=7, fadeout_count=1, fadein_count=0, xcam_count=0, last_split=0.0,
                       prediction_info=PredictionInfo(8, 0.97), fade_status="NO_FADE")

    def logged(self, action):
        with self.assertLogs("detection", "INFO") as logs:
            action()
        return "\n".join(logs.output)

    def test_split_with_the_state_it_split_in(self):
        log = self.logged(self.base.split)
        self.livesplit.split.assert_called_once()
        for part in ("Split", "CCM 8", "split 2 of 3", "star count 7", "needs 8", "fadeouts 1"):
            self.assertIn(part, log)

    def test_split_not_sent_and_why(self):
        self.base.last_split = split_detection.time.perf_counter()
        log = self.logged(self.base.split)
        self.livesplit.split.assert_not_called()
        self.assertIn("cooldown", log)

    def test_a_split_on_an_event_is_sent_once(self):
        # A fadeout's centre stays black for many looks, and the next split can need the same one too
        log = self.logged(lambda: [self.base.split(("fadeout", 3)) for _ in range(2)])
        self.livesplit.split.assert_called_once()
        self.assertIn("already split on this fadeout", log)

    def test_a_split_on_another_event_is_sent(self):
        self.base.split(("fadeout", 3))
        self.base.last_split -= 1
        self.base.split(("fadeout", 4))
        self.base.last_split -= 1
        self.base.split(("X-Cam", 4))
        self.assertEqual(self.livesplit.split.call_count, 3)

    def test_a_split_on_no_event_is_sent(self):
        self.base.split(("X-Cam", 1))
        self.base.last_split -= 1
        self.base.split()
        self.assertEqual(self.livesplit.split.call_count, 2)

    def test_no_split_cooldown_in_a_model_without_it(self):
        # AS64++ sends a split once per event instead
        self.base._features = set()
        self.base.last_split = split_detection.time.perf_counter()
        self.logged(self.base.split)
        self.livesplit.split.assert_called_once()

    def test_no_split_once_the_timer_ended_the_run(self):
        # The timer is past the last split, which split detection stays on
        self.assertIn("Timer ended the run", self.logged(lambda: self.base._sync_split_index(3)))
        log = self.logged(self.base.split)
        self.livesplit.split.assert_not_called()
        self.assertIn("past the last split", log)

    def test_splits_again_once_the_timer_is_back_in_a_run(self):
        for index in (3, -1):
            self.base._sync_split_index(index)
        self.logged(self.base.split)
        self.livesplit.split.assert_called_once()

    def test_timer_commands(self):
        for command, words in (("undo", "Undid"), ("skip", "Skipped"), ("reset", "Reset"), ("restart", "Restarted")):
            with self.subTest(command):
                self.base.set_star_count = mock.Mock()
                self.assertIn(words, self.logged(getattr(self.base, command)))

    def test_pause_only_while_running_and_connected(self):
        self.base._ls_socket = mock.Mock()
        for running, connected in ((False, True), (True, False)):
            with self.subTest(running=running, connected=connected):
                self.base._running = running
                self.base._ls_socket = mock.Mock() if connected else False
                self.base.pause()
                self.livesplit.pause.assert_not_called()
        self.base._running, self.base._ls_socket = True, mock.Mock()
        self.assertIn("Paused", self.logged(self.base.pause))
        self.livesplit.pause.assert_called_once_with(self.base._ls_socket)

    def test_star_count_change_with_its_prediction(self):
        log = self.logged(lambda: self.base.set_star_count(8))
        self.assertIn("Star count 7 -> 8", log)
        self.assertIn("0.97", log)

    def test_timer_moves_to_another_split(self):
        self.assertIn("BitDW 9", self.logged(lambda: self.base.set_split_index(2)))

    def test_in_game(self):
        self.base._in_game = False
        self.assertIn("In game", self.logged(lambda: self.base.set_in_game(True)))

    def test_fades_counted(self):
        b = self.base
        b._game_capture, b._count_fades, b._black_threshold, b._white_threshold = mock.Mock(), True, 0.1, 0.8
        b._fade_start_time, b._minimum_fadeout_time, b._fade_seen, b._fade_number = 0, 0.4, (None, 0.0), 0
        b.current_time = 100.0
        black = split_detection.perception.Fade(hud_black=True, hud_white=False, centre_black=True, fadein_white=False)
        with mock.patch.object(split_detection.perception, "fade", return_value=black):
            log = self.logged(b.analyze_fade_status)
        self.assertIn("Fadeout 2", log)
        self.assertIn("CCM 8", log)

    def test_setup_when_starting(self):
        settings = {("game", "capture_source"): "window", ("game", "use_obs"): False, ("game", "process_name"): "Emulator",
                    ("game", "capture_device"): "", ("game", "game_region"): [1, 2, 3, 4], ("game", "capture_size"): [5, 6],
                    ("game", "vc_fix"): False, ("connection", "ls_connection_type"): 1, ("general", "srl_mode"): False,
                    ("general", "operation_mode"): 0}
        with patch_settings(settings):
            setup = self.base._setup()
        for part in ("16 Star", "JP", "RTA", "3 splits", "Emulator", "[1, 2, 3, 4]", "[5, 6]", "TCP", "Probability"):
            self.assertIn(part, setup)

    def test_current_split_not_in_the_route(self):
        self.base._current_split = SimpleNamespace(title="Not in it")
        with self.assertLogs("detection", "WARNING") as logs:
            self.assertIsNone(self.base.split_index())
        self.assertIn("isn't in the route", logs.output[0])

    def test_errors(self):
        self.base.stop = mock.Mock()
        self.base._error_listener = mock.Mock()
        with self.assertLogs("detection", "WARNING") as logs:
            self.base._error_occurred("Could not connect to LiveSplit.")
        self.assertIn("Could not connect to LiveSplit.", logs.output[0])


class StatusTest(unittest.TestCase):
    """ What split detection is doing, for the Debug window """

    def test_status(self):
        b = make_base(star_counts=(6, 8, 9), current=1)
        vars(b).update(star_count=7, fadeout_count=1, fadein_count=0, xcam_count=2)
        b._current_split.on_xcam = -1
        b._running, b._in_game = True, False
        self.assertEqual(b.status(), {
            "running": True, "in_game": False, "split_index": 1, "split_count": 3, "split": "Split 8",
            "split_type": "Normal", "needs_stars": 8, "needs_fadeouts": 1, "needs_fadeins": 0, "needs_xcams": -1,
            "stars": 7, "fadeouts": 1, "fadeins": 0, "xcams": 2})

    def test_without_a_route(self):
        b = make_base()
        b._route, b._current_split = None, None
        b._running, b._in_game = False, False
        self.assertEqual(b.status(), {"running": False, "in_game": False})


class FirstSplitsTest(unittest.TestCase):
    """ Lookups of earlier splits at the start of the route mustn't wrap around to its end """

    def setUp(self):
        self.base = make_base(star_counts=(5, 8, 10, 120), current=0)
        vars(self.base).update(star_count=5, prediction_info=PredictionInfo(4, 0.9), xcam_count=0,
                               previous_split_initial_star=0, next_split_split_star=0)
        self.base.undo = mock.Mock()
        self.base._update_occurred = mock.Mock()

    def test_undo_check_at_first_split(self):
        b = self.base
        b._minimum_undo_count, b._undo_prediction_threshold = 3, 0.85
        b._star_skip_enabled, b._previous_prediction = False, None
        # Confident predictions of one star less than counted
        b._predictions = [PredictionInfo(4, 0.95)] * 3
        b.set_star_count = mock.Mock(side_effect=lambda count: setattr(b, "star_count", count))

        b._star_error_check()

        b.set_star_count.assert_called_once_with(4)
        b.undo.assert_not_called()

    def test_star_skip_window_at_second_split(self):
        self.base._reset_fade_count = mock.Mock()
        self.base.set_split_index(1)
        self.assertEqual(self.base.previous_split_initial_star, 0)


class ProbabilityModeTest(unittest.TestCase):
    """ The star count in Probability mode, from two predictions of the next star """

    def setUp(self):
        b = self.base = make_base(star_counts=(5, 10), current=1)
        b._game_capture = mock.Mock(get_region=mock.Mock(return_value=np.zeros((47, 89, 3), np.uint8)))
        b._model = mock.Mock(width=67, height=40)
        b._prediction_processing_length = 20
        b._predictions = [PredictionInfo(0, 0)] * 20
        b._probability_threshold, b._confirmation_threshold = 0.6, 0.4
        b._star_error_check = mock.Mock()
        b._update_occurred = mock.Mock()
        vars(b).update(star_count=5, in_xcam=False, xcam_count=0, fadeout_count=0, fadein_count=0, prediction_info=None)

    def star_counts(self, *predictions):
        """ The star count after each frame's prediction """
        counts = []
        for prediction in predictions:
            self.base._model.predict.return_value = prediction
            self.base._analyze_star_count_probability_mode()
            counts.append(self.base.star_count)
        return counts

    def test_failing_model_is_reloaded(self):
        self.base._error_occurred = mock.Mock()
        self.base._model.predict.side_effect = RuntimeError("Invalid input")
        working = mock.Mock(width=67, height=40, predict=mock.Mock(return_value=PredictionInfo(6, 0.9)))
        with mock.patch.object(split_detection, "Model", return_value=working), \
             self.assertLogs("detection", "INFO") as logs:
            self.base._analyze_star_count_probability_mode()
            # Nothing for the processes to act on while it fails
            self.assertEqual(self.base.prediction_info, split_detection.NO_PREDICTION)
            self.base._analyze_star_count_probability_mode()
            self.base._analyze_star_count_probability_mode()
        self.base._error_occurred.assert_not_called()
        self.assertIs(self.base._model, working)
        # The failed look isn't counted, the two after it count the next star
        self.assertEqual(self.base.star_count, 6)
        log = "\n".join(logs.output)
        self.assertIn("reloading the model: Invalid input", log)
        self.assertIn("predicts again", log)

    def test_failing_model_is_reported_once_failing_too_long(self):
        self.base._error_occurred = mock.Mock()
        self.base._model.predict.side_effect = RuntimeError("Invalid input")
        still_failing = mock.Mock(width=67, height=40, predict=mock.Mock(side_effect=RuntimeError("Invalid input")))
        with mock.patch.object(split_detection, "Model", return_value=still_failing), \
             mock.patch.object(split_detection, "MODEL_RECOVERY_TIME", 0), self.assertLogs("detection"):
            self.base._analyze_star_count_probability_mode()
            self.base._analyze_star_count_confirmation_mode()
        self.base._error_occurred.assert_called_once_with("Model prediction failed: Invalid input")
        self.assertEqual(self.base.star_count, 5)

    def test_the_second_prediction_of_the_next_star_counts_it(self):
        # On the frame of the second prediction, not one frame later
        self.assertEqual(self.star_counts(*[PredictionInfo(6, 0.9)] * 3), [5, 6, 6])

    def test_again_after_counting_a_star(self):
        self.assertEqual(self.star_counts(*[PredictionInfo(6, 0.9)] * 2, *[PredictionInfo(7, 0.9)] * 3), [5, 6, 6, 7, 7])

    def test_the_second_prediction_must_follow_the_first(self):
        # One prediction of the current star count between them
        self.assertEqual(self.star_counts(PredictionInfo(6, 0.9), PredictionInfo(5, 0.9), PredictionInfo(6, 0.9),
                                          PredictionInfo(6, 0.9)), [5, 5, 5, 6])


class StarSkipTest(unittest.TestCase):
    """ Predictions above 120 mean no star count was readable, e.g. during a fade """

    def setUp(self):
        b = self.base = make_base(star_counts=(110, 120), current=1)
        vars(b).update(star_count=119, prediction_info=PredictionInfo(121, 0.99),
                       previous_split_initial_star=110, next_split_split_star=120)
        b._predictions, b._minimum_undo_count = [], 3
        b._probability_threshold, b._max_star_skip = 0.6, 3
        # Enough matching predictions in a row to correct the star count
        b._previous_prediction = PredictionInfo(121, 0.99)
        b._minimum_consecutive_predictions = b._matching_consecutive_predictions = 4
        b.set_star_count = mock.Mock()
        b.undo = mock.Mock()

    def test_disabled_star_skip_does_nothing(self):
        self.base._star_skip_enabled = False
        self.base._star_error_check()
        self.base.set_star_count.assert_not_called()

    def test_star_count_is_never_set_above_120(self):
        self.base._star_skip_enabled = True
        self.base._star_error_check()
        self.base.set_star_count.assert_not_called()

    def test_star_skip_still_corrects_star_counts(self):
        self.base._star_skip_enabled = True
        self.base.prediction_info = self.base._previous_prediction = PredictionInfo(120, 0.99)
        self.base._star_error_check()
        self.base.set_star_count.assert_called_once_with(120)

if __name__ == "__main__":
    unittest.main()


class DiedTest(unittest.TestCase):
    """ Whether a fadeout is a death, by the iris it closes with """

    def setUp(self):
        self.base = make_base()
        self.base.fadeout_count = 3
        # Two seconds of looks at 30 a second
        looks = [(n / 30, np.zeros((60, 80), np.float32)) for n in range(60)]
        self.base._game_capture = SimpleNamespace(looks=looks)

    def verdict(self, iris):
        return mock.patch.object(split_detection.irises, "classify",
                                 return_value=split_detection.irises.Verdict(iris, {"bowser": 0.2, "star": 0.05}))

    def test_bowsers_iris_is_a_death_and_takes_back_two_fadeouts(self):
        # This fadeout, and the one that brought Mario into the stage or the fight
        with self.verdict("bowser"), self.assertLogs("detection", "INFO") as logs:
            self.assertTrue(self.base.died())
        self.assertEqual(self.base.fadeout_count, 1)
        self.assertIn("Death, Bowser's iris, fadeouts 3 -> 1", "\n".join(logs.output))

    def test_no_fadeouts_taken_back_below_zero(self):
        self.base.fadeout_count = 1
        with self.verdict("bowser"), self.assertLogs("detection", "INFO"):
            self.base.died()
        self.assertEqual(self.base.fadeout_count, 0)

    def test_any_other_iris_is_no_death(self):
        for iris in ("star", "circle", "mario", "unknown"):
            with self.subTest(iris), self.verdict(iris), self.assertLogs("detection", "INFO") as logs:
                self.assertFalse(self.base.died())
                self.assertEqual(self.base.fadeout_count, 3)
                # The verdict is logged either way, to tell from a bug report what each fadeout was
                self.assertIn(f"Iris {iris}", "\n".join(logs.output))

    def test_no_death_in_a_model_without_them(self):
        self.base._features = set()
        with self.verdict("bowser"):
            self.assertFalse(self.base.died())
        self.assertEqual(self.base.fadeout_count, 3)

    def test_irises_ending_late_only_in_a_model_with_them(self):
        # A dark stage's centre goes black up to 4 frames before the game does
        for features, early in (({split_detection.detection_model.DEATHS, split_detection.detection_model.IRISES_ENDING_LATE}, 5),
                                ({split_detection.detection_model.DEATHS}, 3)):
            with self.subTest(early=early), self.verdict("star") as classify, self.assertLogs("detection", "INFO"):
                self.base._features = features
                self.base.died()
                self.assertEqual(classify.call_args.kwargs, {"early": early})

    def test_no_verdict_from_less_than_a_seconds_looks(self):
        self.base._game_capture.looks = self.base._game_capture.looks[:20]
        with mock.patch.object(split_detection.irises, "classify") as classify:
            self.assertFalse(self.base.died())
        classify.assert_not_called()


class EventNumberTest(unittest.TestCase):
    """ Each fade and X-Cam is an event of its own, which a split can be sent on once """

    def detection(self):
        b = SplitDetection.__new__(SplitDetection)
        b._game_capture, b._black_threshold, b._white_threshold = mock.Mock(), 0.1, 0.8
        b._count_fades, b._fade_start_time, b._minimum_fadeout_time, b._fade_seen = False, 0, 0.4, (None, 0.0)
        b._fade_number = b._xcam_number = b.xcam_count = 0
        b.fade_status, b.current_time = "NO_FADE", 100.0
        b.forget_lives()
        return b

    def look(self, b, hud):
        fade = split_detection.perception.Fade(hud_black=hud == "black", hud_white=hud == "white",
                                               centre_black=False, fadein_white=False)
        with mock.patch.object(split_detection.perception, "fade", return_value=fade):
            b.analyze_fade_status()
        return b.fade_event()

    def test_each_fade_is_another_event_counted_or_not(self):
        b = self.detection()
        events = [self.look(b, hud) for hud in (None, "black", "black", None, "white", None, "black")]
        self.assertEqual(events, [("fade", 0), ("fade", 1), ("fade", 1), ("fade", 1), ("fade", 2), ("fade", 2), ("fade", 3)])

    def test_each_xcam_is_another_event(self):
        b = self.detection()
        b._xcam_found_time = 0
        # An X-Cam is a new one half a second after the last was seen, as the X-Cam count goes
        for at, number in ((100.0, 1), (100.3, 1), (101.0, 2)):
            b.current_time = at
            b._xcam_seen()
            self.assertEqual(b.xcam_event(), ("X-Cam", number))


class FadeStartTest(unittest.TestCase):
    """ Whether a frame between looks starts a fade, which split detection looks at right away """

    def setUp(self):
        b = self.detection = SplitDetection.__new__(SplitDetection)
        b._game_capture, b._black_threshold, b._white_threshold, b.fade_status = mock.Mock(), 0.1, 0.8, "NO_FADE"
        b._fade_seen = (None, 0.0)

    def frames(self, *frames):
        """ Whether each frame, (seconds, what the HUD shows), starts a fade """
        starts = []
        for at, hud in frames:
            fade = split_detection.perception.Fade(hud_black=hud == "black", hud_white=hud == "white",
                                                   centre_black=False, fadein_white=False)
            with mock.patch.object(split_detection.perception, "fade", return_value=fade), \
                 mock.patch.object(split_detection.time, "perf_counter", return_value=at):
                starts.append(self.detection.fade_start())
        return starts

    def test_a_fade_starts_once_the_hud_is_black_for_a_game_frame(self):
        frame = 1 / 30
        self.assertEqual(self.frames((1.0, None), (1.0 + frame, "black"), (1.0 + 2 * frame, "black")), [False, False, True])

    def test_and_white(self):
        frame = 1 / 30
        self.assertEqual(self.frames((1.0, "white"), (1.0 + frame, "white")), [False, True])

    def test_not_a_flicker_shorter_than_a_game_frame(self):
        # The HUD coming back near the black threshold, on a 60 fps capture
        self.assertEqual(self.frames((1.0, "black"), (1.017, None), (1.033, "black"), (1.05, None)), [False] * 4)

    def test_a_look_that_sees_the_fade_end_ends_it_for_the_frames_too(self):
        b = self.detection
        b.fade_status, b._count_fades, b._fade_start_time, b._minimum_fadeout_time = "FADEOUT_PARTIAL", False, 0, 0.4
        self.frames((1.0, "black"), (1.1, "black"))
        # The look on the frame between, where the HUD came back
        clear = split_detection.perception.Fade(hud_black=False, hud_white=False, centre_black=False, fadein_white=False)
        with mock.patch.object(split_detection.perception, "fade", return_value=clear), \
             mock.patch.object(split_detection.time, "perf_counter", return_value=1.117):
            b.current_time = 1.117
            b.analyze_fade_status()
        self.assertEqual(b.fade_status, "NO_FADE")
        # A flicker back to black isn't a fade that started at 1.0
        self.assertEqual(self.frames((1.133, "black"), (1.15, None)), [False, False])

    def test_not_while_a_fade_goes_on_or_ends(self):
        # The looks tell when it ends, as they did
        self.detection.fade_status = "FADEOUT_PARTIAL"
        self.assertEqual(self.frames((1.0, "black"), (1.1, "black"), (1.2, None), (1.3, None)), [False] * 4)


class LivesTest(unittest.TestCase):
    """ A death the iris couldn't see, as a falls into the dark, from a life lost after it """

    def setUp(self):
        self.livesplit = mock.Mock()
        patcher = mock.patch.object(split_detection, "livesplit", self.livesplit)
        patcher.start()
        self.addCleanup(patcher.stop)
        b = self.base = make_base(current=3)
        b._ls_socket = None
        b._update_occurred = mock.Mock()
        vars(b).update(star_count=3, fadeout_count=0, fadein_count=0, xcam_count=0, last_split=0.0)
        b._lives_trusted = True
        b.forget_lives()
        b._lives_changed(4)

    def test_a_life_lost_after_a_fadeout_takes_back_two_fadeouts(self):
        self.base.fadeout_count = 2
        self.base._lives_since["fadeouts"] = 1
        with self.assertLogs("detection", "INFO") as logs:
            self.base._lives_changed(3)
        self.assertEqual(self.base.fadeout_count, 0)
        self.assertIn("Death, a life lost, fadeouts 2 -> 0", "\n".join(logs.output))
        self.livesplit.undo.assert_not_called()

    def test_a_death_bowsers_iris_counted_isnt_counted_again(self):
        self.base.fadeout_count = 1
        # On the fadeout the life was lost on, the latest
        self.base._lives_since.update(fadeouts=1, death=1)
        self.base._lives_changed(3)
        self.assertEqual(self.base.fadeout_count, 1)

    def test_a_split_on_the_death_is_undone(self):
        # Three fadeouts made the split, the third a fall; the timer moved on to split 5, with no fadeouts yet
        self.base._lives_since.update(fadeouts=1, split=(3, 3, 1))
        self.base.set_split_index(4)
        with self.assertLogs("detection", "INFO") as logs:
            self.base._lives_changed(3)
        self.livesplit.undo.assert_called_once()
        self.assertEqual((self.base.split_index(), self.base.fadeout_count), (3, 1))
        self.assertIn("Death, a life lost after a split, undid it, fadeouts 3 -> 1", "\n".join(logs.output))

    def split_on_a_fadeout(self):
        """ A fadeout that split, as split detection counts and splits on one """
        b = self.base
        vars(b).update(_split_event=None, _split_cooldown=0.5, _run_ended=False)
        b._lives_since["fadeouts"] += 1
        b.fadeout_count += 1
        with self.assertLogs("detection", "INFO"):
            b.split()

    def test_a_split_before_the_deaths_fadeout_is_not_undone(self):
        # Leaving CCM split, then BitDW's entry and a fall off it are two fadeouts more before the life is lost
        self.split_on_a_fadeout()
        self.base.set_split_index(4)
        self.base.fadeout_count = 0
        for _ in range(2):
            self.base._lives_since["fadeouts"] += 1
            self.base.fadeout_count += 1
        with self.assertLogs("detection", "INFO") as logs:
            self.base._lives_changed(3)
        self.livesplit.undo.assert_not_called()
        self.assertEqual((self.base.split_index(), self.base.fadeout_count), (4, 0))
        self.assertIn("Death, a life lost, fadeouts 2 -> 0", "\n".join(logs.output))

    def test_a_split_on_the_deaths_fadeout_is_undone(self):
        self.split_on_a_fadeout()
        self.base.set_split_index(4)
        with self.assertLogs("detection", "INFO"):
            self.base._lives_changed(3)
        self.livesplit.undo.assert_called_once()
        self.assertEqual(self.base.split_index(), 3)

    def test_a_death_bowsers_iris_called_on_an_earlier_fadeout_is_another(self):
        # Bowser's iris called wrongly on a fadeout with no life lost, then a fall the iris can't see, two fadeouts later
        self.base.fadeout_count = 3
        self.base._lives_since.update(fadeouts=3, death=1)
        with self.assertLogs("detection", "INFO") as logs:
            self.base._lives_changed(3)
        self.assertEqual(self.base.fadeout_count, 1)
        self.assertIn("Death, a life lost, fadeouts 3 -> 1", "\n".join(logs.output))

    def test_a_life_gained_is_no_death(self):
        self.base.fadeout_count = 2
        self.base._lives_since["fadeouts"] = 1
        self.base._lives_changed(5)
        self.assertEqual(self.base.fadeout_count, 2)

    def test_lives_that_dont_move_by_one_arent_lives(self):
        # As Usamune shows its own counter where the lives are
        with self.assertLogs("detection", "INFO") as logs:
            self.base._lives_changed(29)
        self.assertIn("aren't lives", "\n".join(logs.output))
        self.base.fadeout_count = 2
        self.base._lives_since["fadeouts"] = 1
        self.base._lives_changed(28)
        self.assertEqual(self.base.fadeout_count, 2)

    def test_a_life_lost_without_a_fadeout_isnt_lives(self):
        self.base.fadeout_count = 2
        self.base._lives_changed(3)
        self.assertEqual(self.base.fadeout_count, 2)
        self.assertFalse(self.base._lives_trusted)

    def test_a_reset_forgets_the_lives(self):
        # A new file starts with 4 lives, after the attempt before ended with 5
        self.base._lives_changed(5)
        self.base.forget_lives()
        self.base.fadeout_count = 1
        self.base._lives_since["fadeouts"] = 1
        self.base._lives_changed(4)
        self.assertEqual(self.base.fadeout_count, 1)


class LivesReadingTest(unittest.TestCase):
    """ The lives count only when the model is sure of the same number three looks in a row """

    def setUp(self):
        self.base = make_base()
        self.base._lives_trusted = True
        self.base.forget_lives()
        # Taking the new lives, as it does
        self.base._lives_changed = mock.Mock(side_effect=lambda lives: setattr(self.base, "_lives", lives))
        self.readings = []
        self.base._read_lives = lambda: self.readings.pop(0)

    def read(self, *readings):
        self.readings = [PredictionInfo(lives, probability) for lives, probability in readings]
        for _ in readings:
            self.base.analyze_lives()

    def test_three_sure_readings_in_a_row(self):
        self.read((4, 0.95), (4, 0.99), (4, 0.97))
        self.base._lives_changed.assert_called_once_with(4)

    def test_unsure_readings_start_again(self):
        self.read((4, 0.95), (4, 0.5), (4, 0.97), (4, 0.99))
        self.base._lives_changed.assert_not_called()

    def test_the_same_lives_again_change_nothing(self):
        self.read((4, 0.95), (4, 0.99), (4, 0.97), (4, 0.95))
        self.base._lives_changed.assert_called_once_with(4)

    def test_a_failed_reading_starts_again(self):
        # The model failing, which is reloaded
        self.readings = [PredictionInfo(4, 0.95), PredictionInfo(4, 0.99), None, PredictionInfo(4, 0.97)]
        for _ in range(4):
            self.base.analyze_lives()
        self.base._lives_changed.assert_not_called()

    def test_no_reading_once_they_arent_lives(self):
        self.base._lives_trusted = False
        self.base._read_lives = mock.Mock()
        self.base.analyze_lives()
        self.base._read_lives.assert_not_called()

