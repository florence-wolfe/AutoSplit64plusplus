import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
from PyQt6 import QtWidgets

from autosplit64.core import config
from autosplit64.gui.dialogs.reset_generator_dialog import ResetGenerator, ResetGeneratorDialog

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

    def test_generated_frames_are_shown(self):
        self.dialog.on_generate()
        self.assertFalse(self.dialog.gen_1_px.pixmap().isNull())
        self.assertEqual((self.dialog.gen_1_sb.value(), self.dialog.gen_2_sb.value()), (2, 3))
        self.assertTrue(self.dialog.apply_btn.isEnabled())

    def test_apply_keeps_the_chosen_frames(self):
        self.dialog.on_generate()
        self.dialog.gen_1_sb.setValue(1)
        self.dialog.gen_2_sb.setValue(4)
        self.dialog.apply_clicked()

        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["generated_reset_one.jpg", "generated_reset_two.jpg"])
        self.assertEqual((self.shade("generated_reset_one.jpg"), self.shade("generated_reset_two.jpg")), (1, 4))
        self.assertEqual(config.get("advanced", "reset_frame_one"), str(self.dir) + "/generated_reset_one.jpg")
        self.assertEqual(config.get("advanced", "reset_frame_two"), str(self.dir) + "/generated_reset_two.jpg")
        config.save_config.assert_called_once()

    def test_cancel_removes_the_generated_frames(self):
        (self.dir / "generated_reset_one.jpg").write_bytes(b"earlier")
        self.dialog.cancel_clicked()
        self.assertEqual([p.name for p in self.dir.iterdir()], ["generated_reset_one.jpg"])

    def test_closing_removes_the_generated_frames(self):
        self.dialog.close()
        self.assertEqual(list(self.dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
