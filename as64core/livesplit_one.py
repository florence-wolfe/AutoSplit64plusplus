"""
LiveSplit One connection.

LiveSplit One runs in the browser and can't accept connections, so AutoSplit64 hosts a
WebSocket server and LiveSplit One connects to it (Settings > Connect to Server).
Commands use livesplit-core's JSON server protocol:
https://github.com/LiveSplit/livesplit-core/blob/master/src/networking/server_protocol.rs
"""
import json
import logging
import threading
from collections import deque

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

# LiveSplit Server commands used by livesplit.py -> server protocol commands
_COMMANDS = {
    "startorsplit": "splitOrStart",
    "reset": "reset",
    "starttimer": "start",
    "skipsplit": "skipSplit",
    "unsplit": "undoSplit",
}

_server = None


def get_server(port):
    """ Return the running server, (re)starting it if the port changed """
    global _server
    if _server is not None and _server.port != port:
        _server.close()
        _server = None
    if _server is None:
        _server = LiveSplitOneServer(port)
    return _server


class LiveSplitOneServer:
    def __init__(self, port):
        self.port = port
        self._lock = threading.Lock()
        self._client = None
        # Kind of each command awaiting a response, oldest first. LiveSplit One answers in order.
        self._pending = deque()
        self._state_query_pending = False
        self._state = None
        self._state_received = threading.Event()
        self._last_index = -1

        self._server = serve(self._handle_client, "localhost", port)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self):
        self._server.shutdown()

    def connected(self):
        return self._client is not None

    def _handle_client(self, ws):
        # The newest connection wins, e.g. after reloading the LiveSplit One tab
        with self._lock:
            old_client = self._client
            self._client = ws
            self._pending.clear()
            self._state_query_pending = False
        if old_client is not None:
            old_client.close()

        try:
            for message in ws:
                self._on_message(message)
        except ConnectionClosed:
            pass
        finally:
            with self._lock:
                if self._client is ws:
                    self._client = None

    def _on_message(self, message):
        data = json.loads(message)
        # Events are informational and not responses to a command
        if "event" in data:
            return

        with self._lock:
            kind = self._pending.popleft() if self._pending else None
            if kind == "state":
                self._state_query_pending = False
                self._state = data.get("success")
                self._state_received.set()
            elif "error" in data:
                logging.getLogger(".log").warning("LiveSplit One error: %s", data["error"])

    def _send(self, command, kind):
        """ Must be called with the lock held so _pending matches send order """
        if self._client is None:
            raise ConnectionAbortedError("LiveSplit One is not connected")
        self._pending.append(kind)
        try:
            self._client.send(json.dumps({"command": command}))
        except ConnectionClosed:
            raise ConnectionAbortedError("LiveSplit One connection lost")

    def send_classic(self, command):
        """ Send LiveSplit Server style commands, e.g. "reset\\r\\nstarttimer\\r\\n" """
        with self._lock:
            for line in command.split():
                self._send(_COMMANDS[line], "action")

    def split_index(self):
        """ Return the split index like LiveSplit's getsplitindex, or False on failure """
        with self._lock:
            if self._client is None:
                return False
            if not self._state_query_pending:
                self._state_received.clear()
                try:
                    self._send("getCurrentState", "state")
                except ConnectionAbortedError:
                    return False
                self._state_query_pending = True

        if not self._state_received.wait(0.5):
            return False

        state = self._state
        if state is None:
            return False
        if state["state"] == "NotRunning":
            self._last_index = -1
        elif state["state"] in ("Running", "Paused"):
            self._last_index = state["index"]
        elif state["state"] == "Ended":
            # Ended carries no index. A run only ends by splitting the last segment,
            # and LiveSplit reports one past it.
            return self._last_index + 1
        return self._last_index
