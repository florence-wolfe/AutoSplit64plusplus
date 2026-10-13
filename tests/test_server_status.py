import unittest
from unittest import mock

from PyQt6 import QtWidgets

from autosplit64.core import config, livesplit
from autosplit64.gui.server_status import ServerStatus

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ClientModesTest(unittest.TestCase):
    def status(self, mode, status):
        real_get = config.get
        for patcher in [mock.patch.object(config, "get", side_effect=lambda section, key=None:
                                          mode if (section, key) == ("connection", "ls_connection_type") else real_get(section, key)),
                        mock.patch.object(livesplit, "client_status", return_value=status)]:
            patcher.start()
            self.addCleanup(patcher.stop)
        status = ServerStatus()
        self.addCleanup(status.deleteLater)
        return status

    def test_tcp_tooltip_and_copy(self):
        status = self.status(1, ("stopped", "localhost:16834", None))
        self.assertEqual(status.tooltip, "Connects to LiveSplit when split detection starts\nlocalhost:16834\nClick to copy")
        self.assertEqual(status.copy(), "localhost:16834")
        self.assertEqual(QtWidgets.QApplication.clipboard().text(), "localhost:16834")

    def test_states(self):
        for status, tooltip in [(("connected", "localhost:16834", None), "Connected to LiveSplit\nlocalhost:16834\nClick to copy"),
                                (("error", "localhost:16834", "Is LiveSplit's server started?"),
                                 "Couldn't connect to LiveSplit: Is LiveSplit's server started?\nlocalhost:16834\nClick to copy")]:
            with self.subTest(status[0]):
                self.assertEqual(self.status(1, status).tooltip, tooltip)

    def test_the_window_shows_it_in_its_color(self):
        from autosplit64.gui import theme
        from autosplit64.gui.app import App
        from tests.qt import close_window
        self.status(1, ("connected", "localhost:16834", None))
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            window = App()
        self.addCleanup(close_window, window)
        self.assertEqual((window.main.values["statusColor"], window.main.values["statusTip"]),
                         (theme.status_color("green").name(), "Connected to LiveSplit\nlocalhost:16834\nClick to copy"))


if __name__ == "__main__":
    unittest.main()
