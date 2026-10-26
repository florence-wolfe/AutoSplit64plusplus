"""
Asking the runner whether a web page may control the timer over WebSocket, for livesplit_one.ask. The server asks
from its thread while the page waits to connect, and the question is shown on the GUI thread.
"""
import threading

from PyQt6 import QtCore, QtWidgets

from autosplit64.core import config

# How long a page waits for the runner's answer, in seconds. One allowed later connects the next time it tries.
WAIT = 60


class OriginPrompt(QtCore.QObject):
    _asked = QtCore.pyqtSignal(str, object)

    def __init__(self, window=None):
        super().__init__(window)
        self._window = window
        self._asked.connect(self._ask)

    def __call__(self, origin):
        """ From the server's thread: whether the runner allowed the page at origin """
        answered = threading.Event()
        answer = []
        self._asked.emit(origin, (answered, answer))
        return answered.wait(WAIT) and answer[0]

    def _ask(self, origin, reply):
        box = QtWidgets.QMessageBox(self._window)
        box.setWindowTitle("WebSocket")
        box.setText(f"The web page at {origin} wants to control your timer.")
        box.setInformativeText("Allow it only if it's your timer. Allowed pages are listed in Settings > Connection.")
        allow = box.addButton("Allow", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(box.addButton("Deny", QtWidgets.QMessageBox.ButtonRole.RejectRole))
        box.exec()

        allowed = box.clickedButton() is allow
        if allowed:
            config.save_key("connection", "ws_allowed_origins",
                            list(config.get("connection", "ws_allowed_origins")) + [origin])
        answered, answer = reply
        answer.append(allowed)
        answered.set()
