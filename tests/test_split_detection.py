import unittest
from types import SimpleNamespace
from unittest import mock

from autosplit64.core import split_detection
from autosplit64.core.split_detection import SplitDetection
from autosplit64.core.constants import INITIAL_STATE
from autosplit64.core.model import PredictionInfo


def make_base(star_counts=(1, 2, 3, 4, 5, 6), current=3):
    """ A SplitDetection with a route of splits with the given star counts, without capture, model or timer """
    b = SplitDetection.__new__(SplitDetection)
    splits = [SimpleNamespace(title=f"Split {s}", star_count=s, on_fadeout=1, on_fadein=0, split_type="Normal")
              for s in star_counts]
    b._route = SimpleNamespace(title="Route", splits=splits, initial_star=0, version="JP", timing="RTA")
    b._current_split = b._route.splits[current]
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
        b.logger = mock.Mock()
        # A failing check reports the error, which also stops split detection
        b.validity_check = mock.Mock(return_value=False)
        b.stop = mock.Mock()

        with mock.patch.object(split_detection.livesplit, "connect"):
            b.run()

        b.logger.error.assert_not_called()
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
        b.logger = mock.Mock()
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


class GameVersionTest(unittest.TestCase):
    """ The version the capture regions are laid out for """

    def version_for(self, route, override=False):
        real_get = split_detection.config.get
        settings = {("game", "override_version"): override, ("game", "version"): "US", ("route", "path"): "routes/missing.as64"}
        with mock.patch.object(split_detection.config, "load_config"), \
             mock.patch.object(split_detection.config, "get", side_effect=lambda section, key=None: settings.get((section, key), real_get(section, key))), \
             mock.patch.object(split_detection, "load_route", return_value=route), \
             mock.patch.object(split_detection, "Model"), \
             mock.patch.object(split_detection, "GameCapture") as game_capture:
            game_capture.return_value.get_region_rect.return_value = [0, 0, 10, 10]
            SplitDetection(None)
        return game_capture.call_args.args[4]

    def test_route_version(self):
        self.assertEqual(self.version_for(SimpleNamespace(version="JP", splits=[SimpleNamespace(star_count=1)], initial_star=0)), "JP")

    def test_overridden(self):
        self.assertEqual(self.version_for(SimpleNamespace(version="JP", splits=[SimpleNamespace(star_count=1)], initial_star=0), override=True), "US")

    def test_route_that_failed_to_load(self):
        self.assertEqual(self.version_for(None), "US")


class StateTest(unittest.TestCase):
    """ Split detection's state, which each start carries over from the last """

    def setUp(self):
        route = SimpleNamespace(version="JP", splits=[SimpleNamespace(star_count=1)], initial_star=0)
        real_get = split_detection.config.get
        for patcher in [mock.patch.object(split_detection.config, "load_config"),
                        mock.patch.object(split_detection.config, "get", side_effect=lambda section, key=None: "routes/missing.as64" if section == "route" else real_get(section, key)),
                        mock.patch.object(split_detection, "load_route", return_value=route), mock.patch.object(split_detection, "Model"),
                        mock.patch.object(split_detection, "GameCapture")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        split_detection.GameCapture.return_value.get_region_rect.return_value = [0, 0, 10, 10]

    def test_the_first_start_begins_with_the_initial_state(self):
        detection = SplitDetection(None)
        # Except the route's, which each start sets
        route = ("route", "route_length", "star_count")
        self.assertEqual({name: getattr(detection, name) for name in INITIAL_STATE if name not in route},
                         {name: value for name, value in INITIAL_STATE.items() if name not in route})

    def test_each_start_carries_the_state_over(self):
        # Like when the core module kept it
        first = SplitDetection(None)
        first.fadeout_count, first.fps, first.prediction_info = 2, 15, PredictionInfo(7, 0.9)
        first.star_count = 5
        second = SplitDetection(first)
        self.assertEqual((second.fadeout_count, second.fps, second.prediction_info), (2, 15, PredictionInfo(7, 0.9)))
        # Except the route's, which each start sets
        self.assertEqual(second.star_count, 0)


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
        b._split_on_current_xcam = False
        b._in_game = True
        b._prediction_processing_length = 3
        b._update_occurred = mock.Mock()
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
        self.base.last_split = split_detection.time.time()
        log = self.logged(self.base.split)
        self.livesplit.split.assert_not_called()
        self.assertIn("cooldown", log)

    def test_timer_commands(self):
        for command, words in (("undo", "Undid"), ("skip", "Skipped"), ("reset", "Reset"), ("restart", "Restarted")):
            with self.subTest(command):
                self.base.set_star_count = mock.Mock()
                self.assertIn(words, self.logged(getattr(self.base, command)))

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
        b._game_capture, b._count_fades, b._black_threshold = mock.Mock(), True, 0.1
        b._fade_start_time, b._minimum_fadeout_time = 0, 0.4
        b.current_time = 100.0
        with mock.patch.object(split_detection, "is_black", return_value=True):
            log = self.logged(b.analyze_fade_status)
        self.assertIn("Fadeout 2", log)
        self.assertIn("CCM 8", log)

    def test_setup_when_starting(self):
        settings = {("game", "capture_source"): "window", ("game", "use_obs"): False, ("game", "process_name"): "Emulator",
                    ("game", "capture_device"): "", ("game", "game_region"): [1, 2, 3, 4], ("game", "capture_size"): [5, 6],
                    ("game", "vc_fix"): False, ("connection", "ls_connection_type"): 1, ("general", "srl_mode"): False,
                    ("general", "operation_mode"): 0}
        with mock.patch.object(split_detection.config, "get", side_effect=lambda section, key=None: settings[(section, key)]):
            setup = self.base._setup()
        for part in ("16 Star", "JP", "RTA", "3 splits", "Emulator", "[1, 2, 3, 4]", "[5, 6]", "TCP", "Probability"):
            self.assertIn(part, setup)

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
