import os
import threading
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from ..constants import (
    ICON_PATH
)

from autosplit64 import core as as64
from autosplit64.core import resource_utils, config, logs
from autosplit64.gui.widgets import HLine


def update_rate():
    """ How many times a second the window shows the latest values. 0 was allowed before, which is 1 now. """
    return max(1, config.get("general", "output_update_rate"))


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
        self.setMinimumSize(*self.DEFAULT_SIZE)
        self.resize(*(config.get("general", "debug_window_size") or self.DEFAULT_SIZE))

        # Output Reader
        self.output_reader = None

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        # Each output key's field
        self.fields = {}
        row = 0
        for fields in self.ROWS:
            if isinstance(fields, int):
                if fields:
                    layout.addItem(QtWidgets.QSpacerItem(10, fields), row, 0)
                layout.addWidget(HLine(), row + 1, 0, 1, 4)
                if fields:
                    layout.addItem(QtWidgets.QSpacerItem(10, fields), row + 2, 0)
                row += 3
                continue
            for column, (text, key, *wide) in enumerate(fields):
                label = QtWidgets.QLabel(text)
                label.setFixedWidth(100)
                self.fields[key] = QtWidgets.QLineEdit()
                self.fields[key].setDisabled(True)
                if wide:
                    layout.addWidget(self.fields[key], row + 1, column, 1, 2)
                else:
                    self.fields[key].setFixedWidth(100)
                    layout.addWidget(self.fields[key], row + 1, column)
                layout.addWidget(label, row, column)
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
        layout.addLayout(update_rate_layout, row, 1)
        layout.addItem(QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding), row + 1, 0)

        # The logs open in the text editor
        self.open_log_btn = QtWidgets.QPushButton("Open Log")
        self.open_log_btn.setToolTip("This session's log")
        self.open_old_log_btn = QtWidgets.QPushButton("Open Previous Log")
        self.open_old_log_btn.setToolTip("The previous session's log")
        self.save_debug_info_btn = QtWidgets.QPushButton("Save Debug Info")
        self.save_debug_info_btn.setToolTip("Save the logs, settings, route and a captured frame in one file, for a bug report")
        layout.addWidget(self.open_log_btn, row + 2, 0)
        layout.addWidget(self.open_old_log_btn, row + 2, 1)
        layout.addWidget(self.save_debug_info_btn, row + 3, 0, 1, 2)

        # Connections
        self.update_le.editingFinished.connect(self._update_rate_changed)
        self.open_log_btn.clicked.connect(lambda: self._open(logs.LOG_FILE))
        self.open_old_log_btn.clicked.connect(lambda: self._open(logs.OLD_LOG_FILE))
        self.save_debug_info_btn.clicked.connect(self.save_debug_info)

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
                "execution": as64.execution_time
            }

            self.output.emit(output_data)

            # Returns as soon as it's stopped
            self._stopped.wait(1 / self.update_rate)
