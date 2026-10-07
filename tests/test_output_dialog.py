import unittest
from types import SimpleNamespace
from unittest import mock

from PyQt6 import QtGui, QtWidgets

from autosplit64.core import config
from autosplit64.gui.dialogs.output_dialog import OutputDialog

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

OUTPUT = {"fade_status": "FADEOUT_PARTIAL", "fadeout_count": 2, "fadein_count": 1, "xcam_percent": 0.123456789,
          "xcam_count": 3, "xcam_status": True, "prediction": 16, "probability": 0.987654321, "execution": 0.0123456}


class OutputDialogTest(unittest.TestCase):
    def setUp(self):
        for patcher in [mock.patch.object(config, "_config", {"general": {"output_update_rate": 10}}),
                        mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog = OutputDialog()
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

    def test_closing_before_it_was_shown(self):
        # The main window closes it when quitting, also when it was never shown. An exception in
        # closeEvent would abort the app, so it's called directly here to fail the test instead.
        self.dialog.closeEvent(QtGui.QCloseEvent())
        self.dialog.hide()


if __name__ == "__main__":
    unittest.main()
