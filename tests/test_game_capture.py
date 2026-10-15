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
    """ Starting split detection never shows macOS's Screen Recording prompt; Configure Capture does """

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
        # The window set in Configure Capture, which may not be the one the runner uses, e.g. the default
        with self.assertRaisesRegex(Exception, "(?s)Could not find configured capture source.*Configure Capture"):
            capture.is_valid()

    def test_logs_the_window_it_didnt_find(self):
        # Only in the log, for bug reports: the message says to set up the capture
        capture = self.capture(granted=True)
        with self.assertLogs(".log", "WARNING") as logs, self.assertRaises(Exception):
            capture.is_valid()
        self.assertIn("Emulator", logs.output[0])

if __name__ == "__main__":
    unittest.main()


class DefaultRegionsTest(unittest.TestCase):
    def regions(self, version):
        capture = GameCapture.__new__(GameCapture)
        capture._game_region = [0, 0, 617, 454]
        capture._version = version
        capture._regions = {}
        capture._add_default_regions()
        return capture._regions

    def test_life_region_is_a_lives_counter_tall_in_both_versions(self):
        for version in (game_capture.GAME_US, "JP"):
            with self.subTest(version):
                _, _, _, height = self.regions(version)[game_capture.LIFE_REGION]
                self.assertEqual(height, 42)
