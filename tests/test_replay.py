"""
Split detection over recorded runs (see tests/replay.py), against the runner's own splits: each must happen
within the tenth of a second that the runner's timer shows for it.
"""
import difflib
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from autosplit64.core import detection_model, route_loader
from autosplit64.core.constants import SPLIT_NORMAL
from tests.replay import DEFAULT, DEFAULTS, ROUNDING, Recording, Variant, first_black_centre, generate_reset_templates, replay

NEEDS_VIDEO = "Needs the recording, from: uv run python -m tests.replay"
# What split detection did over each recording, which a change to it must not change unless it means to
TRACES = Path(__file__).parent / "recordings" / "traces"
# Writes the traces instead of checking them, after a change that means to change them
UPDATE_TRACES = os.environ.get("UPDATE_TRACES") == "1"


def variants(recording):
    """ Other settings and routes to replay a recording with, besides the default """
    return [
        Variant("fade-ins", route_file=f"{recording}_fade_ins.as64"),
        # How a run starts: the first 150 s of the video
        Variant("file-select", route={"timing": "File Select"}, length=150),
        Variant("up-rta", route={"timing": "Up RTA"}, length=150),
        Variant("srl-mode", settings={("general", "srl_mode"): True}, length=150),
        # Which looks at frames between looks too
        Variant("as64pp", settings={("model", "detection"): detection_model.AS64PP}),
    ]


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

    def assert_same_trace(self, variant, trace):
        path = TRACES / f"{self.RECORDING.name}.{variant.name}.txt"
        text = "\n".join(trace) + "\n"
        if UPDATE_TRACES:
            path.parent.mkdir(exist_ok=True)
            path.write_text(text)
            return
        self.assertTrue(path.exists(), f"No trace of {path.name} yet, which UPDATE_TRACES=1 writes")
        expected = path.read_text()
        if text != expected:
            diff = "".join(difflib.unified_diff(expected.splitlines(True), text.splitlines(True), "expected", "replayed", n=1))
            self.fail(f"Split detection does something else over {path.name} than before. If it means to, "
                      f"rerun with UPDATE_TRACES=1 and check the change:\n{diff[:5000]}")

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

    def test_same_trace(self):
        self.assert_same_trace(DEFAULT, self.result.trace)

    def test_starts_the_timer_on_the_console_reset(self):
        (_, reset, _), (time, start, index) = self.result.run_commands()[:2]
        self.assertEqual((reset, start, index), ("reset", "split", 0))
        earliest, latest = self.RECORDING.start_window()
        self.assertTrue(earliest <= time <= latest, f"Started at {time:.3f} s, the runner between {earliest:.3f} and {latest:.3f} s")

    def test_default_templates_start_the_timer_on_the_console_reset(self):
        # The SM64 logo only matches them for two frames: even seeing every other frame, detection must see one.
        # Within a frame of the runner's start, as the logo frames show for a frame or two.
        advanced = json.loads(DEFAULTS.read_text())["advanced"]
        templates = [DEFAULTS.parent / advanced["reset_frame_one"], DEFAULTS.parent / advanced["reset_frame_two"]]
        earliest, latest = self.RECORDING.start_window()
        for fps in (29.97, 15):
            # Where detection's frames fall between the video's
            for phase in range(3):
                with self.subTest(fps=fps, phase=phase):
                    variant = Variant("default-templates", settings={("advanced", "fadeout_process_frame_rate"): fps})
                    result = replay(self.RECORDING, phase / 90, latest + 1, templates, variant=variant)
                    starts = [time for time, command, index in result.commands if command == "split" and index == 0]
                    self.assertTrue(starts and earliest - 1 / 30 <= starts[-1] <= latest,
                                    f"Started at {starts}, the runner between {earliest:.3f} and {latest:.3f} s")

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


class _VariantTest(_RecordingTest):
    """ A recording replayed with a variant, against its trace """
    VARIANT = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = replay(cls.RECORDING, 0, cls.VARIANT.length or cls.RECORDING.length(), cls.templates, variant=cls.VARIANT)

    def test_no_errors(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual(self.result.log, [])

    def test_same_trace(self):
        self.assert_same_trace(self.VARIANT, self.result.trace)


# A test class for each recording and variant, e.g. GreensuigiTest_fade_ins
for _recording_test in (GreensuigiTest, NoraSM64Test):
    for _variant in variants(_recording_test.RECORDING.name):
        _name = f"{_recording_test.__name__}_{_variant.name.replace('-', '_')}"
        globals()[_name] = type(_name, (_VariantTest,), {"RECORDING": _recording_test.RECORDING, "VARIANT": _variant})


class GreensuigiTest_x_cam_mode(_VariantTest):
    """ The other operation mode, which counts stars differently, over the whole run """
    RECORDING = GreensuigiTest.RECORDING
    VARIANT = Variant("x-cam-mode", settings={("general", "operation_mode"): 1})


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


# The detection model that waits for Bowser's last speech before it looks for the Grand Star
AS64PP = Variant("as64pp", settings={("model", "detection"): detection_model.AS64PP})


class _As64ppBitsTest(_RecordingTest):
    """ AS64++'s final split over the recording, from the split before """
    BITS = 11

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start = cls.RECORDING.split_windows()[cls.BITS - 1][2]
        cls.result = replay(cls.RECORDING, start, cls.RECORDING.length(), cls.templates, split_index=cls.BITS, variant=AS64PP)

    def test_splits_when_the_runner_did(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual([command for _, command, _ in self.result.commands], ["split"])
        self.assert_split_in_window(self.result, self.BITS)

    def test_after_bowsers_last_speech(self):
        self.assertEqual(len([line for line in self.result.trace if "Bowser's last speech" in line]), 1)


class GreensuigiAs64ppBitsTest(_As64ppBitsTest):
    RECORDING = GreensuigiTest.RECORDING


class NoraSM64As64ppBitsTest(_As64ppBitsTest):
    RECORDING = NoraSM64Test.RECORDING


class _BowserStageDeathTest(unittest.TestCase):
    """ Split detection over a Bowser stage that Mario dies in once, with the timer on its split, from the castle before it """

    RECORDING = None
    # The Bowser stage's split in the route
    SPLIT = None

    @classmethod
    def setUpClass(cls):
        if cls.RECORDING is None:
            raise unittest.SkipTest("Not a recording")
        if not cls.RECORDING.available():
            raise unittest.SkipTest(f"No {cls.RECORDING.video}")
        # It has no console reset to make reset templates from
        advanced = json.loads(DEFAULTS.read_text())["advanced"]
        templates = [DEFAULTS.parent / advanced["reset_frame_one"], DEFAULTS.parent / advanced["reset_frame_two"]]
        cls.result = replay(cls.RECORDING, 0, cls.RECORDING.length(), templates, split_index=cls.SPLIT)

    def test_no_errors(self):
        self.assertEqual(self.result.errors, [])
        self.assertEqual(self.result.log, [])

    def fadeouts_after(self, time):
        """ The fadeouts detection logged after `time`, as (count, the split it counted it for) """
        fadeouts = []
        for line in self.result.trace:
            match = re.match(r"(\S+) Fadeout (\d+): split \d+ of \d+, (.+?) \(needs", line)
            if match and float(match[1]) > time:
                fadeouts.append((int(match[2]), match[3]))
        return fadeouts


class FlosBitdwFallTest(_BowserStageDeathTest):
    """ Falling off BitDW, which split on re-entering it """
    RECORDING = Recording.load("flo_bitdw_fall_ares")
    SPLIT = 3
    # Mario re-enters BitDW, and leaves it with the key
    REENTRY = 60.6
    KEY_EXIT = (148, 149)

    def test_splits_bitdw_once_on_the_key_exit(self):
        look = 1 / json.loads(DEFAULTS.read_text())["advanced"]["fadeout_process_frame_rate"]
        self.assertEqual([command for _, command, _ in self.result.commands], ["split"],
                         f"Splits at {[time for time, _, _ in self.result.commands]}, the key exit at {self.KEY_EXIT[0]} s")
        time = self.result.commands[0][0]
        black = first_black_centre(self.RECORDING, *self.KEY_EXIT)
        self.assertIsNotNone(black)
        self.assertTrue(black - ROUNDING <= time <= black + look + ROUNDING,
                        f"Split at {time:.3f} s, the centre is black for the key exit from {black:.3f} s")

    def test_reentering_bitdw_is_its_first_fadeout(self):
        self.assertEqual(self.fadeouts_after(self.REENTRY - 1)[:3], [(1, "BitDW"), (2, "BitDW"), (3, "BitDW")])


class FlosBitfsDeathTest(_BowserStageDeathTest):
    """ Dying in the BitFS fight, which split on the death """
    RECORDING = Recording.load("flo_bitfs_death_ares")
    SPLIT = 9
    # Mario respawns by the pipe to Bowser, and takes it again
    PIPE_AGAIN = 145.7

    def test_no_split_for_the_death(self):
        # The recording ends before BitFS does
        self.assertEqual(self.result.commands, [])

    def test_taking_the_pipe_again_is_its_second_fadeout(self):
        self.assertEqual(self.fadeouts_after(self.PIPE_AGAIN - 1), [(2, "BitFS")])


class FlosDeathsTest(unittest.TestCase):
    """ Deaths in stage after stage, with Usamune, which split detection doesn't follow the lives in """
    RECORDING = Recording.load("flo_deaths_ares")
    # When the game is all black for each death that closes with Bowser's iris; the others are falls
    BOWSER_IRISES = [49.4, 66.767, 102.433, 158.933, 284.667]

    @classmethod
    def setUpClass(cls):
        if not cls.RECORDING.available():
            raise unittest.SkipTest(f"No {cls.RECORDING.video}")
        advanced = json.loads(DEFAULTS.read_text())["advanced"]
        templates = [DEFAULTS.parent / advanced["reset_frame_one"], DEFAULTS.parent / advanced["reset_frame_two"]]
        # Which fits irises ending later, as a dark stage's do
        cls.result = replay(cls.RECORDING, 0, cls.RECORDING.length(), templates, split_index=0, variant=AS64PP)

    def test_each_death_by_bowsers_iris_is_a_death(self):
        deaths = [float(line.split()[0]) for line in self.result.trace if " Death, Bowser's iris" in line]
        # Judged as the centre goes black, a few frames before the game is
        self.assertEqual(len(deaths), len(self.BOWSER_IRISES), f"Deaths at {deaths}")
        for death, black in zip(deaths, self.BOWSER_IRISES):
            self.assertTrue(black - 0.3 <= death <= black + ROUNDING, f"Death at {death}, the game black at {black}")


class _EndingTest(unittest.TestCase):
    """ AS64++'s final split over a recording of a run's ending, with the timer on BitS, the route's last split """

    RECORDING = None
    # The first frame without the Grand Star, once Mario grabbed it
    GRAB = None
    # From when to when Bowser's last speech shows
    SPEECH = None

    @classmethod
    def setUpClass(cls):
        if cls.RECORDING is None:
            raise unittest.SkipTest("Not a recording")
        if not cls.RECORDING.available():
            raise unittest.SkipTest(NEEDS_VIDEO if cls.RECORDING.url else f"No {cls.RECORDING.video}")
        # It has no console reset to make reset templates from
        advanced = json.loads(DEFAULTS.read_text())["advanced"]
        templates = [DEFAULTS.parent / advanced["reset_frame_one"], DEFAULTS.parent / advanced["reset_frame_two"]]
        start, end = cls.RECORDING.ending or (0, cls.RECORDING.length())
        bits = len(route_loader.load(cls.RECORDING.route_path).splits) - 1
        cls.result = replay(cls.RECORDING, start, end, templates, split_index=bits, variant=AS64PP)

    def test_no_errors(self):
        self.assertEqual(self.result.errors, [])

    def test_splits_when_mario_grabs_the_grand_star(self):
        look = 1 / json.loads(DEFAULTS.read_text())["advanced"]["fadeout_process_frame_rate"]
        self.assertEqual([command for _, command, _ in self.result.commands], ["split"])
        time = self.result.commands[0][0]
        self.assertTrue(self.GRAB - ROUNDING <= time <= self.GRAB + look + ROUNDING,
                        f"Split at {time:.3f} s, Mario grabs the Grand Star at {self.GRAB:.3f} s")

    def test_only_bowsers_last_speech_counts(self):
        # Not the speech before the fight, nor what else looks like one
        speeches = [float(line.split()[0]) for line in self.result.trace if "Bowser's last speech" in line]
        self.assertEqual(len(speeches), 1, f"Bowser's last speech at {speeches}, it shows from {self.SPEECH[0]} s")
        self.assertTrue(self.SPEECH[0] <= speeches[0] <= self.SPEECH[1],
                        f"Bowser's last speech at {speeches[0]:.3f} s, it shows from {self.SPEECH[0]} to {self.SPEECH[1]} s")


class FlosBitsTest(_EndingTest):
    """ Flo's Bowser in the Sky, which 0.6.0 split while Bowser was alive """
    RECORDING = Recording.load("flo_bits_ares")
    # At 361.867 s
    GRAB = 10856 / 30
    SPEECH = (351.5, 352.3)


class FlosBitsOverThePinkSkyTest(_EndingTest):
    """ The same over his Bowser in the Sky, where his last speech's box is brighter, over the pink sky """
    RECORDING = Recording.load("flo_bits_ares_2")
    # At 120.6 s
    GRAB = 3618 / 30
    SPEECH = (108.4, 109.2)


class JorbiieEndingTest(_EndingTest):
    """ On console, where the speech's text is grey """
    RECORDING = Recording.load("jorbiie_70_star")
    # At 3316.933 s
    GRAB = 99508 / 30
    SPEECH = (3307.9, 3308.7)


class Ronc3naEndingTest(_EndingTest):
    """ On console, where the speech's text is grey, at 60 fps """
    RECORDING = Recording.load("ronc3na_70_star")
    # At 2967.765 s
    GRAB = 177888 / (60000 / 1001)
    SPEECH = (2958.5, 2959.2)


class KannoEndingTest(_EndingTest):
    """ On emulator, with smoke that looks like a speech during the fight """
    RECORDING = Recording.load("kanno_16_star")
    # At 921.154 s
    GRAB = 27607 / (30000 / 1001)
    SPEECH = (911.7, 912.9)


class OhyeahEndingTest(_EndingTest):
    """ On emulator """
    RECORDING = Recording.load("ohyeah_16_star")
    # At 886.963 s, at the video's 29.999 fps
    GRAB = 886.963
    SPEECH = (877.7, 878.8)


if __name__ == "__main__":
    unittest.main()
