import json
import threading
import time
import unittest

from websockets.sync.client import connect

from as64core.livesplit_one import LiveSplitOneServer

PORT = 16899


class FakeLiveSplitOne:
    """Plays the LiveSplit One side: answers commands the way livesplit-core's server protocol does."""

    def __init__(self, port, state):
        self.state = state
        self.commands = []
        self.ws = connect(f"ws://localhost:{port}")
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        for message in self.ws:
            command = json.loads(message)["command"]
            self.commands.append(command)
            if command == "getCurrentState":
                self.ws.send(json.dumps({"success": self.state}))
            else:
                # Mutating commands are preceded by an event, like LSO does
                self.ws.send(json.dumps({"event": "Splitted"}))
                self.ws.send(json.dumps({"success": None}))

    def close(self):
        self.ws.close()


def wait_for(predicate, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class LiveSplitOneServerTest(unittest.TestCase):
    def setUp(self):
        self.server = LiveSplitOneServer(PORT)

    def tearDown(self):
        self.server.close()

    def connect_client(self, state):
        client = FakeLiveSplitOne(PORT, state)
        self.addCleanup(client.close)
        self.assertTrue(wait_for(self.server.connected))
        return client

    def test_not_connected(self):
        self.assertFalse(self.server.connected())
        self.assertIs(self.server.split_index(), False)
        with self.assertRaises(ConnectionAbortedError):
            self.server.send_classic("startorsplit\r\n")

    def test_split_index_states(self):
        client = self.connect_client({"state": "NotRunning"})
        self.assertEqual(self.server.split_index(), -1)

        client.state = {"state": "Running", "index": 3}
        self.assertEqual(self.server.split_index(), 3)

        client.state = {"state": "Paused", "index": 4}
        self.assertEqual(self.server.split_index(), 4)

        # Ended carries no index; LiveSplit reports one past the last split
        client.state = {"state": "Ended"}
        self.assertEqual(self.server.split_index(), 5)

    def test_classic_commands_are_translated(self):
        client = self.connect_client({"state": "Running", "index": 0})
        self.server.send_classic("startorsplit\r\n")
        self.server.send_classic("reset\r\nstarttimer\r\n")
        self.server.send_classic("skipsplit\r\n")
        self.server.send_classic("unsplit\r\n")
        self.assertTrue(wait_for(lambda: len(client.commands) == 5))
        self.assertEqual(client.commands, ["splitOrStart", "reset", "start", "skipSplit", "undoSplit"])

    def test_split_index_after_commands_ignores_their_responses(self):
        self.connect_client({"state": "Running", "index": 7})
        self.server.send_classic("startorsplit\r\n")
        self.server.send_classic("skipsplit\r\n")
        self.assertEqual(self.server.split_index(), 7)

    def test_reconnect_replaces_client(self):
        first = self.connect_client({"state": "Running", "index": 1})
        self.connect_client({"state": "Running", "index": 2})
        self.assertTrue(wait_for(lambda: self.server.split_index() == 2))
        first.close()
        time.sleep(0.1)
        self.assertTrue(self.server.connected())


if __name__ == "__main__":
    unittest.main()
