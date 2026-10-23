import unittest

import numpy as np

from autosplit64.core.image_utils import colour_shown

YELLOW, LOWER, UPPER = (0, 255, 255), (0, 200, 200), (80, 255, 255)


def with_yellow(pixels):
    """ A 10x10 grey picture with that many yellow pixels """
    image = np.full((10, 10, 3), 128, np.uint8)
    image.reshape(-1, 3)[:pixels] = YELLOW
    return image


class ColourShownTest(unittest.TestCase):
    def test_colour_shown(self):
        # Only the yellow is kept: 2 of each pixel's 3 channels, 10 of 300 values, isn't black
        self.assertTrue(colour_shown(with_yellow(5), LOWER, UPPER, 0.99))

    def test_too_little_of_it(self):
        self.assertFalse(colour_shown(with_yellow(1), LOWER, UPPER, 0.99))

    def test_none_of_it(self):
        # The grey isn't in the range
        self.assertFalse(colour_shown(with_yellow(0), LOWER, UPPER, 0.5))

    def test_bounds_as_lists(self):
        # As the settings have them
        self.assertTrue(colour_shown(with_yellow(5), list(LOWER), list(UPPER), 0.99))


if __name__ == "__main__":
    unittest.main()
