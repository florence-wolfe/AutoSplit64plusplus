import contextlib
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import cv2
import numpy as np

from autosplit64 import core
from autosplit64.core import config, debug_info, logs
from autosplit64.core.constants import GAME_REGION, STAR_REGION


class SaveTest(unittest.TestCase):
    """ One file with what a bug report needs """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        # Everything is next to the settings, which is where AutoSplit64++ runs
        chdir = contextlib.chdir(self.dir)
        chdir.__enter__()
        self.addCleanup(chdir.__exit__, None, None, None)
        for name in (logs.LOG_FILE, logs.OLD_LOG_FILE, "config.ini"):
            Path(name).write_text(name)
        Path("routes").mkdir()
        Path("routes/16 star.as64").write_text("route")
        Path("templates").mkdir()
        for name in ("one", "two"):
            Path(f"templates/reset_{name}.jpg").write_bytes(b"jpeg")
        self.settings = {("route", "path"): "routes/16 star.as64", ("advanced", "reset_frame_one"): "templates/reset_one.jpg",
                         ("advanced", "reset_frame_two"): "templates/reset_two.jpg"}
        patcher = mock.patch.object(config, "get", side_effect=lambda section, key=None: self.settings[(section, key)])
        patcher.start()
        self.addCleanup(patcher.stop)

    def saved(self, frame=None, error=None):
        path = self.dir / "debug.zip"
        debug_info.save(path, frame, error)
        with zipfile.ZipFile(path) as saved:
            return {name: saved.read(name) for name in saved.namelist()}

    def test_logs_settings_route_and_templates(self):
        files = self.saved(np.zeros((4, 4, 3), np.uint8))
        self.assertEqual(files[logs.LOG_FILE], logs.LOG_FILE.encode())
        self.assertEqual(files[logs.OLD_LOG_FILE], logs.OLD_LOG_FILE.encode())
        self.assertEqual(files["config.ini"], b"config.ini")
        self.assertEqual(files["16 star.as64"], b"route")
        self.assertEqual(files["reset_one.jpg"], b"jpeg")
        self.assertEqual(files["reset_two.jpg"], b"jpeg")
        frame = cv2.imdecode(np.frombuffer(files["capture.png"], np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(frame.shape, (4, 4, 3))

    def test_whats_missing_is_left_out(self):
        Path(logs.OLD_LOG_FILE).unlink()
        self.settings[("route", "path")] = ""
        files = self.saved(np.zeros((4, 4, 3), np.uint8))
        self.assertNotIn(logs.OLD_LOG_FILE, files)
        self.assertNotIn("16 star.as64", files)
        self.assertIn(logs.LOG_FILE, files)

    def test_why_there_is_no_frame(self):
        files = self.saved(error="Could not find AmaRecTV.exe")
        self.assertNotIn("capture.png", files)
        self.assertEqual(files["capture.txt"], b"Could not find AmaRecTV.exe")


class FakeCapture:
    """ A capture of a gray frame, with the game in the middle """

    def __init__(self, *args):
        self._window_image = np.full((100, 200, 3), 128, np.uint8)

    def is_valid(self):
        pass

    def capture(self):
        pass

    def get_region_rect(self, region):
        return {GAME_REGION: [50, 10, 100, 80], STAR_REGION: [120, 12, 20, 10]}.get(region)

    def close(self):
        pass


class CaptureFrameTest(unittest.TestCase):
    def setUp(self):
        real_get = config.get
        patcher = mock.patch.object(config, "get", side_effect=lambda section, key=None:
                                    "" if (section, key) == ("route", "path") else real_get(section, key))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_regions_are_drawn_on_the_frame(self):
        with mock.patch.object(debug_info, "GameCapture", FakeCapture), mock.patch.object(core, "_base", None, create=True):
            frame, error = debug_info.capture_frame()
        self.assertIsNone(error)
        self.assertEqual(frame.shape, (100, 200, 3))
        # Each region's outline, around the gray frame
        self.assertNotEqual(tuple(frame[10, 75]), (128, 128, 128))
        self.assertNotEqual(tuple(frame[12, 130]), (128, 128, 128))
        self.assertEqual(tuple(frame[50, 10]), (128, 128, 128))

    def test_while_split_detection_runs_its_frame_is_used(self):
        detection = SimpleNamespace(_game_capture=FakeCapture(), is_alive=lambda: True)
        # A second capture would compete with the running one, and stop it when closed
        with mock.patch.object(debug_info, "GameCapture") as new_capture, mock.patch.object(core, "_base", detection, create=True):
            frame, error = debug_info.capture_frame()
        new_capture.assert_not_called()
        self.assertEqual(frame.shape, (100, 200, 3))

    def test_split_detection_starting_without_a_frame_yet(self):
        # e.g. while Autostart tries to connect to LiveSplit
        capture = FakeCapture()
        capture._window_image = None
        detection = SimpleNamespace(_game_capture=capture, is_alive=lambda: True)
        with mock.patch.object(core, "_base", detection, create=True):
            frame, error = debug_info.capture_frame()
        self.assertIsNone(frame)
        self.assertIn("hasn't captured", error)

    def test_why_capturing_failed(self):
        class Missing(FakeCapture):
            def is_valid(self):
                raise Exception("Could not find AmaRecTV.exe")

        with mock.patch.object(debug_info, "GameCapture", Missing), mock.patch.object(core, "_base", None, create=True):
            frame, error = debug_info.capture_frame()
        self.assertIsNone(frame)
        self.assertEqual(error, "Could not find AmaRecTV.exe")


if __name__ == "__main__":
    unittest.main()
