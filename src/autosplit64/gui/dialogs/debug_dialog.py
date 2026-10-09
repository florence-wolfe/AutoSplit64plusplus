import logging
import os
import threading
from collections import deque
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..constants import (
    ICON_PATH
)

from autosplit64 import core as as64
from autosplit64.core import resource_utils, config, livesplit, livesplit_one, logs
from autosplit64.core.constants import SPLIT_FADE_ONLY, SPLIT_FINAL, SPLIT_MIPS, SPLIT_MIPS_X, SPLIT_XCAM
from autosplit64.gui.widgets import HLine

# The connection to LiveSplit, as the dot in the main window shows it
LIVESPLIT_STATES = {"connected": "LiveSplit connected", "waiting": "waiting for LiveSplit One",
                    "error": "LiveSplit not connected", "stopped": "LiveSplit not connected"}


def update_rate():
    """ How many times a second the window shows the latest values. 0 was allowed before, which is 1 now. """
    return max(1, config.get("general", "output_update_rate"))


class _EventSignal(QtCore.QObject):
    line = QtCore.pyqtSignal(str)


class DetectionEvents(logging.Handler):
    """ This session's last detection log lines, with their time, and a signal of each new one, from any thread """

    MAX = 200

    def __init__(self):
        super().__init__(logging.INFO)
        self.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        self._lines = deque(maxlen=self.MAX)
        self.signal = _EventSignal()

    def emit(self, record):
        line = self.format(record)
        self._lines.append(line)
        self.signal.line.emit(line)

    def lines(self):
        # Logging calls emit with the lock held
        with self.lock:
            return list(self._lines)


_events = None


def detection_events():
    """ The one DetectionEvents, on the detection log from the first time it's needed, when the main window is made """
    global _events
    if _events is None:
        _events = DetectionEvents()
        detection = logging.getLogger("detection")
        detection.setLevel(logging.INFO)
        detection.addHandler(_events)
    return _events


def livesplit_state():
    if config.get("connection", "ls_connection_type") == 2:
        return LIVESPLIT_STATES[livesplit_one.status()[0]]
    return LIVESPLIT_STATES[livesplit.client_status()[0]]


def _stars(count):
    return f"{count} star" if count == 1 else f"{count} stars"


def describe(status, livesplit):
    """ (status, split, what the split needs, what's counted) in words, from Base.status() and livesplit_state() """
    if not status or not status["running"] or "split" not in status:
        return f"Not running · {livesplit}", "", "", ""

    split_type = status["split_type"]
    fades = f"fadeout {status['needs_fadeouts']} · fade-in {status['needs_fadeins']}"
    counted = f"{_stars(status['stars'])} · fadeouts {status['fadeouts']} · fade-ins {status['fadeins']}"
    if split_type == SPLIT_FADE_ONLY:
        needs = fades
    elif split_type == SPLIT_XCAM:
        needs = f"{_stars(status['needs_stars'])} · {fades} · X-Cam {status['needs_xcams']}"
        counted += f" · X-Cams {status['xcams']}"
    elif split_type == SPLIT_MIPS:
        needs = "entering the DDD painting"
    elif split_type == SPLIT_MIPS_X:
        needs = "an X-Cam at the DDD painting"
        counted = f"{_stars(status['stars'])} · X-Cams {status['xcams']}"
    elif split_type == SPLIT_FINAL:
        needs = "grabbing the Grand Star"
    else:
        needs = f"{_stars(status['needs_stars'])} · {fades}"

    run = "in a run" if status["in_game"] else "waiting for a run"
    return (f"Running, {run} · {livesplit}", f"Split {status['split_index'] + 1} of {status['split_count']}: {status['split']}",
            needs, counted)


class DebugDialog(QtWidgets.QDialog):
    open_capture = QtCore.pyqtSignal()
    save_debug_info = QtCore.pyqtSignal()

    # Before it's resized
    DEFAULT_SIZE = (300, 400)

    # Rows of up to two (label, output key) fields, each label above its field, or one field
    # (label, output key, True) as wide as two. A number is a line between groups of rows, with
    # that much space around it.
    ROWS = [
        # Wide enough for the longest status, FADEOUT_COMPLETE
        [("Fade Status:", "fade_status", True)],
        [("Fade-out Count:", "fadeout_count"), ("Fade-in Count:", "fadein_count")],
        5,
        [("X-Cam Percent:", "xcam_percent")],
        [("X-Cam Count:", "xcam_count"), ("X-Cam Status:", "xcam_status")],
        0,
        [("Prediction:", "prediction"), ("Probability:", "probability")],
        0,
        [("Execution Time:", "execution")],
        5,
    ]
    # Fractions, of which only the first characters are shown
    SHORTENED = {"xcam_percent", "probability", "execution"}

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Debug")
        self.setWindowIcon(QtGui.QIcon(resource_utils.base_path(ICON_PATH)))
        self.resize(*(config.get("general", "debug_window_size") or self.DEFAULT_SIZE))

        # Output Reader
        self.output_reader = None

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # What split detection is doing
        self.status_lb, self.split_lb, self.needs_lb, self.counted_lb = (QtWidgets.QLabel() for _ in range(4))
        self.needs_lb.setToolTip("What the current split needs for split detection to split")
        self.counted_lb.setToolTip("What split detection counted since the last split or star")
        basics = self._basics = QtWidgets.QFormLayout()
        basics.addRow(self.status_lb)
        basics.addRow(self.split_lb)
        basics.addRow("Needs:", self.needs_lb)
        basics.addRow("Counted:", self.counted_lb)
        layout.addLayout(basics)

        # What split detection did in this session, the latest at the bottom
        self.events = QtWidgets.QPlainTextEdit()
        self.events.setReadOnly(True)
        self.events.setMaximumBlockCount(DetectionEvents.MAX)
        self.events.setToolTip("What split detection did in this session, like in the log")
        events = detection_events()
        self.events.setPlainText("\n".join(events.lines()))
        events.signal.line.connect(self._add_event)
        layout.addWidget(QtWidgets.QLabel("Recent events:"))
        layout.addWidget(self.events, 1)

        # Everything else split detection sees, collapsed at first
        self.advanced_btn = QtWidgets.QToolButton()
        self.advanced_btn.setText("Advanced")
        self.advanced_btn.setToolTip("Fades, X-Cams, star predictions and timings")
        self.advanced_btn.setCheckable(True)
        self.advanced_btn.setAutoRaise(True)
        self.advanced_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(self.advanced_btn)
        self.advanced = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(self.advanced)
        grid.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.advanced)

        # Each output key's field
        self.fields = {}
        row = 0
        for fields in self.ROWS:
            if isinstance(fields, int):
                if fields:
                    grid.addItem(QtWidgets.QSpacerItem(10, fields), row, 0)
                grid.addWidget(HLine(), row + 1, 0, 1, 4)
                if fields:
                    grid.addItem(QtWidgets.QSpacerItem(10, fields), row + 2, 0)
                row += 3
                continue
            for column, (text, key, *wide) in enumerate(fields):
                label = QtWidgets.QLabel(text)
                label.setFixedWidth(100)
                self.fields[key] = QtWidgets.QLineEdit()
                self.fields[key].setDisabled(True)
                if wide:
                    grid.addWidget(self.fields[key], row + 1, column, 1, 2)
                else:
                    self.fields[key].setFixedWidth(100)
                    grid.addWidget(self.fields[key], row + 1, column)
                grid.addWidget(label, row, column)
            row += 2

        self.update_lb = QtWidgets.QLabel("Update Rate:")
        self.update_lb.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.update_le = QtWidgets.QLineEdit()
        self.update_le.setValidator(QtGui.QIntValidator(1, 30, self))
        for widget in (self.update_lb, self.update_le):
            widget.setToolTip("How many times a second this window shows split detection's latest values, from 1 to 30. "
                              "Split detection itself isn't affected.")
        update_rate_layout = QtWidgets.QHBoxLayout()
        update_rate_layout.addWidget(self.update_lb)
        update_rate_layout.addWidget(self.update_le)
        grid.addLayout(update_rate_layout, row, 1)

        # The logs open in the text editor
        self.open_log_btn = QtWidgets.QPushButton("Open Log")
        self.open_log_btn.setToolTip("This session's log")
        self.open_old_log_btn = QtWidgets.QPushButton("Open Previous Log")
        self.open_old_log_btn.setToolTip("The previous session's log")
        self.save_debug_info_btn = QtWidgets.QPushButton("Save Debug Info")
        self.save_debug_info_btn.setToolTip("Save the logs, settings, route and a captured frame in one file, for a bug report")
        buttons = QtWidgets.QGridLayout()
        buttons.addWidget(self.open_log_btn, 0, 0)
        buttons.addWidget(self.open_old_log_btn, 0, 1)
        buttons.addWidget(self.save_debug_info_btn, 1, 0, 1, 2)
        layout.addLayout(buttons)

        self._show_advanced(bool(config.get("general", "debug_advanced")), save=False)

        # Connections
        self.update_le.editingFinished.connect(self._update_rate_changed)
        self.open_log_btn.clicked.connect(lambda: self._open(logs.LOG_FILE))
        self.open_old_log_btn.clicked.connect(lambda: self._open(logs.OLD_LOG_FILE))
        self.save_debug_info_btn.clicked.connect(self.save_debug_info)
        self.advanced_btn.toggled.connect(self._show_advanced)

    def _show_advanced(self, shown, save=True):
        self.advanced_btn.setChecked(shown)
        self.advanced_btn.setArrowType(QtCore.Qt.ArrowType.DownArrow if shown else QtCore.Qt.ArrowType.RightArrow)
        self.advanced.setVisible(shown)
        # Taller for Advanced, if it doesn't fit
        if shown:
            self.resize(self.width(), max(self.height(), self.sizeHint().height()))
        if save:
            config.set_key("general", "debug_advanced", shown)
            config.save_config()

    def _add_event(self, line):
        # Following the latest, unless reading further up
        bar = self.events.verticalScrollBar()
        following = bar.value() == bar.maximum()
        self.events.appendPlainText(line)
        if following:
            bar.setValue(bar.maximum())

    def update_log_buttons(self):
        """ The previous session's log is there from the second session on """
        self.open_old_log_btn.setEnabled(os.path.exists(logs.OLD_LOG_FILE))

    def _open(self, log):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(log).absolute())))

    def show(self):
        self.update_log_buttons()
        self.output_reader = OutputReader(parent=self)
        self.update_le.setText(str(update_rate()))

        self.output_reader.start()
        self.output_reader.output.connect(self.display_output)

        super().show()

    def display_output(self, output):
        for label, text in zip((self.status_lb, self.split_lb, self.needs_lb, self.counted_lb),
                               describe(output["status"], output["livesplit"])):
            label.setText(text)
        # Only the status while it isn't running
        for row in (1, 2, 3):
            self._basics.setRowVisible(row, bool(self.split_lb.text()))
        for key, field in self.fields.items():
            text = str(output[key])
            field.setText(text[:6] if key in self.SHORTENED else text)

    def _stop_reader(self):
        # Started when the dialog is shown
        if self.output_reader:
            self.output_reader.stop()
            # Deleting the window while the thread runs would abort AutoSplit64++
            self.output_reader.wait()

    def hide(self):
        self._stop_reader()
        super().hide()

    def closeEvent(self, e):
        # Closed when AutoSplit64++ quits too, also when it wasn't open
        if self.isVisible():
            config.set_key("general", "debug_window_size", [self.width(), self.height()])
            config.save_config()
        self._stop_reader()
        super().closeEvent(e)

    def _update_rate_changed(self):
        try:
            self.output_reader.update_rate = int(self.update_le.text())
            config.set_key("general", "output_update_rate", self.output_reader.update_rate)
            config.save_config()
        except ValueError:
            pass


class OutputReader(QtCore.QThread):
    output = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.running = True
        self.update_rate = update_rate()
        self._stopped = threading.Event()

    def stop(self):
        self.running = False
        self._stopped.set()

    def run(self):
        while self.running:
            try:
                prediction = as64.prediction_info.prediction
                if prediction > 120:
                    prediction = "None"
                probability = as64.prediction_info.probability
            except AttributeError:
                prediction = None
                probability = None

            output_data = {
                "fade_status": as64.fade_status,
                "fadeout_count": as64.fadeout_count,
                "fadein_count": as64.fadein_count,
                "xcam_percent": as64.xcam_percent,
                "xcam_count": as64.xcam_count,
                "xcam_status": as64.in_xcam,
                "prediction": prediction,
                "probability": probability,
                "execution": as64.execution_time,
                # Split detection, once it was started
                "status": as64._base.status() if getattr(as64, "_base", None) else None,
                "livesplit": livesplit_state(),
            }

            self.output.emit(output_data)

            # Returns as soon as it's stopped
            self._stopped.wait(1 / self.update_rate)
