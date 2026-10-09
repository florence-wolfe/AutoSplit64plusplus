"""
Debug info for a bug report, in one zip: the session logs, settings, route, reset templates, and a captured frame
with split detection's regions drawn on it.
"""
import os
import zipfile

import cv2

from autosplit64 import core
from . import config, logs
from .constants import (
    GAME_REGION,
    STAR_REGION,
    LIFE_REGION,
    NO_HUD_REGION,
    RESET_REGION,
    FADEOUT_REGION,
    FADEIN_REGION,
    POWER_REGION,
    XCAM_REGION,
)
from .game_capture import GameCapture
from .resource_utils import resource_path
from .route_loader import load_or_none

# Each region's name and outline color (BGR) on the captured frame
REGIONS = [
    (GAME_REGION, "game", (0, 255, 0)),
    (NO_HUD_REGION, "no HUD", (200, 200, 0)),
    (STAR_REGION, "stars", (0, 255, 255)),
    (LIFE_REGION, "lives", (255, 0, 0)),
    (RESET_REGION, "reset", (0, 0, 255)),
    (FADEOUT_REGION, "fadeout", (255, 0, 255)),
    (FADEIN_REGION, "fade-in", (255, 128, 0)),
    (POWER_REGION, "power", (0, 128, 255)),
    (XCAM_REGION, "X-Cam", (128, 0, 255)),
]


def save(path, frame=None, frame_error=None):
    """ Save the debug info to the zip at path, with frame, or why there's none """
    files = [logs.LOG_FILE, logs.OLD_LOG_FILE, "config.ini", config.get("route", "path"),
             resource_path(config.get("advanced", "reset_frame_one")), resource_path(config.get("advanced", "reset_frame_two"))]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as debug_zip:
        for file in files:
            if file and os.path.isfile(file):
                debug_zip.write(file, os.path.basename(file))
        if frame is not None:
            debug_zip.writestr("capture.png", cv2.imencode(".png", frame)[1].tobytes())
        else:
            debug_zip.writestr("capture.txt", frame_error)


def capture_frame():
    """ A frame of the capture with the regions drawn on it, or None and why there's none """
    detection = getattr(core, "_base", None)
    # Split detection's own capture: closing a second one would stop the capture it shares with it
    if detection is not None and detection.is_alive():
        capture = detection._game_capture
        if capture._window_image is None:
            return None, "Split detection hasn't captured a frame yet"
        return _draw_regions(capture._window_image, capture), None

    capture = GameCapture(config.get("game", "use_obs"), config.get("game", "vc_fix"), config.get("game", "process_name"),
                          config.get("game", "game_region"), _version(),
                          config.get("game", "capture_device") if config.get("game", "capture_source") == "device" else None)
    try:
        capture.is_valid()
        capture.capture()
        return _draw_regions(capture._window_image, capture), None
    except Exception as e:
        return None, str(e)
    finally:
        capture.close()


def _version():
    """ The game version the regions are laid out for, like split detection does """
    route = load_or_none(config.get("route", "path"))
    if config.get("game", "override_version") or not route:
        return config.get("game", "version")
    return route.version


def _draw_regions(image, capture):
    frame = image.copy()
    for region, name, color in REGIONS:
        rect = capture.get_region_rect(region)
        if rect is None:
            continue
        x, y, width, height = rect
        cv2.rectangle(frame, (x, y), (x + width - 1, y + height - 1), color, 1)
        cv2.putText(frame, name, (x + 2, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    return frame
