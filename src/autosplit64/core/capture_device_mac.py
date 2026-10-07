"""
Video device capture for macOS using AVFoundation: capture cards, the OBS Virtual Camera or webcams.

Devices are identified by their AVFoundation unique ID. Like window capture, the device is
streamed and capture() returns the latest frame.
"""
import logging
import subprocess
import sys
import threading

import AVFoundation as AV
import objc
import Quartz
from dispatch import dispatch_queue_create
from Foundation import NSBundle, NSObject

from .capture_window_mac import bgr_frame

_DEVICE_TYPES = [
    AV.AVCaptureDeviceTypeExternal,  # Capture cards and virtual cameras like OBS
    AV.AVCaptureDeviceTypeBuiltInWideAngleCamera,
    AV.AVCaptureDeviceTypeContinuityCamera,
]

# The session of the device currently being captured: (unique id, session, output)
_active = None


class _VideoOutput(NSObject, protocols=[objc.protocolNamed("AVCaptureVideoDataOutputSampleBufferDelegate")]):
    def init(self):
        self = objc.super(_VideoOutput, self).init()
        self.frame = None
        self.frame_received = threading.Event()
        return self

    def captureOutput_didOutputSampleBuffer_fromConnection_(self, output, sample_buffer, connection):
        frame = bgr_frame(sample_buffer)
        if frame is not None:
            self.frame = frame
            self.frame_received.set()


def get_devices():
    """ Returns a list of (unique id, name) of the connected video devices """
    session = AV.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
        _DEVICE_TYPES, AV.AVMediaTypeVideo, AV.AVCaptureDevicePositionUnspecified)
    return [(device.uniqueID(), device.localizedName()) for device in session.devices()]


def has_permission():
    """ Whether the app has the Camera permission """
    return AV.AVCaptureDevice.authorizationStatusForMediaType_(AV.AVMediaTypeVideo) == AV.AVAuthorizationStatusAuthorized


def request_permission():
    """
    Show macOS's Camera prompt. Like Screen Recording, macOS only asks once and keeps a grant
    for one build of an ad-hoc signed app, so forget the earlier decision first.
    """
    bundle_id = NSBundle.mainBundle().bundleIdentifier()
    # Running from source, the permission belongs to the terminal app instead
    if getattr(sys, "frozen", False) and bundle_id:
        reset = subprocess.run(["tccutil", "reset", "Camera", bundle_id], capture_output=True, text=True)
        if reset.returncode != 0:
            logging.getLogger(".log").warning("Resetting the Camera permission failed: %s", reset.stderr.strip())
            open_permission_settings()
            return
    AV.AVCaptureDevice.requestAccessForMediaType_completionHandler_(AV.AVMediaTypeVideo, lambda granted: None)


def open_permission_settings():
    subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"])


def _start_session(unique_id):
    global _active
    stop()

    device = AV.AVCaptureDevice.deviceWithUniqueID_(unique_id)
    if device is None:
        raise Exception("Could not find the video device\n\nMake sure it is connected!")
    device_input, error = AV.AVCaptureDeviceInput.deviceInputWithDevice_error_(device, None)
    if device_input is None:
        raise Exception(f"Failed to open \"{device.localizedName()}\"\n\n{error.localizedDescription()}")

    output = _VideoOutput.alloc().init()
    video_output = AV.AVCaptureVideoDataOutput.alloc().init()
    video_output.setVideoSettings_({Quartz.kCVPixelBufferPixelFormatTypeKey: Quartz.kCVPixelFormatType_32BGRA})
    video_output.setAlwaysDiscardsLateVideoFrames_(True)
    video_output.setSampleBufferDelegate_queue_(output, dispatch_queue_create(b"as64.capture_device", None))

    session = AV.AVCaptureSession.alloc().init()
    session.addInput_(device_input)
    session.addOutput_(video_output)
    session.startRunning()

    _active = (unique_id, session, output)
    return output


def stop():
    """ Stop the active capture session """
    global _active
    if _active is not None:
        _active[1].stopRunning()
        _active = None


def capture(unique_id):
    """ Returns the latest frame of the device as a BGR image """
    if _active is not None and _active[0] == unique_id:
        output = _active[2]
    else:
        output = _start_session(unique_id)

    if not output.frame_received.wait(2):
        raise Exception("No video from the video device\n\nMake sure it is connected and the Camera permission is allowed!")
    return output.frame


def get_capture_size(unique_id):
    frame = capture(unique_id)
    return [frame.shape[1], frame.shape[0]]
