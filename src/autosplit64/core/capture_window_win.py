"""
Window capture for Windows using Windows.Graphics.Capture (through windows-capture), the API
screen sharing apps and OBS use. Like the macOS capture, the window is streamed and capture()
returns the latest frame, also while the window is covered.

Same interface as capture_window.py, which still lists the windows, and captures with
PrintWindow where Windows.Graphics.Capture isn't available (before Windows 10 1903).
"""
import logging
import threading

from windows_capture import WindowsCapture

from . import capture_window

get_visible_processes = capture_window.get_visible_processes
get_hwnd_from_list = capture_window.get_hwnd_from_list
get_capture_size = capture_window.get_capture_size

# Seconds to wait for the first frame of a window
_FRAME_TIMEOUT = 1

# The stream of the window currently being captured
_active = None
# Windows.Graphics.Capture failed to start, so PrintWindow is used instead
_unavailable = False


class _Stream:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.frame = None
        self.closed = False
        self.frame_received = threading.Event()

        try:
            self.control = self._start(draw_border=False)
        except Exception:
            # Windows 10 doesn't let apps turn off the yellow capture border
            self.control = self._start(draw_border=None)

    def _start(self, draw_border):
        capture = WindowsCapture(cursor_capture=False, draw_border=draw_border, window_hwnd=self.hwnd)
        capture.frame_handler = self._on_frame_arrived
        capture.closed_handler = self._on_closed
        return capture.start_free_threaded()

    def _on_frame_arrived(self, frame, capture_control):
        # BGRA in a buffer that is reused for the next frame; keep BGR like the PrintWindow capture
        self.frame = frame.frame_buffer[:, :, :3].copy()
        self.frame_received.set()

    def _on_closed(self):
        self.closed = True


def capture(hwnd, client_area=True):
    """ Returns the latest frame of the window as a BGR image """
    global _active, _unavailable
    if _unavailable:
        return capture_window.capture(hwnd, client_area)

    if _active is None or _active.hwnd != hwnd or _active.closed:
        stop()
        try:
            _active = _Stream(hwnd)
        except Exception:
            logging.getLogger(".log").warning("Windows.Graphics.Capture is unavailable, using PrintWindow", exc_info=True)
            _unavailable = True
            return capture_window.capture(hwnd, client_area)

    if not _active.frame_received.wait(_FRAME_TIMEOUT):
        raise Exception(f"Failed to capture \"{capture_window.window_title(hwnd)}\"\n\nMake sure the window is not minimized!")
    return _active.frame


def stop():
    """ Stop the active capture stream """
    global _active
    if _active is not None:
        _active.control.stop()
        _active = None
