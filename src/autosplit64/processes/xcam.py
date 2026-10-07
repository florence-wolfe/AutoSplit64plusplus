import cv2
import numpy as np
import time

from autosplit64 import core

from autosplit64.core.image_utils import is_black
from autosplit64.core.processing import Process


class ProcessXCam(Process):
    def __init__(self,):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("FADEIN")

    def execute(self):
        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        #if core.fade_status in (core.FADEIN_PARTIAL, core.FADEIN_COMPLETE):
            #return self.signals["FADEIN"]

        if core.incoming_split():
            if core.xcam_count == 0 and core.in_xcam and core.current_time - core.collection_time < 1:
                core.split()
            elif core.xcam_count == core.current_split().on_xcam:
                core.xcam_count = 0
                core.split()

        return self.signals["LOOP"]

    def on_transition(self):
        core.fps = 29.97
        core.enable_predictions(True)
        core.enable_xcam_count(True)

        super().on_transition()


class ProcessXCamStartUpSegment(Process):
    def __init__(self,):
        super().__init__()
        self.register_signal("FADEOUT")
        self.register_signal("START")
        self.lower_bound = [0, 0, 50]
        self.upper_bound = [30, 40, 200]

        self._predictions = True

    def execute(self):
        if core.fade_status in (core.FADEOUT_PARTIAL, core.FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if core.fadeout_count == 1:
            core.fps = 29.97
            core.enable_predictions(not self._predictions)
            xcam = core.get_region(core.XCAM_REGION)
            lower = np.array(self.lower_bound, dtype="uint8")
            upper = np.array(self.upper_bound, dtype="uint8")

            mask = cv2.inRange(xcam, lower, upper)
            output = cv2.bitwise_and(xcam, xcam, mask=mask)

            if not is_black(output, 0.1, 0.7):
                core.split()
                core.fps = 10
                core.fadeout_count = 0
                core.set_in_game(True)
                return self.signals["START"]

        return self.signals["LOOP"]

    def on_transition(self):
        core.fps = 10
        core.enable_predictions(True)

        super().on_transition()
