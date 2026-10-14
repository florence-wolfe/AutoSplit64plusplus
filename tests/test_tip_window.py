import unittest
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtTest import QTest

from autosplit64.gui.tip_window import GAP, TipWindow
from tests.qt import close_window, qml_items, wait_until

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TipWindowTest(unittest.TestCase):
    def setUp(self):
        self.tips = TipWindow()
        self.addCleanup(self.tips.hide)
        self.screen = QtGui.QGuiApplication.primaryScreen().availableGeometry()

    def test_left_of_what_its_about(self):
        x, y = self.screen.left() + 400, self.screen.top() + 300
        self.tips.show("A tooltip", x, y, 50, 20)
        shown = self.tips.view.geometry()
        self.assertTrue(self.tips.view.isVisible())
        self.assertEqual(shown.right() + 1, x - GAP)
        self.assertLessEqual(abs(shown.center().y() - (y + 10)), 1)

    def test_right_where_the_screen_has_no_room_on_the_left(self):
        x = self.screen.left() + 10
        self.tips.show("A tooltip", x, self.screen.top() + 300, 50, 20)
        self.assertEqual(self.tips.view.geometry().left(), x + 50 + GAP)

    def test_long_ones_wrap(self):
        # The window as wide as the wrapped text, not the text on one line
        self.tips.show("A tooltip " * 30, self.screen.left() + 900, self.screen.top() + 300, 50, 20)
        one_line = self.tips.view.rootObject().property("implicitHeight")
        self.assertLessEqual(self.tips.view.width(), 320 + 16)
        self.tips.show("A tooltip", self.screen.left() + 900, self.screen.top() + 300, 50, 20)
        self.assertGreater(one_line, self.tips.view.rootObject().property("implicitHeight"))

    def test_hide(self):
        self.tips.show("A tooltip", self.screen.left() + 400, self.screen.top() + 300, 50, 20)
        self.tips.hide()
        self.assertFalse(self.tips.view.isVisible())


class MainWindowTipsTest(unittest.TestCase):
    """ The main window's tooltips are a window of their own, to the left of what they're about """

    def setUp(self):
        from autosplit64.gui.app import App
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.app = App()
        self.addCleanup(close_window, self.app)
        self.app.move(self.app.screen().availableGeometry().center())
        # Rendered, before which the mouse over it isn't hovering
        frames = []
        self.app.view.frameSwapped.connect(lambda: frames.append(True))
        self.app.view.update()
        wait_until(lambda: frames)
        self.tips = next(child for child in self.app.view.children() if child.metaObject().className() == "TipWindow")

    def hover(self, window, item):
        QTest.mouseMove(window, item.mapToScene(QtCore.QPointF(item.width() / 2, item.height() / 2)).toPoint())
        wait_until(self.tips.view.isVisible)

    def test_start_button(self):
        button = next(item for item in qml_items(self.app.view) if item.objectName() == "start")
        self.hover(self.app.view, button)
        self.assertEqual(self.tips.view.rootObject().property("text"), "Start split detection")
        left = int(button.mapToGlobal(QtCore.QPointF(0, 0)).x())
        self.assertEqual(self.tips.view.geometry().right() + 1, left - GAP)

    def test_menu_entries_beside_the_menu(self):
        button = next(item for item in qml_items(self.app.view) if item.objectName() == "menuButton")
        QtCore.QMetaObject.invokeMethod(button, "clicked")
        # Open, after its entries moved in
        wait_until(lambda: any(child.property("opened") for child in self.app.view.rootObject().findChildren(QtCore.QObject)
                               if child.metaObject().className().startswith("QQuickMenu")))
        menu = self.menu()
        items = [menu.contentItem()]
        for item in items:
            items.extend(item.childItems())
        debug = next(item for item in items if item.property("text") == "Debug" and item.property("hovered") is not None)
        # As on screens: the tests' offscreen platform has no hover effects, which turns hovering controls off
        debug.setProperty("hoverEnabled", True)

        self.hover(menu, debug)
        self.assertEqual(self.tips.view.rootObject().property("text"), "Show what split detection sees and does, and its logs")
        self.assertLessEqual(self.tips.view.geometry().right(), menu.geometry().left())
        # It's no popup, which would close the menu
        self.assertTrue(menu.isVisible())

    def test_menu_never_shows_below_the_button(self):
        button = next(item for item in qml_items(self.app.view) if item.objectName() == "menuButton")
        top = int(button.mapToGlobal(QtCore.QPointF(0, 0)).y())
        seen = []

        def record():
            menu = self.menu()
            if menu:
                seen.append(menu.geometry().bottom() + 1)
            return False

        QtCore.QMetaObject.invokeMethod(button, "clicked")
        wait_until(record, timeout=1)
        self.assertTrue(seen)
        # Not even for a frame, which is what looks like it opening downwards and then upwards
        self.assertLessEqual(max(seen), top)

    def menu(self):
        return next((window for window in QtGui.QGuiApplication.topLevelWindows()
                     if window.metaObject().className() == "QQuickPopupWindow" and window.isVisible()), None)


if __name__ == "__main__":
    unittest.main()
