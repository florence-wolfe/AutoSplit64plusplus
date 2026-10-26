import unittest
from unittest import mock

from PyQt6 import QtWidgets

from autosplit64.core import livesplit
from autosplit64.gui.server_status import ServerStatus
import tests.qt  # noqa: F401, for its QApplication
from tests.settings import patch_settings


class ClientModesTest(unittest.TestCase):
    def status(self, mode, status):
        for patcher in [patch_settings({("connection", "ls_connection_type"): mode}, real=True),
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

    def test_label_says_the_state_whatever_the_connection(self):
        from autosplit64.core import livesplit_one
        for state, label in [("connected", "Connected"), ("waiting", "Waiting"), ("stopped", "Not connected"),
                             ("error", "Error")]:
            with self.subTest(state):
                if state != "waiting":
                    self.assertEqual(self.status(1, (state, "localhost:16834", None)).label, label)
                with patch_settings({("connection", "ls_connection_type"): 2, ("connection", "lso_port"): 5000},
                                    real=True), mock.patch.object(livesplit_one, "status", return_value=(state, 5000, None)):
                    status = ServerStatus()
                    self.addCleanup(status.deleteLater)
                    self.assertEqual(status.label, label)

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
        self.assertEqual(window.main.values["statusLabel"], "Connected")


if __name__ == "__main__":
    unittest.main()
