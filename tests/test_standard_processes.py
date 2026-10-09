""" Behavior of the split detection processes in processes/standard.py, with core stubbed """
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from autosplit64 import core
from autosplit64.core import config
from autosplit64.core.model import PredictionInfo
from autosplit64.processes import standard

SETTINGS = {
    ("general", "mid_run_start_enabled"): True,
    ("general", "srl_mode"): False,
    ("thresholds", "probability_threshold"): 0.6,
    ("thresholds", "reset_threshold"): 0.1,
    ("thresholds", "black_threshold"): 0.1,
    ("thresholds", "undo_threshold"): 4.5,
    ("advanced", "fadeout_process_frame_rate"): 29.97,
    ("advanced", "file_select_frame_offset"): -29,
    ("advanced", "reset_frame_one"): "templates/default_reset_one.jpg",
    ("advanced", "reset_frame_two"): "templates/default_reset_two.jpg",
}


def patch_detection(test, **state):
    """ Split detection's state for the test, on a stand-in for the Base that started last, where core keeps it """
    detection = SimpleNamespace(**state)
    patcher = mock.patch.object(core, "_base", detection)
    patcher.start()
    test.addCleanup(patcher.stop)
    return detection


class ProcessTestCase(unittest.TestCase):
    """ A stand-in for split detection, self.detection, which processes are given and core reads and writes """

    def setUp(self):
        self.calls = []
        record = lambda name: mock.Mock(side_effect=lambda *args, **kwargs: self.calls.append((name, *args)))
        splits = [SimpleNamespace(star_count=s, split_type=core.SPLIT_NORMAL, on_fadeout=1, on_fadein=0, on_xcam=-1) for s in (5, 10, 16)]
        functions = {
            "split_index": lambda: 1, "current_split": lambda: splits[1], "incoming_split": mock.Mock(return_value=True),
            "get_region_rect": lambda region: [0, 0, 251, 137],
            "get_region": mock.Mock(return_value=np.zeros((137, 251, 3), np.uint8)),
        }
        for name in ("enable_fade_count", "enable_xcam_count", "enable_predictions", "set_in_game", "set_star_count",
                     "split", "reset", "undo", "skip"):
            functions[name] = record(name)
        self.detection = patch_detection(
            self, fade_status=core.NO_FADE, star_count=5, prediction_info=PredictionInfo(5, 0.9),
            route=SimpleNamespace(splits=splits, initial_star=0), fadein_count=0, fadeout_count=0,
            current_time=100.0, last_split=0.0, start_on_reset=True, fps=0.0,
            xcam_count=0, in_xcam=False, collection_time=0.0, **functions)
        for name, value in functions.items():
            patcher = mock.patch.object(core, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(config, "get", side_effect=lambda section, key=None: SETTINGS[(section, key)])
        patcher.start()
        self.addCleanup(patcher.stop)

    def names(self):
        return [call[0] for call in self.calls]


class RunStartTest(ProcessTestCase):
    """ ProcessRunStart, ProcessRunStartUpSegment and ProcessFileSelectSplit detect being in game """

    CASES = [(standard.ProcessRunStart, "START", True),
             (standard.ProcessRunStartUpSegment, "START", False),
             (standard.ProcessFileSelectSplit, "COMPLETE", True)]

    def test_fadeout(self):
        for cls, _, _ in self.CASES:
            with self.subTest(cls.__name__):
                core.fade_status = core.FADEOUT_PARTIAL
                process = cls()
                self.assertIs(process.execute(), process.signals["FADEOUT"])

    def test_star_count_matches(self):
        for cls, signal, sets_in_game in self.CASES:
            with self.subTest(cls.__name__):
                self.calls.clear()
                process = cls()
                self.assertIs(process.execute(), process.signals[signal])
                expected = ["enable_fade_count", "enable_xcam_count"] + (["set_in_game"] if sets_in_game else [])
                self.assertEqual(self.names(), expected)

    def test_mid_run_start_after_five_matching_predictions(self):
        for cls, signal, sets_in_game in self.CASES:
            with self.subTest(cls.__name__):
                self.calls.clear()
                process = cls()
                core.prediction_info = PredictionInfo(8, 0.9)
                results = [process.execute() for _ in range(5)]
                self.assertEqual(results[:4], [process.signals["LOOP"]] * 4)
                self.assertIs(results[4], process.signals[signal])
                expected = ["enable_fade_count", "enable_xcam_count", "set_star_count"] + (["set_in_game"] if sets_in_game else [])
                self.assertEqual(self.names(), expected)
                self.assertEqual(self.calls[2], ("set_star_count", 8))
                core.prediction_info = PredictionInfo(5, 0.9)

    def test_unlikely_prediction_keeps_waiting(self):
        for cls, _, _ in self.CASES:
            with self.subTest(cls.__name__):
                core.prediction_info = PredictionInfo(5, 0.3)
                process = cls()
                self.assertIs(process.execute(), process.signals["LOOP"])


class FadeoutTest(ProcessTestCase):
    """ ProcessFadeout, ProcessFadeoutNoStar and ProcessFadeoutResetOnly: splits and console resets in a fadeout """

    def setUp(self):
        super().setUp()
        core.fade_status = core.FADEOUT_COMPLETE

    def run_process(self, cls, reset_template=None, split_type=core.SPLIT_NORMAL):
        core.current_split().split_type = split_type
        process = cls()
        process._is_reset = lambda region, template: reset_template is not None and template is getattr(process, reset_template)
        return process, process.execute()

    def test_split_on_matching_split_type(self):
        for cls, split_type, incoming_split_args in [(standard.ProcessFadeout, core.SPLIT_NORMAL, ()),
                                                     (standard.ProcessFadeoutNoStar, core.SPLIT_FADE_ONLY, ({"star_count": False},))]:
            with self.subTest(cls.__name__):
                self.calls.clear()
                core.incoming_split.reset_mock()
                process, result = self.run_process(cls, split_type=split_type)
                self.assertIs(result, process.signals["LOOP"])
                self.assertEqual(self.names(), ["split"])
                self.assertEqual(core.incoming_split.call_args.kwargs, incoming_split_args[0] if incoming_split_args else {})

    def test_no_split_on_other_split_types(self):
        for cls, split_type in [(standard.ProcessFadeout, core.SPLIT_FADE_ONLY),
                                (standard.ProcessFadeoutNoStar, core.SPLIT_NORMAL),
                                (standard.ProcessFadeoutResetOnly, core.SPLIT_NORMAL)]:
            with self.subTest(cls.__name__):
                self.calls.clear()
                self.run_process(cls, split_type=split_type)
                self.assertNotIn("split", self.names())

    def test_reset(self):
        for cls in (standard.ProcessFadeout, standard.ProcessFadeoutNoStar, standard.ProcessFadeoutResetOnly):
            for template in ("_reset_template", "_reset_template_2"):
                with self.subTest(cls=cls.__name__, template=template):
                    self.calls.clear()
                    core.star_count = 9
                    # The last split was under undo_threshold seconds ago
                    core.last_split = core.current_time - 1
                    process, result = self.run_process(cls, template, split_type="none")
                    self.assertIs(result, process.signals["RESET"])
                    self.assertEqual(self.names(), ["enable_predictions", "undo", "reset", "split",
                                                    "enable_fade_count", "enable_xcam_count", "set_in_game"])
                    self.assertEqual(core.star_count, 0)

    def test_no_split_while_the_centre_is_not_black(self):
        core.get_region.return_value = np.full((137, 251, 3), 255, np.uint8)
        for cls, split_type in [(standard.ProcessFadeout, core.SPLIT_NORMAL),
                                (standard.ProcessFadeoutNoStar, core.SPLIT_FADE_ONLY)]:
            with self.subTest(cls.__name__):
                self.calls.clear()
                process, result = self.run_process(cls, split_type=split_type)
                self.assertIs(result, process.signals["LOOP"])
                self.assertNotIn("split", self.names())

    def test_reset_without_undo_after_the_undo_threshold(self):
        core.last_split = core.current_time - 5
        process, result = self.run_process(standard.ProcessFadeoutResetOnly, "_reset_template")
        self.assertIs(result, process.signals["RESET"])
        self.assertEqual(self.names(), ["enable_predictions", "reset", "split",
                                        "enable_fade_count", "enable_xcam_count", "set_in_game"])

    def test_reset_without_start_on_reset(self):
        core.last_split = core.current_time - 5
        core.start_on_reset = False
        self.run_process(standard.ProcessFadeoutResetOnly, "_reset_template")
        self.assertEqual(self.names(), ["enable_predictions", "reset",
                                        "enable_fade_count", "enable_xcam_count", "set_in_game"])

    def test_reset_in_srl_mode_sends_no_timer_commands(self):
        core.last_split = core.current_time - 1
        core.star_count = 9
        core.route.initial_star = 2
        with mock.patch.dict(SETTINGS, {("general", "srl_mode"): True}):
            process, result = self.run_process(standard.ProcessFadeoutResetOnly, "_reset_template")
        self.assertIs(result, process.signals["RESET"])
        self.assertEqual(self.calls, [("enable_predictions", True), ("enable_fade_count", False),
                                      ("enable_xcam_count", False), ("set_in_game", False)])
        self.assertEqual(core.star_count, 2)

    def test_fadeout_completes(self):
        for cls in (standard.ProcessFadeout, standard.ProcessFadeoutNoStar, standard.ProcessFadeoutResetOnly):
            with self.subTest(cls.__name__):
                core.fade_status = core.NO_FADE
                process, result = self.run_process(cls, split_type="none")
                self.assertIs(result, process.signals["COMPLETE"])

    def test_on_transition(self):
        for cls in (standard.ProcessFadeout, standard.ProcessFadeoutNoStar, standard.ProcessFadeoutResetOnly):
            with self.subTest(cls.__name__):
                self.calls.clear()
                cls().on_transition()
                self.assertEqual(core.fps, 29.97)
                self.assertEqual(self.names(), ["enable_predictions", "enable_xcam_count"])


class ClockTestCase(ProcessTestCase):
    """ A process transitioned to at self.now, with time.time() stopped there until a test moves it """

    def setUp(self):
        super().setUp()
        self.start = self.now = 1000.0
        patcher = mock.patch("time.time", side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def signal(self, result):
        return {signal: name for name, signal in self.process.signals.items()}[result]


# The power meter, and none of it (BGR)
POWER = np.full((40, 40, 3), (230, 100, 0), np.uint8)
NO_POWER = np.zeros((40, 40, 3), np.uint8)


class PostFadeoutTest(ClockTestCase):
    """ ProcessPostFadeout: the death check, and the signal for the flashes of a star """

    def setUp(self):
        super().setUp()
        core.collection_time = self.now - 20
        core.fadeout_count = 3
        core.incoming_split.return_value = False
        self.process = standard.ProcessPostFadeout()
        self.process.on_transition()

    def at(self, seconds, frame=NO_POWER):
        """ The signal for the frame, seconds after the fadeout """
        self.now = self.start + seconds
        core.get_region.return_value = frame
        return self.signal(self.process.execute())

    def test_death_removes_two_fadeouts(self):
        # The power meter shows after a death, and goes away after 3 s
        self.assertEqual([self.at(2.5, POWER), self.at(3.5)], ["LOOP", "LOOP"])
        self.assertEqual(core.fadeout_count, 1)

    def test_death_removes_no_fadeouts_below_zero(self):
        core.fadeout_count = 1
        self.at(2.5, POWER)
        self.at(3.5)
        self.assertEqual(core.fadeout_count, 0)

    def test_no_death_while_the_power_meter_stays(self):
        self.at(2.5, POWER)
        self.at(3.5, POWER)
        self.assertEqual(core.fadeout_count, 3)

    def test_no_death_without_the_power_meter_between_2_and_3_seconds(self):
        self.at(1.5, POWER)
        self.at(3.5)
        self.assertEqual(core.fadeout_count, 3)

    def test_no_death_check_within_11_seconds_of_a_star(self):
        # 9.5 and 10.5 s after the star
        core.collection_time = self.start - 7
        self.at(2.5, POWER)
        self.at(3.5)
        self.assertEqual(core.fadeout_count, 3)

    def test_flash_after_a_second(self):
        for prediction in (121, 122):
            with self.subTest(prediction):
                core.prediction_info = PredictionInfo(prediction, 0.9)
                self.now = self.start
                self.process.on_transition()
                self.assertEqual([self.at(0.5), self.at(1.5)], ["LOOP", "FLASH"])

    def test_complete_after_6_seconds(self):
        self.assertEqual([self.at(5.9), self.at(6)], ["LOOP", "COMPLETE"])

    def test_split_on_the_xcam_count(self):
        core.incoming_split.return_value = True
        core.current_split().on_xcam = 2
        core.xcam_count = 1
        self.at(0.5)
        self.assertNotIn("split", self.names())
        core.xcam_count = 2
        self.at(0.6)
        self.assertIn("split", self.names())
        self.assertEqual(core.xcam_count, 0)

    def test_split_on_an_xcam_long_after_a_star(self):
        # Unlike ProcessXCam, which splits on an X-Cam only within a second of a star
        core.incoming_split.return_value = True
        core.in_xcam = True
        core.current_time = self.start + 0.5
        self.at(0.5)
        self.assertIn("split", self.names())

    def test_no_xcam_split_before_the_split_is_incoming(self):
        core.in_xcam = True
        core.current_split().on_xcam = 0
        self.at(0.5)
        self.assertNotIn("split", self.names())


class FlashCheckTest(ClockTestCase):
    """ ProcessFlashCheck: a star collected without a fadeout, from the star count flashing """

    def setUp(self):
        super().setUp()
        core.collection_time = self.now - 20
        core.set_star_count.side_effect = lambda count: (self.calls.append(("set_star_count", count)),
                                                         setattr(core, "star_count", count))
        self.process = standard.ProcessFlashCheck()
        self.process.on_transition()

    def flashes(self):
        """ The signals for the star count flashing on and off, as predictions 121 and 122 when it's off """
        results = []
        for prediction in (121, 5, 122, 5, 121):
            core.prediction_info = PredictionInfo(prediction, 0.9)
            results.append(self.signal(self.process.execute()))
        return results

    def test_four_flashes_count_a_star(self):
        with self.assertLogs("detection") as logs:
            self.assertEqual(self.flashes(), ["LOOP"] * 4 + ["COMPLETE"])
        self.assertEqual(logs.output, ["INFO:detection:Star count flashed 4 times, running total 1"])
        self.assertEqual(core.star_count, 6)
        self.assertEqual(core.fadeout_count, 0)
        self.assertNotIn("skip", self.names())

    def test_reaching_a_split_that_ends_on_its_first_fadeout_skips_it(self):
        core.star_count = 9
        self.flashes()
        self.assertEqual(core.star_count, 10)
        self.assertEqual(self.names(), ["enable_predictions", "set_star_count", "skip"])

    def test_reaching_a_split_that_ends_on_a_later_fadeout_counts_one(self):
        core.star_count = 9
        core.current_split().on_fadeout = 2
        self.flashes()
        self.assertEqual(core.fadeout_count, 1)
        self.assertNotIn("skip", self.names())

    def test_no_star_within_15_seconds_of_the_last(self):
        core.collection_time = self.now - 15
        self.assertEqual(self.flashes()[-1], "COMPLETE")
        self.assertEqual(core.star_count, 5)
        self.assertNotIn("set_star_count", self.names())

    def test_complete_after_2_seconds_without_flashes(self):
        results = [self.signal(self.process.execute())]
        self.now += 2
        results.append(self.signal(self.process.execute()))
        self.assertEqual(results, ["LOOP", "COMPLETE"])
        self.assertEqual(core.star_count, 5)


class ResetTest(ProcessTestCase):
    def test_reset_processes_signal_reset(self):
        process = standard.ProcessReset()
        self.assertIs(process.execute(), process.signals["RESET"])


if __name__ == "__main__":
    unittest.main()
