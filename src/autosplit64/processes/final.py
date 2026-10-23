import logging
import time

from autosplit64.core.constants import DEFAULT_FRAME_RATE, NO_HUD_REGION

from autosplit64.core import config
from autosplit64.core.image_utils import colour_shown
from autosplit64.core.processing import Process, Signal

# What split detection does and why, in the session log
log = logging.getLogger("detection")


class ProcessFindFinalStage(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("ENTERED")
        self.register_signal("FADEOUT")
        self.bowser_lower_bound = config.get("split_final_star", "stage_lower_bound")
        self.bowser_upper_bound = config.get("split_final_star", "stage_upper_bound")

    def execute(self):
        no_hud = self.core.get_region(NO_HUD_REGION)

        if self.fading_out():
            return self.signals["FADEOUT"]

        if colour_shown(no_hud, self.bowser_lower_bound, self.bowser_upper_bound, 0.9):
            return self.signals["ENTERED"]
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = 10
        self.core.enable_xcam_count(False)
        super().on_transition()


class ProcessFindFinalStar(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("SPAWNED")
        self.register_signal("FADEOUT")
        self._iteration_value = {0: 1, 1: 4, 2: 1}
        self._looping_iteration = 0
        # When to look for the star again, after seeing it
        self._next_look = None

        self.star_lower_bound = config.get("split_final_star", "star_lower_bound")
        self.star_upper_bound = config.get("split_final_star", "star_upper_bound")

    def execute(self):
        # Waiting to look again, it looks at nothing, as it did asleep: the AS64+ and legacy models' final split, which
        # split when they did
        if self._next_look is not None:
            if time.perf_counter() < self._next_look:
                return self.signals["LOOP"]
            self._next_look = None
        if self.fading_out():
            return self.signals["FADEOUT"]
        if self._star_visible() and self.loop_time() > 20:
            if self._looping_iteration == len(self._iteration_value):
                log.info("Grand Star spawned")
                return self.signals["SPAWNED"]
            else:
                log.info("Grand Star seen, iteration %d", self._looping_iteration)
                self._next_look = time.perf_counter() + self._iteration_value[self._looping_iteration]

            self._looping_iteration += 1

            return self.signals["LOOP"]
        else:
            self._looping_iteration = 0

        return self.signals["LOOP"]

    def look_at(self):
        return self._next_look

    def on_transition(self):
        self.core.fps = DEFAULT_FRAME_RATE
        self._looping_iteration = 0
        self._next_look = None

        super().on_transition()

    def _star_visible(self, threshold=0.999):
        return colour_shown(self.core.get_region(NO_HUD_REGION), self.star_lower_bound, self.star_upper_bound, threshold)


class ProcessFinalStarSplit(Process):
    def __init__(self, core):
        super().__init__(core)
        self.register_signal("COMPLETE")
        self.register_signal("FADEOUT")
        self.star_lower_bound = config.get("split_final_star", "star_lower_bound")
        self.star_upper_bound = config.get("split_final_star", "star_upper_bound")

    def execute(self):
        if self.fading_out():
            return self.signals["FADEOUT"]

        if not self._star_visible():
            self.core.split()
            log.info("Grand Star grabbed")
            return self.signals["COMPLETE"]

        return self.signals["LOOP"]

    def on_transition(self):
        self.core.fps = DEFAULT_FRAME_RATE

        super().on_transition()

    def _star_visible(self, threshold=0.999):
        return colour_shown(self.core.get_region(NO_HUD_REGION), self.star_lower_bound, self.star_upper_bound, threshold)
