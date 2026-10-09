""" Behavior of the DDD split processes in processes/ddd.py, with core stubbed """
import unittest
from unittest import mock

import numpy as np

from autosplit64 import core
from autosplit64.core import config
from autosplit64.processes.ddd import ProcessDDDSplit

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
        for name, value in {"split": self.split, "fade_status": core.NO_FADE, "get_region": mock.Mock(),
                            "fps": 0}.items():
            patcher = mock.patch.object(core, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(config, "get", side_effect=lambda section, key=None: SETTINGS[(section, key)])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.process = ProcessDDDSplit()
        self.process.on_transition()

    def frames(self, *frames):
        """ The signal names for each frame """
        names = {signal: name for name, signal in self.process.signals.items()}
        results = []
        for frame in frames:
            core.get_region.return_value = frame
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
        core.fade_status = core.FADEOUT_PARTIAL
        self.assertEqual(self.frames(NO_HAT), ["FADEOUT"])
        self.split.assert_not_called()


if __name__ == "__main__":
    unittest.main()
