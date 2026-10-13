import logging
import os
import threading
from collections import deque
from pathlib import Path
from types import SimpleNamespace

from PyQt6 import QtCore, QtGui, QtWidgets

from ..constants import (
    ICON_PATH
)

from autosplit64.core import resource_utils, config, livesplit, livesplit_one, logs
from autosplit64.core.constants import INITIAL_STATE, SPLIT_FADE_ONLY, SPLIT_FINAL, SPLIT_MIPS, SPLIT_MIPS_X, SPLIT_XCAM
from autosplit64.gui.qml_view import qml_view

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
    """ (status, split, what the split needs, what's counted) in words, from SplitDetection.status() and livesplit_state() """
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


class Debug(QtCore.QObject):
    """
    What DebugDialog.qml shows, in values: what split detection is doing, its fields, whether Advanced is
    shown, the update rate and whether there's a previous log. line() is each new event, after lines, and
    its other signals are the QML's changes and clicks.
    """
    changed = QtCore.pyqtSignal()
    line = QtCore.pyqtSignal(str)
    advanced_toggled = QtCore.pyqtSignal(bool)
    update_rate_changed = QtCore.pyqtSignal(int)
    open_log = QtCore.pyqtSignal()
    open_old_log = QtCore.pyqtSignal()
    save_info = QtCore.pyqtSignal()

    def __init__(self, lines):
        super().__init__()
        self._lines = lines
        self._values = {"status": "", "split": "", "needs": "", "counted": "", "fields": {}, "advanced": False,
                        "updateRate": 1, "oldLog": False}

    @QtCore.pyqtProperty("QVariantMap", notify=changed)
    def values(self):
        return self._values

    @QtCore.pyqtProperty("QVariantList", constant=True)
    def lines(self):
        return self._lines

    def update(self, **values):
        self._values.update(values)
        self.changed.emit()


class DebugDialog(QtWidgets.QDialog):
    open_capture = QtCore.pyqtSignal()
    save_debug_info = QtCore.pyqtSignal()

    # Before it's resized
    DEFAULT_SIZE = (360, 480)

    # Fractions, of which only the first characters are shown
    SHORTENED = {"xcam_percent", "probability", "execution"}

    def __init__(self, parent=None, detection=lambda: None):
        super().__init__(parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Debug")
        self.setWindowIcon(QtGui.QIcon(resource_utils.base_path(ICON_PATH)))
        self.resize(*(config.get("general", "debug_window_size") or self.DEFAULT_SIZE))

        # Output Reader
        self.output_reader = None
        # The split detection that started last, or None
        self._detection = detection

        events = detection_events()
        self.debug = Debug(events.lines())
        events.signal.line.connect(self.debug.line)
        self.debug.advanced_toggled.connect(self._show_advanced)
        self.debug.update_rate_changed.connect(self._update_rate_changed)
        self.debug.open_log.connect(lambda: self._open(logs.LOG_FILE))
        self.debug.open_old_log.connect(lambda: self._open(logs.OLD_LOG_FILE))
        self.debug.save_info.connect(self.save_debug_info)
        self.view = qml_view(self, "DebugDialog", debug=self.debug, maxEvents=DetectionEvents.MAX)
        # Tall enough for what's shown, e.g. Advanced. Queued: resizing while the QML renders a frame breaks it.
        self.view.rootObject().implicitHeightChanged.connect(self._fit, QtCore.Qt.ConnectionType.QueuedConnection)
        self._fit()

        self._show_advanced(bool(config.get("general", "debug_advanced")), save=False)

    def _fit(self):
        self.setMinimumHeight(int(self.view.rootObject().property("implicitHeight")))

    def _show_advanced(self, shown, save=True):
        self.debug.update(advanced=shown)
        if save:
            config.set_key("general", "debug_advanced", shown)
            config.save_config()

    def update_log_buttons(self):
        """ The previous session's log is there from the second session on """
        self.debug.update(oldLog=os.path.exists(logs.OLD_LOG_FILE))

    def _open(self, log):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(log).absolute())))

    def show(self):
        self.update_log_buttons()
        self.output_reader = OutputReader(self._detection, parent=self)
        self.debug.update(updateRate=update_rate())

        self.output_reader.start()
        self.output_reader.output.connect(self.display_output)

        super().show()

    def display_output(self, output):
        status, split, needs, counted = describe(output["status"], output["livesplit"])
        fields = {key: str(output[key])[:6] if key in self.SHORTENED else str(output[key])
                  for key in ("fade_status", "fadeout_count", "fadein_count", "xcam_percent", "xcam_count", "xcam_status",
                              "prediction", "probability", "execution")}
        self.debug.update(status=status, split=split, needs=needs, counted=counted, fields=fields)

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

    def _update_rate_changed(self, rate):
        self.output_reader.update_rate = rate
        self.debug.update(updateRate=rate)
        config.set_key("general", "output_update_rate", rate)
        config.save_config()


class OutputReader(QtCore.QThread):
    output = QtCore.pyqtSignal(dict)

    def __init__(self, detection, parent=None):
        super().__init__(parent)

        # Gives the split detection that started last, or None
        self._detection = detection
        self.running = True
        self.update_rate = update_rate()
        self._stopped = threading.Event()

    def stop(self):
        self.running = False
        self._stopped.set()

    def run(self):
        while self.running:
            detection = self._detection()
            # Before split detection first starts, its initial state
            state = SimpleNamespace(**INITIAL_STATE) if detection is None else detection
            try:
                prediction = state.prediction_info.prediction
                if prediction > 120:
                    prediction = "None"
                probability = state.prediction_info.probability
            except AttributeError:
                prediction = None
                probability = None

            output_data = {
                "fade_status": state.fade_status,
                "fadeout_count": state.fadeout_count,
                "fadein_count": state.fadein_count,
                "xcam_percent": state.xcam_percent,
                "xcam_count": state.xcam_count,
                "xcam_status": state.in_xcam,
                "prediction": prediction,
                "probability": probability,
                "execution": state.execution_time,
                # Split detection, once it was started
                "status": detection.status() if detection is not None else None,
                "livesplit": livesplit_state(),
            }

            self.output.emit(output_data)

            # Returns as soon as it's stopped
            self._stopped.wait(1 / self.update_rate)
