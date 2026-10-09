""" Behavior of the DDD split processes in processes/ddd.py, with core stubbed """
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from autosplit64 import core
from autosplit64.core import config
from autosplit64.processes.ddd import ProcessDDDSplit, ProcessDDDSplitX
from tests.test_standard_processes import ProcessTestCase

SETTINGS = {
    ("split_ddd_enter", "hat_lower_bound"): [0, 0, 80],
    ("split_ddd_enter", "hat_upper_bound"): [30, 30, 255],
}

# Blue painting, with or without a few pixels of Mario's red hat (BGR)
NO_HAT = np.full((20, 20, 3), (200, 60, 30), np.uint8)
HAT = NO_HAT.copy()
HAT[5:7, 5:7] = (10, 10, 200)


class DDDSplitTest(unittest.TestCase):
    def setUp(self):
        self.split = mock.Mock()
        self.detection = SimpleNamespace(split=self.split, fade_status=core.NO_FADE, get_region=mock.Mock(), fps=0)
        patcher = mock.patch.object(config, "get", side_effect=lambda section, key=None: SETTINGS[(section, key)])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.process = ProcessDDDSplit(self.detection)
        self.process.on_transition()

    def frames(self, *frames):
        """ The signal names for each frame """
        names = {signal: name for name, signal in self.process.signals.items()}
        results = []
        for frame in frames:
            self.detection.get_region.return_value = frame
            results.append(names[self.process.execute()])
        return results

    def test_hat_visible(self):
        self.assertEqual(self.frames(HAT, HAT), ["LOOP", "LOOP"])
        self.split.assert_not_called()

    def test_splits_on_the_first_frame_without_the_hat(self):
        # Like AutoSplit64 always has, which runners' Mips and DDD times were made with: see ProcessDDDSplit
        self.assertEqual(self.frames(HAT, NO_HAT), ["LOOP", "ENTERED"])
        self.split.assert_called_once()

    def test_fadeout(self):
        self.detection.fade_status = core.FADEOUT_PARTIAL
        self.assertEqual(self.frames(NO_HAT), ["FADEOUT"])
        self.split.assert_not_called()


class DDDSplitXTest(ProcessTestCase):
    """ ProcessDDDSplitX (Mips-X) splits on the first X-Cam """

    def setUp(self):
        super().setUp()
        self.detection.xcam_count = 3
        self.process = ProcessDDDSplitX(self.detection)
        self.process.on_transition()

    def test_on_transition_counts_xcams_from_zero(self):
        self.assertEqual(self.detection.xcam_count, 0)
        self.assertEqual(self.calls, [("enable_xcam_count", True)])
        self.assertEqual(self.detection.fps, 29.97)

    def test_splits_on_the_first_xcam(self):
        results = []
        for count in (0, 1):
            self.detection.xcam_count = count
            results.append(self.process.execute())
        self.assertEqual(results, [self.process.signals["LOOP"], self.process.signals["ENTERED"]])
        self.assertEqual(self.names(), ["enable_xcam_count", "split"])

    def test_no_split_past_the_first_xcam(self):
        self.detection.xcam_count = 2
        self.assertIs(self.process.execute(), self.process.signals["LOOP"])
        self.assertNotIn("split", self.names())

    def test_fadeout(self):
        self.detection.fade_status = core.FADEOUT_PARTIAL
        self.detection.xcam_count = 1
        self.assertIs(self.process.execute(), self.process.signals["FADEOUT"])
        self.assertNotIn("split", self.names())


if __name__ == "__main__":
    unittest.main()
