""" Behavior of the X-Cam split processes in processes/xcam.py, with core stubbed """
import unittest

import numpy as np

from autosplit64 import core
from autosplit64.processes.xcam import ProcessXCam, ProcessXCamStartUpSegment
from tests.test_standard_processes import ProcessTestCase

# The red of the X-Cam's camera symbol, and a frame without it (BGR)
XCAM = np.full((20, 20, 3), (0, 0, 150), np.uint8)
NO_XCAM = np.zeros((20, 20, 3), np.uint8)


class XCamTest(ProcessTestCase):
    """ ProcessXCam splits on the split's X-Cam count, or on an X-Cam right after a star """

    def setUp(self):
        super().setUp()
        core.current_split().on_xcam = 2
        self.process = ProcessXCam()

    def test_split_on_the_xcam_count(self):
        core.xcam_count = 1
        self.assertIs(self.process.execute(), self.process.signals["LOOP"])
        self.assertEqual(self.names(), [])
        core.xcam_count = 2
        self.assertIs(self.process.execute(), self.process.signals["LOOP"])
        self.assertEqual(self.names(), ["split"])
        self.assertEqual(core.xcam_count, 0)

    def test_split_on_an_xcam_within_a_second_of_a_star(self):
        core.in_xcam = True
        core.collection_time = core.current_time - 0.9
        self.process.execute()
        self.assertEqual(self.names(), ["split"])

    def test_no_split_on_an_xcam_a_second_after_a_star(self):
        core.in_xcam = True
        core.collection_time = core.current_time - 1
        self.process.execute()
        self.assertEqual(self.names(), [])

    def test_no_split_before_the_split_is_incoming(self):
        core.incoming_split.return_value = False
        core.xcam_count = 2
        self.process.execute()
        self.assertEqual(self.names(), [])

    def test_fadeout(self):
        core.fade_status = core.FADEOUT_PARTIAL
        core.xcam_count = 2
        self.assertIs(self.process.execute(), self.process.signals["FADEOUT"])
        self.assertEqual(self.names(), [])


class XCamStartUpSegmentTest(ProcessTestCase):
    """ ProcessXCamStartUpSegment starts an Up RTA segment on the X-Cam after the first fadeout """

    def setUp(self):
        super().setUp()
        self.process = ProcessXCamStartUpSegment()

    def test_waits_for_the_first_fadeout(self):
        core.get_region.return_value = XCAM
        self.assertIs(self.process.execute(), self.process.signals["LOOP"])
        self.assertEqual(self.names(), [])

    def test_waits_for_the_xcam_after_the_first_fadeout(self):
        core.fadeout_count = 1
        core.get_region.return_value = NO_XCAM
        self.assertIs(self.process.execute(), self.process.signals["LOOP"])
        self.assertEqual(self.calls, [("enable_predictions", False)])
        self.assertEqual(core.fps, 29.97)

    def test_split_on_the_xcam(self):
        core.fadeout_count = 1
        core.get_region.return_value = XCAM
        self.assertIs(self.process.execute(), self.process.signals["START"])
        self.assertEqual(self.calls, [("enable_predictions", False), ("split",), ("set_in_game", True)])
        self.assertEqual(core.fadeout_count, 0)
        self.assertEqual(core.fps, 10)

    def test_fadeout(self):
        core.fade_status = core.FADEOUT_PARTIAL
        core.fadeout_count = 1
        core.get_region.return_value = XCAM
        self.assertIs(self.process.execute(), self.process.signals["FADEOUT"])
        self.assertEqual(self.names(), [])


if __name__ == "__main__":
    unittest.main()
