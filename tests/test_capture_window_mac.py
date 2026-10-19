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
class StreamOutputTest(unittest.TestCase):
    """ The stream sends more frames than split detection reads, which are converted only when read """

    def test_frames_are_converted_when_read(self):
        output = capture_window_mac._StreamOutput.alloc().init()
        with mock.patch.object(capture_window_mac, "bgr_frame") as bgr_frame, \
             mock.patch.object(capture_window_mac, "CMSampleBufferGetImageBuffer", return_value=object()):
            for _ in range(5):
                output.stream_didOutputSampleBuffer_ofType_(None, object(), capture_window_mac.SCK.SCStreamOutputTypeScreen)
            bgr_frame.assert_not_called()
            self.assertTrue(output.frame_received.is_set())

    def test_bgr_frame_drops_alpha_and_row_padding(self):
        # 401 pixels are 1604 bytes a row, which Core Video pads
        width, height = 401, 3
        status, image_buffer = Quartz.CVPixelBufferCreate(None, width, height, Quartz.kCVPixelFormatType_32BGRA, None, None)
        self.assertEqual(status, 0)
        bytes_per_row = Quartz.CVPixelBufferGetBytesPerRow(image_buffer)
        self.assertGreater(bytes_per_row, width * 4)
        bgra = np.random.default_rng(0).integers(0, 255, (height, width, 4), dtype=np.uint8)
        Quartz.CVPixelBufferLockBaseAddress(image_buffer, 0)
        rows = np.frombuffer(Quartz.CVPixelBufferGetBaseAddress(image_buffer).as_buffer(height * bytes_per_row), np.uint8)
        rows.reshape(height, bytes_per_row)[:, :width * 4] = bgra.reshape(height, width * 4)
        Quartz.CVPixelBufferUnlockBaseAddress(image_buffer, 0)

        with mock.patch.object(capture_window_mac, "CMSampleBufferGetImageBuffer", return_value=image_buffer):
            frame = capture_window_mac.bgr_frame(object())
        np.testing.assert_array_equal(frame, bgra[:, :, :3])

    def test_frames_without_an_image_are_skipped(self):
        output = capture_window_mac._StreamOutput.alloc().init()
        with mock.patch.object(capture_window_mac, "CMSampleBufferGetImageBuffer", return_value=None):
            output.stream_didOutputSampleBuffer_ofType_(None, object(), capture_window_mac.SCK.SCStreamOutputTypeScreen)
        self.assertFalse(output.frame_received.is_set())


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
        output = mock.Mock(sample_buffer=frame, error=None, frame_received=threading.Event())
        output.frame_received.set()
        # The frame stands in for its sample buffer
        self.enterContext(mock.patch.object(capture_window_mac, "bgr_frame", side_effect=lambda sample_buffer: sample_buffer))
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
