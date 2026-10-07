import unittest

import numpy as np

from as64core.game_capture import GameCapture


class RegionTest(unittest.TestCase):
    def setUp(self):
        self.capture = GameCapture.__new__(GameCapture)
        self.capture._regions = {"STAR": [1, 2, 3, 4]}
        self.capture._region_images = {}
        self.capture._window_image = np.arange(100 * 100 * 3, dtype=np.uint8).reshape(100, 100, 3)

    def test_region_image_is_cropped_and_cached(self):
        star = self.capture.get_region("STAR")
        np.testing.assert_array_equal(star, self.capture._window_image[2:6, 1:4])
        self.assertIs(self.capture.get_region("STAR"), star)

    def test_unknown_region(self):
        self.assertIsNone(self.capture.get_region("UNKNOWN"))
        self.assertIsNone(self.capture.get_region_rect("UNKNOWN"))

    def test_region_rect(self):
        self.assertEqual(self.capture.get_region_rect("STAR"), [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
