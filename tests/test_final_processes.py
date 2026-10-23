""" Behavior of the final split's processes in processes/final.py, with split detection stubbed """
import unittest
from unittest import mock

from autosplit64.core.constants import FADEOUT_PARTIAL
from autosplit64.processes import final
from tests.processes import SETTINGS, ClockTestCase

FINAL_SETTINGS = {("split_final_star", "star_lower_bound"): [0, 0, 0], ("split_final_star", "star_upper_bound"): [0, 0, 0]}


class FindFinalStarTest(ClockTestCase):
    """ ProcessFindFinalStar: the Grand Star seen again 1, 4 and 1 s apart is spawned, timed without sleeping """

    def setUp(self):
        patcher = mock.patch.dict(SETTINGS, FINAL_SETTINGS)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        patcher = mock.patch.object(final.time, "sleep", side_effect=AssertionError("slept, leaving frames unseen"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.process = final.ProcessFindFinalStar(self.detection)
        self.process.on_transition()
        self.visible = True
        self.process._star_visible = lambda: self.visible
        # It looks for the star from 20 s after it starts
        self.now += 21

    def at(self, seconds):
        self.now = self.start + 21 + seconds
        return self.signal(self.process.execute())

    def test_spawned_once_seen_after_each_wait(self):
        self.assertEqual(self.at(0), "LOOP")
        self.assertEqual(self.process.look_at(), self.now + 1)
        # Not looked for again until then
        self.visible = False
        self.assertEqual(self.at(0.5), "LOOP")
        self.visible = True
        self.assertEqual(self.at(1), "LOOP")
        self.assertEqual(self.process.look_at(), self.now + 4)
        self.assertEqual(self.at(5), "LOOP")
        self.assertEqual(self.at(6), "SPAWNED")

    def test_gone_after_a_wait_starts_again(self):
        self.at(0)
        self.visible = False
        self.at(1)
        self.assertIsNone(self.process.look_at())
        self.visible = True
        self.at(1.1)
        self.assertEqual(self.process.look_at(), self.now + 1)

    def test_nothing_while_it_waits(self):
        # Not even a fadeout, as it did asleep, for the AS64+ and legacy models, which this final split is for
        self.at(0)
        self.detection.fade_status = FADEOUT_PARTIAL
        self.assertEqual(self.at(0.5), "LOOP")
        self.assertEqual(self.at(1), "FADEOUT")


if __name__ == "__main__":
    unittest.main()
