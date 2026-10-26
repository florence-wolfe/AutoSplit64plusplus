""" Behavior of the DDD split processes in processes/ddd.py, with split detection stubbed """
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from autosplit64.core.constants import FADEOUT_PARTIAL, NO_FADE
from autosplit64.core import detection_model
from autosplit64.processes.ddd import ProcessDDDSplit, ProcessDDDSplitX
from tests.processes import ProcessTestCase
from tests.settings import patch_settings

SETTINGS = {
    ("split_ddd_enter", "hat_lower_bound"): [0, 0, 80],
    ("split_ddd_enter", "hat_upper_bound"): [30, 30, 255],
}

# Blue painting, with or without Mario's red hat (BGR): as much of it as when he runs into the painting, or a few
# pixels, as when he's far and in shadow
NO_HAT = np.full((100, 100, 3), (200, 60, 30), np.uint8)
HAT = NO_HAT.copy()
HAT[5:9, 5:9] = (10, 10, 200)
FAINT_HAT = NO_HAT.copy()
FAINT_HAT[5, 5:7] = (10, 10, 200)


class DDDSplitTest(unittest.TestCase):
    def setUp(self):
        self.split = mock.Mock()
        # The AS64++ model's features
        self.features = set(detection_model.FEATURES[detection_model.AS64PP])
        self.detection = SimpleNamespace(split=self.split, fade_status=NO_FADE, get_region=mock.Mock(), fps=0,
                                         has=lambda feature: feature in self.features)
        patcher = patch_settings(SETTINGS)
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

    def test_no_split_without_the_hat_at_the_first_look(self):
        # Mario out of sight as the portal shows, after clipping through the door
        self.assertEqual(self.frames(NO_HAT, NO_HAT, HAT, NO_HAT), ["LOOP", "LOOP", "LOOP", "ENTERED"])
        self.split.assert_called_once()

    def test_no_split_when_a_faint_hat_fades(self):
        # Mario far down the hallway, too dark for his hat's red to show
        self.assertEqual(self.frames(HAT, FAINT_HAT, NO_HAT, HAT, NO_HAT), ["LOOP", "LOOP", "LOOP", "LOOP", "ENTERED"])
        self.split.assert_called_once()

    def test_other_models_split_on_the_first_look_without_the_hat(self):
        # As in 0.8.0, which their runners' times are compared against
        for model in (detection_model.LEGACY, detection_model.STAR_PREDICTOR):
            with self.subTest(model):
                self.features = set(detection_model.FEATURES[model])
                self.process.on_transition()
                self.assertEqual(self.frames(HAT, FAINT_HAT, NO_HAT), ["LOOP", "LOOP", "ENTERED"])
                self.process.on_transition()
                self.assertEqual(self.frames(NO_HAT), ["ENTERED"])

    def test_fadeout(self):
        self.detection.fade_status = FADEOUT_PARTIAL
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
        self.detection.fade_status = FADEOUT_PARTIAL
        self.detection.xcam_count = 1
        self.assertIs(self.process.execute(), self.process.signals["FADEOUT"])
        self.assertNotIn("split", self.names())


if __name__ == "__main__":
    unittest.main()
