import threading
import unittest
from unittest import mock

from PyQt6 import QtWidgets
from PyQt6.QtTest import QTest

import AutoSplit64
from as64gui.app import App
from tests.qt import close_window

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ListenerThreadTest(unittest.TestCase):
    """ Split detection runs on its own thread, but only the GUI thread may change widgets """

    def setUp(self):
        self.calls = []
        record = lambda name: lambda *args: self.calls.append((name, threading.current_thread()))
        patches = [
            mock.patch("as64gui.updates.Updates.check"),
            mock.patch.object(AutoSplit64.livesplit, "connect"),
            mock.patch.object(App, "set_started", record("set_started")),
            mock.patch.object(App, "update_display", record("update_display")),
            mock.patch.object(App, "display_error_message", record("display_error_message")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.autosplit64 = AutoSplit64.AutoSplit64()
        self.addCleanup(close_window, self.autosplit64.app)
        # Only record what the listeners cause
        QTest.qWait(50)
        self.calls.clear()

    def call_from_detection_thread(self, function, *args):
        thread = threading.Thread(target=function, args=args)
        thread.start()
        thread.join()
        QTest.qWait(50)

    def assert_on_gui_thread(self, names):
        self.assertEqual([name for name, _ in self.calls], names)
        for name, thread in self.calls:
            self.assertIs(thread, threading.main_thread(), f"{name} ran on {thread.name}")

    def test_start(self):
        self.call_from_detection_thread(self.autosplit64.on_start)
        self.assert_on_gui_thread(["set_started"])

    def test_update(self):
        self.call_from_detection_thread(self.autosplit64.on_update, 2, 5, 8)
        self.assert_on_gui_thread(["update_display"])

    def test_error(self):
        self.call_from_detection_thread(self.autosplit64.on_error, "boom")
        self.assert_on_gui_thread(["display_error_message", "set_started"])


if __name__ == "__main__":
    unittest.main()
