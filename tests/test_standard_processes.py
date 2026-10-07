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


class ProcessTestCase(unittest.TestCase):
    def setUp(self):
        self.calls = []
        record = lambda name: mock.Mock(side_effect=lambda *args, **kwargs: self.calls.append((name, *args)))
        splits = [SimpleNamespace(star_count=s, split_type=core.SPLIT_NORMAL, on_fadeout=1, on_fadein=0, on_xcam=-1) for s in (5, 10, 16)]
        self.state = {
            "fade_status": core.NO_FADE, "star_count": 5, "prediction_info": PredictionInfo(5, 0.9),
            "route": SimpleNamespace(splits=splits, initial_star=0), "fadein_count": 0, "fadeout_count": 0,
            "current_time": 100.0, "last_split": 0.0, "start_on_reset": True,
            "split_index": lambda: 1, "current_split": lambda: splits[1], "incoming_split": mock.Mock(return_value=True),
            "get_region_rect": lambda region: [0, 0, 251, 137],
            "get_region": mock.Mock(return_value=np.zeros((137, 251, 3), np.uint8)),
        }
        for name in ("enable_fade_count", "enable_xcam_count", "enable_predictions", "set_in_game", "set_star_count",
                     "split", "reset", "undo"):
            self.state[name] = record(name)
        for name, value in self.state.items():
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


class ResetTest(ProcessTestCase):
    def test_reset_processes_signal_reset(self):
        process = standard.ProcessReset()
        self.assertIs(process.execute(), process.signals["RESET"])


if __name__ == "__main__":
    unittest.main()
