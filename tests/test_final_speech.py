""" Behavior of the AS64++ final split's processes in processes/final_speech.py, with split detection stubbed """
import unittest
from unittest import mock

import numpy as np

from autosplit64.core.constants import FADEOUT_PARTIAL, GAME_REGION, NO_HUD_REGION
from autosplit64.processes import final_speech
from tests.processes import SETTINGS, ClockTestCase

# Grand Star yellow, in BGR
YELLOW = (0, 255, 255)
STAR_SETTINGS = {("split_final_star", "star_lower_bound"): [0, 200, 200],
                 ("split_final_star", "star_upper_bound"): [80, 255, 255]}


def game(speech=False, blob=False):
    """ The game's picture, dark, with Bowser's speech box showing, or one bright patch in its place like an explosion """
    image = np.full((300, 400, 3), 30, np.uint8)
    x, y, width, height = final_speech.SPEECH_BOX
    box = image[int(300 * y):int(300 * (y + height)), int(400 * x):int(400 * (x + width))]
    if speech:
        # Lines of white letters, spread over the box
        rows, columns = np.indices(box.shape[:2])
        box[(rows % 8 < 4) & ((rows + columns) % 5 == 0)] = 255
    if blob:
        box[20:60, 20:60] = 255
    return image


def no_hud(yellow_pixels):
    """ The region the Grand Star is looked for in, with that many pixels of its yellow """
    image = np.zeros((100, 200, 3), np.uint8)
    image.reshape(-1, 3)[:yellow_pixels] = YELLOW
    return image


class FinalSpeechTestCase(ClockTestCase):
    PROCESS = None

    def setUp(self):
        patcher = mock.patch.dict(SETTINGS, STAR_SETTINGS)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.game, self.no_hud = game(), no_hud(0)
        self.detection.get_region = lambda region: {GAME_REGION: self.game, NO_HUD_REGION: self.no_hud}[region]
        self.process = self.PROCESS(self.detection)
        self.process.on_transition()

    def at(self, seconds):
        self.now = self.start + seconds
        return self.signal(self.process.execute())


class SpeechShownTest(unittest.TestCase):
    def test_speech_box(self):
        self.assertTrue(final_speech.speech_shown(game(speech=True)))

    def test_no_speech_box(self):
        self.assertFalse(final_speech.speech_shown(game()))

    def test_a_bright_patch_isnt_one(self):
        # As much of the box is bright as with text, but in one place, like smoke or an explosion
        self.assertFalse(final_speech.speech_shown(game(blob=True)))


class FindBowserSpeechTest(FinalSpeechTestCase):
    """ ProcessFindBowserSpeech: the speech box shown for 0.2 s, 15 s after the arena shows, is the last speech """
    PROCESS = final_speech.ProcessFindBowserSpeech

    def test_last_speech(self):
        self.game = game(speech=True)
        self.assertEqual(self.at(20), "LOOP")
        self.assertEqual(self.at(20.1), "LOOP")
        self.assertEqual(self.at(20.2), "SPOKEN")

    def test_speech_before_the_fight_doesnt_count(self):
        self.game = game(speech=True)
        for seconds in (5, 5.5, 6):
            self.assertEqual(self.at(seconds), "LOOP")

    def test_a_frame_without_it_starts_again(self):
        self.game = game(speech=True)
        self.at(20)
        self.game = game()
        self.at(20.1)
        self.game = game(speech=True)
        self.assertEqual(self.at(20.2), "LOOP")
        self.assertEqual(self.at(20.5), "SPOKEN")

    def test_fadeout(self):
        self.detection.fade_status = FADEOUT_PARTIAL
        self.assertEqual(self.at(20), "FADEOUT")


class FindGrandStarTest(FinalSpeechTestCase):
    """ ProcessFindGrandStar: its yellow showing for 4 s is the Grand Star spawned """
    PROCESS = final_speech.ProcessFindGrandStar

    def test_spawned(self):
        self.no_hud = no_hud(1000)
        self.assertEqual(self.at(0), "LOOP")
        self.assertEqual(self.at(3.9), "LOOP")
        self.assertEqual(self.at(4), "SPAWNED")

    def test_no_yellow_starts_again(self):
        self.no_hud = no_hud(1000)
        self.at(0)
        self.no_hud = no_hud(0)
        self.at(2)
        self.no_hud = no_hud(1000)
        self.at(3)
        self.assertEqual(self.at(6.9), "LOOP")
        self.assertEqual(self.at(7), "SPAWNED")

    def test_a_little_yellow_keeps_it(self):
        # Like the star moving past the top of the region
        self.no_hud = no_hud(1000)
        self.at(0)
        self.no_hud = no_hud(5)
        self.assertEqual(self.at(4), "SPAWNED")


class GrandStarSplitTest(FinalSpeechTestCase):
    """ ProcessGrandStarSplit: splits on the first frame the Grand Star's yellow drops, as Mario grabbed it """
    PROCESS = final_speech.ProcessGrandStarSplit

    def test_split_when_the_yellow_drops(self):
        self.no_hud = no_hud(1000)
        self.assertEqual(self.at(0), "LOOP")
        # Mario's buttons, close behind him
        self.no_hud = no_hud(10)
        self.assertEqual(self.at(0.1), "COMPLETE")
        self.assertEqual(self.names(), ["split"])

    def test_no_split_while_it_shows(self):
        for seconds, pixels in enumerate((1000, 600, 1200, 300)):
            self.no_hud = no_hud(pixels)
            self.assertEqual(self.at(seconds / 10), "LOOP")
        self.assertEqual(self.names(), [])

    def test_little_yellow_dropping_less_isnt_the_grab(self):
        self.no_hud = no_hud(15)
        self.at(0)
        self.no_hud = no_hud(10)
        self.assertEqual(self.at(0.1), "LOOP")

    def test_split_at_once_when_already_gone(self):
        self.assertEqual(self.at(0), "COMPLETE")
        self.assertEqual(self.names(), ["split"])

    def test_fadeout(self):
        self.detection.fade_status = FADEOUT_PARTIAL
        self.assertEqual(self.at(0), "FADEOUT")
        self.assertEqual(self.names(), [])


if __name__ == "__main__":
    unittest.main()
