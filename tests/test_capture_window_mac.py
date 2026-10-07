import subprocess
import sys
import time
import unittest

if sys.platform == "darwin":
    import Quartz
    from PyQt6 import QtWidgets
    from as64core import capture_window_mac

    # Capture streams need a window server connection, which the app gets from Qt
    _app = QtWidgets.QApplication([])

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
    def setUp(self):
        self.proc = subprocess.Popen([sys.executable, "-c", WINDOW_SCRIPT])
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


if __name__ == "__main__":
    unittest.main()
