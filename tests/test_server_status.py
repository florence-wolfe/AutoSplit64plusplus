import unittest
from unittest import mock

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtTest import QTest

from as64core import config, livesplit
from as64gui.widgets import ServerStatusIndicator

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ClientModesTest(unittest.TestCase):
    def indicator(self, mode, status):
        real_get = config.get
        for patcher in [mock.patch.object(config, "get", side_effect=lambda section, key=None:
                                          mode if (section, key) == ("connection", "ls_connection_type") else real_get(section, key)),
                        mock.patch.object(livesplit, "client_status", return_value=status)]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.window = QtWidgets.QWidget()
        self.addCleanup(self.window.deleteLater)
        return ServerStatusIndicator(self.window)

    def test_tcp_tooltip_and_copy(self):
        indicator = self.indicator(1, ("stopped", "localhost:16834", None))
        self.assertTrue(indicator.isVisibleTo(self.window))
        self.assertEqual(indicator.toolTip(), "Connects to LiveSplit when split detection starts\nlocalhost:16834\nClick to copy")
        QTest.mouseClick(indicator, QtCore.Qt.MouseButton.LeftButton)
        self.assertEqual(QtWidgets.QApplication.clipboard().text(), "localhost:16834")

    def test_states(self):
        for status, tooltip in [(("connected", "localhost:16834", None), "Connected to LiveSplit\nlocalhost:16834\nClick to copy"),
                                (("error", "localhost:16834", "Is LiveSplit's server started?"),
                                 "Couldn't connect to LiveSplit: Is LiveSplit's server started?\nlocalhost:16834\nClick to copy")]:
            with self.subTest(status[0]):
                self.assertEqual(self.indicator(1, status).toolTip(), tooltip)


if __name__ == "__main__":
    unittest.main()
