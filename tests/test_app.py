import inspect
import unittest
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtTest import QTest

from autosplit64.gui.app import App
from tests.qt import close_window, qml, wait_until

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
        self.app._set_start_state("init")

        self.app.start_clicked()

        self.assertEqual(self.app.start_state, "start")
        self.stopped.assert_called_once()



class MenuTest(unittest.TestCase):
    def test_order(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            app = App()
        self.addCleanup(close_window, app)
        menu = QtWidgets.QMenu(app)
        app._populate_menu(menu)
        items = [a.text() if not a.isSeparator() else "---" for a in menu.actions()]
        self.assertEqual(items, ["Edit Route", "Open Route", "---", "Configure Capture", "Generate Reset Templates", "---",
                                 "Settings", "---", "Debug", "---", "Autostart", "SRL Mode",
                                 "---", "About", "---", "Exit"])


class MenuActionsTest(unittest.TestCase):
    def setUp(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.app = App()
        self.addCleanup(close_window, self.app)
        self.menu = QtWidgets.QMenu(self.app)
        self.app._populate_menu(self.menu)

    def action(self, text):
        return next(a for a in self.menu.actions() if a.text() == text)

    def test_tooltips_and_checkboxes(self):
        items = [(a.text(), a.toolTip(), a.isCheckable(), a.menuRole()) for a in self.menu.actions() if not a.isSeparator()]
        no_role = QtGui.QAction.MenuRole.NoRole
        self.assertEqual(items, [
            ("Edit Route", "Edit the splits of the current route, or create or open another route", False, no_role),
            ("Open Route", "Switch to another route", False, no_role),
            ("Configure Capture", "Choose what to capture and where the game is in it", False, no_role),
            ("Generate Reset Templates", "Record what a console reset looks like in your capture, so resets are detected", False, no_role),
            ("Settings", "Connection to LiveSplit, detection thresholds and other settings", False, no_role),
            ("Debug", "Show what split detection sees and does, and its logs", False, no_role),
            ("Autostart", "Start split detection when AutoSplit64++ opens, trying for up to 5 minutes", True, no_role),
            ("SRL Mode", "Don't reset the timer when you reset the console, e.g. in races", True, no_role),
            ("About", "Version and credits", False, no_role),
            ("Exit", "Quit AutoSplit64++", False, no_role)])

    def test_actions_open_their_dialog(self):
        for text, dialog in [("Edit Route", "route_editor"), ("Configure Capture", "capture_editor"),
                             ("Settings", "settings_dialog"), ("Generate Reset Templates", "reset_dialog"),
                             ("Debug", "debug_dialog"), ("About", "about_dialog")]:
            with self.subTest(text), mock.patch.object(self.app.dialogs[dialog], "show") as show:
                # The menu connects to show when it's filled
                self.menu = QtWidgets.QMenu(self.app)
                self.app._populate_menu(self.menu)
                self.action(text).trigger()
                show.assert_called_once()

    def test_open_route_lists_the_routes_and_from_file(self):
        routes = self.action("Open Route").menu().actions()
        self.assertEqual(routes[-1].text(), "From File")
        self.assertTrue(routes[-2].isSeparator())

    def save_debug_info(self, chosen, error=None):
        """ Save Debug Info in the Debug window, choosing `chosen` to save to """
        with mock.patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(chosen, "")) as dialog, \
             mock.patch("autosplit64.gui.app.debug_info.capture_frame", return_value=(None, "No capture")), \
             mock.patch("autosplit64.gui.app.debug_info.save", side_effect=error) as save, \
             mock.patch.object(QtWidgets.QMessageBox, "information") as information, \
             mock.patch.object(QtWidgets.QMessageBox, "warning") as warning:
            QtCore.QMetaObject.invokeMethod(qml(self.app.dialogs["debug_dialog"].view, "saveInfo"), "clicked")
        return dialog, save, information, warning

    def test_save_debug_info(self):
        dialog, save, information, warning = self.save_debug_info("/somewhere/debug.zip")
        self.assertTrue(dialog.call_args.args[2].endswith(".zip"))
        save.assert_called_once_with("/somewhere/debug.zip", None, "No capture")
        self.assertIn("/somewhere/debug.zip", information.call_args.args[2])
        warning.assert_not_called()

    def test_save_debug_info_cancelled(self):
        dialog, save, information, warning = self.save_debug_info("")
        save.assert_not_called()
        information.assert_not_called()

    def test_save_debug_info_failing(self):
        dialog, save, information, warning = self.save_debug_info("/read-only/debug.zip", PermissionError("Permission denied"))
        information.assert_not_called()
        self.assertIn("Permission denied", warning.call_args.args[2])

    def from_file(self, chosen):
        """ Open Route -> From File, choosing `chosen` in the file dialog. Returns the dialog's file filter. """
        with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(chosen, "")) as dialog:
            self.app.open_route_browser()
        return dialog.call_args.args[3]

    def test_from_file_offers_routes_and_livesplit_splits(self):
        file_filter = self.from_file("")
        self.assertIn("*.as64", file_filter)
        self.assertIn("*.lss", file_filter)

    def test_from_file_switches_to_a_route(self):
        with mock.patch.object(self.app, "_save_open_route") as switch:
            self.from_file("/routes/16 star.as64")
        switch.assert_called_once_with("/routes/16 star.as64")

    def test_from_file_converts_livesplit_splits_in_the_route_editor(self):
        editor = self.app.dialogs["route_editor"]
        with mock.patch.object(self.app, "_save_open_route") as switch, mock.patch.object(editor, "show") as show, \
             mock.patch.object(editor, "convert_lss") as convert:
            self.from_file("/splits/16 star.LSS")
        # Like the Route Editor's Open, to check the guessed details before saving the route
        show.assert_called_once()
        convert.assert_called_once_with("/splits/16 star.LSS")
        switch.assert_not_called()


class MainWindowTest(unittest.TestCase):
    def setUp(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.app = App()
        self.addCleanup(close_window, self.app)

    def on_top(self):
        return bool(self.app.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint)

    def test_always_on_top_follows_the_setting(self):
        from autosplit64.core import config
        get = config.get
        for on_top in (True, False):
            # Applying settings starts the LiveSplit One server in its connection mode, the default on macOS
            with self.subTest(on_top), mock.patch.object(config, "get", lambda section, key=None: on_top if key == "on_top" else get(section, key)), \
                    mock.patch("autosplit64.gui.app.livesplit.connect"), mock.patch("autosplit64.gui.app.livesplit_one.stop_server"):
                self.app.settings_updated()
                self.assertIs(self.on_top(), on_top)
                self.assertTrue(self.app.isVisible())

    def test_size(self):
        self.assertEqual((self.app.minimumWidth(), self.app.minimumHeight()), (365, 259))
        panel = qml(self.app.view, "rightPanel")
        self.assertEqual((panel.width(), panel.height()), (182, 259))

    def test_start_button_grows_while_hovered(self):
        button = qml(self.app.view, "start")
        center = button.mapToScene(QtCore.QPointF(button.width() / 2, button.height() / 2)).toPoint()
        # Rendered first: before, the mouse over it isn't hovering. Hovering is then updated with the next frame.
        frames = []
        self.app.view.frameSwapped.connect(lambda: frames.append(True))
        self.app.view.update()
        wait_until(lambda: frames)
        QTest.mouseMove(self.app.view, center)
        wait_until(lambda: button.scale() != 1)
        self.assertAlmostEqual(button.scale(), 1.1)
        QTest.mouseMove(self.app.view, QtCore.QPoint(10, 10))
        wait_until(lambda: button.scale() == 1)
        self.assertAlmostEqual(button.scale(), 1)

    def test_split_index_past_the_end_shows_the_last_split(self):
        self.app.main.update(splits=[{"title": title, "icon": ""} for title in ("A", "B")])
        self.app.update_display(5, 3, 4)
        self.assertEqual(qml(self.app.view, "splitList").property("currentIndex"), 1)
        self.assertEqual(qml(self.app.view, "starCount").property("text"), "3  /  4")

    def test_split_star_of_none_is_a_dash(self):
        self.app.update_display(0, 3, -1)
        self.assertEqual(qml(self.app.view, "starCount").property("text"), "3  /  -")

    def test_quitting_stops_detection_and_installs_a_downloaded_update(self):
        stopped = mock.Mock()
        self.app.stop.connect(stopped)
        with mock.patch.object(self.app.updates, "on_quit") as on_quit, \
                mock.patch.object(self.app.dialogs["debug_dialog"], "close") as close_output:
            self.app.close()
        stopped.assert_called()
        on_quit.assert_called()
        close_output.assert_called()
        self.assertFalse(self.app.isVisible())


class MenuFromFileTest(unittest.TestCase):
    """ Open Route -> From File in the main window's menu, whose file dialog the menu closes for """

    def setUp(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.app = App()
        self.addCleanup(close_window, self.app)

    def test_menu_outlives_its_entry_opening_the_file_dialog(self):
        QtCore.QMetaObject.invokeMethod(qml(self.app.view, "menuButton"), "clicked")
        objects = lambda: self.app.view.rootObject().findChildren(QtCore.QObject)
        wait_until(lambda: any(o.metaObject().className().startswith("QQuickMenu") and o.property("opened") for o in objects()))
        from_file = next(o for o in objects() if o.property("text") == "From File" and o.property("key") is not None)

        # Whether the entry was deleted while its trigger still ran
        deleted = []
        from_file.destroyed.connect(lambda: deleted.append(
            any(frame.function == "trigger" and frame.filename.endswith("app.py") for frame in inspect.stack())))

        def file_dialog(*args):
            # A modal window takes the focus from the menu, which closes it, but not in the tests' offscreen platform
            for menu in objects():
                if menu.metaObject().className().startswith("Menu_QMLTYPE") and menu.property("opened"):
                    QtCore.QMetaObject.invokeMethod(menu, "close")
            # Like the file dialog, it has its own event loop, in which the closed menu deletes itself
            dialog = QtWidgets.QDialog(self.app)
            QtCore.QTimer.singleShot(500, dialog.reject)
            dialog.exec()
            return "", ""

        with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileName", side_effect=file_dialog) as dialog:
            QtCore.QMetaObject.invokeMethod(from_file, "triggered")
            wait_until(lambda: dialog.called and deleted, timeout=3)

        dialog.assert_called_once()
        # Deleted while its trigger runs, Qt crashes once the dialog returns to it, which ends AutoSplit64++ on Windows
        self.assertEqual(deleted, [False])


class DragTest(unittest.TestCase):
    """ Dragging the main window anywhere moves it """

    def setUp(self):
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.app = App()
        self.addCleanup(close_window, self.app)
        self.app.move(100, 100)
        QtWidgets.QApplication.processEvents()
        self.start = self.app.pos()

    def mouse(self, action, x, y):
        """ A mouse press, move or release on the split list, which is no button """
        point = QtCore.QPoint(x, y)
        if action == "move":
            QTest.mouseMove(self.app.view, point)
        else:
            getattr(QTest, f"mouse{action.title()}")(self.app.view, QtCore.Qt.MouseButton.LeftButton,
                                                       QtCore.Qt.KeyboardModifier.NoModifier, point)

    def drag(self, system_move):
        with mock.patch.object(QtGui.QWindow, "startSystemMove", return_value=system_move) as start_system_move:
            self.mouse("press", 10, 10)
            self.mouse("move", 60, 40)
        return start_system_move

    def test_window_manager_moves_the_window(self):
        start_system_move = self.drag(system_move=True)
        start_system_move.assert_called_once()
        self.assertEqual(self.app.pos(), self.start)

    def test_no_drag_while_the_menu_is_open(self):
        # On Windows, pressing a menu entry over the main window presses the main window too, and moving it raised it
        # over the menu, whose entry then never got the click
        def menu():
            return next((window for window in QtGui.QGuiApplication.topLevelWindows()
                         if window.metaObject().className() == "QQuickPopupWindow" and window.isVisible()), None)

        QtCore.QMetaObject.invokeMethod(qml(self.app.view, "menuButton"), "clicked")
        wait_until(menu)
        start_system_move = self.drag(system_move=True)
        start_system_move.assert_not_called()
        self.assertEqual(self.app.pos(), self.start)

        # And again once it's closed
        self.mouse("release", 60, 40)
        QTest.keyClick(menu(), QtCore.Qt.Key.Key_Escape)
        wait_until(lambda: not menu())
        self.drag(system_move=True).assert_called_once()

    def test_moves_it_itself_when_the_window_manager_cant(self):
        self.drag(system_move=False)
        self.assertEqual(self.app.pos(), self.start + QtCore.QPoint(50, 30))

    def test_no_jump_without_a_press_on_the_window(self):
        self.mouse("move", 60, 40)
        self.assertEqual(self.app.pos(), self.start)

    def test_no_drag_after_release(self):
        self.drag(system_move=False)
        self.mouse("release", 60, 40)
        moved = self.app.pos()
        self.mouse("move", 90, 90)
        self.assertEqual(self.app.pos(), moved)

if __name__ == "__main__":
    unittest.main()
