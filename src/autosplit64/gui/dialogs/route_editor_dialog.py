from os import path
import sys
from json import JSONDecodeError
import re
import xml.etree.ElementTree as ET
from functools import partial

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QIcon, QIntValidator

from autosplit64.core import resource_utils
from autosplit64.core import route_loader, config
from autosplit64.core.route import Route, Split
from autosplit64.gui.widgets import TableWidgetDragRows, HLine
from autosplit64.gui.constants import (
    ICON_PATH
)
from autosplit64.core.constants import (
    SPLIT_NORMAL,
    SPLIT_FADE_ONLY,
    SPLIT_MIPS,
    SPLIT_MIPS_X,
    SPLIT_XCAM,
    SPLIT_FINAL,
    TIMING_RTA,
    TIMING_UP_RTA,
    TIMING_FILE_SELECT
)

# The split table's columns
ICON, TITLE, STAR_COUNT, FADEOUT, FADEIN, XCAM, SPLIT_TYPE = range(7)

EDITABLE = QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsEnabled
NOT_EDITABLE = QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled


class RouteEditor(QtWidgets.QMainWindow):
    route_updated = QtCore.pyqtSignal()

    CATEGORIES = ["0 Star", "1 Star", "16 Star", "70 Star", "120 Star"]
    SPLIT_TYPES = [SPLIT_NORMAL, SPLIT_FADE_ONLY, SPLIT_MIPS, SPLIT_MIPS_X, SPLIT_XCAM, SPLIT_FINAL]
    # The counts each split type doesn't use, shown as "-"
    UNUSED_COUNTS = {
        SPLIT_NORMAL: {XCAM},
        SPLIT_FADE_ONLY: {STAR_COUNT, XCAM},
        SPLIT_MIPS: {FADEOUT, FADEIN, XCAM},
        SPLIT_MIPS_X: {FADEOUT, FADEIN, XCAM},
        SPLIT_XCAM: set(),
        SPLIT_FINAL: {FADEOUT, FADEIN, XCAM},
    }
    # Each count's column and name, and the split types that need it
    COUNTS = [(STAR_COUNT, "Star Count", [t for t in SPLIT_TYPES if t != SPLIT_FADE_ONLY]),
              (FADEOUT, "Fadeout", [SPLIT_NORMAL]),
              (FADEIN, "Fadein", [SPLIT_NORMAL]),
              (XCAM, "XCam", [SPLIT_XCAM])]

    DOWN = 1
    UP = -1

    def __init__(self, parent=None):
        super(RouteEditor, self).__init__(parent)

        # On macOS, only dialogs are kept at their parent's window level, so a normal window
        # would open behind the main window when it's always on top
        if sys.platform == "darwin":
            self.setWindowFlag(QtCore.Qt.WindowType.Dialog)

        # Route
        self.route = None
        self.route_path = None
        # Name of the LiveSplit splits the route was converted from, if any
        self._lss_name = None

        self.setWindowTitle("Route Editor")
        self.resize(780, 600)
        self.setWindowIcon(QIcon(resource_utils.resource_path(ICON_PATH)))

        self.main_layout = QtWidgets.QVBoxLayout()
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_widget.setLayout(self.main_layout)
        self.file_buttons()

        # The route's details
        self.title_le = QtWidgets.QLineEdit()
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItems(self.CATEGORIES)
        self.category_combo.setEditable(True)
        self.category_combo.lineEdit().setText("")
        self.init_star_le = QtWidgets.QLineEdit()
        self.init_star_le.setFixedWidth(45)
        self.init_star_le.setValidator(QIntValidator(self))
        self.version_combo = QtWidgets.QComboBox()
        self.version_combo.setMaximumWidth(65)
        self.version_combo.addItems(["JP", "US"])
        self.timing_combo = QtWidgets.QComboBox()
        self.timing_combo.setMaximumWidth(80)
        self.timing_combo.addItems([TIMING_RTA, TIMING_UP_RTA, TIMING_FILE_SELECT])

        details_layout = QtWidgets.QFormLayout()
        details_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        details_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for text, field in [("Title:", self.title_le), ("Category:", self.category_combo),
                            ("Initial Star:", self.init_star_le), ("Version:", self.version_combo),
                            ("Timing:", self.timing_combo)]:
            details_layout.addRow(text, field)

        # The splits
        self.split_table = TableWidgetDragRows()
        self.split_table.setIconSize(QtCore.QSize(30, 30))
        self.split_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.split_table.setColumnCount(7)
        self.split_table.setHorizontalHeaderLabels(["Icon", "Split Title", "Star count", "Fadeout", "Fadein", "X-Cam", "Split Type"])
        self.split_table.cellDoubleClicked.connect(self.double_clicked)

        split_buttons_layout = QtWidgets.QVBoxLayout()
        split_buttons_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        for text, slot in [("Insert Above", lambda: self._insert_row(self.split_table.currentIndex().row())),
                           ("Insert Below", lambda: self._insert_row(self.split_table.currentIndex().row() + 1)),
                           ("Remove", self.remove_clicked),
                           ("Move Up", lambda: self.moveCurrentRow(self.UP)),
                           ("Move Down", lambda: self.moveCurrentRow(self.DOWN))]:
            button = QtWidgets.QPushButton(text)
            button.setMinimumWidth(125)
            button.clicked.connect(slot)
            split_buttons_layout.addWidget(button)
        split_buttons_layout.addStretch()

        splits_layout = QtWidgets.QHBoxLayout()
        splits_layout.addLayout(split_buttons_layout)
        splits_layout.addWidget(self.split_table)

        # Apply and Cancel
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.setMaximumWidth(100)
        self.apply_btn.clicked.connect(self.apply_clicked)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setMaximumWidth(100)
        cancel_btn.clicked.connect(self.close)
        apply_cancel_layout = QtWidgets.QHBoxLayout()
        apply_cancel_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        apply_cancel_layout.addWidget(self.apply_btn)
        apply_cancel_layout.addWidget(cancel_btn)

        self.main_layout.addLayout(details_layout)
        self.main_layout.addWidget(HLine())
        self.main_layout.addLayout(splits_layout)
        self.main_layout.addLayout(apply_cancel_layout)

    def file_buttons(self):
        """ New, Open, Save and Save As buttons above the route """
        file_layout = QtWidgets.QHBoxLayout()

        for text, tooltip, shortcut, slot in [
            ("New", "Create new route", QtGui.QKeySequence.StandardKey.New, self.new),
            ("Open", "Open a route (.as64), or LiveSplit splits (.lss) to convert to a route", QtGui.QKeySequence.StandardKey.Open, self.open),
            ("Save", "Save route", QtGui.QKeySequence.StandardKey.Save, self.save),
            ("Save As...", "Save route as", None, self.save_as),
        ]:
            button = QtWidgets.QPushButton(text)
            button.setToolTip(tooltip)
            button.setAutoDefault(False)
            if shortcut is not None:
                button.setShortcut(QtGui.QKeySequence(shortcut))
            button.clicked.connect(slot)
            file_layout.addWidget(button)
        file_layout.addStretch()

        QtGui.QShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Close), self, self.close)

        self.main_layout.addLayout(file_layout)
        self.main_layout.addWidget(HLine())

    def show(self):
        # Already open: bring it to the front, keeping unsaved changes
        if self.isVisible():
            self.raise_()
            self.activateWindow()
            return
        self.load_route()
        super().show()

    def moveCurrentRow(self, direction=DOWN):
        if direction not in (self.DOWN, self.UP):
            return

        indexes = sorted(set(item.row() for item in self.split_table.selectedItems()), reverse=(direction == self.DOWN))
        new_indexes = []

        if not indexes:
            return

        for idx in indexes:
            new_idx = idx + direction

            if new_idx >= self.split_table.rowCount() or new_idx < 0:
                break

            new_indexes.append(new_idx)

            try:
                icon_path = self.split_table.item(idx, ICON).toolTip()
            except AttributeError:
                icon_path = None
            row_data = [self.split_table.item(idx, column).text() for column in range(TITLE, SPLIT_TYPE)]
            split_type = self.split_table.cellWidget(idx, SPLIT_TYPE).currentText()

            self.split_table.removeRow(idx)
            self._insert_row(new_idx, icon_path, *row_data, split_type)

        self.split_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)

        for idx in new_indexes:
            for col in range(self.split_table.columnCount()):
                try:
                    self.split_table.item(idx, col).setSelected(True)
                except AttributeError:
                    pass

        self.split_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

    def remove_clicked(self):
        indexes = sorted(set(item.row() for item in self.split_table.selectedItems()), reverse=True)

        for index in indexes:
            self.split_table.removeRow(index)
            self.split_table.selectRow(index)

    def apply_clicked(self):
        err_code = self.save()

        if err_code == -1:
            return

        self.close()

    def double_clicked(self, x, y):
        if y != ICON:
            return

        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Icon", resource_utils.base_path("resources/icons"))

        if not file_name:
            return

        # Convert to relative path, if possible
        self._set_icon(x, resource_utils.abs_to_rel(file_name))

    def _set_icon(self, row, icon_path):
        item = QtWidgets.QTableWidgetItem()
        item.setIcon(QIcon(icon_path))
        item.setToolTip(icon_path)
        item.setFlags(NOT_EDITABLE)
        self.split_table.setItem(row, ICON, item)

    def load_route(self, route_path=None):
        """
        Loads route from path specified in preferences
        :return:
        """
        if not route_path:
            _route_path = config.get("route", "path")
        else:
            _route_path = route_path

        try:
            route = route_loader.load(_route_path)

            if route:
                route_error = route_loader.validate_route(route)
            else:
                self.new()
                return

            if route_error:
                self.display_error_message(route_error, "Route Error")

        except FileNotFoundError:
            route = None
            self.display_error_message("Route file not found.", "Invalid route: {}".format(path.basename(_route_path)))
        except KeyError:
            route = None
            self.display_error_message("Invalid or missing Key", "Invalid route: {}".format(path.basename(_route_path)))
        except JSONDecodeError:
            route = None
            self.display_error_message("Invalid JSON formatting", "Invalid route: {}".format(path.basename(_route_path)))
        except PermissionError:
            route = None

        if route:
            self.route = route
            self.route_path = self.route.file_path
            config.set_key("route", "path", resource_utils.abs_to_rel(_route_path))
            config.save_config()
            self.display_route()

    def display_route(self):
        if not self.route:
            return

        self.title_le.setText(self.route.title)
        self.init_star_le.setText(str(self.route.initial_star))
        self.category_combo.lineEdit().setText(self.route.category)
        self.version_combo.setCurrentIndex(1 if self.route.version == "US" else 0)
        self.timing_combo.setCurrentText(self.route.timing)

        self.split_table.setRowCount(len(self.route.splits))
        for row, split in enumerate(self.route.splits):
            self._set_row(row, split.icon_path, split.title, split.star_count, split.on_fadeout, split.on_fadein,
                          split.on_xcam, split.split_type)

    def display_error_message(self, message, title):
        """
        Display a warning dialog with given title and message
        :param title: Window title
        :param message: Warning/error message
        :return:
        """
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.show()

    def new(self):
        self.route = None
        self.route_path = None
        self._lss_name = None

        self.split_table.setRowCount(0)

        self.title_le.setText("")
        self.init_star_le.setText("")
        self.version_combo.setCurrentIndex(0)

    def open(self):
        """ Show native file dialog to select a route, or LiveSplit splits to convert to one. """
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Route", resource_utils.absolute_path("routes"),
                                                             "Routes and LiveSplit Splits (*.as64 *.lss)")

        if not file_name:
            return
        if file_name.lower().endswith(".lss"):
            self.convert_lss(file_name)
        else:
            self.load_route(file_name)

    def save_as(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Route", resource_utils.base_path() + "/routes", "AS64 Route Files (*.as64)")

        if file_name != '':
            self.route_path = file_name
        else:
            return

        self.save()

    def save(self):
        self.apply_btn.setFocus()

        splits = []

        if self.split_table.rowCount() < 1:
            self.display_error_message("No Splits", "Route Error")
            return -1

        for row in range(self.split_table.rowCount()):
            title = self.split_table.item(row, TITLE).text()
            if len(title) <= 0:
                self.display_error_message("Invalid Title - Row: " + str(row + 1), "Route Error")
                self.split_table.setCurrentCell(row, TITLE)
                return -1

            split_type = self.split_table.cellWidget(row, SPLIT_TYPE).currentText()
            # -1 for a count the split type doesn't need
            counts = []
            for column, name, needed_by in self.COUNTS:
                try:
                    counts.append(int(self.split_table.item(row, column).text()))
                except (ValueError, AttributeError):
                    if split_type in needed_by:
                        self.display_error_message(f"Invalid {name} - Row: {row + 1}", "Route Error")
                        self.split_table.setCurrentCell(row, column)
                        return -1
                    counts.append(-1)

            try:
                icon_path = self.split_table.item(row, ICON).toolTip()
            except (ValueError, AttributeError):
                icon_path = ""

            splits.append(Split(title, *counts, split_type, icon_path))

        title = self.title_le.text()
        if len(title) <= 0:
            self.display_error_message("Invalid Route Title", "Route Error")
            return -1

        try:
            initial_star = int(self.init_star_le.text())
        except (ValueError, AttributeError):
            self.display_error_message("Invalid Initial Star", "Route Error")
            return -1

        route = Route(self.route_path,
                      title,
                      splits,
                      initial_star,
                      self.version_combo.currentText(),
                      self.category_combo.lineEdit().text(),
                      self.timing_combo.currentText())

        route_error = route_loader.validate_route(route)

        if route_error:
            self.display_error_message(route_error, "Route Error")
            return -1

        if not self.route_path:
            suggested = resource_utils.base_path() + "/routes" + (f"/{self._lss_name}.as64" if self._lss_name else "")
            file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Route", suggested, "AS64 Route Files (*.as64)")

            if file_name != '':
                self.route_path = file_name
            else:
                return -1

        route_loader.save(route, self.route_path)
        config.set_key("route", "path", self.route_path)
        config.save_config()
        self.route_updated.emit()

    def convert_lss(self, file_name):
        """ Fill in a new route from LiveSplit splits, guessing each split's details from its name """
        self.new()
        # Suggested name when saving the converted route
        self._lss_name = path.splitext(path.basename(file_name))[0]

        tree = ET.parse(file_name)
        root = tree.getroot()
        segments = root.find('Segments')

        # Default initial star to 0
        self.init_star_le.setText("0")

        # STAGE NAMES: a word of the split's name, or a part of it
        DW_NAMES_IN = ['key1', 'key 1', 'bowser', 'dw', 'dark world', 'darkworld', 'bitdw', 'dworld']
        DW_NAMES_CONTAINS = ['key 1', 'dark world']

        LBLJ_NAMES_CONTAINS = ['lblj']

        FS_NAMES_IN = ['key2', 'key 2', 'fs', 'firesea', 'fire sea', 'bitfs', 'fsea']
        FS_NAMES_CONTAINS = ['key 2', 'fire sea']

        UPSTAIRS_NAMES_CONTAINS = [r'/up', r'/upstairs', 'upstairs']

        MIPS_NAMES = ['mips']

        BLJ_NAMES_IN = ['bljs', 'blj']

        is_16 = False
        for seg in reversed(segments):
            name = seg.find('Name').text

            numbers = re.findall(r'\d+', name)

            try:
                if int(numbers[len(numbers)-1]) == 16:
                    is_16 = True
                    break
                elif int(numbers[len(numbers)-1]) > 16:
                    break
            except (IndexError, ValueError):
                pass

        for i, child in enumerate(segments):
            name = child.find('Name').text
            words = name.lower().split()

            def named(names_in=(), names_contained=()):
                return any(n in words for n in names_in) or any(n in name.lower() for n in names_contained)

            # Attempt to determine star count
            numbers = re.findall(r'\d+', name)

            try:
                star_count = str(numbers[len(numbers)-1])
            except IndexError:
                star_count = ""

            # Determine most likely fadeout count & split type (will redo this code at some point, ran out of time :[ )
            fadeouts = "1"
            split_type = SPLIT_NORMAL

            if named(DW_NAMES_IN, DW_NAMES_CONTAINS):
                fadeouts = "2"
            if named(names_contained=LBLJ_NAMES_CONTAINS):
                fadeouts = "2"
                star_count = "0"
            if named(FS_NAMES_IN, FS_NAMES_CONTAINS):
                fadeouts = "3" if is_16 else "2"
            if named(names_contained=UPSTAIRS_NAMES_CONTAINS):
                fadeouts = "4"
            if named(MIPS_NAMES):
                split_type = SPLIT_MIPS
            if named(BLJ_NAMES_IN):
                fadeouts = "4"

            if i == len(segments) - 1:
                split_type = SPLIT_FINAL

            if star_count == "" and i != len(segments) - 1:
                try:
                    star_count = self.split_table.item(self.split_table.rowCount() - 1, STAR_COUNT).text()
                except:
                    star_count = "0"

            self._insert_row(title=name,
                             star_count=star_count,
                             fadeouts=fadeouts,
                             row_type=split_type)

        # Set final star (as often not in split title)
        try:
            final_star = int(self.split_table.item(self.split_table.rowCount() - 1, STAR_COUNT).text())
        except IndexError:
            final_star = None
        except ValueError:
            try:
                prev_star_count = int(self.split_table.item(self.split_table.rowCount() - 2, STAR_COUNT).text())
                if prev_star_count == 16:
                    final_star = "16"
                elif prev_star_count == 69:
                    final_star = "70"
                elif prev_star_count == 119:
                    final_star = "120"
                elif prev_star_count >= 0:
                    final_star = str(prev_star_count)

                self.split_table.setItem(self.split_table.rowCount() - 1, STAR_COUNT, QtWidgets.QTableWidgetItem(final_star))
            except (ValueError, IndexError, UnboundLocalError):
                final_star = None

        # Set Category
        if final_star == "16":
            self.category_combo.lineEdit().setText("16 Star")
        elif final_star == "70":
            self.category_combo.lineEdit().setText("70 Star")
            self.version_combo.setCurrentIndex(1)
        elif final_star == "120":
            self.category_combo.lineEdit().setText("120 Star")

    def split_type_changed(self, combo):
        for row in range(self.split_table.rowCount()):
            if combo == self.split_table.cellWidget(row, SPLIT_TYPE):
                self._set_disable_columns(row, combo.currentText())
                return

    def _set_disable_columns(self, row, row_type, fadeouts="1", fadeins="0", xcam="1", star_count="0"):
        """ Shows the counts the split type uses, and "-" for the others """
        unused = self.UNUSED_COUNTS.get(row_type)
        if unused is None:
            return
        for column, value in [(FADEOUT, fadeouts), (FADEIN, fadeins), (XCAM, xcam), (STAR_COUNT, star_count)]:
            item = self.split_table.item(row, column)
            item.setText("-" if column in unused else str(value))
            item.setFlags(NOT_EDITABLE if column in unused else EDITABLE)

    def _set_row(self, row, icon_path, title, star_count, fadeouts, fadeins, xcam, row_type):
        if icon_path is not None:
            self._set_icon(row, icon_path)
        self.split_table.setItem(row, TITLE, QtWidgets.QTableWidgetItem(title))
        for column in (STAR_COUNT, FADEOUT, FADEIN, XCAM):
            self.split_table.setItem(row, column, QtWidgets.QTableWidgetItem(""))
        self._add_split_combo(row, row_type)
        self._set_disable_columns(row, row_type, fadeouts, fadeins, xcam, star_count)

    def _insert_row(self, index=None, icon_path=None, title="", star_count="", fadeouts="1", fadeins="0", xcam="-1", row_type=SPLIT_NORMAL):
        if index is None:
            index = self.split_table.rowCount()

        index = max(index, 0)

        self.split_table.insertRow(index)
        self._set_row(index, icon_path or None, title, star_count, fadeouts, fadeins, xcam, row_type)
        self.split_table.selectRow(index)

    def _add_split_combo(self, row, default=SPLIT_NORMAL):
        combo = QtWidgets.QComboBox()
        combo.addItems(self.SPLIT_TYPES)
        self.split_table.setCellWidget(row, SPLIT_TYPE, combo)
        if default in self.SPLIT_TYPES:
            combo.setCurrentIndex(self.SPLIT_TYPES.index(default))

        combo.currentIndexChanged.connect(partial(self.split_type_changed, combo))
