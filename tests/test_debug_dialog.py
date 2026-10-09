import contextlib
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.core import config, logs
from autosplit64.gui.dialogs.debug_dialog import DebugDialog, describe

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

OUTPUT = {"fade_status": "FADEOUT_PARTIAL", "fadeout_count": 2, "fadein_count": 1, "xcam_percent": 0.123456789,
          "xcam_count": 3, "xcam_status": True, "prediction": 16, "probability": 0.987654321, "execution": 0.0123456,
          "status": None, "livesplit": "LiveSplit connected"}

STATUS = {"running": True, "in_game": True, "split_index": 2, "split_count": 12, "split": "CCM 8", "split_type": "Normal",
          "needs_stars": 8, "needs_fadeouts": 1, "needs_fadeins": 0, "needs_xcams": -1,
          "stars": 7, "fadeouts": 0, "fadeins": 1, "xcams": 0}


class DescribeTest(unittest.TestCase):
    """ What split detection is doing, in words """

    def test_in_a_run(self):
        self.assertEqual(describe(STATUS, "LiveSplit connected"), (
            "Running, in a run · LiveSplit connected", "Split 3 of 12: CCM 8",
            "8 stars · fadeout 1 · fade-in 0", "7 stars · fadeouts 0 · fade-ins 1"))

    def test_waiting_for_a_run(self):
        status = dict(STATUS, in_game=False)
        self.assertEqual(describe(status, "LiveSplit connected")[0], "Running, waiting for a run · LiveSplit connected")

    def test_not_running(self):
        for status in (None, dict(STATUS, running=False), {"running": False, "in_game": False}):
            with self.subTest(status):
                self.assertEqual(describe(status, "LiveSplit not connected"), ("Not running · LiveSplit not connected", "", "", ""))

    def test_one_star(self):
        self.assertEqual(describe(dict(STATUS, needs_stars=1, stars=1), "")[2:], ("1 star · fadeout 1 · fade-in 0", "1 star · fadeouts 0 · fade-ins 1"))

    def test_what_each_split_type_needs(self):
        for split_type, needs, counted in [
                ("Fade", "fadeout 1 · fade-in 0", "7 stars · fadeouts 0 · fade-ins 1"),
                ("X-Cam", "8 stars · fadeout 1 · fade-in 0 · X-Cam 2", "7 stars · fadeouts 0 · fade-ins 1 · X-Cams 1"),
                ("Mips", "entering the DDD painting", "7 stars · fadeouts 0 · fade-ins 1"),
                ("Mips-X", "an X-Cam at the DDD painting", "7 stars · X-Cams 1"),
                ("Final", "grabbing the Grand Star", "7 stars · fadeouts 0 · fade-ins 1")]:
            with self.subTest(split_type):
                status = dict(STATUS, split_type=split_type, needs_xcams=2, xcams=1)
                self.assertEqual(describe(status, "")[2:], (needs, counted))


class DebugDialogTest(unittest.TestCase):
    def setUp(self):
        for patcher in [mock.patch.object(config, "_config", {"general": {"output_update_rate": 10}}),
                        mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = DebugDialog()
        self.addCleanup(self.dialog.deleteLater)

    def fields(self):
        """ Each label's text and the read-only field under it, in Advanced """
        grid = self.dialog.advanced.layout()
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

    def test_what_split_detection_is_doing(self):
        self.dialog.display_output(dict(OUTPUT, status=STATUS))
        self.assertEqual((self.dialog.status_lb.text(), self.dialog.split_lb.text(), self.dialog.needs_lb.text(),
                          self.dialog.counted_lb.text()), describe(STATUS, "LiveSplit connected"))

    def test_only_the_status_while_not_running(self):
        self.dialog.display_output(dict(OUTPUT, status=None))
        self.assertTrue(self.dialog.status_lb.isVisibleTo(self.dialog))
        for label in (self.dialog.split_lb, self.dialog.needs_lb, self.dialog.counted_lb):
            self.assertFalse(label.isVisibleTo(self.dialog))
        self.dialog.display_output(dict(OUTPUT, status=STATUS))
        for label in (self.dialog.split_lb, self.dialog.needs_lb, self.dialog.counted_lb):
            self.assertTrue(label.isVisibleTo(self.dialog))

    def test_advanced_is_collapsed_at_first(self):
        self.assertFalse(self.dialog.advanced.isVisibleTo(self.dialog))
        self.dialog.advanced_btn.click()
        self.assertTrue(self.dialog.advanced.isVisibleTo(self.dialog))
        self.assertIs(config.get("general", "debug_advanced"), True)
        config.save_config.assert_called_once()

    def test_advanced_stays_open(self):
        config.set_key("general", "debug_advanced", True)
        again = DebugDialog()
        self.addCleanup(again.deleteLater)
        self.assertTrue(again.advanced.isVisibleTo(again))
        self.assertTrue(again.advanced_btn.isChecked())

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
