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



class WaitTest(unittest.TestCase):
    """ Waiting until split detection's next look, capturing every frame of the game in between """

    def setUp(self):
        self.now = 0.0
        self.capture = GameCapture.__new__(GameCapture)
        self.capture.capture = mock.Mock()

        def sleep(seconds):
            self.now += seconds
        for name, value in (("perf_counter", lambda: self.now), ("sleep", sleep)):
            patcher = mock.patch.object(game_capture.time, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_waits_the_whole_time_capturing_each_frame(self):
        # 7.5 frames
        self.capture.wait(0.25)
        self.assertAlmostEqual(self.now, 0.25)
        self.assertEqual(self.capture.capture.call_count, 7)

    def test_capturing_doesnt_delay_the_next_frame(self):
        # A capture that takes 10 ms, which only shortens the sleep to the next frame
        times = []
        self.capture.capture.side_effect = lambda: times.append(self.now) or setattr(self, "now", self.now + 0.01)
        self.capture.wait(0.25)
        self.assertEqual(len(times), 7)
        for frame, at in enumerate(times, 1):
            self.assertAlmostEqual(at, frame * game_capture.FRAME)
        self.assertAlmostEqual(self.now, 0.25)

    def test_a_capture_longer_than_a_frame_doesnt_capture_twice_at_once(self):
        # 50 ms captures: the next starts as soon as one ends, not to catch up on the frames it missed
        times = []
        self.capture.capture.side_effect = lambda: times.append(self.now) or setattr(self, "now", self.now + 0.05)
        self.capture.wait(0.25)
        self.assertTrue(all(b - a >= 0.05 - 1e-9 for a, b in zip(times, times[1:])), times)

    def test_a_frame_split_detection_wants_to_look_at_ends_the_wait(self):
        frames = []
        self.capture.wait(0.2, lambda: frames.append(self.now) or len(frames) == 2)
        # On the second frame, without waiting the rest
        self.assertEqual(len(frames), 2)
        self.assertAlmostEqual(self.now, 2 * game_capture.FRAME)


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

class ReconnectTest(unittest.TestCase):
    """ Finding the capture source again, after it was lost in a run """

    def capture(self, use_obs=False, device=None):
        capture = GameCapture.__new__(GameCapture)
        capture._use_obs, capture._device, capture._process_name, capture._hwnd = use_obs, device, "Emulator", 1
        return capture

    def window(self, found):
        window = game_capture.capture_window
        for name, value in [("get_visible_processes", mock.Mock(return_value=[])),
                            ("get_hwnd_from_list", mock.Mock(return_value=found)),
                            ("has_permission_quietly", mock.Mock(return_value=True))]:
            patcher = mock.patch.object(window, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_window_is_found_again(self):
        # The capture software was restarted, so its window is another one
        self.window(found=2)
        capture = self.capture()
        capture.reconnect()
        self.assertEqual(capture._hwnd, 2)
        game_capture.capture_window.get_hwnd_from_list.assert_called_once_with("Emulator", [])

    def test_window_that_isnt_back(self):
        self.window(found=None)
        with self.assertRaisesRegex(Exception, "Could not find configured capture source"):
            self.capture().reconnect()

    def test_obs_plugin_is_opened_again(self):
        capture = self.capture(use_obs=True)
        capture._shmem = mock.Mock()
        capture.reconnect()
        self.assertEqual([call[0] for call in capture._shmem.method_calls], ["close_shmem", "open_shmem"])

    @unittest.skipUnless(sys.platform == "darwin", "macOS video devices")
    def test_device_session_is_started_again(self):
        # The capture card was plugged in again: its old session sends nothing
        device = game_capture.capture_device
        with mock.patch.object(device, "stop") as stop, \
             mock.patch.object(device, "has_permission", return_value=True), \
             mock.patch.object(device, "get_devices", return_value=[("card", "Capture Card")]):
            self.capture(device="card").reconnect()
        stop.assert_called_once()


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
