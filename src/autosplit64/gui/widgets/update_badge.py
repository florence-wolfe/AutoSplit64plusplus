from PyQt6 import QtCore, QtWidgets

from autosplit64.gui import theme


class UpdateBadge(QtWidgets.QLabel):
    """ Shows the installed version, with a green dot when an update is available. Clicking it checks for or installs an update. """

    clicked = QtCore.pyqtSignal()

    def __init__(self, version, parent=None):
        super().__init__(parent=parent)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        # Not with a style sheet, which would keep theme changes from reaching it
        font = self.font()
        font.setPixelSize(11)
        self.setFont(font)
        self.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self._update = None
        self.show_version(version)

    def show_version(self, version):
        self._version = f"v{version}" if version[0].isdigit() else version
        self.setToolTip("Click to check for updates")
        self._show()

    def show_update(self, version):
        self._update = version
        self.setToolTip(f"Update available: v{version}\nClick to update")
        self._show()

    def _show(self):
        """ The version in the theme's muted text color, and a green dot when there's an update """
        text = f"<span style='color: {theme.muted(self.palette()).name()};'>{self._version}</span>"
        if self._update:
            # The same green as the server status when LiveSplit One is connected
            text += f" <span style='color: {theme.status_color('green').name()};'>&#9679;</span>"
        self.setText(text)
        self.adjustSize()

    def changeEvent(self, event):
        # e.g. another theme
        if event.type() == QtCore.QEvent.Type.PaletteChange:
            self._show()
        super().changeEvent(event)

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
