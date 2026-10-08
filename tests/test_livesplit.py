import select
import socket
import struct
import sys
import unittest
from unittest import mock

from autosplit64.core import config, livesplit


class TcpTest(unittest.TestCase):
    def test_refused_connection(self):
        # A port nothing listens on
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        settings = {("connection", "ls_connection_type"): 1, ("connection", "ls_host"): "127.0.0.1", ("connection", "ls_port"): port}
        with mock.patch.object(config, "get", side_effect=lambda section, key=None: settings[(section, key)]):
            self.assertIs(livesplit.connect(), False)

    def split_index_answering(self, answer):
        ours, timer = socket.socketpair()
        self.addCleanup(ours.close)
        self.addCleanup(timer.close)
        timer.sendall(answer)
        return livesplit.split_index(ours)

    def test_split_index(self):
        self.assertEqual(self.split_index_answering(b"3\r\n"), 3)

    def test_unreadable_answer(self):
        self.assertIs(self.split_index_answering(b"not a number"), False)

    def test_other_errors_are_not_hidden(self):
        ours, timer = socket.socketpair()
        self.addCleanup(ours.close)
        self.addCleanup(timer.close)
        timer.sendall(b"3")
        with mock.patch.object(livesplit, "int", side_effect=RuntimeError("bug"), create=True):
            with self.assertRaises(RuntimeError):
                livesplit.split_index(ours)

    def test_no_answer_in_time(self):
        ours, timer = socket.socketpair()
        self.addCleanup(ours.close)
        self.addCleanup(timer.close)
        self.assertIs(livesplit.split_index(ours), False)


class LostConnectionTest(unittest.TestCase):
    """ LiveSplit closing during split detection is reported, rather than every later split being lost silently """

    def setUp(self):
        timer = socket.socket()
        timer.bind(("127.0.0.1", 0))
        timer.listen()
        self.addCleanup(timer.close)
        settings = {("connection", "ls_connection_type"): 1, ("connection", "ls_host"): "127.0.0.1",
                    ("connection", "ls_port"): timer.getsockname()[1]}
        for patcher in [mock.patch.object(config, "get", side_effect=lambda section, key=None: settings[(section, key)]),
                        mock.patch.object(livesplit, "_connected", False), mock.patch.object(livesplit, "_connect_failed", False)]:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.ls_socket = livesplit.connect()
        self.addCleanup(self.ls_socket.close)
        self.timer_connection, _ = timer.accept()

    def test_split_index(self):
        # LiveSplit quits
        self.timer_connection.close()
        with self.assertRaises(ConnectionAbortedError):
            livesplit.split_index(self.ls_socket)
        self.assertEqual(livesplit.client_status()[0], "error")

    def test_commands(self):
        # The connection is reset, e.g. LiveSplit crashed
        self.timer_connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("HH" if sys.platform == "win32" else "ii", 1, 0))
        self.timer_connection.close()
        select.select([self.ls_socket], [], [], 1)
        with self.assertRaises(ConnectionAbortedError):
            livesplit.split(self.ls_socket)
        self.assertEqual(livesplit.client_status()[0], "error")

    def test_checking_the_connection_at_start(self):
        self.timer_connection.close()
        self.assertIs(livesplit.check_connection(self.ls_socket), False)


@unittest.skipUnless(sys.platform == "win32", "Named pipes are only available on Windows")
class LostPipeTest(unittest.TestCase):
    def setUp(self):
        for patcher in [mock.patch.object(livesplit, "_connected", True), mock.patch.object(livesplit, "_connect_failed", False),
                        mock.patch.object(livesplit.win32file, "WriteFile", side_effect=livesplit.pywintypes.error(232, "WriteFile", "The pipe is being closed."))]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_split_index(self):
        with self.assertRaises(ConnectionAbortedError):
            livesplit.split_index(object())
        self.assertIs(livesplit._connect_failed, True)

    def test_commands(self):
        with self.assertRaises(ConnectionAbortedError):
            livesplit.split(object())



class ClientStatusTest(unittest.TestCase):
    """ The state of the connection to LiveSplit's server in TCP and named pipe mode, for the status dot """

    def setUp(self):
        self.settings = {("connection", "ls_connection_type"): 1, ("connection", "ls_host"): "localhost",
                         ("connection", "ls_port"): 16834, ("connection", "ls_pipe_host"): "."}
        for patcher in [mock.patch.object(config, "get", side_effect=lambda section, key=None: self.settings[(section, key)]),
                        mock.patch.object(livesplit, "_connected", False), mock.patch.object(livesplit, "_connect_failed", False)]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_tcp(self):
        self.assertEqual(livesplit.client_status(), ("stopped", "localhost:16834", None))

        timer = socket.socket()
        timer.bind(("127.0.0.1", 0))
        timer.listen()
        self.addCleanup(timer.close)
        self.settings[("connection", "ls_port")] = timer.getsockname()[1]
        ls_socket = livesplit.connect()
        self.assertEqual(livesplit.client_status()[0], "connected")

        livesplit.disconnect(ls_socket)
        self.assertEqual(livesplit.client_status()[0], "stopped")

    def test_failed_connection(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.settings[("connection", "ls_port")] = probe.getsockname()[1]
        livesplit.connect()
        state, address, error = livesplit.client_status()
        self.assertEqual(state, "error")
        self.assertIn("server", error)

    def test_named_pipe(self):
        self.settings[("connection", "ls_connection_type")] = 0
        state, address, error = livesplit.client_status()
        self.assertEqual(address, "\\\\.\\pipe\\LiveSplit")
        if sys.platform != "win32":
            self.assertEqual((state, error), ("error", "Named pipes are only available on Windows"))

if __name__ == "__main__":
    unittest.main()
