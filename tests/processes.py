""" A stand-in for split detection to run its processes in, for their tests """
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from autosplit64.core import detection_model
from autosplit64.core.constants import NO_FADE, SPLIT_NORMAL
from autosplit64.core.model import PredictionInfo
from tests.settings import patch_settings

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
    """ A stand-in for split detection, self.detection, which the processes run in """

    def setUp(self):
        self.calls = []
        record = lambda name: mock.Mock(side_effect=lambda *args, **kwargs: self.calls.append((name, *args)))
        splits = [SimpleNamespace(star_count=s, split_type=SPLIT_NORMAL, on_fadeout=1, on_fadein=0, on_xcam=-1) for s in (5, 10, 16)]
        functions = {
            "split_index": lambda: 1, "current_split": lambda: splits[1], "incoming_split": mock.Mock(return_value=True),
            "get_region_rect": lambda region: [0, 0, 251, 137],
            "get_region": mock.Mock(return_value=np.zeros((137, 251, 3), np.uint8)),
        }
        for name in ("enable_fade_count", "enable_xcam_count", "enable_predictions", "set_in_game", "set_star_count",
                     "split", "reset", "undo", "skip"):
            functions[name] = record(name)
        # Whether the fadeout is a death, by its iris, and forgetting the lives; not recorded, as neither sends the timer
        # anything or changes what else is called
        functions["died"] = mock.Mock(return_value=False)
        functions["forget_lives"] = mock.Mock()
        # The fade and the X-Cam a split is on, which it's sent on once
        functions["fade_event"] = lambda: ("fade", 7)
        # The AS64++ model's features
        self.features = set(detection_model.FEATURES[detection_model.AS64PP])
        functions["has"] = lambda feature: feature in self.features
        functions["xcam_event"] = lambda: ("X-Cam", 3)
        self.detection = SimpleNamespace(
            fade_status=NO_FADE, star_count=5, prediction_info=PredictionInfo(5, 0.9),
            route=SimpleNamespace(splits=splits, initial_star=0), fadein_count=0, fadeout_count=0,
            current_time=100.0, last_split=0.0, start_on_reset=True, fps=0.0, reset_logo_shown=False,
            xcam_count=0, in_xcam=False, collection_time=0.0, **functions)
        patcher = patch_settings(SETTINGS)
        patcher.start()
        self.addCleanup(patcher.stop)

    def names(self):
        return [call[0] for call in self.calls]


class ClockTestCase(ProcessTestCase):
    """ A process transitioned to at self.now, with time.perf_counter() stopped there until a test moves it """

    def setUp(self):
        super().setUp()
        self.start = self.now = 1000.0
        patcher = mock.patch("time.perf_counter", side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def signal(self, result):
        return {signal: name for name, signal in self.process.signals.items()}[result]
