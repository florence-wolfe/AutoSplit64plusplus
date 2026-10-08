"""
Split detection over recorded runs (see tests/replay.py), against the runner's own splits: each must happen
within the tenth of a second that the runner's timer shows for it.
"""
import shutil
import tempfile
import unittest

from tests.replay import Recording, generate_reset_templates, replay

RECORDING = Recording.load("greensuigi_16_star")
NEEDS_VIDEO = "Needs the recording, from: uv run python -m tests.replay"


def _templates(test_class):
    directory = tempfile.mkdtemp()
    test_class.addClassCleanup(shutil.rmtree, directory)
    return generate_reset_templates(RECORDING, directory)


class _SplitsTest(unittest.TestCase):
    def assert_split_in_window(self, result, index):
        title, earliest, latest = RECORDING.split_windows()[index]
        time = result.split_times().get(index)
        self.assertIsNotNone(time, f"{title} didn't split")
        self.assertTrue(earliest <= time <= latest,
                        f"{title} split at {time:.2f} s, the runner between {earliest:.2f} and {latest:.2f} s")


@unittest.skipUnless(RECORDING.available(), NEEDS_VIDEO)
class FullRunTest(_SplitsTest):
    """ The whole run, from the console reset, which takes a couple of minutes """

    @classmethod
    def setUpClass(cls):
        cls.result = replay(RECORDING, 0, RECORDING.length(), _templates(cls))

    def test_no_errors(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual(self.result.log, [])

    def test_starts_the_timer_on_the_console_reset(self):
        (_, first, _), (time, start, index) = self.result.commands[:2]
        self.assertEqual((first, start, index), ("reset", "split", 0))
        earliest, latest = RECORDING.start_window()
        self.assertTrue(earliest <= time <= latest, f"Started at {time:.2f} s, the runner between {earliest:.2f} and {latest:.2f} s")

    def test_splits_when_the_runner_did(self):
        for index, (title, _, _) in enumerate(RECORDING.split_windows()):
            with self.subTest(title):
                self.assert_split_in_window(self.result, index)

    def test_only_splits_after_the_start(self):
        commands = [command for _, command, _ in self.result.commands[2:]]
        self.assertEqual(commands, ["split"] * len(RECORDING.splits))


@unittest.skipUnless(RECORDING.available(), NEEDS_VIDEO)
class MidRunStartTest(_SplitsTest):
    """ Starting split detection during CCM, with the timer on that split """

    CCM = 2

    @classmethod
    def setUpClass(cls):
        cls.result = replay(RECORDING, 300, 362, _templates(cls), split_index=cls.CCM)

    def test_splits_ccm(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual([command for _, command, _ in self.result.commands], ["split"])
        self.assert_split_in_window(self.result, self.CCM)


if __name__ == "__main__":
    unittest.main()
