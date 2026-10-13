import logging
import time

import cv2
import numpy as np

from autosplit64.core.constants import FADEOUT_COMPLETE, FADEOUT_PARTIAL, NO_HUD_REGION

from autosplit64.core import config
from autosplit64.core.image_utils import is_black
from autosplit64.core.processing import Process, Signal

# What split detection does and why, in the session log
log = logging.getLogger("detection")

# _star_visible's threshold for any yellow at all, rather than the Grand Star
NO_YELLOW_THRESHOLD = 0.9999


class ProcessFindFinalStage(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("ENTERED")
        self.register_signal("FADEOUT")
        self.bowser_lower_bound = config.get("split_final_star", "stage_lower_bound")
        self.bowser_upper_bound = config.get("split_final_star", "stage_upper_bound")

    def execute(self):
        no_hud = self.core.get_region(NO_HUD_REGION)

        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        lower = np.array(self.bowser_lower_bound, dtype="uint8")
        upper = np.array(self.bowser_upper_bound, dtype="uint8")

        star_mask = cv2.inRange(no_hud, lower, upper)
        output = cv2.bitwise_and(no_hud, no_hud, mask=star_mask)

        if not is_black(output, 0.1, 0.9):
            return self.signals["ENTERED"]
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 10
        self.core.enable_xcam_count(False)
        super().on_transition()


class ProcessFindFinalStar(Process):
    # How long the Grand Star shows before it counts as spawned. It shows for about 7.5 s before Mario can grab it,
    # while other yellow in the fight, like explosions, Bowser and the close-up of Mario after the last hit, shows
    # for under 2 s at a time.
    SPAWN_SECONDS = 4

    def __init__(self, core):
        super().__init__(core)
        self.register_signal("SPAWNED")
        self.register_signal("FADEOUT")
        # When the yellow that may be the Grand Star showed, or None
        self._seen_since = None

        self.star_lower_bound = config.get("split_final_star", "star_lower_bound")
        self.star_upper_bound = config.get("split_final_star", "star_upper_bound")

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]
        if self.loop_time() <= 20:
            return self.signals["LOOP"]

        if self._seen_since is None:
            if self._star_visible():
                log.info("Grand Star seen")
                self._seen_since = time.time()
        # Only a frame without any yellow ends it, so the star moving past the top of the region doesn't
        elif not self._star_visible(NO_YELLOW_THRESHOLD):
            log.info("Grand Star gone after %.2f s", time.time() - self._seen_since)
            self._seen_since = None
        elif time.time() - self._seen_since >= self.SPAWN_SECONDS:
            log.info("Grand Star spawned")
            return self.signals["SPAWNED"]

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 29.97
        self._seen_since = None

        super().on_transition()

    def _star_visible(self, threshold=0.999):
        no_hud = self.core.get_region(NO_HUD_REGION)

        lower = np.array(self.star_lower_bound, dtype="uint8")
        upper = np.array(self.star_upper_bound, dtype="uint8")

        star_mask = cv2.inRange(no_hud, lower, upper)
        output = cv2.bitwise_and(no_hud, no_hud, mask=star_mask)

        return not is_black(output, 0.1, threshold)


class ProcessFinalStarSplit(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("COMPLETE")
        self.register_signal("FADEOUT")
        self.star_lower_bound = config.get("split_final_star", "star_lower_bound")
        self.star_upper_bound = config.get("split_final_star", "star_upper_bound")

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        # Grabbing the Grand Star leaves no yellow, while it moving past the top of the region leaves its sparkles
        if not self._star_visible(NO_YELLOW_THRESHOLD):
            self.core.split()
            log.info("Grand Star grabbed")
            return self.signals["COMPLETE"]

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 29.97

        super().on_transition()

    def _star_visible(self, threshold=0.999):
        no_hud = self.core.get_region(NO_HUD_REGION)

        lower = np.array(self.star_lower_bound, dtype="uint8")
        upper = np.array(self.star_upper_bound, dtype="uint8")

        star_mask = cv2.inRange(no_hud, lower, upper)
        output = cv2.bitwise_and(no_hud, no_hud, mask=star_mask)

        return not is_black(output, 0.1, threshold)
