import contextlib
import os
import time

from PyQt6 import QtCore, QtGui, QtWidgets
import cv2

from ..constants import (
    ICON_PATH
)
from ..qml_view import qml_view
from autosplit64.core import resource_utils

from autosplit64.core.game_capture import GameCapture
from autosplit64.core.image_utils import is_black
from autosplit64.core import config
from autosplit64.core.constants import (
    GAME_JP,
    RESET_REGION,
    FADEOUT_REGION
)


def image_url(path, version):
    """ The QML image source for path, a different one for each version of the file """
    return QtCore.QUrl.fromLocalFile(os.path.abspath(path)).toString() + f"?{version}"


class Templates(QtCore.QObject):
    """
    What ResetGeneratorDialog.qml shows, in values: the generate button's status, whether it's busy, whether
    frames were generated, the frame chosen for each template, and the images shown. Its other signals are
    the QML's clicks, and failed() shows an error.
    """
    changed = QtCore.pyqtSignal()
    generate = QtCore.pyqtSignal()
    apply = QtCore.pyqtSignal()
    cancel = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._values = {"status": "Generate", "busy": False, "generated": False, "chosen": [2, 3], "shown": ["", ""]}
        self._version = 0

    @QtCore.pyqtProperty("QVariantMap", notify=changed)
    def values(self):
        return self._values

    def update(self, **values):
        self._values.update(values)
        self.changed.emit()

    def show_images(self, paths):
        # A new version each time: the generated frames are written to the same files
        self._version += 1
        self.update(shown=[image_url(path, self._version) for path in paths])

    @QtCore.pyqtSlot(int, int)
    def choose(self, column, number):
        chosen = list(self._values["chosen"])
        chosen[column] = number
        self.update(chosen=chosen)
        paths = [ResetGeneratorDialog._temp_path(number) for number in chosen]
        self.show_images(paths)


class ResetGeneratorDialog(QtWidgets.QDialog):
    applied = QtCore.pyqtSignal()

    TEMPLATE_DIR = "templates/"

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Reset Template Generator")
        self.setWindowIcon(QtGui.QIcon(resource_utils.base_path(ICON_PATH)))
        self.resize(620, 480)

        self._reset_generator = None
        # Counts the wait for the runner to reset the console, which takes as long as they take
        self._wait_timer = QtCore.QTimer(self)
        self._wait_timer.setInterval(1000)
        self._wait_timer.timeout.connect(self._show_wait)
        self._wait_start = 0

        self.templates = Templates()
        self.templates.generate.connect(self.generate_clicked)
        self.templates.apply.connect(self.apply_clicked)
        self.templates.cancel.connect(self.cancel_clicked)
        defaults = [image_url(config.get_default("advanced", f"reset_frame_{name}"), 0) for name in ("one", "two")]
        self.view = qml_view(self, "ResetGeneratorDialog", templates=self.templates, defaults=defaults,
                             captureCount=ResetGenerator.CAPTURE_COUNT)

    @classmethod
    def _temp_path(cls, number):
        return f"{cls.TEMPLATE_DIR}generated_temp_{number}.jpg"

    def _remove_temp_files(self):
        for number in range(1, ResetGenerator.CAPTURE_COUNT + 1):
            with contextlib.suppress(FileNotFoundError):
                os.remove(self._temp_path(number))

    def show(self):
        self._reset_generator = ResetGenerator()
        self._reset_generator.generated.connect(self.on_generate)
        self._reset_generator.error.connect(self.on_error)
        self._reset_generator.reset_seen.connect(self.on_reset_seen)

        # The templates in use until new ones are generated
        self.templates.show_images([config.get("advanced", "reset_frame_one"), config.get("advanced", "reset_frame_two")])
        self.templates.update(status="Generate", busy=False, generated=False)
        super().show()

    def hide(self):
        self._reset_generator.stop()
        super().hide()

    def generate_clicked(self):
        self._wait_start = time.monotonic()
        self._show_wait()
        self._wait_timer.start()
        self.templates.update(busy=True)
        self._reset_generator.start()

    def _show_wait(self):
        self.templates.update(status=f"Reset your console… {int(time.monotonic() - self._wait_start)} s")

    def on_reset_seen(self):
        self._wait_timer.stop()
        self.templates.update(status="Capturing…")

    def apply_clicked(self):
        for name, number in zip(("one", "two"), self.templates.values["chosen"]):
            template = f"{self.TEMPLATE_DIR}generated_reset_{name}.jpg"
            with contextlib.suppress(FileNotFoundError):
                os.remove(template)
            with contextlib.suppress(FileNotFoundError):
                os.rename(self._temp_path(number), template)
            config.set_key("advanced", f"reset_frame_{name}", template)
        self._remove_temp_files()
        config.save_config()

        self._reset_generator.stop()
        self.hide()
        self.applied.emit()

    def cancel_clicked(self):
        self._wait_timer.stop()
        self._remove_temp_files()
        self._reset_generator.stop()
        self.hide()

    def on_generate(self):
        self._wait_timer.stop()
        self.templates.update(chosen=[2, 3], status="Generate", busy=False, generated=True)
        self.templates.show_images([self._temp_path(2), self._temp_path(3)])

    def closeEvent(self, event):
        self._wait_timer.stop()
        self._remove_temp_files()
        self._reset_generator.stop()
        super().closeEvent(event)

    def on_error(self, error):
        # The window stays open, to generate again once the capture is fixed
        self._wait_timer.stop()
        self.templates.update(status="Generate", busy=False, generated=False)
        self.templates.failed.emit(error)


class ResetGenerator(QtCore.QThread):
    CAPTURE_COUNT = 5

    generated = QtCore.pyqtSignal()
    # The black screen of the reset, after which the logo's frames are captured
    reset_seen = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running = False
        self._game_capture = GameCapture(config.get("game", "use_obs"), config.get("game", "vc_fix"), config.get("game", "process_name"), config.get("game", "game_region"), GAME_JP, config.get("game", "capture_device") if config.get("game", "capture_source") == "device" else None)

    def run(self):
        self._running = True
        reset_occurred = False
        frame = 0

        generated_frames = []
        
        try:
            self._game_capture.is_valid()
        except Exception as e:
            self.error.emit(str(e))
            self.stop()
            return

        while self._running:
            c_time = time.perf_counter()
            try:
                self._game_capture.capture()
            except Exception as e:
                self.error.emit(str(e))
                self.stop()
                return

            reset_region = self._game_capture.get_region(RESET_REGION)
            fadeout_region = self._game_capture.get_region(FADEOUT_REGION)

            if is_black(fadeout_region, 0.1, 0.97) and not reset_occurred:
                reset_occurred = True
                self.reset_seen.emit()

            if reset_occurred:
                if not is_black(fadeout_region, config.get("thresholds", "black_threshold"), 0.99):
                    frame += 1

                    if frame <= self.CAPTURE_COUNT:
                        generated_frames.append(reset_region)
                    else:
                        self._running = False

            try:
                time.sleep((1 / 29.97) - (time.perf_counter() - c_time))
            except ValueError:
                pass

        for i, frame in enumerate(generated_frames):
            cv2.imwrite(ResetGeneratorDialog._temp_path(i + 1), frame)

        self.generated.emit()

    def stop(self):
        self._running = False



