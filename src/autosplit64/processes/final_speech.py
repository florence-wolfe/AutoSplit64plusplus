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
from autosplit64.core.image_utils import colour_shown
from autosplit64.core.processing import Process

# What split detection does and why, in the session log
log = logging.getLogger("detection")

# Where Bowser's speech box always is, as fractions of the game: x, y, width and height
SPEECH_BOX = (0.09, 0.15, 0.39, 0.33)
# How much brighter than most of it its text is: white on emulators, grey on some consoles' captures
SPEECH_CONTRAST = 60
# How much of it is text while it shows: 7 to 18%
SPEECH_TEXT = (0.04, 0.2)
# How much of its columns and rows have text while it shows, as the lines span it, which smoke and explosions don't
SPEECH_SPREAD = (0.6, 0.4)
# How bright the rest of it is at most while it shows, as it dims what's behind it by half: 12 to 50 for the last speech
# over the dark and the pink sky
SPEECH_BACKGROUND = 55
# Yellow in more of the region than this is the Grand Star, once Bowser spoke
STAR_THRESHOLD = 0.999
# Yellow in no more of the region than this is none
NO_YELLOW_THRESHOLD = 0.9999
# Mario grabbed the Grand Star when the region's yellow drops to less than this share of what it was the look before,
# and to less of it than GRAB_YELLOW: the star is 0.05 to 6% of the region, and Mario's buttons after the grab up to
# 0.06%, close behind him, which no frame of the star's ever dropped to at once
GRAB_DROP = 0.25
GRAB_YELLOW = 0.001


def speech_shown(game):
    """ Whether game, the game's picture, shows a speech box: lines of light text on a see-through black box """
    height, width = game.shape[:2]
    x, y, box_width, box_height = SPEECH_BOX
    box = cv2.cvtColor(game[int(height * y):int(height * (y + box_height)), int(width * x):int(width * (x + box_width))],
                       cv2.COLOR_BGR2HSV)
    value = box[:, :, 2]
    text = (value > np.median(value) + SPEECH_CONTRAST) & (box[:, :, 1] < 70)
    return (SPEECH_TEXT[0] <= text.mean() <= SPEECH_TEXT[1] and value[~text].mean() <= SPEECH_BACKGROUND
            and text.any(axis=0).mean() >= SPEECH_SPREAD[0] and text.any(axis=1).mean() >= SPEECH_SPREAD[1])


def _star_bounds():
    """ The Grand Star's yellow, from lower to upper """
    return config.get("split_final_star", "star_lower_bound"), config.get("split_final_star", "star_upper_bound")


def star_visible(core, threshold):
    """ Whether there's Grand Star yellow in more of the region than threshold allows """
    return colour_shown(core.get_region(NO_HUD_REGION), *_star_bounds(), threshold)


def star_yellow(core):
    """ How much of the region is Grand Star yellow """
    lower, upper = _star_bounds()
    star_mask = cv2.inRange(core.get_region(NO_HUD_REGION), np.array(lower, dtype="uint8"), np.array(upper, dtype="uint8"))
    return cv2.countNonZero(star_mask) / star_mask.size


class ProcessFindBowserSpeech(Process):
    """ Bowser speaks after his last hit, just before the Grand Star appears, and before the fight, which doesn't count """
    # How long it shows at least, to tell it from a frame or two that looks like it: over 0.9 s, even when skipped
    SPEECH_SECONDS = 0.2
    # How long after the arena shows a speech is the last one: the one before the fight shows 4.5 to 6 s after, the last
    # 29 s and more after
    ARENA_SECONDS = 15

    def __init__(self, core):
        super().__init__(core)
        self.register_signal("SPOKEN")
        self.register_signal("FADEOUT")
        # When the speech box showed, or None
        self._shown_since = None

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        if self.loop_time() < self.ARENA_SECONDS or not speech_shown(self.core.get_region(GAME_REGION)):
            self._shown_since = None
        elif self._shown_since is None:
            self._shown_since = time.perf_counter()
        elif time.perf_counter() - self._shown_since >= self.SPEECH_SECONDS:
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
                self._seen_since = time.perf_counter()
        # Only a frame without any yellow ends it, so the star moving past the top of the region doesn't
        elif not star_visible(self.core, NO_YELLOW_THRESHOLD):
            log.info("Grand Star gone after %.2f s", time.perf_counter() - self._seen_since)
            self._seen_since = None
        elif time.perf_counter() - self._seen_since >= self.SPAWN_SECONDS:
            log.info("Grand Star spawned")
            return self.signals["SPAWNED"]

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 29.97
        self._seen_since = None
        super().on_transition()


class ProcessGrandStarSplit(Process):
    """
    Splits once Mario grabbed the Grand Star, on the first frame without it: where its yellow drops at once, or none is
    left, for when it was already gone at the first look
    """

    def __init__(self, core):
        super().__init__(core)
        self.register_signal("COMPLETE")
        self.register_signal("FADEOUT")
        # How much of the region was yellow at the last look, or None
        self._yellow = None

    def execute(self):
        if self.core.fade_status in (FADEOUT_PARTIAL, FADEOUT_COMPLETE):
            return self.signals["FADEOUT"]

        yellow = star_yellow(self.core)
        dropped = self._yellow is not None and yellow < GRAB_YELLOW and yellow < self._yellow * GRAB_DROP
        if dropped or not star_visible(self.core, NO_YELLOW_THRESHOLD):
            self.core.split()
            log.info("Grand Star grabbed, yellow %.3f%% -> %.3f%%", 100 * (self._yellow or 0), 100 * yellow)
            return self.signals["COMPLETE"]
        self._yellow = yellow

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 29.97
        self._yellow = None
        super().on_transition()
