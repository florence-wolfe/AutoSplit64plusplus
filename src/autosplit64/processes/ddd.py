import cv2
import numpy as np

from autosplit64 import core

from autosplit64.core import config
from autosplit64.core.image_utils import is_black
from autosplit64.core.processing import Process, Signal


class ProcessFindDDDPortal(Process):
    def __init__(self,):
        super().__init__()
        self.register_signal("FOUND")
        self.register_signal("FADEOUT")
        self.portal_lower_bound = config.get("split_ddd_enter", "portal_lower_bound")
        self.portal_upper_bound = config.get("split_ddd_enter", "portal_upper_bound")

    def execute(self):
        no_hud = core.get_region(core.GAME_REGION)

        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        lower = np.array(self.portal_lower_bound, dtype="uint8")
        upper = np.array(self.portal_upper_bound, dtype="uint8")

        portal_mask = cv2.inRange(no_hud, lower, upper)
        output = cv2.bitwise_and(no_hud, no_hud, mask=portal_mask)

        if not is_black(output, 0.1, 0.99):
            return self.signals["FOUND"]
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        core.fps = 10
        core.enable_xcam_count(False)
        super().on_transition()


class ProcessDDDSplit(Process):
    # Mario entered the painting once his hat is gone for this many frames in a row. While he runs to the
    # painting, small against it, his hat can go unfound for a frame.
    FRAMES_WITHOUT_HAT = 2

    def __init__(self,):
        super().__init__()
        self.register_signal("ENTERED")
        self.register_signal("FADEOUT")
        self.lower_bound = np.array(config.get("split_ddd_enter", "hat_lower_bound"), dtype="uint8")
        self.upper_bound = np.array(config.get("split_ddd_enter", "hat_upper_bound"), dtype="uint8")
        self._frames_without_hat = 0

    def execute(self):
        no_hud = core.get_region(core.NO_HUD_REGION)

        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if cv2.inRange(no_hud, self.lower_bound, self.upper_bound).any():
            self._frames_without_hat = 0
            return self.signals["LOOP"]

        self._frames_without_hat += 1
        if self._frames_without_hat < self.FRAMES_WITHOUT_HAT:
            return self.signals["LOOP"]
        core.split()
        return self.signals["ENTERED"]

    def on_transition(self):
        core.fps = 29.97
        self._frames_without_hat = 0
        super().on_transition()


class ProcessDDDSplitX(Process):
    def __init__(self,):
        super().__init__()
        self.register_signal("ENTERED")
        self.register_signal("FADEOUT")

    def execute(self):
        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if core.xcam_count == 1:
            core.split()
            return self.signals["ENTERED"]
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        core.fps = 29.97
        core.enable_xcam_count(True)
        core.xcam_count = 0
        super().on_transition()
