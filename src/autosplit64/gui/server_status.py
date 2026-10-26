import errno

from PyQt6 import QtCore, QtWidgets

from autosplit64.core import config, livesplit, livesplit_one

# Each state's theme color, muted text for none
STATUS_COLORS = {"connected": "green", "waiting": "yellow", "error": "red", "stopped": None}

# TCP and named pipe mode, where split detection connects to LiveSplit
CLIENT_DESCRIPTIONS = {
    "connected": "Connected to LiveSplit",
    "stopped": "Connects to LiveSplit when split detection starts",
    "error": "Couldn't connect to LiveSplit",
}

# Each state in a word, whatever it's connected to
LABELS = {"connected": "Connected", "waiting": "Waiting", "error": "Error", "stopped": "Not connected"}

DESCRIPTIONS = {
    "connected": "LiveSplit One connected",
    "waiting": "Waiting for LiveSplit One to connect",
    "error": "Server could not start",
    "stopped": "Server not running",
}


class ServerStatus(QtCore.QObject):
    """ The state of the connection to LiveSplit, which the main window's dot shows, read twice a second """
    changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "stopped"
        self.url = ""
        self.tooltip = ""
        # The state in a word, which the main window's status says beside the dot
        self.label = ""

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        self.refresh()

    def refresh(self):
        # LiveSplit One mode (2) runs a server; TCP and named pipe mode connect to LiveSplit's
        if config.get("connection", "ls_connection_type") != 2:
            self.state, self.url, error = livesplit.client_status()
            self.tooltip = CLIENT_DESCRIPTIONS[self.state] + (f": {error}" if error else "") + f"\n{self.url}\nClick to copy"
        else:
            self.state, port, error = livesplit_one.status()
            self.url = f"ws://localhost:{port or config.get('connection', 'lso_port')}"
            self.tooltip = f"{DESCRIPTIONS[self.state]}\n{self.url}\nClick to copy"
            if error is not None:
                reason = f"port {port} is already in use" if error.errno == errno.EADDRINUSE else str(error)
                self.tooltip = f"{DESCRIPTIONS[self.state]}: {reason}\n{self.url}"
        self.label = LABELS[self.state]
        self.changed.emit()

    def color(self):
        """ The theme's color name for the state, or None for muted text """
        return STATUS_COLORS[self.state]

    def copy(self):
        """ Copies the address, which it returns """
        QtWidgets.QApplication.clipboard().setText(self.url)
        return self.url
