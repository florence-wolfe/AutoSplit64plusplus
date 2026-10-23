import os
from os import path
import sys
from json import JSONDecodeError
import re
import xml.etree.ElementTree as ET

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QIcon

from autosplit64.core import resource_utils
from autosplit64.core import route_loader, config
from autosplit64.core.route import Route, Split
from autosplit64.gui.qml_view import Values, qml_view
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

# A split's counts, as the route editor shows them
STAR_COUNT, FADEOUT, FADEIN, XCAM = "star_count", "fadeout", "fadein", "xcam"


class Splits(QtCore.QAbstractListModel):
    """
    The route's splits for RouteEditor.qml, as shown: each a dict of its icon's path, title, counts as text,
    "-" for those its split type doesn't use, and split type. Also which are selected, and the current one.
    """
    KEYS = ["icon", "icon_url", "title", STAR_COUNT, FADEOUT, FADEIN, XCAM, "split_type", "unused", "selected"]
    icon_clicked = QtCore.pyqtSignal(int)

    def __init__(self, unused_counts):
        super().__init__()
        self._unused_counts = unused_counts
        self.rows = []
        self.selected = set()
        # The row inserting above and below is from, or -1
        self.current = -1

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def roleNames(self):
        return {QtCore.Qt.ItemDataRole.UserRole + i: key.encode() for i, key in enumerate(self.KEYS)}

    def data(self, index, role):
        key = self.KEYS[role - QtCore.Qt.ItemDataRole.UserRole]
        row = self.rows[index.row()]
        if key == "selected":
            return index.row() in self.selected
        if key == "unused":
            return sorted(self._unused_counts.get(row["split_type"], ()))
        if key == "icon_url":
            return QtCore.QUrl.fromLocalFile(os.path.abspath(row["icon"])).toString() if row["icon"] else ""
        return row[key]

    def changed(self, row):
        self.dataChanged.emit(self.index(row), self.index(row))

    def reset(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.selected = set()
        self.current = -1
        self.endResetModel()

    def insert(self, index, row):
        self.beginInsertRows(QtCore.QModelIndex(), index, index)
        self.rows.insert(index, row)
        self.endInsertRows()

    def remove(self, index):
        self.beginRemoveRows(QtCore.QModelIndex(), index, index)
        del self.rows[index]
        self.endRemoveRows()

    def move(self, index, to):
        # The destination is the row it goes before, which is one further when moving down
        self.beginMoveRows(QtCore.QModelIndex(), index, index, QtCore.QModelIndex(), to + 1 if to > index else to)
        self.rows.insert(to, self.rows.pop(index))
        self.endMoveRows()

    def select_rows(self, rows):
        self.selected = set(rows)
        self.current = max(rows, default=-1)
        self.dataChanged.emit(self.index(0), self.index(len(self.rows) - 1))

    @QtCore.pyqtSlot(int, str)
    def select(self, row, mode):
        """ Select only the row, toggle it ("toggle"), or select from the current row to it ("range") """
        if mode == "toggle":
            self.select_rows(self.selected ^ {row})
        elif mode == "range" and self.current >= 0:
            self.select_rows(range(min(row, self.current), max(row, self.current) + 1))
        else:
            self.select_rows({row})
        self.current = row

    @QtCore.pyqtSlot(int, str, str)
    def set(self, row, key, text):
        # Not shown again: it's the field's text already
        self.rows[row][key] = text

    @QtCore.pyqtSlot(int, str)
    def set_type(self, row, split_type):
        """ Shows the counts the split type uses, at their defaults, and "-" for the others """
        self.rows[row] = RouteEditor.split_row(self.rows[row]["icon"], self.rows[row]["title"], split_type=split_type)
        self.changed(row)

    @QtCore.pyqtSlot(int)
    def click_icon(self, row):
        self.icon_clicked.emit(row)


class Editor(Values):
    """
    The route's details for RouteEditor.qml, in values: its title, category, initial star, version and timing.
    Its other signals are the QML's clicks, and failed() shows an error.
    """
    failed = QtCore.pyqtSignal(str, str)
    new = QtCore.pyqtSignal()
    open = QtCore.pyqtSignal()
    save = QtCore.pyqtSignal()
    save_as = QtCore.pyqtSignal()
    insert_above = QtCore.pyqtSignal()
    insert_below = QtCore.pyqtSignal()
    remove = QtCore.pyqtSignal()
    move_up = QtCore.pyqtSignal()
    move_down = QtCore.pyqtSignal()
    apply = QtCore.pyqtSignal()
    cancel = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__({"title": "", "category": "", "initialStar": "", "version": "JP", "timing": TIMING_RTA})

    @QtCore.pyqtSlot(str, str)
    def set(self, key, text):
        # Not shown again: it's the field's text already
        self._values[key] = text


class RouteEditor(QtWidgets.QMainWindow):
    route_updated = QtCore.pyqtSignal()

    CATEGORIES = ["0 Star", "1 Star", "16 Star", "70 Star", "120 Star"]
    SPLIT_TYPES = [SPLIT_NORMAL, SPLIT_FADE_ONLY, SPLIT_MIPS, SPLIT_MIPS_X, SPLIT_XCAM, SPLIT_FINAL]
    TIMINGS = [TIMING_RTA, TIMING_UP_RTA, TIMING_FILE_SELECT]
    # The counts each split type doesn't use, shown as "-"
    UNUSED_COUNTS = {
        SPLIT_NORMAL: {XCAM},
        SPLIT_FADE_ONLY: {STAR_COUNT, XCAM},
        SPLIT_MIPS: {FADEOUT, FADEIN, XCAM},
        SPLIT_MIPS_X: {FADEOUT, FADEIN, XCAM},
        SPLIT_XCAM: set(),
        SPLIT_FINAL: {FADEOUT, FADEIN, XCAM},
    }
    # Each count, its name, and the split types that need it
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
        self.resize(900, 640)
        self.setWindowIcon(QIcon(resource_utils.resource_path(ICON_PATH)))

        self.splits = Splits({split_type: unused for split_type, unused in self.UNUSED_COUNTS.items()})
        self.splits.icon_clicked.connect(self.choose_icon)
        self.editor = Editor()
        for signal, slot in [(self.editor.new, self.new), (self.editor.open, self.open), (self.editor.save, self.save),
                             (self.editor.save_as, self.save_as), (self.editor.remove, self.remove_clicked),
                             (self.editor.insert_above, lambda: self._insert_row(self.splits.current)),
                             (self.editor.insert_below, lambda: self._insert_row(self.splits.current + 1)),
                             (self.editor.move_up, lambda: self.move_current_row(self.UP)),
                             (self.editor.move_down, lambda: self.move_current_row(self.DOWN)),
                             (self.editor.apply, self.apply_clicked), (self.editor.cancel, self.close)]:
            signal.connect(slot)
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        self.view = qml_view(main_widget, "RouteEditor", editor=self.editor, splits=self.splits,
                             categories=self.CATEGORIES, splitTypes=self.SPLIT_TYPES, timings=self.TIMINGS)

        Key = QtGui.QKeySequence.StandardKey
        for key, slot in [(Key.New, self.new), (Key.Open, self.open), (Key.Save, self.save), (Key.Close, self.close)]:
            QtGui.QShortcut(QtGui.QKeySequence(key), self, slot)

    def show(self):
        # Already open: bring it to the front, keeping unsaved changes
        if self.isVisible():
            self.raise_()
            self.activateWindow()
            return
        self.load_route()
        super().show()

    def move_current_row(self, direction=DOWN):
        if direction not in (self.DOWN, self.UP):
            return

        indexes = sorted(self.splits.selected, reverse=(direction == self.DOWN))
        new_indexes = []

        for idx in indexes:
            new_idx = idx + direction

            if new_idx >= len(self.splits.rows) or new_idx < 0:
                break

            new_indexes.append(new_idx)
            self.splits.move(idx, new_idx)

        if new_indexes:
            self.splits.select_rows(new_indexes)

    def remove_clicked(self):
        indexes = sorted(self.splits.selected, reverse=True)

        for index in indexes:
            self.splits.remove(index)
        # The row after the removed ones, now where they were
        if indexes and self.splits.rows:
            self.splits.select_rows({min(indexes[-1], len(self.splits.rows) - 1)})
        else:
            self.splits.select_rows(set())

    def apply_clicked(self):
        err_code = self.save()

        if err_code == -1:
            return

        self.close()

    def choose_icon(self, row):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Icon", resource_utils.base_path("resources/icons"))

        if not file_name:
            return

        # Convert to relative path, if possible
        self.splits.rows[row]["icon"] = resource_utils.abs_to_rel(file_name)
        self.splits.changed(row)

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

        except KeyError:
            route = None
            self.display_error_message("Invalid or missing Key", "Invalid route: {}".format(path.basename(_route_path)))
        except JSONDecodeError:
            route = None
            self.display_error_message("Invalid JSON formatting", "Invalid route: {}".format(path.basename(_route_path)))
        except OSError as e:
            route = None
            self.display_error_message(f"Couldn't read the route file: {e.strerror or e}", "Invalid route: {}".format(path.basename(_route_path)))

        if route:
            self.route = route
            self.route_path = self.route.file_path
            config.set_key("route", "path", resource_utils.abs_to_rel(_route_path))
            config.save_config()
            self.display_route()

    def display_route(self):
        if not self.route:
            return

        self.editor.update(title=self.route.title, initialStar=str(self.route.initial_star), category=self.route.category,
                           version="US" if self.route.version == "US" else "JP", timing=self.route.timing)
        self.splits.reset([self.split_row(split.icon_path, split.title, split.star_count, split.on_fadeout,
                                          split.on_fadein, split.on_xcam, split.split_type)
                           for split in self.route.splits])

    def display_error_message(self, message, title):
        """ Show a warning over the window with given title and message """
        self.editor.failed.emit(title, message)

    def new(self):
        self.route = None
        self.route_path = None
        self._lss_name = None

        self.splits.reset([])
        self.editor.update(title="", initialStar="", version="JP")

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
        splits = []

        if not self.splits.rows:
            self.display_error_message("No Splits", "Route Error")
            return -1

        for row, split in enumerate(self.splits.rows):
            title = split["title"]
            if len(title) <= 0:
                self.display_error_message("Invalid Title - Row: " + str(row + 1), "Route Error")
                self.splits.select_rows({row})
                return -1

            split_type = split["split_type"]
            # -1 for a count the split type doesn't need
            counts = []
            for key, name, needed_by in self.COUNTS:
                try:
                    counts.append(int(split[key]))
                except ValueError:
                    if split_type in needed_by:
                        self.display_error_message(f"Invalid {name} - Row: {row + 1}", "Route Error")
                        self.splits.select_rows({row})
                        return -1
                    counts.append(-1)

            splits.append(Split(title, *counts, split_type, split["icon"]))

        details = self.editor.values
        title = details["title"]
        if len(title) <= 0:
            self.display_error_message("Invalid Route Title", "Route Error")
            return -1

        try:
            initial_star = int(details["initialStar"])
        except ValueError:
            self.display_error_message("Invalid Initial Star", "Route Error")
            return -1

        route = Route(self.route_path,
                      title,
                      splits,
                      initial_star,
                      details["version"],
                      details["category"],
                      details["timing"])

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
        self.editor.update(initialStar="0")

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
                    star_count = self.splits.rows[-1][STAR_COUNT]
                except IndexError:
                    star_count = "0"

            self._insert_row(title=name,
                             star_count=star_count,
                             fadeouts=fadeouts,
                             row_type=split_type)

        # Set final star (as often not in split title)
        try:
            final_star = int(self.splits.rows[-1][STAR_COUNT])
        except IndexError:
            final_star = None
        except ValueError:
            try:
                prev_star_count = int(self.splits.rows[-2][STAR_COUNT])
                if prev_star_count == 16:
                    final_star = "16"
                elif prev_star_count == 69:
                    final_star = "70"
                elif prev_star_count == 119:
                    final_star = "120"
                elif prev_star_count >= 0:
                    final_star = str(prev_star_count)

                self.splits.rows[-1][STAR_COUNT] = final_star
                self.splits.changed(len(self.splits.rows) - 1)
            except (ValueError, IndexError, UnboundLocalError):
                final_star = None

        # Set Category
        if final_star == "16":
            self.editor.update(category="16 Star")
        elif final_star == "70":
            self.editor.update(category="70 Star", version="US")
        elif final_star == "120":
            self.editor.update(category="120 Star")

    @classmethod
    def split_row(cls, icon_path, title, star_count="0", fadeouts="1", fadeins="0", xcam="1", split_type=SPLIT_NORMAL):
        """ A split as shown: the counts the split type uses, and "-" for the others """
        unused = cls.UNUSED_COUNTS.get(split_type, set())
        row = {"icon": icon_path or "", "title": title, "split_type": split_type}
        for key, value in [(FADEOUT, fadeouts), (FADEIN, fadeins), (XCAM, xcam), (STAR_COUNT, star_count)]:
            row[key] = "-" if key in unused else str(value)
        return row

    def _insert_row(self, index=None, icon_path=None, title="", star_count="", fadeouts="1", fadeins="0", xcam="-1", row_type=SPLIT_NORMAL):
        if index is None:
            index = len(self.splits.rows)

        index = max(index, 0)

        self.splits.insert(index, self.split_row(icon_path, title, star_count, fadeouts, fadeins, xcam, row_type))
        self.splits.select_rows({index})
