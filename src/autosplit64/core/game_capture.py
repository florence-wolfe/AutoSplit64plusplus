import logging
import sys
import time
from collections import deque

from . import capture_shmem
if sys.platform == "darwin":
    from . import capture_device_mac as capture_device
    from . import capture_window_mac as capture_window
else:
    from . import capture_window_win as capture_window
from .image_utils import enhance_contrast
from . import irises
import numpy as np

from .constants import (
    GAME_US,
    GAME_REGION_BASE,
    GAME_REGION_RATIO,
    STAR_REGION_US_RATIO,
    STAR_REGION_JP_RATIO,
    LIFE_REGION_US_RATIO,
    LIFE_REGION_JP_RATIO,
    FADEOUT_REGION_RATIO,
    FADEIN_REGION_RATIO,
    RESET_REGION_RATIO,
    NO_HUD_REGION_RATIO,
    POWER_REGION_RATIO,
    XCAM_REGION_RATIO,
    LIVES_REGION_US_RATIO,
    LIVES_REGION_JP_RATIO,
    GAME_REGION,
    STAR_REGION,
    LIFE_REGION,
    FADEOUT_REGION,
    FADEIN_REGION,
    RESET_REGION,
    NO_HUD_REGION,
    POWER_REGION,
    XCAM_REGION,
    LIVES_REGION
)


# How long the looks at the game are kept for the iris matcher: a death's iris (1.6 s) and the looks before it
LOOKS_KEPT = 2.4
# The game's frames are 1/30 s apart
FRAME = 1 / 30


class GameCapture(object):
    def __init__(self, use_obs, vc_fix, process_name, game_region, version, device=None):
        # Initialize GameCapture
        # The OBS Plugin is only available on Windows
        self._use_obs = use_obs and sys.platform == "win32"
        self._process_name = process_name
        self._vc_fix = vc_fix
        
        # Unique id of the video device to capture on macOS, instead of a window
        self._device = device

        if self._use_obs:
        # Initialize SharedMemoryCapture
            self._shmem = capture_shmem.SharedMemoryCapture()
        elif self._device:
            pass
        elif sys.platform == "darwin" and not capture_window.has_permission_quietly():
            # Listing windows would show macOS's Screen Recording prompt; Configure Capture asks for it instead
            self._hwnd = None
        else:
            self._hwnd: int = capture_window.get_hwnd_from_list(process_name, capture_window.get_visible_processes())
        
        
        self._game_region: list = game_region
        self._version = version

        self._regions: dict = {}
        self._window_image = None
        self._region_images: dict = {}
        # (time, brightness) of every frame captured in the last LOOKS_KEPT seconds, for the iris matcher
        self.looks = deque()

        self._add_default_regions()

    def _add_default_regions(self):
        """ Add default regions as per constants """
        def calc_ratio(c: list, b: list) -> list:
            return [c[0] / b[0], c[1] / b[1], c[2] / b[0], c[3] / b[1]]

        def calc_region(ratio: list) -> list:
            """ Convert a region expressed as a ratio into absolute coordinates """
            return [int(round(self._game_region[0] + (self._game_region[2] * ratio[0]))),
                    int(round(self._game_region[1] + (self._game_region[3] * ratio[1]))),
                    int(round(self._game_region[2] * ratio[2])),
                    int(round(self._game_region[3] * ratio[3]))]

        if self._version == GAME_US:
            self._regions[STAR_REGION] = calc_region(calc_ratio(STAR_REGION_US_RATIO, GAME_REGION_BASE))
            self._regions[LIFE_REGION] = calc_region(calc_ratio(LIFE_REGION_US_RATIO, GAME_REGION_BASE))
            self._regions[LIVES_REGION] = calc_region(calc_ratio(LIVES_REGION_US_RATIO, GAME_REGION_BASE))
        else:
            self._regions[STAR_REGION] = calc_region(calc_ratio(STAR_REGION_JP_RATIO, GAME_REGION_BASE))
            self._regions[LIFE_REGION] = calc_region(calc_ratio(LIFE_REGION_JP_RATIO, GAME_REGION_BASE))
            self._regions[LIVES_REGION] = calc_region(calc_ratio(LIVES_REGION_JP_RATIO, GAME_REGION_BASE))

        self._regions[GAME_REGION] = calc_region(calc_ratio(GAME_REGION_RATIO, GAME_REGION_BASE))
        self._regions[FADEOUT_REGION] = calc_region(calc_ratio(FADEOUT_REGION_RATIO, GAME_REGION_BASE))
        self._regions[FADEIN_REGION] = calc_region(calc_ratio(FADEIN_REGION_RATIO, GAME_REGION_BASE))
        self._regions[RESET_REGION] = calc_region(calc_ratio(RESET_REGION_RATIO, GAME_REGION_BASE))
        self._regions[NO_HUD_REGION] = calc_region(calc_ratio(NO_HUD_REGION_RATIO, GAME_REGION_BASE))
        self._regions[POWER_REGION] = calc_region(calc_ratio(POWER_REGION_RATIO, GAME_REGION_BASE))
        self._regions[XCAM_REGION] = calc_region(calc_ratio(XCAM_REGION_RATIO, GAME_REGION_BASE))

    def is_valid(self):
        if self._use_obs:
            try:
                self._shmem.open_shmem()
            except Exception as e:
                raise Exception(str(e))    
        elif self._device:
            if not capture_device.has_permission():
                raise Exception("AutoSplit64++ needs the Camera permission to capture the video device.\n\nOpen Configure Capture to allow it.")
            if self._device not in [device[0] for device in capture_device.get_devices()]:
                raise Exception("Could not find the video device\n\nMake sure it is connected!")
        else:
            if not bool(self._hwnd) and sys.platform == "darwin" and not capture_window.has_permission_quietly():
                raise Exception("AutoSplit64++ needs the Screen Recording permission to capture the game.\n\n"
                                "Open Configure Capture to allow it. If you just allowed it, restart AutoSplit64++.")
            if not bool(self._hwnd):
                logging.getLogger(".log").warning("Could not find the window to capture: %s", self._process_name)
                raise Exception("Could not find configured capture source.\n\nMake sure it's running and visible, "
                                "or set up what to capture in Configure Capture.")

    def reconnect(self):
        """ Find the capture source again, e.g. after the capture software restarted or the capture card was replugged """
        if self._use_obs:
            self._shmem.close_shmem()
        elif self._device:
            # A replugged device's old session sends nothing
            capture_device.stop()
        else:
            self._hwnd = capture_window.get_hwnd_from_list(self._process_name, capture_window.get_visible_processes())
        self.is_valid()

    def capture(self) -> None:
        if self._use_obs:
            self._window_image = self._shmem.capture()
        elif self._device:
            self._window_image = capture_device.capture(self._device)
        else:
            self._window_image = capture_window.capture(self._hwnd) 
            
        if self._vc_fix:
            # Fix for VC (Experimental) - Increases latency
            self._window_image = enhance_contrast(self._window_image, 1.2)
        
        self._region_images = {}  
        self._remember(time.perf_counter(), self._window_image)

    def _remember(self, at, image):
        """ Keep a look at the game in `image`, captured at `at`, for the iris matcher """
        x, y, width, height = self._regions[GAME_REGION]
        self.looks.append((at, irises.brightness_of(image[y:y + height, x:x + width])))
        while self.looks[0][0] < at - LOOKS_KEPT:
            self.looks.popleft()

    def wait(self, seconds, look_now=None):
        """
        Sleep `seconds` until split detection's next look, capturing every frame of the game in between, so the iris
        matcher sees every frame of a transition however seldom split detection looks. Ends on a frame `look_now`
        says split detection should look at now.
        """
        end = time.perf_counter() + seconds
        # A frame after the last capture started, not after it ended, so capturing doesn't make it fall behind the game
        next_frame = time.perf_counter() + FRAME
        while next_frame < end:
            time.sleep(max(next_frame - time.perf_counter(), 0))
            # Once behind, as soon as this capture is done, rather than again and again to catch up
            next_frame = max(next_frame + FRAME, time.perf_counter())
            try:
                self.capture()
            except Exception:
                # The next look captures again, and reports it
                break
            if look_now and look_now():
                return
        remaining = end - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)

    def get_capture_size(self):
        if self._use_obs:
            return self._shmem.get_capture_size()
        elif self._device:
            return capture_device.get_capture_size(self._device)
        else:
            return capture_window.get_capture_size(self._hwnd)

    def get_region(self, region):
        if self._window_image is None:
            self.capture()

        if region not in self._regions:
            return None
        if region not in self._region_images:
            self._region_images[region] = self._crop(*self._regions[region])
        return self._region_images[region]

    def get_region_rect(self, region):
        return self._regions.get(region)

    def _crop(self, x, y, width, height):
        return self._window_image[y:y + height, x:x + width]
    
    # Destructor
    def close(self):
        if self._use_obs:
            self._shmem.close_shmem()
        else:
            capture_window.stop()
            if sys.platform == "darwin":
                capture_device.stop()

