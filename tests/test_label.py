import unittest

from tests import label


class FadeFramesTest(unittest.TestCase):
    def test_a_fade_is_the_first_frame_the_screen_is_all_black(self):
        # Gameplay, a fade over three frames, black, then gameplay again
        fractions = [0.3, 0.32, 0.3, 0.5, 0.8, 0.95, 1.0, 1.0, 1.0, 0.4, 0.3]
        self.assertEqual(label.fade_frames(fractions), [6])

    def test_each_time_the_screen_is_all_black_is_a_fade(self):
        fractions = [0.0, 0.5, 1.0, 1.0, 0.0, 0.0, 0.6, 1.0, 0.0]
        self.assertEqual(label.fade_frames(fractions), [2, 7])

    def test_a_screen_that_is_nearly_all_black_is_not_a_fade(self):
        self.assertEqual(label.fade_frames([0.2, 0.6, 0.9, 0.6, 0.2]), [])

    def test_a_fade_lasts_until_the_screen_is_far_from_all_black(self):
        # e.g. a course's intro, its title on white between the painting's white and the course's
        fractions = [0.3, 1.0, 1.0, 0.97, 0.97, 1.0, 0.3, 1.0]
        self.assertEqual(label.fade_frames(fractions), [1, 7])

    def test_a_video_that_starts_black_starts_with_a_fade(self):
        self.assertEqual(label.fade_frames([1.0, 1.0, 0.3]), [0])


if __name__ == "__main__":
    unittest.main()
