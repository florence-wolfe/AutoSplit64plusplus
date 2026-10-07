import sys
import unittest
from unittest import mock

import numpy as np

from autosplit64.core import game_capture
from autosplit64.core.game_capture import GameCapture


class RegionTest(unittest.TestCase):
    def setUp(self):
        self.capture = GameCapture.__new__(GameCapture)
        self.capture._regions = {"STAR": [1, 2, 3, 4]}
        self.capture._region_images = {}
        self.capture._window_image = np.arange(100 * 100 * 3, dtype=np.uint8).reshape(100, 100, 3)

    def test_region_image_is_cropped_and_cached(self):
        star = self.capture.get_region("STAR")
        np.testing.assert_array_equal(star, self.capture._window_image[2:6, 1:4])
        self.assertIs(self.capture.get_region("STAR"), star)

    def test_unknown_region(self):
        self.assertIsNone(self.capture.get_region("UNKNOWN"))
        self.assertIsNone(self.capture.get_region_rect("UNKNOWN"))

    def test_region_rect(self):
        self.assertEqual(self.capture.get_region_rect("STAR"), [1, 2, 3, 4])



@unittest.skipUnless(sys.platform == "darwin", "macOS window capture")
class StartWithoutScreenRecordingTest(unittest.TestCase):
    """ Starting split detection never shows macOS's Screen Recording prompt; Edit Coordinates does """

    def capture(self, granted):
        window = game_capture.capture_window
        for name, value in [("has_permission_quietly", mock.Mock(return_value=granted)),
                            ("has_permission", mock.Mock(side_effect=AssertionError("would show the prompt"))),
                            ("get_visible_processes", mock.Mock(return_value=[]))]:
            # has_permission is gone, and must not come back as a way to check
            patcher = mock.patch.object(window, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        return GameCapture(False, False, "Emulator", [0, 0, 100, 100], "JP")

    def test_without_permission(self):
        capture = self.capture(granted=False)
        game_capture.capture_window.get_visible_processes.assert_not_called()
        with self.assertRaisesRegex(Exception, "Screen Recording permission"):
            capture.is_valid()

    def test_with_permission(self):
        capture = self.capture(granted=True)
        game_capture.capture_window.get_visible_processes.assert_called_once()
        with self.assertRaisesRegex(Exception, "Could not find Emulator"):
            capture.is_valid()

if __name__ == "__main__":
    unittest.main()
