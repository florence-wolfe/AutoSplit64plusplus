import errno

from PyQt6 import QtCore, QtGui, QtWidgets

from as64core import config, livesplit_one

COLORS = {
    "connected": QtGui.QColor(76, 175, 80),
    "waiting": QtGui.QColor(255, 193, 7),
    "error": QtGui.QColor(244, 67, 54),
    "stopped": QtGui.QColor(120, 123, 127),
}

DESCRIPTIONS = {
    "connected": "LiveSplit One connected",
    "waiting": "Waiting for LiveSplit One to connect",
    "error": "Server could not start",
    "stopped": "Server not running",
}


class ServerStatusIndicator(QtWidgets.QWidget):
    """ Dot showing the LiveSplit One server state. Clicking it copies the server URL. """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedSize(12, 12)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        self._state = "stopped"
        self._url = ""

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        self.refresh()

    def refresh(self):
        # The server only exists in LiveSplit One mode (2)
        self.setVisible(config.get("connection", "ls_connection_type") == 2)

        state, port, error = livesplit_one.status()
        self._state = state
        self._url = f"ws://localhost:{port or config.get('connection', 'lso_port')}"

        tooltip = f"{DESCRIPTIONS[state]}\n{self._url}\nClick to copy"
        if error is not None:
            reason = f"port {port} is already in use" if error.errno == errno.EADDRINUSE else str(error)
            tooltip = f"{DESCRIPTIONS[state]}: {reason}\n{self._url}"
        self.setToolTip(tooltip)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(12, 12, 12), 1))
        painter.setBrush(COLORS[self._state])
        painter.drawEllipse(QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            QtWidgets.QApplication.clipboard().setText(self._url)
            QtWidgets.QToolTip.showText(event.globalPosition().toPoint(), f"Copied {self._url}", self)
            event.accept()
        else:
            super().mousePressEvent(event)
