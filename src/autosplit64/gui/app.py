import os
import logging
from functools import partial
import re
from datetime import datetime
from pathlib import Path
from PyQt6 import QtCore, QtGui, QtWidgets
from autosplit64.core import app_location, debug_info, route_loader, config, livesplit, livesplit_one
from autosplit64.core.resource_utils import base_path, absolute_path, rel_to_abs
from . import constants
from . import theme
from .dialogs import AboutDialog, CaptureEditor, SettingsDialog, RouteEditor, ResetGeneratorDialog, DebugDialog
from .qml_view import Values, qml_window
from .server_status import ServerStatus
from .tip_window import TipWindow
from .updates import Updates, UpdateBadge

log = logging.getLogger(".log")


def _window_flags(on_top):
    flags = QtCore.Qt.WindowType.Window
    return flags | QtCore.Qt.WindowType.WindowStaysOnTopHint if on_top else flags


class Main(Values):
    """
    What MainWindow.qml shows, in values: the route's splits, the current one, the star counts, the start
    button's state, the connection's status, the version and the theme's colors for them. Its other signals
    are the window's clicks and drags, and menu() and trigger() are its menu.
    """
    start_clicked = QtCore.pyqtSignal()
    restart = QtCore.pyqtSignal()
    version_clicked = QtCore.pyqtSignal()
    # Global positions of a press on the window, and of the mouse while it's held
    press = QtCore.pyqtSignal(int, int)
    drag = QtCore.pyqtSignal(int, int)
    release = QtCore.pyqtSignal()

    def __init__(self, menu_items, set_general, copy_status, screen_top):
        """
        menu_items() are the menu's entries, see App._menu_items(), set_general(key, checked) sets a checkbox's
        setting, copy_status() copies the address, and screen_top() is where the window's screen's free space starts
        """
        super().__init__({"splits": [], "routeTitle": "", "current": 0, "starCount": "-", "splitStar": "-",
                         "start": "start", "statusColor": "gray", "statusTip": "", "statusLabel": "", "version": "", "update": False, "versionTip": "",
                         "muted": "gray", "green": "green"})
        self._menu_items = menu_items
        self._set_general = set_general
        self._copy_status = copy_status
        self._screen_top = screen_top
        self._actions = {}

    @QtCore.pyqtSlot(result=str)
    def copy_status(self):
        return self._copy_status()

    @QtCore.pyqtSlot(result=int)
    def screen_top(self):
        return self._screen_top()

    @QtCore.pyqtSlot(result="QVariantList")
    def menu(self):
        """ The menu's entries for the QML, by key, which trigger() is given """
        self._actions = {}

        def entries(items, prefix):
            result = []
            for i, item in enumerate(items):
                if item is None:
                    result.append({"separator": True})
                    continue
                text, tooltip, action = item
                key = f"{prefix}{i}"
                if isinstance(action, list):
                    result.append({"text": text, "tooltip": tooltip, "items": entries(action, key + ".")})
                elif isinstance(action, str):
                    result.append({"text": text, "tooltip": tooltip, "key": key, "checkable": True,
                                   "checked": bool(config.get("general", action))})
                    self._actions[key] = action
                else:
                    result.append({"text": text, "tooltip": tooltip, "key": key})
                    self._actions[key] = action
            return result
        return entries(self._menu_items(), "")

    @QtCore.pyqtSlot(str)
    def trigger(self, key):
        action = self._actions[key]
        if isinstance(action, str):
            self._set_general(action, not config.get("general", action))
        else:
            # Once the menu entry's handler has returned: a modal dialog, e.g. From File's, runs an event loop, in
            # which the menu, closed by the dialog taking the focus, deletes its entries, and Qt aborts on deleting
            # the one whose handler is running
            QtCore.QTimer.singleShot(0, action)


class App(QtWidgets.QMainWindow):
    start = QtCore.pyqtSignal()
    stop = QtCore.pyqtSignal()
    # The Stop button was clicked, as opposed to split detection being stopped for another reason
    stop_clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        self.autostarter_active = False
        super().__init__(parent=parent)

        # Window Properties
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        # macOS only shows tooltips in the active app otherwise
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setWindowIcon(QtGui.QIcon(base_path(constants.ICON_PATH)))
        self.setWindowTitle(constants.TITLE)

        # Dragging
        self._drag = False
        self._drag_position = None

        # What the window shows
        self.main = Main(self._menu_items, self._set_general, lambda: self.server_status.copy(),
                         lambda: self.screen().availableGeometry().top())
        self.server_status = ServerStatus(self)
        self.update_badge = UpdateBadge(constants.VERSION, self)
        self.server_status.changed.connect(self._show_status)
        self.update_badge.changed.connect(self._show_version)
        self.central_widget = QtWidgets.QWidget(self)
        self.view = qml_window(self.central_widget, "MainWindow", main=self.main, tips=TipWindow())
        # Split detection is running unless the start button offers to start it
        self.updates = Updates(self, self.update_badge, lambda: self.start_state != "start")

        # Route
        self.route = None
        # The split detection that started last, or None before the first start
        self.detection = None

        # Dialogs
        self.dialogs = {
            "about_dialog": AboutDialog(self),
            "capture_editor": CaptureEditor(self),
            "settings_dialog": SettingsDialog(self),
            "route_editor": RouteEditor(self),
            "reset_dialog": ResetGeneratorDialog(self),
            "debug_dialog": DebugDialog(self, detection=lambda: self.detection)
        }

        self._routes = {}
        self._load_route_dir()

        self.initialize()
        self.show()
        
        if config.get("general", "update_check"):
            self.updates.check()

        # macOS: offer to move the app out of Downloads, where updates may not install
        if config.get("general", "ask_to_move") and app_location.move_reason(app_location.running_app()):
            QtCore.QTimer.singleShot(0, self._offer_move_to_applications)
        
        # Handle splash screen closure
        try:
            import pyi_splash # type: ignore
            pyi_splash.close()
        except (ImportError, ModuleNotFoundError):
            pass
        
        QtCore.QTimer.singleShot(100, self.autostart)

    def _offer_move_to_applications(self):
        app = app_location.running_app()
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Move to Applications")
        if app_location.move_reason(app) == app_location.TRANSLOCATED:
            box.setText("AutoSplit64++ is running from where it was downloaded. Move it to your Applications folder?")
            box.setInformativeText("Until it's moved, macOS runs it from a temporary read-only copy, "
                                   "where updates can't be installed. It reopens from Applications, "
                                   "and you can delete the downloaded copy.")
        else:
            box.setText("AutoSplit64++ is running from your Downloads folder. Move it to your Applications folder?")
            box.setInformativeText("It reopens from Applications, and you can delete the copy in Downloads.")
        move = box.addButton("Move to Applications", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Not Now", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        never = box.addButton("Don't Ask Again", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        if box.clickedButton() is never:
            config.set_key("general", "ask_to_move", False)
            config.save_config()
        if box.clickedButton() is not move:
            return

        try:
            moved = app_location.move_to(app, app_location.applications_folder())
        except Exception as e:
            log.warning("Moving to Applications failed", exc_info=True)
            QtWidgets.QMessageBox.warning(self, "Move to Applications", f"Couldn't move AutoSplit64++:\n\n{e}")
            return
        app_location.reopen_after_exit(moved)
        self.close()
        QtWidgets.QApplication.quit()

    def set_always_on_top(self, on_top):
        self.setWindowFlags(_window_flags(on_top))
        self.show()

    def initialize(self):
        # Configure window
        self.setWindowFlags(_window_flags(config.get("general", "on_top")))
        self.setMinimumSize(constants.WIDTH, constants.HEIGHT)
        self.resize(constants.WIDTH, constants.HEIGHT)
        self.setCentralWidget(self.central_widget)
        self._show_colors()

        self.open_route()

        # Connections
        self.main.start_clicked.connect(self.start_clicked)
        self.main.restart.connect(self._reset)
        self.main.version_clicked.connect(self.update_badge.clicked)
        self.main.press.connect(self._press)
        self.main.drag.connect(self._drag_to)
        self.main.release.connect(self._release)
        self.dialogs["route_editor"].route_updated.connect(self._on_route_update)
        self.dialogs["settings_dialog"].applied.connect(self.settings_updated)
        self.dialogs["debug_dialog"].save_debug_info.connect(self.save_debug_info)
        self.dialogs["capture_editor"].applied.connect(self._reset)
        self.dialogs["reset_dialog"].applied.connect(self._reset)

        # On macOS, the menu is also in the menu bar
        if self.menuBar().isNativeMenuBar():
            self.menu_bar_menu = self.menuBar().addMenu("Options")
            self.menu_bar_menu.aboutToShow.connect(self._rebuild_menu_bar_menu)
            self._populate_menu(self.menu_bar_menu)

    @property
    def start_state(self):
        """ What the start button offers: "start", "stop", or "init" while starting """
        return self.main.values["start"]

    def _set_start_state(self, state):
        self.main.update(start=state)

    def _show_star_count(self, star_count, split_star):
        self.main.update(starCount=str(star_count), splitStar="-" if split_star == -1 else str(split_star))

    def changeEvent(self, event):
        # e.g. another theme
        if event.type() == QtCore.QEvent.Type.PaletteChange:
            self._show_colors()
        super().changeEvent(event)

    def _show_colors(self):
        """ The theme's colors for the status, version and menu button """
        palette = QtWidgets.QApplication.palette()
        self.main.update(muted=theme.muted(palette).name(), green=theme.status_color("green").name())
        self._show_status()
        self._show_version()

    def _show_status(self):
        color = self.server_status.color()
        self.main.update(statusColor=theme.status_color(color).name() if color else self.main.values["muted"],
                         statusTip=self.server_status.tooltip, statusLabel=self.server_status.label)

    def _show_version(self):
        badge = self.update_badge
        self.main.update(version=badge.version, update=badge.update is not None, versionTip=badge.tooltip)

    def settings_updated(self):
        self.set_always_on_top(config.get("general", "on_top"))
        # Start the LiveSplit One server right away, or stop it when switching modes
        if config.get("connection", "ls_connection_type") == 2:
            livesplit.connect()
        else:
            livesplit_one.stop_server()
        self.server_status.refresh()
        self._reset()

    def update_display(self, split_index, current_star, split_star):
        self.main.update(current=max(0, min(split_index, len(self.main.values["splits"]) - 1)))
        self._show_star_count(current_star, split_star)

    def autostart(self):
        if config.get("general", "auto_start") and self.start_state == "start":
            self.autostarter_active = True
            self._set_start_state("init")

            # While autostarter is active, try every 2000ms to start the timer
            def try_start():
                if self.autostarter_active:
                    self.start.emit()
                    QtCore.QTimer.singleShot(2000, try_start)
            try_start()
            # Quit the autostarter after trying for 5 minutes
            def quit_autostarter():
                if self.autostarter_active:
                    self.autostarter_active = False
                    self._set_start_state("start")
                    self.stop.emit()
                    self.display_error_message("Failed to auto start timer.", "AutoStart Error")
            QtCore.QTimer.singleShot(300000, quit_autostarter)

    def start_clicked(self):
        if self.start_state in ("stop", "init"):
            self.autostarter_active = False
            if self.start_state == "stop":
                self.stop_clicked.emit()
            self._set_start_state("start")
            self.main.update(current=0)
            # No route is loaded when e.g. autostart is retrying without one
            if self.route:
                self._show_star_count(self.route.initial_star, self.route.splits[0].star_count)
            self.stop.emit()
        elif self.start_state == "start":
            self._set_start_state("init")
            self.start.emit()

    def set_started(self, started):
        if started:
            self._set_start_state("stop")
            self.autostarter_active = False
        # The autostarter keeps showing that it's starting
        elif not self.autostarter_active:
            self._set_start_state("start")

    def open_route(self):
        self._reset()

        if config.get("route", "path") == "":
            return

        route = route_loader.load_or_none(config.get("route", "path"))

        if not route:
            self.display_error_message("Could not load route", "Route Error")
            self._load_route_dir()
            config.set_key("route", "path", "")
            config.save_config()
            return False

        error = route_loader.validate_route(route)

        if error:
            self.display_error_message(error, "Route Error")
            return False

        self.route = route

        self._show_star_count(route.initial_star, route.splits[0].star_count)
        self.main.update(current=0, routeTitle=" · ".join(filter(None, [route.category, route.title])), splits=[
            {"title": split.title,
             "icon": QtCore.QUrl.fromLocalFile(rel_to_abs(split.icon_path)).toString() if split.icon_path else "",
             "star": "" if split.star_count == -1 else str(split.star_count), "type": split.split_type}
            for split in route.splits])

        return True

    def open_route_browser(self):
        """ Show native file dialog to select a route to use, or LiveSplit splits to convert to one. """
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Route", absolute_path("routes"),
                                                             "Routes and LiveSplit Splits (*.as64 *.lss)")

        if not file_path:
            return
        # Converted in the Route Editor, like its Open does, to check the guessed details before saving it
        if file_path.lower().endswith(".lss"):
            self.dialogs["route_editor"].show()
            self.dialogs["route_editor"].convert_lss(file_path)
        else:
            self._save_open_route(file_path)

    def _rebuild_menu_bar_menu(self):
        # Rebuilt on every open, like the right-click menu, so routes and checkboxes are current
        for submenu in self.menu_bar_menu.findChildren(QtWidgets.QMenu):
            submenu.deleteLater()
        self.menu_bar_menu.clear()
        self._populate_menu(self.menu_bar_menu)

    def _menu_items(self):
        """
        The menu's entries, for the window's menu and the menu bar: (text, tooltip, action) with action a
        callable, a list of entries for a submenu, or a general setting's key for a checkbox. None is a separator.
        """
        routes = []
        for category in sorted(self._routes, key=lambda text:[int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]):
            entries = [(title, "", partial(self._save_open_route, path)) for title, path in self._routes[category]]
            if len(entries) == 1 or category == "":
                routes += entries
            else:
                routes.append((str(category), "", entries))
        routes += [None, ("From File", "Open a route (.as64) from anywhere, or LiveSplit splits (.lss) to convert to a route",
                          self.open_route_browser)]

        return [
            ("Edit Route", "Edit the splits of the current route, or create or open another route", self.dialogs["route_editor"].show),
            ("Open Route", "Switch to another route", routes),
            None,
            ("Configure Capture", "Choose what to capture and where the game is in it", self._edit_coordinates),
            ("Generate Reset Templates", "Record what a console reset looks like in your capture, so resets are detected", self.dialogs["reset_dialog"].show),
            None,
            ("Settings", "Connection to LiveSplit, detection thresholds and other settings", self.dialogs["settings_dialog"].show),
            None,
            ("Debug", "Show what split detection sees and does, and its logs", self.dialogs["debug_dialog"].show),
            None,
            ("Autostart", "Start split detection when AutoSplit64++ opens, trying for up to 5 minutes", "auto_start"),
            ("SRL Mode", "Don't reset the timer when you reset the console, e.g. in races", "srl_mode"),
            None,
            ("About", "Version and credits", self.dialogs["about_dialog"].show),
            None,
            ("Exit", "Quit AutoSplit64++", self.close),
        ]

    def _populate_menu(self, menu, items=None):
        """ Fill a QMenu with the menu's entries, see _menu_items(). The menu bar's. """
        # Qt menus only show tooltips when asked to
        menu.setToolTipsVisible(True)
        for item in self._menu_items() if items is None else items:
            if item is None:
                menu.addSeparator()
                continue
            text, tooltip, slot = item
            if isinstance(slot, list):
                submenu = QtWidgets.QMenu(text, menu)
                self._populate_menu(submenu, slot)
                action = menu.addMenu(submenu)
            elif isinstance(slot, str):
                action = QtGui.QAction(text, menu, checkable=True)
                menu.addAction(action)
                action.setChecked(config.get("general", slot))
                action.triggered.connect(partial(self._set_general, slot))
            else:
                action = menu.addAction(text)
                action.triggered.connect(slot)
            action.setToolTip(tooltip)
            # Keep About, Settings and Exit in this menu instead of macOS moving them to the application menu
            action.setMenuRole(QtGui.QAction.MenuRole.NoRole)

    def save_debug_info(self):
        default = Path.home() / f"AutoSplit64++ debug info {datetime.now():%Y-%m-%d %H-%M}.zip"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Debug Info", str(default), "Zip Files (*.zip)")
        if not path:
            return
        try:
            debug_info.save(path, *debug_info.capture_frame(self.detection))
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Save Debug Info", f"Couldn't save the debug info:\n\n{e}")
            return
        QtWidgets.QMessageBox.information(self, "Save Debug Info", f"Saved to {path}. Please send it with your bug report.")

    def _set_general(self, key, checked):
        config.set_key("general", key, checked)
        config.save_config()
        if key == "auto_start":
            self.autostart()

    def _edit_coordinates(self):
        self.dialogs["capture_editor"].show()
        self.dialogs["debug_dialog"].close()

    def _press(self, x, y):
        # Let the window manager move the window: smoother, and the only way on Wayland
        if self.windowHandle().startSystemMove():
            return
        self._drag = True
        self._drag_position = QtCore.QPoint(x, y) - self.pos()

    def _release(self):
        self._drag = False

    def _drag_to(self, x, y):
        # Only drags that started on the window move it
        if self._drag:
            self.move(QtCore.QPoint(x, y) - self._drag_position)

    def display_error_message(self, message, title="Error"):
        """
        Display a warning dialog with given title and message
        :param title: Window title
        :param message: Warning/error message
        :return:
        """
        if self.autostarter_active:
            return
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec()

    def _load_route_dir(self):
        self._routes = {}

        for file in os.listdir("routes"):
            if file.endswith(".as64"):
                route = route_loader.load_or_none("routes/" + file)

                if route:
                    category = route.category

                    self._routes.setdefault(category, []).append([route.title, "routes/" + file])

    def _on_route_update(self):
        self._load_route_dir()
        self.open_route()

    def _save_open_route(self, file_path):
        prev_route = config.get("route", "path")
        config.set_key("route", "path", file_path)
        config.save_config()

        if not self.open_route():
            config.set_key("route", "path", prev_route)
            config.save_config()
            self.open_route()

    def _reset(self):
        if self.start_state == "stop":
            self._stop()
            self._set_start_state("init")
            self.start.emit()
        else:
            self._stop()

    def _stop(self):
        self.stop.emit()
        self.set_started(False)

    def closeEvent(self, event):
        self.dialogs["debug_dialog"].close()
        self.stop.emit()
        self.updates.on_quit()
        event.accept()
