import cv2
import numpy as np
import time

from autosplit64.core.constants import FADEIN_COMPLETE, FADEIN_PARTIAL, FADEOUT_COMPLETE, FADEOUT_PARTIAL, XCAM_REGION

from autosplit64.core.image_utils import is_black
from autosplit64.core.processing import Process


class ProcessXCam(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("FADEOUT")
        self.register_signal("FADEIN")

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        #if self.core.fade_status in (FADEIN_PARTIAL, FADEIN_COMPLETE):
            #return self.signals["FADEIN"]

        if self.core.incoming_split():
            if self.core.xcam_count == 0 and self.core.in_xcam and self.core.current_time - self.core.collection_time < 1:
                self.core.split()
            elif self.core.xcam_count == self.core.current_split().on_xcam:
                self.core.xcam_count = 0
                self.core.split()

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 29.97
        self.core.enable_predictions(True)
        self.core.enable_xcam_count(True)

        super().on_transition()


class ProcessXCamStartUpSegment(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("FADEOUT")
        self.register_signal("START")
        self.lower_bound = [0, 0, 50]
        self.upper_bound = [30, 40, 200]

        self._predictions = True

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if self.core.fadeout_count == 1:
            self.core.fps = 29.97
            self.core.enable_predictions(not self._predictions)
            xcam = self.core.get_region(XCAM_REGION)
            lower = np.array(self.lower_bound, dtype="uint8")
            upper = np.array(self.upper_bound, dtype="uint8")

            mask = cv2.inRange(xcam, lower, upper)
            output = cv2.bitwise_and(xcam, xcam, mask=mask)

            if not is_black(output, 0.1, 0.7):
                self.core.split()
                self.core.fps = 10
                self.core.fadeout_count = 0
                self.core.set_in_game(True)
                return self.signals["START"]

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 10
        self.core.enable_predictions(True)

        super().on_transition()
