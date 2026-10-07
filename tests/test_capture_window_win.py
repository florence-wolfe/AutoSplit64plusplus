""" capture_window_win with stand-ins for windows-capture and the PrintWindow capture, so it runs on any platform """
import importlib
import sys
import types
import unittest
from unittest import mock

import numpy as np

import as64core


class FakeWindowsCapture:
    """ Stands in for windows_capture.WindowsCapture; the test delivers frames """
    instances = []
    fail_with = None
    border_unsupported = False

    def __init__(self, **kwargs):
        if FakeWindowsCapture.fail_with:
            raise FakeWindowsCapture.fail_with
        self.kwargs = kwargs
        self.frame_handler = self.closed_handler = None
        self.control = mock.Mock()
        FakeWindowsCapture.instances.append(self)

    def start_free_threaded(self):
        if FakeWindowsCapture.border_unsupported and self.kwargs["draw_border"] is False:
            raise Exception("Border configuration is not supported")
        return self.control

    def deliver(self, bgra):
        self.frame_handler(types.SimpleNamespace(frame_buffer=bgra), mock.Mock())


class CaptureWindowWinTest(unittest.TestCase):
    def setUp(self):
        FakeWindowsCapture.instances = []
        FakeWindowsCapture.fail_with = None
        FakeWindowsCapture.border_unsupported = False
        self.print_window = types.SimpleNamespace(
            capture=mock.Mock(return_value=np.full((4, 4, 3), 7, np.uint8)),
            get_visible_processes=mock.Mock(), get_hwnd_from_list=mock.Mock(), get_capture_size=mock.Mock(),
            window_title=mock.Mock(return_value="Emulator"))
        modules = {"windows_capture": types.SimpleNamespace(WindowsCapture=FakeWindowsCapture),
                   "as64core.capture_window": self.print_window}
        # On Windows the real capture_window is already imported, and "from . import" finds it on the package
        for patcher in [mock.patch.dict(sys.modules, modules),
                        mock.patch.object(as64core, "capture_window", self.print_window, create=True)]:
            patcher.start()
            self.addCleanup(patcher.stop)
        sys.modules.pop("as64core.capture_window_win", None)
        self.module = importlib.import_module("as64core.capture_window_win")
        self.addCleanup(sys.modules.pop, "as64core.capture_window_win", None)
        self.addCleanup(self.module.stop)
        self.module._FRAME_TIMEOUT = 0.05

    def bgra(self, value):
        return np.full((3, 5, 4), value, np.uint8)

    def capture_with_frame(self, hwnd, bgra):
        """ Capture hwnd, delivering a frame as soon as the stream starts """
        real_start = FakeWindowsCapture.start_free_threaded

        def start_and_deliver(capture):
            control = real_start(capture)
            capture.deliver(bgra)
            return control

        with mock.patch.object(FakeWindowsCapture, "start_free_threaded", start_and_deliver):
            return self.module.capture(hwnd)

    def test_streams_window_as_bgr_without_cursor_and_border(self):
        frame = self.capture_with_frame(42, self.bgra(9))
        self.assertEqual(frame.shape, (3, 5, 3))
        self.assertTrue((frame == 9).all())
        [capture] = FakeWindowsCapture.instances
        self.assertEqual(capture.kwargs, {"cursor_capture": False, "draw_border": False, "window_hwnd": 42})

    def test_frame_is_copied_from_reused_buffer(self):
        bgra = self.bgra(9)
        frame = self.capture_with_frame(42, bgra)
        bgra[:] = 0
        self.assertTrue((frame == 9).all())

    def test_returns_latest_frame_from_same_stream(self):
        self.capture_with_frame(42, self.bgra(1))
        FakeWindowsCapture.instances[0].deliver(self.bgra(2))
        self.assertTrue((self.module.capture(42) == 2).all())
        self.assertEqual(len(FakeWindowsCapture.instances), 1)

    def test_other_window_replaces_stream(self):
        self.capture_with_frame(42, self.bgra(1))
        self.capture_with_frame(43, self.bgra(2))
        first, second = FakeWindowsCapture.instances
        first.control.stop.assert_called_once()
        self.assertEqual(second.kwargs["window_hwnd"], 43)

    def test_closed_window_restarts_stream(self):
        self.capture_with_frame(42, self.bgra(1))
        FakeWindowsCapture.instances[0].closed_handler()
        self.capture_with_frame(42, self.bgra(2))
        self.assertEqual(len(FakeWindowsCapture.instances), 2)

    def test_border_unsupported_uses_system_default(self):
        # Windows 10 doesn't let apps turn off the capture border
        FakeWindowsCapture.border_unsupported = True
        self.capture_with_frame(42, self.bgra(1))
        self.assertEqual([c.kwargs["draw_border"] for c in FakeWindowsCapture.instances], [False, None])

    def test_falls_back_to_print_window_without_graphics_capture(self):
        FakeWindowsCapture.fail_with = OSError("Windows.Graphics.Capture is not supported")
        self.assertTrue((self.module.capture(42) == 7).all())
        self.module.capture(42)
        # Doesn't try Windows.Graphics.Capture again every frame
        self.assertEqual(self.print_window.capture.call_count, 2)
        FakeWindowsCapture.fail_with = None
        self.module.capture(42)
        self.assertEqual(FakeWindowsCapture.instances, [])

    def test_no_frame_from_window(self):
        with self.assertRaisesRegex(Exception, 'Failed to capture "Emulator"'):
            self.module.capture(42)

    def test_stop(self):
        self.capture_with_frame(42, self.bgra(1))
        self.module.stop()
        FakeWindowsCapture.instances[0].control.stop.assert_called_once()

    def test_window_listing_and_size_come_from_print_window_module(self):
        self.assertIs(self.module.get_visible_processes, self.print_window.get_visible_processes)
        self.assertIs(self.module.get_hwnd_from_list, self.print_window.get_hwnd_from_list)
        self.assertIs(self.module.get_capture_size, self.print_window.get_capture_size)


if __name__ == "__main__":
    unittest.main()
