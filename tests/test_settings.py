import copy
import unittest
from unittest import mock

from PyQt6 import QtWidgets

from autosplit64.core import config
from autosplit64.gui import theme
from autosplit64.gui.dialogs.settings_dialog import ConnectionMenu, SettingsDialog

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ConnectionMenuTest(unittest.TestCase):
    def shown_fields(self, mode):
        menu = ConnectionMenu()
        self.addCleanup(menu.deleteLater)
        menu.ls_mode_combo.setCurrentText(mode)
        fields = {"pipe host": menu.ls_pipe_host_le, "TCP host": menu.host_le, "TCP port": menu.port_le,
                  "LiveSplit One port": menu.lso_port_le}
        labels = [menu.ls_pipe_host_lb, menu.host_lb, menu.port_lb, menu.lso_port_lb]
        # Each field's label is shown and hidden with it
        for field, label in zip(fields.values(), labels):
            self.assertEqual(field.isHidden(), label.isHidden())
        return [name for name, field in fields.items() if not field.isHidden()]

    def test_only_the_selected_modes_settings_are_shown(self):
        self.assertEqual(self.shown_fields("Named Pipe"), ["pipe host"])
        self.assertEqual(self.shown_fields("TCP"), ["TCP host", "TCP port"])
        self.assertEqual(self.shown_fields("LiveSplit One"), ["LiveSplit One port"])


class SettingsDialogTest(unittest.TestCase):
    # A value for every setting the dialog edits, each different from the defaults and its neighbours
    SETTINGS = {
        "general": {"operation_mode": 1, "mid_run_start_enabled": False, "on_top": False, "update_check": True,
                    "auto_start": True, "theme": "dracula"},
        "game": {"override_version": True, "version": "US"},
        "connection": {"ls_host": "host.example", "ls_port": 1234, "ls_pipe_host": "pipe.example", "lso_port": 5678,
                       "ls_connection_type": 2},
        "thresholds": {"probability_threshold": 0.11, "reset_threshold": 0.12, "confirmation_threshold": 0.13,
                       "black_threshold": 0.14, "white_threshold": 0.15, "xcam_bg_threshold": 16,
                       "xcam_rg_threshold": 17, "xcam_bg_activation": 18, "xcam_rg_activation": 19,
                       "xcam_pixel_threshold": 0.2, "undo_threshold": 0.21},
        "split_ddd_enter": {"portal_lower_bound": [1, 2, 3], "portal_upper_bound": [4, 5, 6],
                            "hat_lower_bound": [7, 8, 9], "hat_upper_bound": [10, 11, 12]},
        "split_final_star": {"stage_lower_bound": [13, 14, 15], "stage_upper_bound": [16, 17, 18],
                             "star_lower_bound": [19, 20, 21], "star_upper_bound": [22, 23, 24]},
        "split_xcam": {"lower_bound": [25, 26, 27], "upper_bound": [28, 29, 30]},
        "error": {"processing_length": 22, "minimum_undo_count": 23, "undo_threshold": 0.24,
                  "minimum_consecutive_prediction": 25, "max_star_skip": 26, "star_skip": False},
        "advanced": {"restart_frame_offset": -7, "file_select_frame_offset": -27,
                     "reset_frame_one": "templates/one.jpg", "reset_frame_two": "templates/two.jpg",
                     "star_process_frame_rate": 5.5, "fadeout_process_frame_rate": 28.5},
        "model": {"legacy": True},
    }

    def test_applying_keeps_every_setting(self):
        settings = copy.deepcopy(self.SETTINGS)
        for patcher in [mock.patch.object(config, "_config", settings), mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        dialog = SettingsDialog()
        self.addCleanup(dialog.deleteLater)

        dialog.show()
        dialog.apply_clicked()

        self.assertEqual(settings, self.SETTINGS)
        # Types too: 1 == 1.0 and False == 0
        for section, values in self.SETTINGS.items():
            for key, value in values.items():
                with self.subTest(f"{section}.{key}"):
                    self.assertIs(type(settings[section][key]), type(value))



class ThemeSettingTest(unittest.TestCase):
    """ Choosing a theme shows it right away, but only Apply keeps it """

    def setUp(self):
        palette = _app.palette()
        self.addCleanup(_app.setPalette, palette)
        self.settings = copy.deepcopy(SettingsDialogTest.SETTINGS)
        for patcher in [mock.patch.object(config, "_config", self.settings), mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        theme.apply("dracula")
        self.dialog = SettingsDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.dialog.show()
        self.combo = self.dialog.menus[0].theme_combo

    def test_shows_the_saved_theme(self):
        self.assertEqual(self.combo.currentText(), "Dracula")
        self.assertEqual(self.combo.itemText(0), "Default")

    def test_choosing_shows_the_theme_without_saving_it(self):
        self.combo.setCurrentText("Nord")
        self.assertEqual(theme.current(), "nord")
        self.assertEqual(self.settings["general"]["theme"], "dracula")

    def test_apply_keeps_it(self):
        self.combo.setCurrentText("Nord")
        self.dialog.apply_clicked()
        self.assertEqual((theme.current(), self.settings["general"]["theme"]), ("nord", "nord"))

    def test_cancel_close_and_escape_go_back_to_the_saved_theme(self):
        for close in (self.dialog.cancel_btn.click, self.dialog.close, self.dialog.reject):
            with self.subTest(close.__name__):
                self.dialog.show()
                self.combo.setCurrentText("Nord")
                close()
                self.assertEqual((theme.current(), self.settings["general"]["theme"]), ("dracula", "dracula"))

    def test_theme_that_doesnt_exist_shows_the_default(self):
        self.settings["general"]["theme"] = "removed_theme"
        self.dialog.show()
        self.assertEqual(self.combo.currentText(), "Default")


if __name__ == "__main__":
    unittest.main()
