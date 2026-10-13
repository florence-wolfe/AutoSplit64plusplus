import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
from PyQt6 import QtCore, QtWidgets

from autosplit64.core import config
from autosplit64.gui.dialogs.reset_generator_dialog import ResetGenerator, ResetGeneratorDialog
from tests.qt import qml, wait_until

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ResetGeneratorDialogTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        for patcher in [mock.patch.object(ResetGeneratorDialog, "TEMPLATE_DIR", str(self.dir) + "/"),
                        mock.patch.object(config, "_config", {"advanced": {}}),
                        mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = ResetGeneratorDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.dialog._reset_generator = mock.Mock()
        # Frames 1 to 5 as generated, each a different shade so they can be told apart
        for i in range(1, ResetGenerator.CAPTURE_COUNT + 1):
            cv2.imwrite(str(self.dir / f"generated_temp_{i}.jpg"), np.full((137, 251, 3), i * 40, np.uint8))

    def shade(self, name):
        return int(cv2.imread(str(self.dir / name)).mean() / 40 + 0.5)

    def shown(self):
        """ The files of the images shown above the defaults """
        return [Path(QtCore.QUrl(url).toLocalFile()).name for url in self.dialog.templates.values["shown"]]

    def qml(self, name):
        return qml(self.dialog.view, name)

    def choose(self, column, number):
        """ Choose a generated frame like the spin box does """
        spin_box = self.qml(f"frame{column}")
        spin_box.setProperty("value", number)
        QtCore.QMetaObject.invokeMethod(spin_box, "valueModified")

    def test_generated_frames_are_shown(self):
        self.dialog.on_generate()
        self.assertEqual(self.shown(), ["generated_temp_2.jpg", "generated_temp_3.jpg"])
        self.assertEqual([self.qml(f"frame{column}").property("value") for column in (0, 1)], [2, 3])
        self.assertTrue(self.qml("apply").property("enabled"))

    def test_choosing_a_frame_shows_it(self):
        self.dialog.on_generate()
        self.choose(1, 5)
        self.assertEqual(self.shown(), ["generated_temp_2.jpg", "generated_temp_5.jpg"])

    def test_apply_keeps_the_chosen_frames(self):
        self.dialog.on_generate()
        self.choose(0, 1)
        self.choose(1, 4)
        self.dialog.apply_clicked()

        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["generated_reset_one.jpg", "generated_reset_two.jpg"])
        self.assertEqual((self.shade("generated_reset_one.jpg"), self.shade("generated_reset_two.jpg")), (1, 4))
        self.assertEqual(config.get("advanced", "reset_frame_one"), str(self.dir) + "/generated_reset_one.jpg")
        self.assertEqual(config.get("advanced", "reset_frame_two"), str(self.dir) + "/generated_reset_two.jpg")
        config.save_config.assert_called_once()

    def test_apply_tells_split_detection_to_restart(self):
        # Split detection reads the templates when it starts, so it must restart to use the new ones
        applied = mock.Mock()
        self.dialog.applied.connect(applied)
        self.dialog.on_generate()
        self.dialog.cancel_clicked()
        applied.assert_not_called()
        self.dialog.apply_clicked()
        applied.assert_called_once()

    def test_opening_shows_the_templates_in_use(self):
        # Templates applied earlier, not the temporary frames of a generation
        for name, i in (("one", 1), ("two", 4)):
            path = str(self.dir / f"generated_reset_{name}.jpg")
            cv2.imwrite(path, np.full((137, 251, 3), i * 40, np.uint8))
            config.set_key("advanced", f"reset_frame_{name}", path)
        with mock.patch("autosplit64.gui.dialogs.reset_generator_dialog.ResetGenerator"):
            self.dialog.show()
        self.addCleanup(self.dialog.close)

        self.assertEqual(self.shown(), ["generated_reset_one.jpg", "generated_reset_two.jpg"])
        self.assertFalse(self.qml("apply").property("enabled"))

    def test_cancel_removes_the_generated_frames(self):
        (self.dir / "generated_reset_one.jpg").write_bytes(b"earlier")
        self.dialog.cancel_clicked()
        self.assertEqual([p.name for p in self.dir.iterdir()], ["generated_reset_one.jpg"])

    def test_an_error_is_shown_and_closing_it_keeps_the_window_open(self):
        with mock.patch("autosplit64.gui.dialogs.reset_generator_dialog.ResetGenerator"):
            self.dialog.show()
        self.addCleanup(self.dialog.close)
        self.dialog.on_error("No game capture")
        error = self.qml("error")
        self.assertEqual((error.property("visible"), error.property("text")), (True, "No game capture"))

        QtCore.QMetaObject.invokeMethod(error, "close")
        # Once it has faded out, to generate again after fixing the capture
        wait_until(lambda: not error.property("visible"))
        self.assertTrue(self.dialog.isVisible())
        self.assertEqual((self.qml("generate").property("text"), self.qml("generate").property("enabled")), ("Generate", True))

    def test_closing_removes_the_generated_frames(self):
        self.dialog.close()
        self.assertEqual(list(self.dir.iterdir()), [])


    def test_generate_says_its_waiting_for_the_reset_and_for_how_long(self):
        # How long is up to the runner, who resets the console
        with mock.patch("time.monotonic", return_value=100):
            self.dialog.generate_clicked()
        self.assertEqual(self.qml("generate").property("text"), "Reset your console… 0 s")
        self.assertTrue(self.dialog._wait_timer.isActive())
        with mock.patch("time.monotonic", return_value=112.5):
            self.dialog._wait_timer.timeout.emit()
        self.assertEqual(self.qml("generate").property("text"), "Reset your console… 12 s")

    def test_capturing_once_the_reset_is_seen(self):
        self.dialog.generate_clicked()
        self.dialog.on_reset_seen()
        self.assertEqual(self.qml("generate").property("text"), "Capturing…")
        self.assertFalse(self.dialog._wait_timer.isActive())

    def test_stops_counting_when_generated_or_cancelled(self):
        for finish in (self.dialog.on_generate, self.dialog.cancel_clicked):
            self.dialog.generate_clicked()
            finish()
            self.assertFalse(self.dialog._wait_timer.isActive())
            if finish == self.dialog.on_generate:
                self.assertEqual(self.qml("generate").property("text"), "Generate")


class ResetGeneratorTest(unittest.TestCase):
    def test_says_when_it_sees_the_reset(self):
        black, logo = np.zeros((50, 50, 3), np.uint8), np.full((50, 50, 3), 200, np.uint8)
        # The game, the black screen of the reset, then the logo
        frames = iter([logo, black, black] + [logo] * (ResetGenerator.CAPTURE_COUNT + 1))
        capture = mock.Mock(get_region=mock.Mock(side_effect=lambda region: current[0]))
        current = [None]
        capture.capture.side_effect = lambda: current.__setitem__(0, next(frames))
        with mock.patch("autosplit64.gui.dialogs.reset_generator_dialog.GameCapture", return_value=capture), \
             mock.patch.object(config, "_config", {"game": {}, "thresholds": {"black_threshold": 0.1}}), \
             mock.patch("time.sleep"), mock.patch("cv2.imwrite"):
            generator = ResetGenerator()
            seen = mock.Mock()
            generator.reset_seen.connect(seen)
            generator.run()
        seen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
