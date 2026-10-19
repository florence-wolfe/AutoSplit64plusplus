import unittest

import numpy as np

from autosplit64.core import perception
from autosplit64.core.constants import FADEIN_REGION, LIFE_REGION, RESET_REGION, STAR_REGION

BLACK, WHITE, GAME = 0, 255, 120


class Capture:
    """ A capture whose regions are each one level, the game's unless given """

    def __init__(self, **levels):
        self._levels = {STAR_REGION: GAME, LIFE_REGION: GAME, RESET_REGION: GAME, FADEIN_REGION: GAME}
        self._levels.update({globals()[name]: level for name, level in levels.items()})

    def get_region(self, region):
        return np.full((8, 8, 3), self._levels[region], np.uint8)


def fade(capture):
    return perception.fade(capture, 0.1, 0.8)


class FadeTest(unittest.TestCase):
    def test_gameplay_is_no_fade(self):
        self.assertEqual(fade(Capture()), perception.Fade(False, False, False, False))

    def test_the_hud_is_black_only_when_both_its_corners_are(self):
        self.assertTrue(fade(Capture(STAR_REGION=BLACK, LIFE_REGION=BLACK)).hud_black)
        self.assertFalse(fade(Capture(STAR_REGION=BLACK)).hud_black)
        self.assertFalse(fade(Capture(LIFE_REGION=BLACK)).hud_black)

    def test_the_hud_is_white_only_when_both_its_corners_are(self):
        self.assertTrue(fade(Capture(STAR_REGION=WHITE, LIFE_REGION=WHITE)).hud_white)
        self.assertFalse(fade(Capture(STAR_REGION=WHITE)).hud_white)

    def test_the_centre_goes_black_apart_from_the_hud(self):
        # e.g. an iris, which closes on the centre last
        seen = fade(Capture(STAR_REGION=BLACK, LIFE_REGION=BLACK))
        self.assertFalse(seen.centre_black)
        self.assertTrue(fade(Capture(STAR_REGION=BLACK, LIFE_REGION=BLACK, RESET_REGION=BLACK)).centre_black)

    def test_where_a_fade_in_clears_last(self):
        self.assertTrue(fade(Capture(STAR_REGION=WHITE, LIFE_REGION=WHITE, FADEIN_REGION=WHITE)).fadein_white)
        self.assertFalse(fade(Capture(STAR_REGION=WHITE, LIFE_REGION=WHITE)).fadein_white)


if __name__ == "__main__":
    unittest.main()
