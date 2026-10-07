import unittest
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.gui.app import App
from tests.qt import close_window

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class StartButtonTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("autosplit64.gui.updates.Updates.check")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = App()
        self.addCleanup(close_window, self.app)
        self.stopped = mock.Mock()
        self.app.stop.connect(self.stopped)

    def test_cancel_starting_without_route(self):
        # e.g. autostart retrying while no route is set
        self.app.route = None
        self.app.start_btn.set_state("init")

        self.app.start_clicked()

        self.assertEqual(self.app.start_btn.get_state(), "start")
        self.stopped.assert_called_once()



class MenuTest(unittest.TestCase):
    def test_order(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            app = App()
        self.addCleanup(close_window, app)
        menu = QtWidgets.QMenu(app)
        app._populate_menu(menu)
        items = [a.text() if not a.isSeparator() else "---" for a in menu.actions()]
        self.assertEqual(items, ["Edit Route", "Open Route", "---", "Edit Coordinates", "---", "Settings", "---",
                                 "Generate Reset Templates", "---", "Show Output", "---", "Autostart", "SRL Mode",
                                 "---", "About", "---", "Exit"])


class DragTest(unittest.TestCase):
    """ Dragging the main window anywhere moves it """

    def setUp(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.app = App()
        self.addCleanup(close_window, self.app)
        self.app.move(100, 100)
        QtWidgets.QApplication.processEvents()
        self.start = self.app.pos()

    def mouse(self, kind, x, y, held=True):
        button = QtCore.Qt.MouseButton.LeftButton
        point = QtCore.QPointF(self.start.x() + x, self.start.y() + y)
        buttons = button if held else QtCore.Qt.MouseButton.NoButton
        event = QtGui.QMouseEvent(kind, point, point, button if kind != QtCore.QEvent.Type.MouseMove else QtCore.Qt.MouseButton.NoButton,
                                  buttons, QtCore.Qt.KeyboardModifier.NoModifier)
        {QtCore.QEvent.Type.MouseButtonPress: self.app.mousePressEvent,
         QtCore.QEvent.Type.MouseMove: self.app.mouseMoveEvent,
         QtCore.QEvent.Type.MouseButtonRelease: self.app.mouseReleaseEvent}[kind](event)

    def drag(self, system_move):
        with mock.patch.object(QtGui.QWindow, "startSystemMove", return_value=system_move) as start_system_move:
            self.mouse(QtCore.QEvent.Type.MouseButtonPress, 10, 10)
            self.mouse(QtCore.QEvent.Type.MouseMove, 60, 40)
        return start_system_move

    def test_window_manager_moves_the_window(self):
        start_system_move = self.drag(system_move=True)
        start_system_move.assert_called_once()
        self.assertEqual(self.app.pos(), self.start)

    def test_moves_it_itself_when_the_window_manager_cant(self):
        self.drag(system_move=False)
        self.assertEqual(self.app.pos(), self.start + QtCore.QPoint(50, 30))

    def test_no_jump_without_a_press_on_the_window(self):
        self.mouse(QtCore.QEvent.Type.MouseMove, 60, 40)
        self.assertEqual(self.app.pos(), self.start)

    def test_no_drag_after_release(self):
        self.drag(system_move=False)
        self.mouse(QtCore.QEvent.Type.MouseButtonRelease, 60, 40, held=False)
        moved = self.app.pos()
        self.mouse(QtCore.QEvent.Type.MouseMove, 90, 90)
        self.assertEqual(self.app.pos(), moved)

if __name__ == "__main__":
    unittest.main()
