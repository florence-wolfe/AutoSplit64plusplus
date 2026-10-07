import unittest

from PyQt6 import QtWidgets

from as64gui.dialogs.settings_dialog import ConnectionMenu

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


if __name__ == "__main__":
    unittest.main()
