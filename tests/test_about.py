import unittest
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtTest import QTest

from autosplit64.gui.dialogs.about_dialog import AboutDialog

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class AboutTest(unittest.TestCase):
    def setUp(self):
        self.about = AboutDialog()
        self.addCleanup(self.about.deleteLater)

    def test_normal_movable_window(self):
        self.assertFalse(self.about.windowFlags() & QtCore.Qt.WindowType.FramelessWindowHint)
        self.about.show()
        QTest.mouseClick(self.about, QtCore.Qt.MouseButton.LeftButton)
        self.assertTrue(self.about.isVisible())

    def test_authors(self):
        self.assertEqual(self.about.author_lb.text().splitlines()[0], "Flo Wolfe")

    def test_github(self):
        with mock.patch.object(QtGui.QDesktopServices, "openUrl") as open_url:
            self.about.github_btn.click()
        self.assertEqual(open_url.call_args.args[0].toString(), "https://github.com/florence-wolfe/AutoSplit64plusplus")


if __name__ == "__main__":
    unittest.main()
