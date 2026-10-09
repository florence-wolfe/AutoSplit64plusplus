import contextlib
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.core import config, logs
from autosplit64.gui.dialogs.debug_dialog import DebugDialog

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

OUTPUT = {"fade_status": "FADEOUT_PARTIAL", "fadeout_count": 2, "fadein_count": 1, "xcam_percent": 0.123456789,
          "xcam_count": 3, "xcam_status": True, "prediction": 16, "probability": 0.987654321, "execution": 0.0123456}


class DebugDialogTest(unittest.TestCase):
    def setUp(self):
        for patcher in [mock.patch.object(config, "_config", {"general": {"output_update_rate": 10}}),
                        mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = DebugDialog()
        self.addCleanup(self.dialog.deleteLater)

    def fields(self):
        """ Each label's text and the read-only field under it """
        grid = self.dialog.layout()
        shown = {}
        for i in range(grid.count()):
            label = grid.itemAt(i).widget()
            if isinstance(label, QtWidgets.QLabel) and label.text().endswith(":") and label.text() != "Update Rate:":
                row, column, _, _ = grid.getItemPosition(i)
                shown[label.text()] = grid.itemAtPosition(row + 1, column).widget()
        return shown

    def test_shows_the_output_under_each_label(self):
        self.dialog.display_output(OUTPUT)
        shown = {label: field.text() for label, field in self.fields().items()}
        self.assertEqual(shown, {
            "Fade Status:": "FADEOUT_PARTIAL", "Fade-out Count:": "2", "Fade-in Count:": "1",
            "X-Cam Percent:": "0.1234", "X-Cam Count:": "3", "X-Cam Status:": "True",
            "Prediction:": "16", "Probability:": "0.9876", "Execution Time:": "0.0123"})

    def test_output_fields_are_read_only(self):
        for label, field in self.fields().items():
            with self.subTest(label):
                self.assertFalse(field.isEnabled())

    def test_changing_the_update_rate_saves_it(self):
        self.dialog.output_reader = SimpleNamespace(update_rate=10)
        self.dialog.update_le.setText("25")
        self.dialog.update_le.editingFinished.emit()
        self.assertEqual(self.dialog.output_reader.update_rate, 25)
        self.assertEqual(config.get("general", "output_update_rate"), 25)
        config.save_config.assert_called_once()

    def test_title_and_resizable(self):
        self.assertEqual(self.dialog.windowTitle(), "Debug")
        self.assertLess(self.dialog.minimumSize().width(), self.dialog.maximumSize().width())
        self.assertLess(self.dialog.minimumSize().height(), self.dialog.maximumSize().height())

    def test_remembers_its_size(self):
        self.dialog.show()
        self.dialog.resize(420, 610)
        self.dialog.close()
        self.assertEqual(config.get("general", "debug_window_size"), [420, 610])
        again = DebugDialog()
        self.addCleanup(again.deleteLater)
        self.assertEqual((again.width(), again.height()), (420, 610))

    def test_opens_the_logs_in_the_text_editor(self):
        with mock.patch.object(QtGui.QDesktopServices, "openUrl") as open_url:
            self.dialog.open_log_btn.click()
        self.assertEqual(open_url.call_args.args[0], QtCore.QUrl.fromLocalFile(str(Path(logs.LOG_FILE).absolute())))

    def test_previous_log_only_when_there_is_one(self):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        with contextlib.chdir(directory):
            self.dialog.update_log_buttons()
            self.assertFalse(self.dialog.open_old_log_btn.isEnabled())
            Path(logs.OLD_LOG_FILE).write_text("previous session")
            self.dialog.update_log_buttons()
            self.assertTrue(self.dialog.open_old_log_btn.isEnabled())
            with mock.patch.object(QtGui.QDesktopServices, "openUrl") as open_url:
                self.dialog.open_old_log_btn.click()
            self.assertEqual(open_url.call_args.args[0], QtCore.QUrl.fromLocalFile(str(Path(logs.OLD_LOG_FILE).absolute())))

    def test_save_debug_info(self):
        saved = mock.Mock()
        self.dialog.save_debug_info.connect(saved)
        self.dialog.save_debug_info_btn.click()
        saved.assert_called_once()

    def test_update_rate_is_explained(self):
        for widget in (self.dialog.update_lb, self.dialog.update_le):
            self.assertIn("times a second", widget.toolTip())
            self.assertIn("Split detection itself isn't affected", widget.toolTip())

    def test_update_rate_is_1_to_30(self):
        validator = self.dialog.update_le.validator()
        self.assertNotEqual(validator.validate("0", 0)[0], QtGui.QValidator.State.Acceptable)
        self.assertEqual(validator.validate("1", 0)[0], QtGui.QValidator.State.Acceptable)
        self.assertEqual(validator.validate("30", 0)[0], QtGui.QValidator.State.Acceptable)

    def test_saved_update_rate_of_0_is_1(self):
        # Allowed before, which divided by zero in the thread
        config.set_key("general", "output_update_rate", 0)
        self.dialog.show()
        self.addCleanup(self.dialog.close)
        self.assertEqual(self.dialog.output_reader.update_rate, 1)
        self.assertEqual(self.dialog.update_le.text(), "1")

    def test_reopening_shows_the_changed_update_rate(self):
        self.dialog.show()
        self.dialog.update_le.setText("25")
        self.dialog.update_le.editingFinished.emit()
        self.dialog.close()
        self.dialog.show()
        self.addCleanup(self.dialog.close)
        self.assertEqual(self.dialog.update_le.text(), "25")

    def test_closing_stops_the_output_reader(self):
        # Deleting the window while its thread runs would abort AutoSplit64++
        config.set_key("general", "output_update_rate", 1)
        self.dialog.show()
        reader = self.dialog.output_reader
        self.dialog.close()
        self.assertTrue(reader.isFinished())

    def test_closing_before_it_was_shown(self):
        # The main window closes it when quitting, also when it was never shown. An exception in
        # closeEvent would abort the app, so it's called directly here to fail the test instead.
        self.dialog.closeEvent(QtGui.QCloseEvent())
        self.dialog.hide()
        # Which doesn't change the settings
        config.save_config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
