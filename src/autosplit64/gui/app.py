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
from .widgets import PictureButton, StateButton, StarCountDisplay, SplitListWidget, ServerStatusIndicator, MenuButton, UpdateBadge
from .dialogs import AboutDialog, CaptureEditor, SettingsDialog, RouteEditor, ResetGeneratorDialog, DebugDialog
from .updates import Updates


def _window_flags(on_top):
    flags = QtCore.Qt.WindowType.Window
    return flags | QtCore.Qt.WindowType.WindowStaysOnTopHint if on_top else flags


class App(QtWidgets.QMainWindow):
    start = QtCore.pyqtSignal()
    stop = QtCore.pyqtSignal()

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

        # Pixmaps
        self.start_pixmap = QtGui.QPixmap(base_path(constants.START_PATH))
        self.stop_pixmap = QtGui.QPixmap(base_path(constants.STOP_PATH))
        self.init_pixmap = QtGui.QPixmap(base_path(constants.INIT_PATH))

        # Widgets
        self.central_widget = QtWidgets.QWidget(self)
        self.central_layout = QtWidgets.QHBoxLayout(self.central_widget)
        # Fixed size panel for the star, star count and start button, which keep their positions in it
        self.right_panel = QtWidgets.QWidget(self.central_widget)
        self.star_count = StarCountDisplay(parent=self.right_panel)
        self.star_btn = PictureButton(QtGui.QPixmap(base_path(constants.STAR_PATH)),
                                      pixmap_pressed=QtGui.QPixmap(base_path(constants.STAR_HOVER_PATH)),
                                      pixmap_hover=QtGui.QPixmap(base_path(constants.STAR_HOVER_PATH)),
                                      parent=self.right_panel)
        self.start_btn_initial_x = 23
        self.start_btn_initial_y = 180
        self.start_btn = StateButton(self.start_pixmap, self.start_pixmap, parent=self.right_panel)
        self.split_list = SplitListWidget(self.central_widget)
        self.server_status = ServerStatusIndicator(self.central_widget)
        self.menu_button = MenuButton(self.central_widget)
        self.update_badge = UpdateBadge(constants.VERSION, self.central_widget)
        # Split detection is running unless the start button offers to start it
        self.updates = Updates(self, self.update_badge, lambda: self.start_btn.get_state() != "start")

        # Font
        self.button_font = QtGui.QFont("Tw Cen MT", 14)
        self.start_count_font = QtGui.QFont("Tw Cen MT", 20)

        # Route
        self.route = None

        # Dialogs
        self.dialogs = {
            "about_dialog": AboutDialog(self),
            "capture_editor": CaptureEditor(self),
            "settings_dialog": SettingsDialog(self),
            "route_editor": RouteEditor(self),
            "reset_dialog": ResetGeneratorDialog(self),
            "debug_dialog": DebugDialog(self)
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
            logging.getLogger(".log").warning("Moving to Applications failed", exc_info=True)
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

        # Configure Central Widget
        self.central_widget.setBackgroundRole(QtGui.QPalette.ColorRole.Base)
        self.central_widget.setAutoFillBackground(True)
        self.setCentralWidget(self.central_widget)

        # The split list takes up all extra space, the right panel stays centered
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.central_layout.addWidget(self.split_list, 1)
        self.central_layout.addWidget(self.right_panel, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.right_panel.setFixedSize(182, constants.HEIGHT)

        # Configure Other Widgets
        self.star_btn.move(59, 35)

        self.star_count.setFixedWidth(150)
        self.star_count.move(14, 115)
        self.star_count.setFont(self.start_count_font)
        self.star_count.star_count = "-"
        self.star_count.split_star = "-"

        self.start_btn.move(self.start_btn_initial_x, self.start_btn_initial_y)
        self.start_btn.add_state("start", self.start_pixmap, "", "Start split detection")
        self.start_btn.add_state("stop", self.stop_pixmap, "", "Stop split detection. Your timer isn't affected.")
        self.start_btn.add_state("init", self.init_pixmap, "", "Starting split detection... Click to cancel.")
        self.start_btn.set_state("start")

        # Add hover effects
        self.start_btn.enterEvent = lambda e: self._on_start_btn_hover(True)
        self.start_btn.leaveEvent = lambda e: self._on_start_btn_hover(False)

        self.split_list.setFont(self.button_font)
        self.split_list.setMinimumSize(183, constants.HEIGHT)

        self.open_route()

        # Connections
        self.start_btn.clicked.connect(self.start_clicked)
        self.star_btn.clicked.connect(self._reset)
        self.star_btn.setToolTip("Restart split detection, which picks up from your timer's current split. "
                                 "The timer itself isn't affected.")
        self.dialogs["route_editor"].route_updated.connect(self._on_route_update)
        self.dialogs["settings_dialog"].applied.connect(self.settings_updated)
        self.dialogs["debug_dialog"].save_debug_info.connect(self.save_debug_info)
        self.dialogs["capture_editor"].applied.connect(self._reset)
        self.dialogs["reset_dialog"].applied.connect(self._reset)
        self.menu_button.clicked.connect(self._show_button_menu)

        # On macOS, the right-click menu is also in the menu bar
        if self.menuBar().isNativeMenuBar():
            self.menu_bar_menu = self.menuBar().addMenu("Options")
            self.menu_bar_menu.aboutToShow.connect(self._rebuild_menu_bar_menu)
            self._populate_menu(self.menu_bar_menu)

    def settings_updated(self):
        self.set_always_on_top(config.get("general", "on_top"))
        # Start the LiveSplit One server right away, or stop it when switching modes
        if config.get("connection", "ls_connection_type") == 2:
            livesplit.connect()
        else:
            livesplit_one.stop_server()
        self.server_status.refresh()
        self._reset()

    def resizeEvent(self, event):
        # Keep the server status in the top right corner, the menu button in the bottom right and the
        # version at the bottom left of the right panel, level with the menu button, above the other widgets
        size = self.central_widget.size()
        self.server_status.move(size.width() - self.server_status.size().width() - 6, 6)
        self.server_status.raise_()
        self.menu_button.move(size.width() - self.menu_button.size().width() - 8, size.height() - self.menu_button.size().height() - 8)
        self.menu_button.raise_()
        self.update_badge.move(size.width() - self.right_panel.size().width() + 8,
                               self.menu_button.y() + (self.menu_button.size().height() - self.update_badge.size().height()) // 2)
        self.update_badge.raise_()
        super().resizeEvent(event)

    def _show_button_menu(self):
        """ The right-click menu, opened from the menu button """
        menu = QtWidgets.QMenu(self)
        self._populate_menu(menu)
        # Open upwards from the button, which is in the bottom corner
        menu.exec(self.menu_button.mapToGlobal(QtCore.QPoint(self.menu_button.size().width() - menu.sizeHint().width(), -menu.sizeHint().height())))

    def update_display(self, split_index, current_star, split_star):
        self.split_list.set_selected_index(min(split_index, len(self.split_list.splits) - 1))
        self.star_count.star_count = current_star
        self.star_count.split_star = split_star

    def autostart(self):
        if config.get("general", "auto_start") and self.start_btn.get_state() == "start":
            self.autostarter_active = True
            self.start_btn.set_state("init")

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
                    self.start_btn.set_state("start")
                    self.stop.emit()
                    self.display_error_message("Failed to auto start timer.", "AutoStart Error")
            QtCore.QTimer.singleShot(300000, quit_autostarter)

    def start_clicked(self):
        if self.start_btn.get_state() in ("stop", "init"):
            self.autostarter_active = False
            self.start_btn.set_state("start")
            self.split_list.set_selected_index(0)
            # No route is loaded when e.g. autostart is retrying without one
            if self.route:
                self.star_count.star_count = self.route.initial_star
                self.star_count.split_star = self.route.splits[0].star_count
            self.stop.emit()
        elif self.start_btn.get_state() == "start":
            self.start_btn.set_state("init")
            self.start.emit()

    def set_started(self, started):
        if started:
            self.start_btn.set_state("stop")
            self.autostarter_active = False
        # The autostarter keeps showing that it's starting
        elif not self.autostarter_active:
            self.start_btn.set_state("start")

        self.start_btn.repaint()

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

        self.split_list.clear()
        self.star_count.star_count = route.initial_star
        self.star_count.split_star = route.splits[0].star_count

        for split in route.splits:
            icon = QtGui.QPixmap(rel_to_abs(split.icon_path)) if split.icon_path else None
            self.split_list.add_split(split.title, icon)

        self.split_list.repaint()

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

    def contextMenuEvent(self, event):
        context_menu = QtWidgets.QMenu(self)
        self._populate_menu(context_menu)
        context_menu.exec(self.mapToGlobal(event.pos()))

    def _rebuild_menu_bar_menu(self):
        # Rebuilt on every open, like the right-click menu, so routes and checkboxes are current
        for submenu in self.menu_bar_menu.findChildren(QtWidgets.QMenu):
            submenu.deleteLater()
        self.menu_bar_menu.clear()
        self._populate_menu(self.menu_bar_menu)

    def _populate_menu(self, menu):
        """ Fill menu with the app's actions. Used by the right-click menu and the menu bar. """
        route_menu = QtWidgets.QMenu("Open Route", menu)
        # Qt menus only show tooltips when asked to
        menu.setToolTipsVisible(True)
        route_menu.setToolTipsVisible(True)

        for category in sorted(self._routes, key=lambda text:[int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]):
            if len(self._routes[category]) == 1 or category == "":
                for route in self._routes[category]:
                    route_menu.addAction(route[0]).triggered.connect(partial(self._save_open_route, route[1]))
            else:
                category_menu = QtWidgets.QMenu(str(category), route_menu)
                route_menu.addMenu(category_menu)

                for route in self._routes[category]:
                    category_menu.addAction(route[0]).triggered.connect(partial(self._save_open_route, route[1]))

        route_menu.addSeparator()
        from_file_action = route_menu.addAction("From File")
        from_file_action.setToolTip("Open a route (.as64) from anywhere, or LiveSplit splits (.lss) to convert to a route")
        from_file_action.triggered.connect(self.open_route_browser)

        # (text, tooltip, slot) actions; None is a separator, and a (text, tooltip, setting) slot
        # is a checkbox for a general setting
        for item in [
            ("Edit Route", "Edit the splits of the current route, or create or open another route", self.dialogs["route_editor"].show),
            ("Open Route", "Switch to another route", route_menu),
            None,
            ("Edit Coordinates", "Choose what to capture and where the game is in it", self._edit_coordinates),
            None,
            ("Settings", "Connection to LiveSplit, detection thresholds and other settings", self.dialogs["settings_dialog"].show),
            None,
            ("Generate Reset Templates", "Record what a console reset looks like in your capture, so resets are detected", self.dialogs["reset_dialog"].show),
            None,
            ("Debug", "Show what split detection sees and does, and its logs", self.dialogs["debug_dialog"].show),
            None,
            ("Autostart", "Start split detection when AutoSplit64++ opens, trying for up to 5 minutes", "auto_start"),
            ("SRL Mode", "Don't reset the timer when you reset the console, e.g. in races", "srl_mode"),
            None,
            ("About", "Version and credits", self.dialogs["about_dialog"].show),
            None,
            ("Exit", "Quit AutoSplit64++", self.close),
        ]:
            if item is None:
                menu.addSeparator()
                continue
            text, tooltip, slot = item
            if isinstance(slot, QtWidgets.QMenu):
                action = menu.addMenu(slot)
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
        for action in menu.actions() + route_menu.actions():
            action.setMenuRole(QtGui.QAction.MenuRole.NoRole)

    def save_debug_info(self):
        default = Path.home() / f"AutoSplit64++ debug info {datetime.now():%Y-%m-%d %H-%M}.zip"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Debug Info", str(default), "Zip Files (*.zip)")
        if not path:
            return
        try:
            debug_info.save(path, *debug_info.capture_frame())
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

    def mousePressEvent(self, event):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton:
            # Let the window manager move the window: smoother, and the only way on Wayland
            if self.windowHandle().startSystemMove():
                event.accept()
                return
            self._drag = True
            self._drag_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseReleaseEvent(self, event):
        # buttons() no longer has the released button
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag = False
            event.accept()

    def mouseMoveEvent(self, event):
        # Only drags that started on the window move it
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self._drag:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

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
        if self.start_btn.get_state() == "stop":
            self._stop()
            self.start_btn.set_state("init")
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

    def _on_start_btn_hover(self, hovering):
        """ Grow the start button by 10% around its center while hovered """
        scale = 1.1 if hovering else 1.0
        width = int(self.start_pixmap.width() * scale)
        height = int(self.start_pixmap.height() * scale)
        self.start_btn.setFixedSize(width, height)
        self.start_btn.move(self.start_btn_initial_x - (width - self.start_pixmap.width()) // 2,
                            self.start_btn_initial_y - (height - self.start_pixmap.height()) // 2)
