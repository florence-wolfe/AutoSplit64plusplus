import sys

from PyQt6 import QtCore, QtGui, QtQuick, QtWidgets

import cv2

from autosplit64.core import capture_shmem, config
if sys.platform == "darwin":
    from autosplit64.core import capture_device_mac as capture_device
    from autosplit64.core import capture_window_mac as capture_window
else:
    from autosplit64.core import capture_window_win as capture_window
from autosplit64.core import resource_utils
from ..qml_view import qml_view
from ..constants import (
    ICON_PATH,
    PLACEHOLDER_PATH,
)


class Preview(QtQuick.QQuickImageProvider):
    """ The capture for CaptureEditor.qml, as image://capture/<version> """

    def __init__(self):
        super().__init__(QtQuick.QQuickImageProvider.ImageType.Image)
        self.image = QtGui.QImage()

    def requestImage(self, id, requested_size):
        return self.image, self.image.size()


class Capture(QtCore.QObject):
    """
    What CaptureEditor.qml shows, in values: the capture's source, its permission, the processes and devices
    and the chosen ones, whether to use OBS and the VC fix, the game region, and the capture's version.
    choose(key, value) and set_region() are the QML's changes, and its other signals the buttons' clicks.
    """
    changed = QtCore.pyqtSignal()
    chosen = QtCore.pyqtSignal(str)
    capture_screen = QtCore.pyqtSignal()
    auto_detect = QtCore.pyqtSignal()
    apply = QtCore.pyqtSignal()
    cancel = QtCore.pyqtSignal()
    allow = QtCore.pyqtSignal()
    open_settings = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._values = {"mac": sys.platform == "darwin", "obs": sys.platform == "win32", "source": "window",
                        "permissionMissing": False, "permissionText": "", "allowText": "", "useObs": False,
                        "processes": [], "process": 0, "devices": [], "device": 0, "vcFix": False,
                        "region": [0, 0, 50, 50], "preview": 0}

    @QtCore.pyqtProperty("QVariantMap", notify=changed)
    def values(self):
        return self._values

    def update(self, **values):
        self._values.update(values)
        self.changed.emit()

    @QtCore.pyqtSlot(str, "QVariant")
    def choose(self, key, value):
        self.update(**{key: value})
        self.chosen.emit(key)

    @QtCore.pyqtSlot(int, int, int, int)
    def set_region(self, x, y, width, height):
        self.update(region=[x, y, width, height])


class CaptureEditor(QtWidgets.QDialog):

    applied = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)

        self.setWindowTitle("Game Capture Editor")
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))
        self.resize(1100, 640)

        # Initialize SharedMemoryCapture
        self.shmem_capture = capture_shmem.SharedMemoryCapture()

        # Filled when the editor is shown, so macOS doesn't ask for Screen Recording at launch
        self._process_list = []
        self._devices = []
        # The capture shown
        self.preview = QtGui.QImage()

        self.capture = Capture()
        self._preview = Preview()
        self.capture.chosen.connect(self._chosen)
        self.capture.capture_screen.connect(self.refresh_preview)
        self.capture.auto_detect.connect(self.auto_detect_region)
        self.capture.apply.connect(self.apply_clicked)
        self.capture.cancel.connect(self.cancel_clicked)
        self.capture.allow.connect(lambda: self._capture_module().request_permission())
        self.capture.open_settings.connect(lambda: self._capture_module().open_permission_settings())
        self.view = qml_view(self, "CaptureEditor", images={"capture": self._preview}, capture=self.capture)

        if sys.platform == "darwin":
            # Check again while the editor is open, to notice when the permission is granted
            self._permission_timer = QtCore.QTimer(self)
            self._permission_timer.timeout.connect(self._update_permission)

        self.refresh_preview()

    def _chosen(self, key):
        """ After the QML's choice of key """
        if key == "source":
            self._on_source_changed()
        elif key in ("useObs", "process", "device"):
            self.refresh_preview()

    def _use_obs(self):
        return self.capture.values["useObs"]

    def _refresh_process_list(self):
        # Listing the windows without the Screen Recording permission shows macOS's prompt
        if sys.platform == "darwin" and not capture_window.has_permission_quietly():
            self._process_list = []
        else:
            self._process_list = capture_window.get_visible_processes()
        self.capture.update(processes=[proc[0].name() for proc in self._process_list], process=0)

    def _use_device(self):
        return sys.platform == "darwin" and self.capture.values["source"] == "device"

    def _capture_module(self):
        return capture_device if self._use_device() else capture_window

    def _refresh_device_list(self):
        self._devices = capture_device.get_devices()
        chosen = next((i for i, (unique_id, _) in enumerate(self._devices) if unique_id == config.get("game", "capture_device")), 0)
        self.capture.update(devices=[name for _, name in self._devices], device=chosen)

    def _capture_device(self):
        """ The selected video device's latest frame, or None """
        # Opening the device would ask for the permission by itself, or wait for frames that never come
        if not capture_device.has_permission():
            return None
        try:
            return capture_device.capture(self._devices[self.capture.values["device"]][0])
        except Exception:
            return None

    def _on_source_changed(self):
        # Only capture, and ask for the permission of, the selected source
        capture_window.stop()
        capture_device.stop()
        if self._use_device():
            self._refresh_device_list()
        elif not self._process_list:
            self._refresh_process_list()
        self._update_permission()
        self.refresh_preview()

    def _update_permission(self):
        if self._use_device():
            text = ("Camera permission is needed to capture the video device.\n\n"
                    "If it's already on in System Settings, it may belong to an earlier build. "
                    "Allow Camera asks macOS again for this one.")
            allow = "Allow Camera"
        else:
            text = ("Screen Recording permission is needed to capture the emulator window.\n\n"
                    "If it's already on in System Settings, it may belong to an earlier build. "
                    "Allow Screen Recording asks macOS again for this one.\n\n"
                    "After allowing it, you may need to restart AutoSplit64++.")
            allow = "Allow Screen Recording"

        # Checked every second while missing, so without asking for it: only Allow asks macOS
        granted = capture_device.has_permission() if self._use_device() else capture_window.has_permission_quietly()
        if granted and self.capture.values["permissionMissing"]:
            if not self._use_device():
                self._refresh_process_list()
            self.refresh_preview()
        self.capture.update(permissionMissing=not granted, permissionText=text, allowText=allow)
        if granted:
            self._permission_timer.stop()
        else:
            self._permission_timer.start(1000)

    def show(self):
        if sys.platform == "darwin":
            self.capture.update(source="device" if config.get("game", "capture_source") == "device" else "window")

        # Load game_region from preferences
        self.capture.set_region(*config.get('game', 'game_region'))

        # A video device source doesn't need windows, nor their permission
        if not self._use_device():
            self._refresh_process_list()

        p_name = config.get("game", "process_name")

        for i in range(len(self._process_list)):
            if self._process_list[i][0].name() == p_name:
                self.capture.update(process=i)

        # Load use_obs preference
        self.capture.update(useObs=config.get("game", "use_obs") and sys.platform == "win32",
                            vcFix=config.get("game", "vc_fix"))
        if sys.platform == "darwin":
            self._on_source_changed()

        self.refresh_preview()

        config.create_rollback()
        super().show()

    def apply_clicked(self):
        values = self.capture.values
        # Config
        config.set_key("game", "use_obs", values["useObs"])
        config.set_key("game", "game_region", list(values["region"]))
        if sys.platform == "darwin":
            config.set_key("game", "capture_source", "device" if self._use_device() else "window")
            if self._use_device() and self._devices:
                config.set_key("game", "capture_device", self._devices[values["device"]][0])
        if not values["useObs"] and not self._use_device() and self._process_list:
            config.set_key("game", "process_name", self._process_list[values["process"]][0].name())

        try:
            if values["useObs"]:
                config.set_key("game", "capture_size", self.shmem_capture.get_capture_size())
            elif self._use_device():
                config.set_key("game", "capture_size", capture_device.get_capture_size(self._devices[values["device"]][0]))
            else:
                config.set_key("game", "capture_size", capture_window.get_capture_size(self._process_list[values["process"]][1]))
        except:
            pass

        config.set_key("game", "vc_fix", values["vcFix"])

        config.save_config()
        # Close the shared memory connection
        self.shmem_capture.close_shmem()
        self.applied.emit()
        self.close()

    def cancel_clicked(self):
        # Close the shared memory connection
        self.shmem_capture.close_shmem()
        self.close()

    def _capture(self):
        """ The selected source's latest frame, or None """
        if self._use_obs():
            try:
                return self.shmem_capture.capture()
            except Exception:
                return None
        if self._use_device():
            return self._capture_device()
        try:
            hwnd = self._process_list[self.capture.values["process"]][1]
            return capture_window.capture(hwnd) if hwnd else None
        except Exception:
            return None

    def refresh_preview(self):
        """ Shows the selected source's latest frame """
        preview_image = self._capture()
        if preview_image is not None:
            self.preview = QtGui.QImage.fromData(cv2.imencode(".png", preview_image)[1].tobytes())
        elif self._use_obs():
            self.preview = QtGui.QImage(resource_utils.resource_path(PLACEHOLDER_PATH))
        else:
            # Never show an earlier capture when nothing could be captured now
            self.preview = QtGui.QImage(640, 480, QtGui.QImage.Format.Format_RGB32)
            self.preview.fill(QtCore.Qt.GlobalColor.black)

        self._preview.image = self.preview
        # A new URL, so it's loaded again
        self.capture.update(preview=self.capture.values["preview"] + 1)

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
            if not self._use_obs() and not self._use_device() and \
                    self._process_list[self.capture.values["process"]][0].name() == "AmaRecTV.exe":
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
            
            # Update the region
            self.capture.set_region(x, y, w, h)
            
            # Refresh the capture
            self.refresh_preview()
            
        except Exception as e:
            print(f"Auto region detection failed: {str(e)}")
