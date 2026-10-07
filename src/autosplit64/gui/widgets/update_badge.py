from PyQt6 import QtCore, QtWidgets

_STYLE = "QLabel { color: rgb(150, 153, 157); font-size: 11px; }"
# The same green as the server status when LiveSplit One is connected
_DOT = "<span style='color: rgb(76, 175, 80);'>&#9679;</span>"


class UpdateBadge(QtWidgets.QLabel):
    """ Shows the installed version, with a green dot when an update is available. Clicking it checks for or installs an update. """

    clicked = QtCore.pyqtSignal()

    def __init__(self, version, parent=None):
        super().__init__(parent=parent)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_STYLE)
        self.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.show_version(version)

    def show_version(self, version):
        self._version = f"v{version}" if version[0].isdigit() else version
        self.setText(self._version)
        self.setToolTip("Click to check for updates")
        self.adjustSize()

    def show_update(self, version):
        self.setText(f"{self._version} {_DOT}")
        self.setToolTip(f"Update available: v{version}\nClick to update")
        self.adjustSize()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        # Keep the press from dragging the window
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)
