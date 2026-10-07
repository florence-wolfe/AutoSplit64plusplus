from functools import partial

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QSizePolicy

from autosplit64.core import resource_utils
from autosplit64.core import config
from autosplit64.gui.widgets import HLine
from autosplit64.gui.constants import (
    ICON_PATH
)

Policy = QSizePolicy.Policy
ALIGN_RIGHT = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter


def spacer(width=10, height=10, horizontal=Policy.Minimum, vertical=Policy.Minimum):
    return QtWidgets.QSpacerItem(width, height, horizontal, vertical)


def label(text):
    """ A setting's label, aligned against its field on the right """
    widget = QtWidgets.QLabel(text)
    widget.setAlignment(ALIGN_RIGHT)
    return widget


class SettingsDialog(QtWidgets.QDialog):
    applied = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)

        self.window_title = "Settings"
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))

        # Layouts
        self.main_layout = QtWidgets.QHBoxLayout()
        self.right_layout = QtWidgets.QVBoxLayout()
        self.apply_cancel_layout = QtWidgets.QHBoxLayout()

        # Widgets
        self.right_widget = QtWidgets.QWidget()
        self.apply_cancel_widget = QtWidgets.QWidget()
        self.menu_list = QtWidgets.QListWidget()
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.stacked_widget = QtWidgets.QStackedWidget()

        self.menus = [GeneralMenu(), ConnectionMenu(), ThresholdsMenu(), ColourThresholdsMenu(), ErrorCorrectionMenu(),
                      AdvancedMenu()]

        self.initialize()

    def initialize(self):
        self.setWindowTitle(self.window_title)
        self.resize(650, 400)

        # Set Layouts
        self.setLayout(self.main_layout)
        self.right_widget.setLayout(self.right_layout)
        self.apply_cancel_widget.setLayout(self.apply_cancel_layout)
        self.right_layout.setContentsMargins(0, 0, 0, 0)

        # Configure Widgets
        self.menu_list.setMinimumWidth(80)
        self.menu_list.setSizePolicy(Policy.Minimum, Policy.Minimum)
        self.menu_list.addItems([menu.title for menu in self.menus])
        self.menu_list.setSpacing(8)

        for menu in self.menus:
            self.stacked_widget.addWidget(menu)

        self.stacked_widget.setSizePolicy(Policy.Expanding, Policy.Expanding)

        # Add Widgets
        self.apply_cancel_layout.addItem(spacer(20, 20, Policy.Expanding))
        self.apply_cancel_layout.addWidget(self.apply_btn)
        self.apply_cancel_layout.addWidget(self.cancel_btn)

        self.right_layout.addWidget(self.stacked_widget)
        self.right_layout.addWidget(HLine())
        self.right_layout.addWidget(self.apply_cancel_widget)

        self.main_layout.addWidget(self.menu_list, 33)
        self.main_layout.addWidget(self.right_widget, 66)

        # Connections
        self.menu_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        self.apply_btn.clicked.connect(self.apply_clicked)
        self.cancel_btn.clicked.connect(self.hide)

    def show(self):
        for menu in self.menus:
            menu.load_preferences()

        super().show()

    def apply_clicked(self):
        # Update and save preferences
        for menu in self.menus:
            menu.update_preferences()
        config.save_config()
        self.hide()

        self.applied.emit()


class BaseMenu(QtWidgets.QWidget):
    """
    A page of settings: a title over a grid that's filled row by row with add_row(). The settings'
    fields are bound to their config keys with bind(), or made bound by line_edit() and the like.
    """
    def __init__(self, title="", parent=None):
        super().__init__(parent)

        self.title = title
        self._settings = []
        self._row = 0

        self.whole = QtGui.QIntValidator(self)
        self.fraction = QtGui.QDoubleValidator(0, 1, 3, self)

        title_font = QtGui.QFont()
        title_font.setPointSize(12)
        title_label = QtWidgets.QLabel(self.title)
        title_label.setFont(title_font)
        title_label.setSizePolicy(Policy.Minimum, Policy.Minimum)

        title_line = QtWidgets.QFrame()
        title_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        title_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)

        menu_frame = QtWidgets.QFrame()
        menu_frame.setSizePolicy(Policy.Expanding, Policy.Expanding)
        self.grid = QtWidgets.QGridLayout()
        menu_frame.setLayout(self.grid)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(title_label)
        layout.addWidget(title_line)
        layout.addWidget(menu_frame)

    def add_row(self, *items):
        """ Adds a row of widgets and spacers to the grid, None for an empty column, (widget, columns) to span columns """
        column = 0
        for item in items:
            item, span = item if isinstance(item, tuple) else (item, 1)
            if isinstance(item, QtWidgets.QSpacerItem):
                self.grid.addItem(item, self._row, column)
            elif item is not None:
                self.grid.addWidget(item, self._row, column, 1, span)
            column += span
        self._row += 1

    def add_separator(self, columns, gap=10):
        self.add_row(spacer(10, gap))
        self.add_row((HLine(), columns))
        self.add_row(spacer(10, gap))

    def add_stretch(self):
        """ Keeps the rows at the top """
        self.add_row(spacer(20, 20, vertical=Policy.Expanding))

    def bind(self, section, key, load, save):
        """ load(value) shows the setting's value, save() returns it """
        self._settings.append((section, key, load, save))

    def line_edit(self, section, key, convert=str, validator=None, max_width=None, vertical=Policy.Preferred):
        """ A field for the setting, which is saved as convert(text) """
        edit = QtWidgets.QLineEdit()
        edit.setSizePolicy(Policy.Expanding, vertical)
        if max_width:
            edit.setMaximumWidth(max_width)
        if validator:
            edit.setValidator(validator)
        self.bind(section, key, lambda value: edit.setText(str(value)), lambda: convert(edit.text()))
        return edit

    def check_box(self, section, key, max_width=None):
        box = QtWidgets.QCheckBox()
        if max_width:
            box.setMaximumWidth(max_width)
        self.bind(section, key, box.setChecked, box.isChecked)
        return box

    def combo_box(self, section, key, items, max_width=None):
        """ A choice of items, the setting is the chosen one's index """
        combo = QtWidgets.QComboBox()
        combo.addItems(items)
        if max_width:
            combo.setMaximumWidth(max_width)
        self.bind(section, key, combo.setCurrentIndex, combo.currentIndex)
        return combo

    def spin_box(self, section, key, minimum):
        box = QtWidgets.QSpinBox()
        box.setMaximumWidth(50)
        box.setMinimum(minimum)
        self.bind(section, key, box.setValue, box.value)
        return box

    def load_preferences(self):
        for section, key, load, _ in self._settings:
            load(config.get(section, key))

    def update_preferences(self):
        for section, key, _, save in self._settings:
            config.set_key(section, key, save())


class GeneralMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__(title="General", parent=parent)

        self.override_ver_cb = self.check_box("game", "override_version", 20)
        self.override_ver_combo = QtWidgets.QComboBox()
        self.override_ver_combo.setMaximumWidth(130)
        self.override_ver_combo.addItems(["JP", "US"])
        self.bind("game", "version", lambda version: self.override_ver_combo.setCurrentIndex(1 if version == "US" else 0),
                  self.override_ver_combo.currentText)

        self.add_row(label("Always On Top:"), self.check_box("general", "on_top", 20))
        self.add_row(label("Check for Updates:"), self.check_box("general", "update_check", 20))
        self.add_row(label("Autostart:"), self.check_box("general", "auto_start", 20))
        self.add_separator(3)
        self.add_row(label("Operation Mode:"),
                     self.combo_box("general", "operation_mode", ["Probability", "X-Cam"], 130))
        self.add_separator(3)
        self.add_row(label("Allow Mid-Run Starts:"), self.check_box("general", "mid_run_start_enabled", 20))
        self.add_separator(3)
        self.add_row(label("Override Game Version:"), self.override_ver_cb)
        self.add_row(None, None, spacer(10, 5, Policy.Expanding))
        self.add_row(None, self.override_ver_combo)
        self.add_stretch()

        # Connections
        self.override_ver_cb.clicked.connect(lambda checked: self.override_ver_combo.setDisabled(not checked))

        self.load_preferences()

    def load_preferences(self):
        super().load_preferences()
        self.override_ver_combo.setDisabled(not self.override_ver_cb.isChecked())


class ThresholdsMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__(title="Thresholds", parent=parent)

        edit = partial(self.line_edit, "thresholds")

        self.add_row(spacer())
        self.add_row(label("Probability Threshold:"), edit("probability_threshold", float, self.fraction),
                     label("Reset Threshold:"), edit("reset_threshold", float, self.fraction))
        self.add_row(label("Confirmation Threshold:"), edit("confirmation_threshold", float, self.fraction))
        self.add_separator(4)
        self.add_row(label("Black Threshold:"), edit("black_threshold", float, self.fraction),
                     label("White Threshold:"), edit("white_threshold", float, self.fraction))
        self.add_separator(4)
        self.add_row(label("X-Cam B-G Threshold:"), edit("xcam_bg_threshold", int, self.whole),
                     label("X-Cam R-G Threshold:"), edit("xcam_rg_threshold", int, self.whole))
        self.add_row(label("X-Cam B-G Activation:"), edit("xcam_bg_activation", int, self.whole),
                     label("X-Cam R-G Activation:"), edit("xcam_rg_activation", int, self.whole))
        self.add_row(label("X-Cam Pixel Threshold:"),
                     edit("xcam_pixel_threshold", float, self.fraction, vertical=Policy.Minimum))
        self.add_separator(4)
        self.add_row(label("Undo Threshold:"), edit("undo_threshold", float, self.fraction, vertical=Policy.Minimum))
        self.add_stretch()

        self.load_preferences()


class ColourThresholdsMenu(BaseMenu):
    # The colours of each split type, by config section and key
    SPLIT_TYPES = [
        ("X-Cam", "split_xcam", [("Lower Bound:", "lower_bound"), ("Upper Bound:", "upper_bound")]),
        ("Mips", "split_ddd_enter", [("Portal Lower Bound:", "portal_lower_bound"),
                                     ("Portal Upper Bound:", "portal_upper_bound"),
                                     ("Hat Lower Bound:", "hat_lower_bound"),
                                     ("Hat Upper Bound:", "hat_upper_bound")]),
        ("Final Bowser", "split_final_star", [("Stage Lower Bound:", "stage_lower_bound"),
                                              ("Stage Upper Bound:", "stage_upper_bound"),
                                              ("Star Lower Bound:", "star_lower_bound"),
                                              ("Star Upper Bound:", "star_upper_bound")]),
    ]

    def __init__(self, parent=None):
        super().__init__(title="Colour Thresholds", parent=parent)

        self.split_type_cb = QtWidgets.QComboBox()
        self.split_type_cb.setFixedWidth(100)
        self.stacked_widget = QtWidgets.QStackedWidget()

        for name, section, colours in self.SPLIT_TYPES:
            self.split_type_cb.addItem(name)
            page = QtWidgets.QWidget()
            page.setLayout(QtWidgets.QGridLayout())
            for row, (text, key) in enumerate(colours):
                colour = SettingsColourWidget(text, page)
                self.bind(section, key, colour.set_bgr, colour.bgr)
                page.layout().addWidget(colour, row, 0)
            page.layout().addItem(spacer(horizontal=Policy.Expanding), 0, 1)
            # X-Cam has fewer colours than the tallest page, so they're kept at the top
            if len(colours) < 4:
                page.layout().addItem(spacer(vertical=Policy.Expanding), len(colours), 0)
            else:
                page.layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            self.stacked_widget.addWidget(page)

        split_type_widget = QtWidgets.QWidget()
        split_type_widget.setLayout(QtWidgets.QHBoxLayout())
        split_type_widget.layout().addWidget(QtWidgets.QLabel("Threshold:"))
        split_type_widget.layout().addWidget(self.split_type_cb)

        self.add_row(split_type_widget, None, spacer(horizontal=Policy.Expanding, vertical=Policy.Expanding))
        self.add_separator(3)
        self.add_row((self.stacked_widget, 3))
        self.add_stretch()

        self.load_preferences()

        # Connections
        self.split_type_cb.currentIndexChanged.connect(self.stacked_widget.setCurrentIndex)


class SettingsColourWidget(QtWidgets.QWidget):
    """ A colour's red, green and blue fields. Colours are stored blue first, like OpenCV's. """
    def __init__(self, label, parent=None):
        super().__init__(parent=parent)

        self.label = QtWidgets.QLabel(label)
        self.label.setFixedWidth(100)
        self.label.setAlignment(ALIGN_RIGHT)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.label)

        validator = QtGui.QIntValidator(self)
        self.channels = []
        for _ in range(3):
            edit = QtWidgets.QLineEdit()
            edit.setValidator(validator)
            edit.setFixedWidth(50)
            layout.addWidget(edit)
            self.channels.append(edit)
        layout.addItem(spacer(horizontal=Policy.Expanding, vertical=Policy.Expanding))

    def set_bgr(self, bgr):
        for edit, value in zip(self.channels, reversed(bgr)):
            edit.setText(str(value))

    def bgr(self):
        return [int(edit.text()) for edit in reversed(self.channels)]


class ConnectionMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__(title="Connection", parent=parent)

        edit = partial(self.line_edit, "connection", max_width=150)
        self.ls_mode_combo = self.combo_box("connection", "ls_connection_type", ["Named Pipe", "TCP", "LiveSplit One"], 120)
        self.ls_pipe_host_lb, self.ls_pipe_host_le = label("LiveSplit Pipe Host:"), edit("ls_pipe_host")
        self.host_lb, self.host_le = label("LiveSplit TCP Host:"), edit("ls_host")
        self.port_lb, self.port_le = label("LiveSplit TCP Port:"), edit("ls_port", int, self.whole)
        self.lso_port_lb, self.lso_port_le = label("LiveSplit One Port:"), edit("lso_port", int, self.whole)

        # Only the settings of the selected connection mode are shown, see _show_mode_settings.
        # The column 2 spacer is in the mode's row, which is always shown, so hidden rows collapse.
        self.add_row(label("Connection Mode:"), self.ls_mode_combo, spacer(horizontal=Policy.Expanding))
        self.add_separator(3)
        self.add_row(self.ls_pipe_host_lb, self.ls_pipe_host_le)
        self.add_row(self.host_lb, self.host_le)
        self.add_row(self.port_lb, self.port_le)
        self.add_row(self.lso_port_lb, self.lso_port_le)
        self.add_stretch()

        self.ls_mode_combo.currentIndexChanged.connect(self._show_mode_settings)
        self.load_preferences()
        self._show_mode_settings(self.ls_mode_combo.currentIndex())

    def _show_mode_settings(self, mode):
        """ Show the settings of the connection mode: 0 Named Pipe, 1 TCP, 2 LiveSplit One """
        for widget_mode, widgets in [(0, (self.ls_pipe_host_lb, self.ls_pipe_host_le)),
                                     (1, (self.host_lb, self.host_le, self.port_lb, self.port_le)),
                                     (2, (self.lso_port_lb, self.lso_port_le))]:
            for widget in widgets:
                widget.setVisible(mode == widget_mode)


class ErrorCorrectionMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__(title="Error Correction", parent=parent)

        edit = partial(self.line_edit, "error", max_width=50)

        self.add_row(spacer())
        self.add_row(label("Processing Length:"), edit("processing_length", int, self.whole),
                     spacer(horizontal=Policy.Expanding))
        self.add_row(label("Undo Minimum Length:"), edit("minimum_undo_count", int, self.whole))
        self.add_row(label("Undo Average Threshold:"), edit("undo_threshold", float, self.fraction))
        self.add_separator(4)
        self.add_row(label("Star Skip Enabled:"), self.check_box("error", "star_skip"))
        self.add_row(label("Max Star Skip:"), edit("max_star_skip", int, self.whole))
        self.add_row(label("Consecutive Predictions:"), edit("minimum_consecutive_prediction", int, self.whole))
        self.add_stretch()

        self.load_preferences()


class AdvancedMenu(BaseMenu):
    def __init__(self, parent=None):
        super().__init__(title="Advanced", parent=parent)

        frame_rate = partial(self.line_edit, "advanced", convert=float, validator=QtGui.QDoubleValidator(self),
                             max_width=50)

        # Not in the layout, so it isn't shown, but applying still saves it, within the spin box's range
        self.spin_box("advanced", "restart_frame_offset", -48)

        self.add_row(spacer())
        self.add_row(label("File Select Offset:"), (self.spin_box("advanced", "file_select_frame_offset", -35), 2))
        self.add_separator(4, gap=5)
        for number in ("One", "Two"):
            self.add_reset_frame_row(number)
        self.add_separator(4, gap=5)
        self.add_row(label("Star Frame Rate:"), frame_rate("star_process_frame_rate"))
        self.add_row(label("Fadeout Frame Rate:"), frame_rate("fadeout_process_frame_rate"))
        self.add_separator(4, gap=5)

        model_combo = QtWidgets.QComboBox()
        model_combo.addItems(["AS64+ Star Predictor", "AS64 Legacy Model"])
        model_combo.setSizePolicy(Policy.Expanding, Policy.Preferred)
        self.bind("model", "legacy", lambda legacy: model_combo.setCurrentIndex(1 if legacy else 0),
                  lambda: model_combo.currentIndex() == 1)
        self.add_row(QtWidgets.QLabel("Detection Model:"), (model_combo, 3))
        self.add_stretch()

        self.load_preferences()

    def add_reset_frame_row(self, number):
        edit = self.line_edit("advanced", f"reset_frame_{number.lower()}", convert=resource_utils.abs_to_rel)
        browse = QtWidgets.QPushButton("Browse")
        browse.clicked.connect(lambda: self.browse(edit, f"Select Reset Frame {number}"))
        self.add_row(label(f"Reset Frame {number}:"), (edit, 3), browse)

    def browse(self, edit, title):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, title, "")

        if file_name:
            edit.setText(file_name)
