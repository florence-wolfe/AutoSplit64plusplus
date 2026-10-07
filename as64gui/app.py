import os
import logging
from functools import partial
import re
from PyQt6 import QtCore, QtGui, QtWidgets
from as64core import route_loader, config, livesplit, livesplit_one
from as64core.resource_utils import base_path, resource_path, absolute_path, rel_to_abs
from . import constants
from .widgets import PictureButton, StateButton, StarCountDisplay, SplitListWidget, ServerStatusIndicator, MenuButton, UpdateBadge
from .dialogs import AboutDialog, CaptureEditor, SettingsDialog, RouteEditor, ResetGeneratorDialog, OutputDialog
from .updates import Updates

class App(QtWidgets.QMainWindow):
    start = QtCore.pyqtSignal()
    stop = QtCore.pyqtSignal()
    closed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        self.autostarter_active = False
        super().__init__(parent=parent)

        # Window Properties
        self.title = constants.TITLE
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        # macOS only shows tooltips in the active app otherwise
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.width = 365
        self.height = 259
        self.setWindowIcon(QtGui.QIcon(base_path(constants.ICON_PATH)))

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
            "output_dialog": OutputDialog(self)
        }

        self._routes = {}
        self._load_route_dir()

        self.initialize()
        self.show()
        
        if config.get("general", "update_check"):
            self.updates.check()
        
        # Handle splash screen closure
        try:
            import pyi_splash # type: ignore
            pyi_splash.close()
        except (ImportError, ModuleNotFoundError):
            pass
        
        QtCore.QTimer.singleShot(100, self.autostart)
        

    def set_always_on_top(self, on_top):
        if on_top:
            self.setWindowFlags(QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(QtCore.Qt.WindowType.Window)

        self.show()

    def initialize(self):
        # Configure window
        self.setWindowTitle(self.title)

        if config.get("general", "on_top"):
            self.setWindowFlags(QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        else:
        #     self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
            self.setWindowFlags(QtCore.Qt.WindowType.Window)

        self.setMinimumSize(self.width, self.height)
        self.resize(self.width, self.height)

        # Configure Central Widget
        self.central_widget.setObjectName("central_widget")
        self.central_widget.setStyleSheet("QWidget#central_widget{background-color: rgb(23, 25, 27);}")
        self.setCentralWidget(self.central_widget)

        # The split list takes up all extra space, the right panel stays centered
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.central_layout.addWidget(self.split_list, 1)
        self.central_layout.addWidget(self.right_panel, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.right_panel.setFixedSize(182, self.height)

        # Configure Other Widgets
        self.star_btn.move(59, 35)

        self.star_count.setFixedWidth(150)
        self.star_count.move(14, 115)
        self.star_count.setFont(self.start_count_font)
        self.star_count.star_count = "-"
        self.star_count.split_star = "-"

        self.start_btn.move(self.start_btn_initial_x, self.start_btn_initial_y)
        # self.start_btn.setFont(self.button_font)
        # self.start_btn.setStyleSheet("font-weight: bold; color: black; font-size: 32px;")
        self.start_btn.add_state("start", self.start_pixmap, "", "Start split detection")
        self.start_btn.add_state("stop", self.stop_pixmap, "", "Stop split detection. Your timer isn't affected.")
        self.start_btn.add_state("init", self.init_pixmap, "", "Starting split detection... Click to cancel.")
        self.start_btn.set_state("start")
        
        # Add hover effects
        self.start_btn.enterEvent = lambda e: self._on_start_btn_hover(True)
        self.start_btn.leaveEvent = lambda e: self._on_start_btn_hover(False)

        self.split_list.setFont(self.button_font)
        self.split_list.setMinimumSize(183, self.height)

        self.open_route()

        # Connections
        self.start_btn.clicked.connect(self.start_clicked)
        self.star_btn.clicked.connect(self._reset)
        self.star_btn.setToolTip("Restart split detection, which picks up from your timer's current split. "
                                 "The timer itself isn't affected.")
        self.dialogs["route_editor"].route_updated.connect(self._on_route_update)
        self.dialogs["settings_dialog"].applied.connect(self.settings_updated)
        self.dialogs["capture_editor"].applied.connect(self._reset)
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
        if split_index > len(self.split_list.splits) - 1:
            index = len(self.split_list.splits) - 1
        else:
            index = split_index

        self.split_list.set_selected_index(index)
        self.star_count.star_count = current_star
        self.star_count.split_star = split_star

    def autostart(self):
        if config.get("general", "auto_start") and self.start_btn.get_state() == "start":
            self.autostarter_active = True
            self.start_btn.set_state("init")
            
            # While autostarter is active, try every 2000ms to start the timer
            self.counter = 0
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
        if self.start_btn.get_state() == "stop" or self.start_btn.get_state() == "init":
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
        elif self.autostarter_active:
            pass
        else:
            self.start_btn.set_state("start")
            # TODO: Set split list index to 0?

        self.start_btn.repaint()

    def open_route(self):
        self._reset()

        if config.get("route", "path") == "":
            return

        #try:
        route = route_loader.load_or_none(config.get("route", "path"))
        # except KeyError:
        #     self.display_error_message("Key Error", "Route Error")
        #     return False

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
            split_icon_path = split.icon_path

            if split_icon_path:
                split_icon_path = rel_to_abs(split_icon_path)
                icon = QtGui.QPixmap(split_icon_path)
            else:
                icon = None

            self.split_list.add_split(split.title, icon)

        self.split_list.repaint()

        return True

    def open_route_browser(self):
        """ Show native file dialog to select a .route file for use. """
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Route", absolute_path("routes"),
                                                             "AS64 Route Files (*.as64)")

        if file_path:
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
        from_file_action.setToolTip("Open a route (.as64) from anywhere")
        from_file_action.triggered.connect(self.open_route_browser)

        # Actions
        action = menu.addAction("Edit Route")
        action.setToolTip("Edit the splits of the current route, or create or open another route")
        action.triggered.connect(self.dialogs["route_editor"].show)
        menu.addMenu(route_menu).setToolTip("Switch to another route")
        menu.addSeparator()
        action = menu.addAction("Edit Coordinates")
        action.setToolTip("Choose what to capture and where the game is in it")
        action.triggered.connect(self._edit_coordinates)
        menu.addSeparator()
        action = menu.addAction("Settings")
        action.setToolTip("Connection to LiveSplit, detection thresholds and other settings")
        action.triggered.connect(self.dialogs["settings_dialog"].show)
        menu.addSeparator()
        action = menu.addAction("Generate Reset Templates")
        action.setToolTip("Record what a console reset looks like in your capture, so resets are detected")
        action.triggered.connect(self.dialogs["reset_dialog"].show)
        menu.addSeparator()
        action = menu.addAction("Show Output")
        action.setToolTip("Show what split detection sees: fades, X-Cams and star predictions")
        action.triggered.connect(self.dialogs["output_dialog"].show)
        menu.addSeparator()
        autostart_action = QtGui.QAction("Autostart", menu, checkable=True)
        menu.addAction(autostart_action)
        autostart_action.setChecked(config.get("general", "auto_start"))
        autostart_action.setToolTip("Start split detection when AutoSplit64++ opens, trying for up to 5 minutes")
        autostart_action.triggered.connect(self._set_autostart)
        srl_action = QtGui.QAction("SRL Mode", menu, checkable=True)
        menu.addAction(srl_action)
        srl_action.setChecked(config.get("general", "srl_mode"))
        srl_action.setToolTip("Don't reset the timer when you reset the console, e.g. in races")
        srl_action.triggered.connect(self._set_srl_mode)
        menu.addSeparator()
        action = menu.addAction("About")
        action.setToolTip("Version and credits")
        action.triggered.connect(self.dialogs["about_dialog"].show)
        menu.addSeparator()
        action = menu.addAction("Exit")
        action.setToolTip("Quit AutoSplit64++")
        action.triggered.connect(self.close)

        # Keep About, Settings and Exit in this menu instead of macOS moving them to the application menu
        for action in menu.actions() + route_menu.actions():
            action.setMenuRole(QtGui.QAction.MenuRole.NoRole)

    def _set_srl_mode(self, checked):
        config.set_key("general", "srl_mode", checked)
        config.save_config()

    def _set_autostart(self, checked):
        config.set_key("general", "auto_start", checked)
        config.save_config()
        self.autostart()

    def _edit_coordinates(self):
        self.dialogs["capture_editor"].show()
        try:
            self.dialogs["output_dialog"].close()
        except AttributeError:
            pass

    def mousePressEvent(self, event):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton:
            self._drag = True
            self._drag_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

        self.dialogs["about_dialog"].close()

    def mouseReleaseEvent(self, event):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton:
            self._drag = False
            event.accept()

    def mouseMoveEvent(self, event):
        try:
            if event.buttons() == QtCore.Qt.MouseButton.LeftButton:
                try:
                    self.move(event.globalPosition().toPoint() - self._drag_position)
                except TypeError:
                    pass
                event.accept()
        except AttributeError:
            pass

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
        success = self.open_route()

        if success:
            return
        else:
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

    def close(self):
        import time
        try:
            self.dialogs["output_dialog"].close()
            time.sleep(0.1)
        except AttributeError:
            pass

        self.stop.emit()
        self.updates.on_quit()
        super().close()
        
    def closeEvent(self, event):
        self.close()
        event.accept()

    def _on_start_btn_hover(self, hovering):
        if hovering:
            scale = 1.1
        else:
            scale = 1.0
        
        # Resize button
        new_width = int(self.start_pixmap.width() * scale)
        new_height = int(self.start_pixmap.height() * scale)
        self.start_btn.setFixedSize(new_width, new_height)
        
        # Move button relative to its initial position
        new_x = self.start_btn_initial_x - (new_width - self.start_pixmap.width()) // 2
        new_y = self.start_btn_initial_y - (new_height - self.start_pixmap.height()) // 2
        self.start_btn.move(new_x, new_y)
