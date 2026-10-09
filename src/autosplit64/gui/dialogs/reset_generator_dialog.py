import contextlib
import os
import time

from PyQt6 import QtCore, QtGui, QtWidgets
import cv2

from ..constants import (
    ICON_PATH
)
from autosplit64.core import resource_utils

from autosplit64.core.game_capture import GameCapture
from autosplit64.core.image_utils import is_black
from autosplit64.core import config
from autosplit64.core.constants import (
    GAME_JP,
    RESET_REGION,
    FADEOUT_REGION
)


class ResetGeneratorHelpDialog(QtWidgets.QDialog):
    LINES = ["AutoSplit64's reset feature works based on matching the second and third frame of the Super Mario 64 logo that appears when launching the game.",
             "If the colours or capture size of your particular game feed differ from the default standard it may be required to generate custom templates from your game capture.",
             "While in-game, press generate, then RESET your console. Ensure the generated images look similar to the examples. "]

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Reset Template Generator Help")
        self.setWindowIcon(QtGui.QIcon(resource_utils.base_path(ICON_PATH)))
        self.resize(400, 260)

        text_edit = QtWidgets.QTextEdit()
        text_edit.setEnabled(False)
        text_edit.append("\n\n\n".join(self.LINES))
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.clicked.connect(self.hide)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(text_edit)
        layout.addLayout(button_layout)


class ResetGeneratorDialog(QtWidgets.QDialog):
    applied = QtCore.pyqtSignal()

    TEMPLATE_DIR = "templates/"
    FRAME_WIDTH = 251
    FRAME_HEIGHT = 137

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Reset Template Generator")
        self.setWindowIcon(QtGui.QIcon(resource_utils.base_path(ICON_PATH)))
        self.resize(400, 200)

        self._reset_generator = None
        self.help_dialog = ResetGeneratorHelpDialog(self)

        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.generate_btn = QtWidgets.QPushButton("Generate")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        help_btn = QtWidgets.QPushButton("Help")

        layout = QtWidgets.QGridLayout(self)
        # Frames two and three of the logo: the generated frame chosen for each, above the default
        self.gen_1_sb, self.gen_1_px = self._add_frame_column(layout, 0, "Two", "one")
        self.gen_2_sb, self.gen_2_px = self._add_frame_column(layout, 1, "Three", "two")

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        for button in (help_btn, cancel_btn, self.generate_btn, self.apply_btn):
            button_layout.addWidget(button)
        layout.addLayout(button_layout, 5, 0, 1, 2)

        self.generate_btn.clicked.connect(self.generate_clicked)
        self.apply_btn.clicked.connect(self.apply_clicked)
        cancel_btn.clicked.connect(self.cancel_clicked)
        help_btn.clicked.connect(self.help_dialog.show)

    def _add_frame_column(self, layout, column, frame, default):
        spin_box = QtWidgets.QSpinBox()
        spin_box.setMaximumWidth(40)
        spin_box.setRange(1, ResetGenerator.CAPTURE_COUNT)
        spin_box.setValue(column + 2)
        generated = QtWidgets.QLabel()
        generated.setFixedSize(self.FRAME_WIDTH, self.FRAME_HEIGHT)
        spin_box.valueChanged.connect(lambda number: self._show_frame(generated, number))
        default_px = QtWidgets.QLabel()
        default_px.setFixedSize(self.FRAME_WIDTH, self.FRAME_HEIGHT)
        default_px.setPixmap(QtGui.QPixmap(f"{self.TEMPLATE_DIR}default_reset_{default}.jpg"))

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(spin_box)
        top_layout.addWidget(QtWidgets.QLabel(f"Generated Frame {frame}:"))
        layout.addLayout(top_layout, 1, column)
        layout.addWidget(generated, 2, column)
        layout.addWidget(QtWidgets.QLabel(f"Desired Frame {frame}:"), 3, column)
        layout.addWidget(default_px, 4, column)
        return spin_box, generated

    @classmethod
    def _temp_path(cls, number):
        return f"{cls.TEMPLATE_DIR}generated_temp_{number}.jpg"

    def _show_frame(self, label, number):
        self._show_image(label, self._temp_path(number))

    def _show_image(self, label, path):
        label.setPixmap(QtGui.QPixmap(path).scaledToWidth(self.FRAME_WIDTH).scaledToHeight(self.FRAME_HEIGHT))

    def _remove_temp_files(self):
        for number in range(1, ResetGenerator.CAPTURE_COUNT + 1):
            with contextlib.suppress(FileNotFoundError):
                os.remove(self._temp_path(number))

    def show(self):
        self._reset_generator = ResetGenerator()
        self._reset_generator.generated.connect(self.on_generate)
        self._reset_generator.error.connect(self.on_error)

        # The templates in use until new ones are generated
        self._show_image(self.gen_1_px, config.get("advanced", "reset_frame_one"))
        self._show_image(self.gen_2_px, config.get("advanced", "reset_frame_two"))
        self.generate_btn.setText("Generate")
        self.generate_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        self.gen_1_sb.setEnabled(False)
        self.gen_2_sb.setEnabled(False)
        super().show()

    def hide(self):
        self._reset_generator.stop()
        super().hide()

    def generate_clicked(self):
        self.generate_btn.setText("Waiting..")
        self.generate_btn.setEnabled(False)
        self._reset_generator.start()

    def apply_clicked(self):
        for name, spin_box in (("one", self.gen_1_sb), ("two", self.gen_2_sb)):
            template = f"{self.TEMPLATE_DIR}generated_reset_{name}.jpg"
            with contextlib.suppress(FileNotFoundError):
                os.remove(template)
            with contextlib.suppress(FileNotFoundError):
                os.rename(self._temp_path(spin_box.value()), template)
            config.set_key("advanced", f"reset_frame_{name}", template)
        self._remove_temp_files()
        config.save_config()

        self._reset_generator.stop()
        self.hide()
        self.applied.emit()

    def cancel_clicked(self):
        self._remove_temp_files()
        self._reset_generator.stop()
        self.hide()

    def on_generate(self):
        self._show_frame(self.gen_1_px, 2)
        self._show_frame(self.gen_2_px, 3)
        self.gen_1_sb.setValue(2)
        self.gen_2_sb.setValue(3)
        self.generate_btn.setText("Generate")
        self.generate_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)
        self.gen_1_sb.setEnabled(True)
        self.gen_2_sb.setEnabled(True)

    def closeEvent(self, event):
        self._remove_temp_files()
        self._reset_generator.stop()
        super().closeEvent(event)

    def on_error(self, error):
        self.generate_btn.setText("Generate")
        self.generate_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)

        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg.setWindowTitle("Error")
        msg.setText(error)
        msg.exec()
        self.hide()


class ResetGenerator(QtCore.QThread):
    CAPTURE_COUNT = 5

    generated = QtCore.pyqtSignal()
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
            c_time = time.time()
            try:
                self._game_capture.capture()
            except Exception as e:
                self.error.emit(str(e))
                self.stop()
                return

            reset_region = self._game_capture.get_region(RESET_REGION)
            fadeout_region = self._game_capture.get_region(FADEOUT_REGION)

            if is_black(fadeout_region, 0.1, 0.97):
                reset_occurred = True

            if reset_occurred:
                if not is_black(fadeout_region, config.get("thresholds", "black_threshold"), 0.99):
                    frame += 1

                    if frame <= self.CAPTURE_COUNT:
                        generated_frames.append(reset_region)
                    else:
                        self._running = False

            try:
                time.sleep((1 / 29.97) - (time.time() - c_time))
            except ValueError:
                pass

        for i, frame in enumerate(generated_frames):
            cv2.imwrite(ResetGeneratorDialog._temp_path(i + 1), frame)

        self.generated.emit()

    def stop(self):
        self._running = False



