"""
Split detection over recorded runs (see tests/replay.py), against the runner's own splits: each must happen
within the tenth of a second that the runner's timer shows for it.
"""
import json
import shutil
import tempfile
import unittest

from autosplit64.core import route_loader
from autosplit64.core.constants import SPLIT_NORMAL
from tests.replay import DEFAULTS, ROUNDING, Recording, first_black_centre, generate_reset_templates, replay

NEEDS_VIDEO = "Needs the recording, from: uv run python -m tests.replay"


class _RecordingTest(unittest.TestCase):
    RECORDING = None

    @classmethod
    def setUpClass(cls):
        if cls.RECORDING is None:
            raise unittest.SkipTest("Not a recording")
        if not cls.RECORDING.available():
            raise unittest.SkipTest(NEEDS_VIDEO)
        directory = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, directory)
        cls.templates = generate_reset_templates(cls.RECORDING, directory)

    def assert_split_in_window(self, result, index):
        title, earliest, latest = self.RECORDING.split_windows()[index]
        time = result.split_times().get(index)
        self.assertIsNotNone(time, f"{title} didn't split")
        self.assertTrue(earliest <= time <= latest,
                        f"{title} split at {time:.3f} s, the runner between {earliest:.3f} and {latest:.3f} s")


class _FullRunTest(_RecordingTest):
    """ The whole run, from the console reset, which takes about a minute """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = replay(cls.RECORDING, 0, cls.RECORDING.length(), cls.templates)

    def test_no_errors(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual(self.result.log, [])

    def test_starts_the_timer_on_the_console_reset(self):
        (_, reset, _), (time, start, index) = self.result.run_commands()[:2]
        self.assertEqual((reset, start, index), ("reset", "split", 0))
        earliest, latest = self.RECORDING.start_window()
        self.assertTrue(earliest <= time <= latest, f"Started at {time:.3f} s, the runner between {earliest:.3f} and {latest:.3f} s")

    def test_splits_when_the_runner_did(self):
        for index, (title, _, _) in enumerate(self.RECORDING.split_windows()):
            if title in self.RECORDING.artifacts:
                continue
            with self.subTest(title):
                self.assert_split_in_window(self.result, index)

    def test_recording_artifacts(self):
        # The video isn't the capture split detection had live, so it's no reason to change split detection
        for index, (title, earliest, latest) in enumerate(self.RECORDING.split_windows()):
            if title in self.RECORDING.artifacts:
                with self.subTest(title):
                    time = self.result.split_times().get(index)
                    self.assertFalse(time is not None and earliest <= time <= latest,
                                     f"{title} splits when the runner did now, though: {self.RECORDING.artifacts[title]}")

    def test_fadeout_splits_on_the_first_frame_the_centre_is_black(self):
        # Frame-exact, unlike the runner's timer: at most one look of split detection after the frame
        look = 1 / json.loads(DEFAULTS.read_text())["advanced"]["fadeout_process_frame_rate"]
        times = self.result.split_times()
        for index, split in enumerate(route_loader.load(self.RECORDING.route_path).splits):
            if split.split_type != SPLIT_NORMAL:
                continue
            with self.subTest(split.title):
                time = times[index]
                # Looking a second back also finds a frame the split should have happened on before
                black = first_black_centre(self.RECORDING, time - 1, time)
                self.assertIsNotNone(black, f"The centre isn't black when {split.title} splits, at {time:.3f} s")
                self.assertLessEqual(time - black, look + ROUNDING,
                                     f"{split.title} split at {time:.3f} s, the centre is black from {black:.3f} s")

    def test_only_splits_after_the_start(self):
        commands = [command for _, command, _ in self.result.run_commands()[2:]]
        self.assertEqual(commands, ["split"] * len(self.RECORDING.splits))


class GreensuigiTest(_FullRunTest):
    """ greensuigi's 16 Star No LBLJ world record, on console """
    RECORDING = Recording.load("greensuigi_16_star")


class NoraSM64Test(_FullRunTest):
    """ NoraSM64's 16 Star No LBLJ, on console, recorded at 60 fps """
    RECORDING = Recording.load("norasm64_16_star")


class MidRunStartTest(_RecordingTest):
    """ Starting split detection during CCM in greensuigi's run, with the timer on that split """

    RECORDING = Recording.load("greensuigi_16_star")
    CCM = 2

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = replay(cls.RECORDING, 300, 362, cls.templates, split_index=cls.CCM)

    def test_splits_ccm(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual([command for _, command, _ in self.result.commands], ["split"])
        self.assert_split_in_window(self.result, self.CCM)


if __name__ == "__main__":
    unittest.main()
