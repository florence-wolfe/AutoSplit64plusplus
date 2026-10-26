import cv2
import numpy as np

from autosplit64.core.constants import DEFAULT_FRAME_RATE, GAME_REGION, NO_HUD_REGION

from autosplit64.core import config, detection_model
from autosplit64.core.image_utils import colour_shown
from autosplit64.core.processing import Process, Signal

# With detection_model.MIPS_HAT_DROP, Mario entered the painting when his hat is gone from the region and was in at
# least this share of it the look before: 0.14 to 0.23% as he runs into it. Far down the hallway and in shadow, his hat
# fades out of the colour bounds over a few frames instead, from less than 0.05%, and he's out of sight as the portal
# first shows after the door clip.
HAT_SEEN = 0.0005


class ProcessFindDDDPortal(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("FOUND")
        self.register_signal("FADEOUT")
        self.portal_lower_bound = config.get("split_ddd_enter", "portal_lower_bound")
        self.portal_upper_bound = config.get("split_ddd_enter", "portal_upper_bound")

    def execute(self):
        no_hud = self.core.get_region(GAME_REGION)

        if self.fading_out():
            return self.signals["FADEOUT"]

        if colour_shown(no_hud, self.portal_lower_bound, self.portal_upper_bound, 0.99):
            return self.signals["FOUND"]
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 10
        self.core.enable_xcam_count(False)
        super().on_transition()


class ProcessDDDSplit(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("ENTERED")
        self.register_signal("FADEOUT")
        self.lower_bound = np.array(config.get("split_ddd_enter", "hat_lower_bound"), dtype="uint8")
        self.upper_bound = np.array(config.get("split_ddd_enter", "hat_upper_bound"), dtype="uint8")
        # How much of the region was hat at the last look
        self._hat = 0

    def execute(self):
        no_hud = self.core.get_region(NO_HUD_REGION)

        if self.fading_out():
            return self.signals["FADEOUT"]

        # Split on the first frame without the hat, like AutoSplit64. Waiting for a second frame delays every Mips
        # split by 33 ms, which runners' golds can't be compared to.
        hat_mask = cv2.inRange(no_hud, self.lower_bound, self.upper_bound)
        hat = cv2.countNonZero(hat_mask) / hat_mask.size
        if hat == 0 and (self._hat >= HAT_SEEN or not self.core.has(detection_model.MIPS_HAT_DROP)):
            self.core.split()
            return self.signals["ENTERED"]
        self._hat = hat
        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = DEFAULT_FRAME_RATE
        self._hat = 0
        super().on_transition()


class ProcessDDDSplitX(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("ENTERED")
        self.register_signal("FADEOUT")

    def execute(self):
        if self.fading_out():
            return self.signals["FADEOUT"]

        if self.core.xcam_count == 1:
            self.core.split()
            return self.signals["ENTERED"]
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = DEFAULT_FRAME_RATE
        self.core.enable_xcam_count(True)
        self.core.xcam_count = 0
        super().on_transition()
