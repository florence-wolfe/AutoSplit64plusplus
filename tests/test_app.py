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
                                 "Generate Reset Templates", "---", "Debug", "---", "Autostart", "SRL Mode",
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
            ("Edit Coordinates", "Choose what to capture and where the game is in it", False, no_role),
            ("Settings", "Connection to LiveSplit, detection thresholds and other settings", False, no_role),
            ("Generate Reset Templates", "Record what a console reset looks like in your capture, so resets are detected", False, no_role),
            ("Debug", "Show what split detection sees and does, and its logs", False, no_role),
            ("Autostart", "Start split detection when AutoSplit64++ opens, trying for up to 5 minutes", True, no_role),
            ("SRL Mode", "Don't reset the timer when you reset the console, e.g. in races", True, no_role),
            ("About", "Version and credits", False, no_role),
            ("Exit", "Quit AutoSplit64++", False, no_role)])

    def test_actions_open_their_dialog(self):
        for text, dialog in [("Edit Route", "route_editor"), ("Edit Coordinates", "capture_editor"),
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
            self.app.dialogs["debug_dialog"].save_debug_info_btn.click()
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
        self.assertEqual(self.app.right_panel.size(), QtCore.QSize(182, 259))

    def test_start_button_grows_while_hovered(self):
        button = self.app.start_btn
        normal = (button.geometry().getRect())
        self.app._on_start_btn_hover(True)
        width, height = self.app.start_pixmap.width(), self.app.start_pixmap.height()
        self.assertEqual(button.size(), QtCore.QSize(int(width * 1.1), int(height * 1.1)))
        self.assertEqual(button.pos(), QtCore.QPoint(23 - (int(width * 1.1) - width) // 2, 180 - (int(height * 1.1) - height) // 2))
        self.app._on_start_btn_hover(False)
        self.assertEqual(button.geometry().getRect(), normal)

    def test_split_index_past_the_end_shows_the_last_split(self):
        self.app.split_list.clear()
        for title in ("A", "B"):
            self.app.split_list.add_split(title, None)
        with mock.patch.object(self.app.split_list, "set_selected_index") as set_selected_index:
            self.app.update_display(5, 3, 4)
        set_selected_index.assert_called_once_with(1)
        self.assertEqual((self.app.star_count.star_count, self.app.star_count.split_star), (3, 4))

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
