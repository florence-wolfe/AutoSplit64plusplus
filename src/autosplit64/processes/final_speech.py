"""
The final split of the AS64++ detection model: the Grand Star is only looked for once Bowser gave his last speech,
as the yellow it's found by also shows in the fight, from Bowser himself and the power meter, for longer than the
star does on some captures. See processes/final.py for the other models'.
"""
import logging
import time

import cv2
import numpy as np

from autosplit64.core import config
from autosplit64.core.constants import FADEOUT_COMPLETE, FADEOUT_PARTIAL, GAME_REGION, NO_HUD_REGION
from autosplit64.core.image_utils import is_black
from autosplit64.core.processing import Process

# What split detection does and why, in the session log
log = logging.getLogger("detection")

# Where Bowser's speech box always is, as fractions of the game: x, y, width and height
SPEECH_BOX = (0.09, 0.15, 0.39, 0.33)
# How much of it is white text while it shows: 5 to 10%
SPEECH_TEXT = (0.04, 0.13)
# How bright the rest of it is at most while it shows, as it dims what's behind it by half: 30 to 51 for the last speech
# over the dark and the pink sky, 60 and more for Bowser's speech before the fight and what else looks like one
SPEECH_BACKGROUND = 55
# Yellow in more of the region than this is the Grand Star, once Bowser spoke
STAR_THRESHOLD = 0.999
# Yellow in no more of the region than this is none
NO_YELLOW_THRESHOLD = 0.9999


def speech_shown(game):
    """ Whether game, the game's picture, shows a speech box: white text on a see-through black box """
    height, width = game.shape[:2]
    x, y, box_width, box_height = SPEECH_BOX
    box = cv2.cvtColor(game[int(height * y):int(height * (y + box_height)), int(width * x):int(width * (x + box_width))],
                       cv2.COLOR_BGR2HSV)
    text = (box[:, :, 2] > 180) & (box[:, :, 1] < 70)
    return SPEECH_TEXT[0] <= text.mean() <= SPEECH_TEXT[1] and box[:, :, 2][~text].mean() <= SPEECH_BACKGROUND


def star_visible(core, threshold):
    """ Whether there's Grand Star yellow in more of the region than threshold allows """
    no_hud = core.get_region(NO_HUD_REGION)
    lower = np.array(config.get("split_final_star", "star_lower_bound"), dtype="uint8")
    upper = np.array(config.get("split_final_star", "star_upper_bound"), dtype="uint8")
    star_mask = cv2.inRange(no_hud, lower, upper)
    return not is_black(cv2.bitwise_and(no_hud, no_hud, mask=star_mask), 0.1, threshold)


class ProcessFindBowserSpeech(Process):
    """ Bowser speaks once, after his last hit, just before the Grand Star appears """
    # How long it shows at least, to tell it from a frame or two that looks like it: over 0.9 s, even when skipped
    SPEECH_SECONDS = 0.2

    def __init__(self, core):
        super().__init__(core)
        self.register_signal("SPOKEN")
        self.register_signal("FADEOUT")
        # When the speech box showed, or None
        self._shown_since = None

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if not speech_shown(self.core.get_region(GAME_REGION)):
            self._shown_since = None
        elif self._shown_since is None:
            self._shown_since = time.time()
        elif time.time() - self._shown_since >= self.SPEECH_SECONDS:
            log.info("Bowser's last speech")
            return self.signals["SPOKEN"]

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 29.97
        self._shown_since = None
        super().on_transition()


class ProcessFindGrandStar(Process):
    # How long the Grand Star shows before it counts as spawned. It shows for about 7.5 s before Mario can grab it,
    # while what else is yellow after Bowser's speech, as he disappears, is gone sooner.
    SPAWN_SECONDS = 4

    def __init__(self, core):
        super().__init__(core)
        self.register_signal("SPAWNED")
        self.register_signal("FADEOUT")
        # When the yellow that may be the Grand Star showed, or None
        self._seen_since = None

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if self._seen_since is None:
            if star_visible(self.core, STAR_THRESHOLD):
                log.info("Grand Star seen")
                self._seen_since = time.time()
        # Only a frame without any yellow ends it, so the star moving past the top of the region doesn't
        elif not star_visible(self.core, NO_YELLOW_THRESHOLD):
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


class ProcessGrandStarSplit(Process):
    """ Splits once Mario grabbed the Grand Star, on the first frame without it """

    def __init__(self, core):
        super().__init__(core)
        self.register_signal("COMPLETE")
        self.register_signal("FADEOUT")

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if not star_visible(self.core, NO_YELLOW_THRESHOLD):
            self.core.split()
            log.info("Grand Star grabbed")
            return self.signals["COMPLETE"]

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 29.97
        super().on_transition()
