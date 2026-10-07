import errno

from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.core import config, livesplit, livesplit_one
from autosplit64.gui import theme

# Each state's theme color, muted text for none
STATUS_COLORS = {"connected": "green", "waiting": "yellow", "error": "red", "stopped": None}

# How long the "Copied" message stays up, in milliseconds
COPIED_MESSAGE_TIME = 2500

# TCP and named pipe mode, where split detection connects to LiveSplit
CLIENT_DESCRIPTIONS = {
    "connected": "Connected to LiveSplit",
    "stopped": "Connects to LiveSplit when split detection starts",
    "error": "Couldn't connect to LiveSplit",
}

DESCRIPTIONS = {
    "connected": "LiveSplit One connected",
    "waiting": "Waiting for LiveSplit One to connect",
    "error": "Server could not start",
    "stopped": "Server not running",
}


class ServerStatusIndicator(QtWidgets.QWidget):
    """ Dot showing the state of the connection to LiveSplit. Clicking it copies the address. """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedSize(12, 12)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        self._state = "stopped"
        self._url = ""
        self._showing_copied = False

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        self.refresh()

    def refresh(self):
        # LiveSplit One mode (2) runs a server; TCP and named pipe mode connect to LiveSplit's
        if config.get("connection", "ls_connection_type") != 2:
            self._state, self._url, error = livesplit.client_status()
            tooltip = CLIENT_DESCRIPTIONS[self._state] + (f": {error}" if error else "") + f"\n{self._url}\nClick to copy"
            if tooltip != self.toolTip():
                self.setToolTip(tooltip)
            self.update()
            return

        state, port, error = livesplit_one.status()
        self._state = state
        self._url = f"ws://localhost:{port or config.get('connection', 'lso_port')}"

        tooltip = f"{DESCRIPTIONS[state]}\n{self._url}\nClick to copy"
        if error is not None:
            reason = f"port {port} is already in use" if error.errno == errno.EADDRINUSE else str(error)
            tooltip = f"{DESCRIPTIONS[state]}: {reason}\n{self._url}"
        if tooltip != self.toolTip():
            self.setToolTip(tooltip)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.ColorRole.Dark), 1))
        status = STATUS_COLORS[self._state]
        painter.setBrush(theme.status_color(status) if status else theme.muted(self.palette()))
        painter.drawEllipse(QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))

    def mousePressEvent(self, event):
        # Copy on release instead, since releasing the mouse hides tooltips
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            QtWidgets.QApplication.clipboard().setText(self._url)
            QtWidgets.QToolTip.showText(event.globalPosition().toPoint(), f"Copied {self._url}", self, self.rect(), COPIED_MESSAGE_TIME)
            # Keep the hover tooltip from replacing the message while it's shown
            self._showing_copied = True
            QtCore.QTimer.singleShot(COPIED_MESSAGE_TIME, lambda: setattr(self, "_showing_copied", False))
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def event(self, event):
        if event.type() == QtCore.QEvent.Type.ToolTip and self._showing_copied:
            return True
        return super().event(event)
