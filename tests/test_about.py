import unittest
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtTest import QTest

from autosplit64.gui.dialogs.about_dialog import AboutDialog
from tests.qt import qml

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

    def qml(self, name):
        return qml(self.about.view, name)

    def test_authors(self):
        self.assertEqual(self.qml("authors").property("text").splitlines()[0], "Flo Wolfe")

    def test_github(self):
        with mock.patch.object(QtGui.QDesktopServices, "openUrl") as open_url:
            QtCore.QMetaObject.invokeMethod(self.qml("github"), "clicked")
        self.assertEqual(open_url.call_args.args[0].toString(), "https://github.com/florence-wolfe/AutoSplit64plusplus")

    def test_buttons_show_a_pointer(self):
        handlers = self.qml("github").findChildren(QtCore.QObject)
        cursors = [h.property("cursorShape") for h in handlers if h.metaObject().className().startswith("QQuickHoverHandler")]
        self.assertEqual(cursors, [QtCore.Qt.CursorShape.PointingHandCursor])


if __name__ == "__main__":
    unittest.main()
