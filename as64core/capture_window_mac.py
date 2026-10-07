"""
Window capture for macOS using ScreenCaptureKit, the API screen sharing apps use.

Same interface as capture_window.py, with an SCWindow in place of a hwnd. A window is
captured by a stream that keeps the latest frame, so capture() doesn't wait for the screen.
"""
import logging
import subprocess
import sys
import threading

import numpy as np
import objc
import psutil
import Quartz
import ScreenCaptureKit as SCK
from CoreMedia import CMSampleBufferGetImageBuffer, CMTimeMake
from Foundation import NSBundle, NSObject

_TIMEOUT = 5
_MINIMUM_WINDOW_SIZE = 100

# The stream of the window currently being captured: (window id, stream, output)
_active = None


class _StreamOutput(NSObject, protocols=[objc.protocolNamed("SCStreamOutput"), objc.protocolNamed("SCStreamDelegate")]):
    def init(self):
        self = objc.super(_StreamOutput, self).init()
        self.frame = None
        self.error = None
        self.frame_received = threading.Event()
        return self

    def stream_didOutputSampleBuffer_ofType_(self, stream, sample_buffer, output_type):
        if output_type != SCK.SCStreamOutputTypeScreen:
            return
        # Frames sent while the window is unchanged carry no image
        frame = bgr_frame(sample_buffer)
        if frame is None:
            return
        self.frame = frame
        self.frame_received.set()

    def stream_didStopWithError_(self, stream, error):
        self.error = error


def bgr_frame(sample_buffer):
    """ Returns a BGRA sample buffer as a BGR image like the Windows capture, or None without an image """
    image_buffer = CMSampleBufferGetImageBuffer(sample_buffer)
    if image_buffer is None:
        return None

    Quartz.CVPixelBufferLockBaseAddress(image_buffer, Quartz.kCVPixelBufferLock_ReadOnly)
    try:
        width = Quartz.CVPixelBufferGetWidth(image_buffer)
        height = Quartz.CVPixelBufferGetHeight(image_buffer)
        bytes_per_row = Quartz.CVPixelBufferGetBytesPerRow(image_buffer)
        data = Quartz.CVPixelBufferGetBaseAddress(image_buffer).as_buffer(height * bytes_per_row)
        # Rows may be padded
        return np.frombuffer(data, dtype=np.uint8).reshape(height, bytes_per_row // 4, 4)[:, :width, :3].copy()
    finally:
        Quartz.CVPixelBufferUnlockBaseAddress(image_buffer, Quartz.kCVPixelBufferLock_ReadOnly)


def _wait(start):
    """ Call start(handler) and wait for the completion handler. Returns the handler's arguments. """
    done = threading.Event()
    result = []

    def handler(*args):
        result.extend(args)
        done.set()

    start(handler)
    if not done.wait(_TIMEOUT):
        raise Exception("ScreenCaptureKit did not respond")
    return result


_last_error = None


def _shareable_content():
    """ Returns the windows ScreenCaptureKit can capture, or None without the Screen Recording permission """
    global _last_error
    content, error = _wait(lambda handler: SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(True, True, handler))
    # Log each new refusal once, as this is called repeatedly while waiting for the permission
    if error is not None and error.localizedDescription() != _last_error:
        logging.getLogger(".log").warning("ScreenCaptureKit refused (preflight %s): %s", Quartz.CGPreflightScreenCaptureAccess(), error.localizedDescription())
    _last_error = error.localizedDescription() if error is not None else None
    return content


def _windows():
    content = _shareable_content()
    return content.windows() if content is not None else []


def has_permission():
    """
    Whether the app has the Screen Recording permission. Asks ScreenCaptureKit itself, since
    CGPreflightScreenCaptureAccess() can be out of date.
    """
    return _shareable_content() is not None


def request_permission():
    """
    Show macOS's Screen Recording prompt. macOS only shows it once per app, and keeps a grant
    for one build of an ad-hoc signed app. So forget the earlier decision first, which makes
    macOS ask again for this build.
    """
    bundle_id = NSBundle.mainBundle().bundleIdentifier()
    # Running from source, the permission belongs to the terminal app instead
    if getattr(sys, "frozen", False) and bundle_id:
        reset = subprocess.run(["tccutil", "reset", "ScreenCapture", bundle_id], capture_output=True, text=True)
        if reset.returncode != 0:
            logging.getLogger(".log").warning("Resetting the Screen Recording permission failed: %s", reset.stderr.strip())
            open_permission_settings()
            return
    Quartz.CGRequestScreenCaptureAccess()


def open_permission_settings():
    subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"])


def get_visible_processes():
    """ Returns a list of (process, window) with the largest window of each process """
    largest = {}
    for window in _windows():
        app = window.owningApplication()
        size = window.frame().size
        if app is None or window.windowLayer() != 0 or size.width < _MINIMUM_WINDOW_SIZE or size.height < _MINIMUM_WINDOW_SIZE:
            continue
        pid = app.processID()
        if pid not in largest or size.width * size.height > largest[pid].frame().size.width * largest[pid].frame().size.height:
            largest[pid] = window

    processes = []
    for pid, window in largest.items():
        try:
            processes.append((psutil.Process(pid), window))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return processes


def get_hwnd_from_list(process_name, process_list):
    """ Given a list of processes, return the window of the process with given name """
    for p in process_list:
        if p[0].name() == process_name:
            return p[1]


def _start_stream(window):
    global _active
    stop()

    width, height = get_capture_size(window)
    config = SCK.SCStreamConfiguration.alloc().init()
    config.setWidth_(width)
    config.setHeight_(height)
    config.setPixelFormat_(Quartz.kCVPixelFormatType_32BGRA)
    config.setShowsCursor_(False)
    config.setMinimumFrameInterval_(CMTimeMake(1, 60))

    content_filter = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)
    output = _StreamOutput.alloc().init()
    stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(content_filter, config, output)
    added, error = stream.addStreamOutput_type_sampleHandlerQueue_error_(output, SCK.SCStreamOutputTypeScreen, None, None)
    if not added:
        raise Exception(f"Failed to capture \"{window.title()}\"\n\n{error}")
    error, = _wait(stream.startCaptureWithCompletionHandler_)
    if error is not None:
        raise Exception(f"Failed to capture \"{window.title()}\"\n\n{error.localizedDescription()}")

    _active = (window.windowID(), stream, output)
    return output


def stop():
    """ Stop the active capture stream """
    global _active
    if _active is not None:
        _active[1].stopCaptureWithCompletionHandler_(None)
        _active = None


def capture(window, client_area=True):
    """ Returns the latest frame of the window as a BGR image """
    if _active is not None and _active[0] == window.windowID() and _active[2].error is None:
        output = _active[2]
    else:
        output = _start_stream(window)

    if not output.frame_received.wait(1):
        raise Exception(f"Failed to capture \"{window.title()}\"\n\nMake sure the window is not minimized!")
    return output.frame


def get_capture_size(window):
    """ Returns the current window size in points """
    for w in _windows():
        if w.windowID() == window.windowID():
            window = w
            break
    size = window.frame().size
    return [int(size.width), int(size.height)]
