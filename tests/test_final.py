""" Behavior of the Grand Star processes in processes/final.py, with split detection and the clock stubbed """
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from autosplit64.core import config
from autosplit64.core.constants import NO_FADE
from autosplit64.processes.final import ProcessFinalStarSplit, ProcessFindFinalStar

SETTINGS = {
    ("split_final_star", "star_lower_bound"): [0, 180, 180],
    ("split_final_star", "star_upper_bound"): [120, 255, 255],
}
FPS = 29.97

# The region without the HUD (BGR): nothing yellow, the Grand Star, or only a few yellow pixels, like its
# sparkles once the star itself moves past the top of the region
NOTHING = np.zeros((100, 100, 3), np.uint8)
STAR = NOTHING.copy()
STAR[40:60, 40:60] = (0, 230, 250)
SPARKLES = NOTHING.copy()
SPARKLES[10, 10:15] = (0, 230, 250)


class _FinalTestCase(unittest.TestCase):
    PROCESS = None

    def setUp(self):
        self.now = 1_700_000_000.0
        self.detection = SimpleNamespace(split=mock.Mock(), fade_status=NO_FADE, get_region=mock.Mock(), fps=0,
                                         enable_xcam_count=mock.Mock())
        for patcher in (mock.patch.object(config, "get", side_effect=lambda section, key=None: SETTINGS[(section, key)]),
                        mock.patch("time.time", lambda: self.now),
                        mock.patch("time.sleep", self.sleep)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.process = self.PROCESS(self.detection)
        self.process.on_transition()

    def sleep(self, seconds):
        self.now += seconds

    def run_frames(self, frame_at, seconds):
        """ Runs the process on every frame for up to `seconds`, showing frame_at(seconds since the start), until it
        signals other than LOOP, like the processor moves on then. Returns (the signal, seconds since the start), or
        None. """
        names = {signal: name for name, signal in self.process.signals.items()}
        start = self.now
        while self.now - start < seconds:
            self.detection.get_region.return_value = frame_at(self.now - start)
            name = names[self.process.execute()]
            if name != "LOOP":
                return name, self.now - start
            self.now += 1 / FPS
        return None


class FindFinalStarTest(_FinalTestCase):
    PROCESS = ProcessFindFinalStar

    def setUp(self):
        super().setUp()
        # Past the first 20 s of the fight, before which nothing counts
        self.now += 21

    def test_spawned_on_the_frame_4_s_after_the_star_shows(self):
        signal = self.run_frames(lambda t: NOTHING if t < 1 else STAR, 6)
        self.assertEqual(signal[0], "SPAWNED")
        self.assertAlmostEqual(signal[1], 5, delta=1 / FPS + 0.01)

    def test_yellow_that_comes_and_goes_isnt_the_star(self):
        # Like the last explosion, the close-up of Mario and Bowser after the last hit, ~15 s before the Grand Star
        # can be grabbed. Seen at enough instants, they took the star for spawned and split once they were gone.
        self.assertEqual(self.run_frames(lambda t: STAR if t % 1 < 0.6 else NOTHING, 10), None)

    def test_the_star_dipping_to_its_sparkles_doesnt_restart_it(self):
        # Like it does at the top of the region for a frame or two
        signal = self.run_frames(lambda t: SPARKLES if 2 <= t < 2.1 else STAR, 5)
        self.assertEqual(signal[0], "SPAWNED")
        self.assertAlmostEqual(signal[1], 4, delta=1 / FPS + 0.01)

    def test_nothing_counts_in_the_first_20_s(self):
        self.now -= 21
        signal = self.run_frames(lambda t: STAR, 26)
        self.assertEqual(signal[0], "SPAWNED")
        self.assertGreaterEqual(signal[1], 24)


class FinalStarSplitTest(_FinalTestCase):
    PROCESS = ProcessFinalStarSplit

    def test_splits_on_the_first_frame_without_yellow(self):
        self.assertEqual(self.run_frames(lambda t: STAR if t < 1 else NOTHING, 2)[0], "COMPLETE")
        self.detection.split.assert_called_once()

    def test_the_star_dipping_to_its_sparkles_doesnt_split(self):
        self.assertEqual(self.run_frames(lambda t: SPARKLES if 1 <= t < 1.1 else STAR, 2), None)
        self.detection.split.assert_not_called()


if __name__ == "__main__":
    unittest.main()
