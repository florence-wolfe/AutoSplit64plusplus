import sys

from PyQt6 import QtCore, QtGui, QtWidgets

import cv2

from autosplit64.core import capture_shmem, config
if sys.platform == "darwin":
    from autosplit64.core import capture_device_mac as capture_device
    from autosplit64.core import capture_window_mac as capture_window
else:
    from autosplit64.core import capture_window_win as capture_window
from autosplit64.core import resource_utils
from ..widgets import HLine
from ..graphics import RectangleSelector, ZoomableGraphicsView
from ..constants import (
    ICON_PATH,
    PLACEHOLDER_PATH,
)

class CaptureEditor(QtWidgets.QDialog):

    applied = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)

        self.window_title = "Game Capture Editor"
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))
        
        # Initialize SharedMemoryCapture
        self.shmem_capture = capture_shmem.SharedMemoryCapture()

        # Layouts
        self.main_layout = QtWidgets.QHBoxLayout()
        self.left_layout = QtWidgets.QGridLayout()
        self.right_layout = QtWidgets.QGridLayout()

        # Primary Widgets
        self.left_widget = QtWidgets.QWidget(self)
        self.right_widget = QtWidgets.QWidget(self)

        # Right Panel Widgets
        self.game_region_panel = RectangleCapturePanel("Game Region")
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")

        # Left Panel Widgets
        self.use_obs_cb = QtWidgets.QCheckBox("Use OBS Plugin")
        self.process_lb = QtWidgets.QLabel("Process:")
        self.process_combo = QtWidgets.QComboBox()
        self.capture_btn = QtWidgets.QPushButton("Capture Screen")
        self.auto_region_btn = QtWidgets.QPushButton("Auto Detect Region")
        self.vc_fix_cb = QtWidgets.QCheckBox("VC fix (experimental)")

        # Graphics View
        self.graphics_scene = CaptureGraphicsScene()
        self.graphics_view = ZoomableGraphicsView(self.graphics_scene)

        # Graphics Scene Items
        self.game_region_selector = RectangleSelector(0, 0, 50, 50)

        self.preview_pixmap = QtGui.QPixmap()

        self.initialize()

    def initialize(self):
        self.setWindowTitle(self.window_title)

        # Set Top Level Layouts
        self.setLayout(self.main_layout)
        self.left_widget.setLayout(self.left_layout)
        self.right_widget.setLayout(self.right_layout)
        self.right_widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        # Configure Top Level Widgets
        self.left_widget.setFixedWidth(220)
        self.right_widget.setFixedWidth(220)

        # Add Top Level Widgets
        self.main_layout.addWidget(self.left_widget)
        self.main_layout.addWidget(self.graphics_view)
        self.main_layout.addWidget(self.right_widget)

        # Left Widget
        self.capture_btn.setDefault(False)
        self.capture_btn.setAutoDefault(False)
        self.auto_region_btn.setDefault(False)
        self.auto_region_btn.setAutoDefault(False)
        self.process_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Minimum)

        # Filled when the editor is shown, so macOS doesn't ask for Screen Recording at launch
        self._process_list = []

        self.left_layout.addWidget(self.use_obs_cb, 0, 0, 1, 2)
        # The OBS Plugin is only available on Windows
        self.use_obs_cb.setVisible(sys.platform == "win32")
        if sys.platform == "darwin":
            self._add_mac_capture_widgets()
        self.left_layout.addWidget(self.process_lb, 1, 0)
        self.left_layout.addWidget(self.process_combo, 1, 1)
        self.left_layout.addWidget(self.capture_btn, 2, 0, 1, 2)
        self.left_layout.addWidget(self.auto_region_btn, 3, 0, 1, 2)
        self.left_layout.addWidget(self.vc_fix_cb, 4, 0, 1, 2)
        self.left_layout.addLayout(self._zoom_controls(), 5, 0, 1, 2)

        self.left_layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Expanding), 6, 0)

        # Add connection for checkbox
        self.use_obs_cb.stateChanged.connect(self.toggle_capture_method)

        # Right Widget
        self.apply_btn.setDefault(False)
        self.apply_btn.setAutoDefault(False)
        self.cancel_btn.setDefault(False)
        self.cancel_btn.setAutoDefault(False)

        self.right_layout.addWidget(self.game_region_panel, 5, 0, 1, 2)
        self.right_layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Expanding), 9, 0)
        self.right_layout.addWidget(HLine(), 10, 0, 1, 2)
        self.right_layout.addWidget(self.apply_btn, 15, 0)
        self.right_layout.addWidget(self.cancel_btn, 15, 1)

        # Configure Graphics View
        self.refresh_graphics_scene()

        # Connections
        self.graphics_scene.item_update.connect(self.on_graphics_item_update)
        self.capture_btn.clicked.connect(self.refresh_graphics_scene)
        self.apply_btn.clicked.connect(self.apply_clicked)
        self.cancel_btn.clicked.connect(self.cancel_clicked)
        self.game_region_panel.updated.connect(self.on_game_region_panel_update)
        self.process_combo.currentIndexChanged.connect(self.refresh_graphics_scene)
        self.auto_region_btn.clicked.connect(self.auto_detect_region)

        self.refresh_graphics_scene()

    def toggle_capture_method(self, state):
        use_obs = bool(state)
        self.process_lb.setVisible(not use_obs)
        self.process_combo.setVisible(not use_obs)

        # Refresh the view with new capture method
        self.refresh_graphics_scene()

    def _zoom_controls(self):
        """ Zoom out, fit the capture in the view, zoom in, and the zoom level """
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Zoom:"))
        zoom_lb = QtWidgets.QLabel("100%")
        # Wide enough for any zoom level, so the buttons don't move
        zoom_lb.setFixedWidth(zoom_lb.fontMetrics().horizontalAdvance("1000%"))
        self.graphics_view.zoom_changed.connect(lambda zoom: zoom_lb.setText(f"{zoom:.0%}"))
        for text, tooltip, action in [("−", "Zoom out", self.graphics_view.zoom_out),
                                      ("Fit", "Show the whole capture", self._fit_capture),
                                      ("+", "Zoom in", self.graphics_view.zoom_in)]:
            button = QtWidgets.QPushButton(text)
            button.setToolTip(tooltip)
            button.setAutoDefault(False)
            button.setFixedWidth(32)
            button.clicked.connect(action)
            layout.addWidget(button)
        layout.addWidget(zoom_lb)
        return layout

    def _fit_capture(self):
        self.graphics_view.fit(QtCore.QRectF(self.preview_pixmap.rect()))

    def _refresh_process_list(self):
        self.process_combo.clear()
        # Listing the windows without the Screen Recording permission shows macOS's prompt
        if sys.platform == "darwin" and not capture_window.has_permission_quietly():
            self._process_list = []
            return
        self._process_list = capture_window.get_visible_processes()
        self.process_combo.addItems([proc[0].name() for proc in self._process_list])

    def _add_mac_capture_widgets(self):
        """ On macOS, choose between a video device and a window, each with its own permission """
        mac_panel = QtWidgets.QWidget()
        mac_layout = QtWidgets.QVBoxLayout(mac_panel)
        mac_layout.setContentsMargins(0, 0, 0, 0)

        source_layout = QtWidgets.QHBoxLayout()
        self.source_combo = QtWidgets.QComboBox()
        self.source_combo.addItems(["Video Device", "Window"])
        source_layout.addWidget(QtWidgets.QLabel("Source:"))
        source_layout.addWidget(self.source_combo, 1)
        mac_layout.addLayout(source_layout)

        # Shown while the permission for the selected source is missing
        self.permission_panel = QtWidgets.QWidget()
        permission_layout = QtWidgets.QVBoxLayout(self.permission_panel)
        permission_layout.setContentsMargins(0, 8, 0, 8)
        self.permission_lb = QtWidgets.QLabel()
        self.permission_lb.setWordWrap(True)
        self.allow_btn = QtWidgets.QPushButton()
        settings_btn = QtWidgets.QPushButton("Open System Settings")
        for btn in (self.allow_btn, settings_btn):
            btn.setAutoDefault(False)
        self.allow_btn.clicked.connect(lambda: self._capture_module().request_permission())
        settings_btn.clicked.connect(lambda: self._capture_module().open_permission_settings())
        permission_layout.addWidget(self.permission_lb)
        permission_layout.addWidget(self.allow_btn)
        permission_layout.addWidget(settings_btn)
        mac_layout.addWidget(self.permission_panel)

        # Shares the row of the OBS Plugin checkbox, which is hidden on macOS
        self.left_layout.addWidget(mac_panel, 0, 0, 1, 2)

        # Takes the place of the process selector when capturing a video device
        self.device_lb = QtWidgets.QLabel("Device:")
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.left_layout.addWidget(self.device_lb, 1, 0)
        self.left_layout.addWidget(self.device_combo, 1, 1)
        self._devices = []

        # Check again while the editor is open, to notice when the permission is granted
        self._permission_timer = QtCore.QTimer(self)
        self._permission_timer.timeout.connect(self._update_permission)

        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.device_combo.currentIndexChanged.connect(self.refresh_graphics_scene)

    def _use_device(self):
        return sys.platform == "darwin" and self.source_combo.currentText() == "Video Device"

    def _capture_module(self):
        return capture_device if self._use_device() else capture_window

    def _refresh_device_list(self):
        self._devices = capture_device.get_devices()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItems([name for _, name in self._devices])
        for i, (unique_id, _) in enumerate(self._devices):
            if unique_id == config.get("game", "capture_device"):
                self.device_combo.setCurrentIndex(i)
        self.device_combo.blockSignals(False)

    def _capture_device(self):
        """ The selected video device's latest frame, or None """
        # Opening the device would ask for the permission by itself, or wait for frames that never come
        if not capture_device.has_permission():
            return None
        try:
            return capture_device.capture(self._devices[self.device_combo.currentIndex()][0])
        except Exception:
            return None

    def _on_source_changed(self):
        device = self._use_device()
        self.process_lb.setVisible(not device)
        self.process_combo.setVisible(not device)
        self.device_lb.setVisible(device)
        self.device_combo.setVisible(device)

        # Only capture, and ask for the permission of, the selected source
        capture_window.stop()
        capture_device.stop()
        if device:
            self._refresh_device_list()
        elif not self._process_list:
            self._refresh_process_list()
        self._update_permission()
        self.refresh_graphics_scene()

    def _update_permission(self):
        if self._use_device():
            self.permission_lb.setText("Camera permission is needed to capture the video device.\n\n"
                                       "If it's already on in System Settings, it may belong to an earlier build. "
                                       "Allow Camera asks macOS again for this one.")
            self.allow_btn.setText("Allow Camera")
        else:
            self.permission_lb.setText("Screen Recording permission is needed to capture the emulator window.\n\n"
                                       "If it's already on in System Settings, it may belong to an earlier build. "
                                       "Allow Screen Recording asks macOS again for this one.\n\n"
                                       "After allowing it, you may need to restart AutoSplit64++.")
            self.allow_btn.setText("Allow Screen Recording")

        # Checked every second while missing, so without asking for it: only Allow asks macOS
        granted = capture_device.has_permission() if self._use_device() else capture_window.has_permission_quietly()
        if granted and not self.permission_panel.isHidden():
            if not self._use_device():
                self._refresh_process_list()
            self.refresh_graphics_scene()
        self.permission_panel.setVisible(not granted)
        if granted:
            self._permission_timer.stop()
        else:
            self._permission_timer.start(1000)

    def show(self):
        if sys.platform == "darwin":
            self.source_combo.blockSignals(True)
            self.source_combo.setCurrentText("Video Device" if config.get("game", "capture_source") == "device" else "Window")
            self.source_combo.blockSignals(False)

        # Load game_region from preferences
        game_region = config.get('game', 'game_region')
        self.game_region_selector.resize(game_region[2], game_region[3])
        self.game_region_selector.setPos(game_region[0], game_region[1])

        self.game_region_panel.update_text(*[str(v) for v in game_region])

        # A video device source doesn't need windows, nor their permission
        if not self._use_device():
            self._refresh_process_list()

        p_name = config.get("game", "process_name")

        for i in range(len(self._process_list)):
            if self._process_list[i][0].name() == p_name:
                self.process_combo.setCurrentIndex(i)

        # Load use_obs preference
        use_obs = config.get("game", "use_obs") and sys.platform == "win32"
        self.use_obs_cb.setChecked(use_obs)
        self.toggle_capture_method(use_obs)
        if sys.platform == "darwin":
            self._on_source_changed()
        
        vc_fix = config.get("game", "vc_fix")
        self.vc_fix_cb.setChecked(vc_fix)

        self.refresh_graphics_scene()

        config.create_rollback()
        super().show()

    def apply_clicked(self):
        # Config
        config.set_key("game", "use_obs", self.use_obs_cb.isChecked())
        config.set_key("game", "game_region", self.game_region_panel.get_data())
        if sys.platform == "darwin":
            config.set_key("game", "capture_source", "device" if self._use_device() else "window")
            if self._use_device() and self._devices:
                config.set_key("game", "capture_device", self._devices[self.device_combo.currentIndex()][0])
        if not self.use_obs_cb.isChecked() and not self._use_device():
            config.set_key("game", "process_name", self.process_combo.currentText())

        try:
            if self.use_obs_cb.isChecked():
                config.set_key("game", "capture_size", self.shmem_capture.get_capture_size())
            elif self._use_device():
                config.set_key("game", "capture_size", capture_device.get_capture_size(self._devices[self.device_combo.currentIndex()][0]))
            else:
                config.set_key("game", "capture_size", capture_window.get_capture_size(self._process_list[self.process_combo.currentIndex()][1]))
        except:
            pass
        
        config.set_key("game", "vc_fix", self.vc_fix_cb.isChecked())

        config.save_config()
        # Close the shared memory connection
        self.shmem_capture.close_shmem()
        self.applied.emit()
        self.close()

    def cancel_clicked(self):
        # Close the shared memory connection
        self.shmem_capture.close_shmem()
        self.close()

    def on_graphics_item_update(self, e):
        if e.object_name == self.game_region_selector.object_name:
            rect = e.get_view_space_rect()
            self.game_region_panel.update_text(*[str(v) for v in rect])

    def on_game_region_panel_update(self, e):
        self.game_region_selector.resize(e[2], e[3])
        self.game_region_selector.setPos(e[0], e[1])

    def _capture(self):
        """ The selected source's latest frame, or None """
        if self.use_obs_cb.isChecked():
            try:
                return self.shmem_capture.capture()
            except Exception:
                return None
        if self._use_device():
            return self._capture_device()
        try:
            hwnd = self._process_list[self.process_combo.currentIndex()][1]
            return capture_window.capture(hwnd) if hwnd else None
        except Exception:
            return None

    def refresh_graphics_scene(self):
        """
        Clears the graphics scene and view, redraws all components including new screen capture
        :return:
        """

        # Remove all items that may be in the scene before clearing. Prevents program crash.
        self.graphics_scene.removeItem(self.game_region_selector)

        # Clear scene and update viewport
        self.graphics_scene.clear()
        self.graphics_view.update()
        
        preview_image = self._capture()
        if preview_image is not None:
            self.preview_pixmap.loadFromData(cv2.imencode(".png", preview_image)[1].tobytes())
        elif self.use_obs_cb.isChecked():
            self.preview_pixmap.load(resource_utils.resource_path(PLACEHOLDER_PATH))
        else:
            # Never show an earlier capture when nothing could be captured now
            self.preview_pixmap = QtGui.QPixmap(640, 480)
            self.preview_pixmap.fill(QtCore.Qt.GlobalColor.black)

        # Re-add all items to scene
        self.graphics_scene.addPixmap(self.preview_pixmap)
        self.graphics_scene.addItem(self.game_region_selector)

    def closeEvent(self, e):
        try:
            self.shmem_capture.close_shmem()
        except:
            pass  # Ignore any errors during close
        capture_window.stop()
        if sys.platform == "darwin":
            capture_device.stop()
            self._permission_timer.stop()
        config.rollback()
        super().closeEvent(e)

    def auto_detect_region(self):
        try:
            preview_image = self._capture()
            if preview_image is None:
                return
            # AmaRecTV's window has a bar at the top, which would be found as part of the game
            if not self.use_obs_cb.isChecked() and not self._use_device() and \
                    self._process_list[self.process_combo.currentIndex()][0].name() == "AmaRecTV.exe":
                preview_image[0:68, 0:preview_image.shape[1]] = 0

            # Convert to grayscale
            gray = cv2.cvtColor(preview_image, cv2.COLOR_BGR2GRAY)
            
            # Use a threshold that considers pixels "black" if they're below intensity 20
            # This helps handle dark regions that aren't perfectly black
            _, thresh = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY)
            
            # Apply some morphological operations to remove noise
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Find coordinates of non-black pixels
            non_zero = cv2.findNonZero(thresh)
            if non_zero is None:
                return
                
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(non_zero)
            
            # Add a small padding (5 pixels) to account for border pixels
            x = max(0, x + 2)
            y = max(0, y + 2)
            w = min(preview_image.shape[1] - x, w - 4)
            h = min(preview_image.shape[0] - y, h - 4)
            
            # Update region selector and panel
            self.game_region_selector.resize(w, h)
            self.game_region_selector.setPos(x, y)
            self.game_region_panel.update_text(str(x), str(y), str(w), str(h))
            
            # Refresh the scene
            self.refresh_graphics_scene()
            
        except Exception as e:
            print(f"Auto region detection failed: {str(e)}")


class RectangleCapturePanel(QtWidgets.QWidget):
    """ A rectangle's X and Y offset, width and height """
    updated = QtCore.pyqtSignal(list)

    def __init__(self, title, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow(QtWidgets.QLabel(title))
        layout.addRow(HLine())
        validator = QtGui.QIntValidator(self)
        self.fields = []
        for text in ("X Offset:", "Y Offset:", "Width:", "Height:"):
            label = QtWidgets.QLabel(text)
            label.setFixedWidth(70)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            field = QtWidgets.QLineEdit()
            field.setMinimumWidth(80)
            field.setValidator(validator)
            field.editingFinished.connect(self.text_changed)
            layout.addRow(label, field)
            self.fields.append(field)
        self.xoffset_le, self.yoffset_le, self.width_le, self.height_le = self.fields

    def update_text(self, *values):
        """ Shows the values given as text, keeping the others """
        for field, value in zip(self.fields, values):
            if value:
                field.setText(value)

    def text_changed(self):
        try:
            self.updated.emit(self.get_data())
        except ValueError:
            pass

    def get_data(self):
        return [int(float(field.text())) for field in self.fields]


class CaptureGraphicsScene(QtWidgets.QGraphicsScene):
    item_update = QtCore.pyqtSignal(object)