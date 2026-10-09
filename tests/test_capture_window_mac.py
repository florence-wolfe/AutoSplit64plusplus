import os
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

import numpy as np

if sys.platform == "darwin":
    import AppKit
    import Quartz
    from autosplit64.core import capture_window_mac


# A window whose left half is pure red and right half pure blue
WINDOW_SCRIPT = """
from PyQt6 import QtWidgets, QtGui
app = QtWidgets.QApplication([])
w = QtWidgets.QWidget()
w.setWindowTitle("as64-capture-test")
w.resize(400, 300)
def paint(e):
    p = QtGui.QPainter(w)
    p.fillRect(0, 0, w.width() // 2, w.height(), QtGui.QColor(255, 0, 0))
    p.fillRect(w.width() // 2, 0, w.width() - w.width() // 2, w.height(), QtGui.QColor(0, 0, 255))
w.paintEvent = paint
w.show()
w.raise_()
app.exec()
"""


@unittest.skipUnless(sys.platform == "darwin" and Quartz.CGPreflightScreenCaptureAccess(), "needs macOS with Screen Recording permission")
class CaptureWindowMacTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Capture streams need a window server connection, which the app gets from Qt, and AppKit when the
        # tests run offscreen. Only here, since it makes the test process an app, with a Dock icon on macOS.
        AppKit.NSApplication.sharedApplication()

    def setUp(self):
        # On the screen, also when the tests run offscreen
        env = {key: value for key, value in os.environ.items() if key != "QT_QPA_PLATFORM"}
        self.proc = subprocess.Popen([sys.executable, "-c", WINDOW_SCRIPT], env=env)
        self.addCleanup(self.proc.wait)
        self.addCleanup(self.proc.kill)
        self.addCleanup(capture_window_mac.stop)

        end = time.time() + 10
        self.window = None
        while self.window is None and time.time() < end:
            for proc, window in capture_window_mac.get_visible_processes():
                if proc.pid == self.proc.pid:
                    self.window = window
            time.sleep(0.2)
        self.assertIsNotNone(self.window, "test window not found")

    def test_capture_returns_bgr_frame_of_window(self):
        width, height = capture_window_mac.get_capture_size(self.window)
        frame = capture_window_mac.capture(self.window)

        self.assertEqual(frame.shape, (height, width, 3))
        # Sample below the title bar. BGR order: red is (0, 0, 255).
        y = height * 3 // 4
        left = frame[y, width // 4].astype(int)
        right = frame[y, width * 3 // 4].astype(int)
        self.assertTrue(left[2] > 200 and left[0] < 60 and left[1] < 60, f"expected red, got BGR {left}")
        self.assertTrue(right[0] > 200 and right[1] < 60 and right[2] < 60, f"expected blue, got BGR {right}")

    def test_capture_keeps_returning_frames(self):
        first = capture_window_mac.capture(self.window)
        second = capture_window_mac.capture(self.window)
        self.assertEqual(first.shape, second.shape)


@unittest.skipUnless(sys.platform == "darwin", "needs macOS")
class TitleBarTest(unittest.TestCase):
    """ The title bar isn't part of the capture, like the client area on Windows """

    def setUp(self):
        self.addCleanup(setattr, capture_window_mac, "_active", None)

    def window(self, width, height):
        window = mock.Mock()
        window.windowID.return_value = 7
        window.frame.return_value = Quartz.CGRectMake(100, 50, width, height)
        return window

    def screen(self, *windows, display=(1512, 982)):
        display_mock = mock.Mock()
        display_mock.frame.return_value = Quartz.CGRectMake(0, 0, *display)
        content = mock.Mock()
        content.windows.return_value = list(windows)
        content.displays.return_value = [display_mock]
        return mock.patch.object(capture_window_mac, "_shareable_content", return_value=content)

    def stream(self, window, frame):
        """ Start a stream of window, which has received frame """
        output = mock.Mock(frame=frame, error=None, frame_received=threading.Event())
        output.frame_received.set()
        with mock.patch.object(capture_window_mac.SCK, "SCStream"), \
             mock.patch.object(capture_window_mac.SCK, "SCContentFilter"), \
             mock.patch.object(capture_window_mac, "_StreamOutput") as stream_output, \
             mock.patch.object(capture_window_mac, "_wait", return_value=[None]):
            stream_output.alloc.return_value.init.return_value = output
            capture_window_mac.SCK.SCStream.alloc.return_value.initWithFilter_configuration_delegate_.return_value.addStreamOutput_type_sampleHandlerQueue_error_.return_value = (True, None)
            return capture_window_mac.capture(window)

    def test_size_leaves_out_the_title_bar(self):
        window = self.window(1290, 988)
        with self.screen(window):
            self.assertEqual(capture_window_mac.get_capture_size(window), [1290, 960])

    def test_frame_leaves_out_the_title_bar(self):
        window = self.window(400, 300)
        # Each row's value is its number, so the first row left shows what was cut
        frame = np.repeat(np.arange(300, dtype=np.uint16)[:, None, None], 400, axis=1).repeat(3, axis=2)
        with self.screen(window):
            captured = self.stream(window, frame)
            self.assertEqual(captured.shape, (272, 400, 3))
            self.assertEqual(captured[0, 0, 0], 28)
            # Later frames of the running stream too
            self.assertEqual(capture_window_mac.capture(window).shape, (272, 400, 3))

    def test_fullscreen_window_has_no_title_bar(self):
        window = self.window(1512, 982)
        window.frame.return_value = Quartz.CGRectMake(0, 0, 1512, 982)
        frame = np.zeros((982, 1512, 3), np.uint8)
        with self.screen(window):
            self.assertEqual(capture_window_mac.get_capture_size(window), [1512, 982])
            self.assertEqual(self.stream(window, frame).shape, (982, 1512, 3))


if __name__ == "__main__":
    unittest.main()
