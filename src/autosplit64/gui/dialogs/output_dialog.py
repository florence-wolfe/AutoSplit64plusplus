from PyQt6 import QtCore, QtGui, QtWidgets
import time

from ..constants import (
    ICON_PATH
)

from autosplit64 import core as as64
from autosplit64.core import resource_utils, config
from autosplit64.gui.widgets import HLine


class OutputDialog(QtWidgets.QDialog):
    open_capture = QtCore.pyqtSignal()

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
        self.setWindowTitle("Output")
        self.setWindowIcon(QtGui.QIcon(resource_utils.base_path(ICON_PATH)))
        self.setFixedSize(250, 375)

        # Output Reader
        self.output_reader = None
        self._update_rate = config.get("general", "output_update_rate")

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

        update_lb = QtWidgets.QLabel("Update Rate:")
        update_lb.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.update_le = QtWidgets.QLineEdit()
        self.update_le.setValidator(QtGui.QIntValidator(0, 30, self))
        update_rate_layout = QtWidgets.QHBoxLayout()
        update_rate_layout.addWidget(update_lb)
        update_rate_layout.addWidget(self.update_le)
        layout.addLayout(update_rate_layout, row, 1)
        layout.addItem(QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding), row + 1, 0)

        # Connections
        self.update_le.editingFinished.connect(self._update_rate_changed)

    def show(self):
        self.output_reader = OutputReader(parent=self)
        self.update_le.setText(str(self._update_rate))

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
            self.output_reader.running = False
            self.output_reader.exit()

    def hide(self):
        self._stop_reader()
        super().hide()

    def closeEvent(self, e):
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
        self.update_rate = config.get("general", "output_update_rate")

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

            try:
                time.sleep(1 / self.update_rate)
            except ValueError:
                pass
