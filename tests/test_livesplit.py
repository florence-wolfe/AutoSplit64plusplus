import socket
import unittest
from unittest import mock

from as64core import config, livesplit


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


if __name__ == "__main__":
    unittest.main()
