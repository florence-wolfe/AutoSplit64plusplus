import threading
import time
import unittest
from unittest import mock

from PyQt6 import QtWidgets
from PyQt6.QtTest import QTest

from as64gui import app as app_module
from as64gui.app import App

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class StartButtonTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(App, "update_check")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = App()
        self.addCleanup(self.app.close)
        self.stopped = mock.Mock()
        self.app.stop.connect(self.stopped)

    def test_cancel_starting_without_route(self):
        # e.g. autostart retrying while no route is set
        self.app.route = None
        self.app.start_btn.set_state("init")

        self.app.start_clicked()

        self.assertEqual(self.app.start_btn.get_state(), "start")
        self.stopped.assert_called_once()


class UpdateCheckTest(unittest.TestCase):
    def setUp(self):
        real_get = app_module.config.get
        patcher = mock.patch.object(app_module.config, "get", side_effect=lambda section, key=None:
                                    True if (section, key) == ("general", "update_check") else real_get(section, key))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.release = threading.Event()
        self.addCleanup(self.release.set)

    def slow_github(self, *args, **kwargs):
        self.request_kwargs = kwargs
        self.release.wait(3)
        return mock.Mock(text='{"tag_name": "v99.0.0"}')

    def test_window_opens_without_waiting_for_the_network(self):
        calls = []
        with mock.patch.object(app_module.constants, "VERSION", "0.4.0"), \
             mock.patch.object(app_module.requests, "get", side_effect=self.slow_github), \
             mock.patch.object(App, "display_update_message", lambda self, version: calls.append((version, threading.current_thread()))):
            started = time.time()
            app = App()
            self.addCleanup(app.close)
            self.assertLess(time.time() - started, 2)

            self.release.set()
            for _ in range(100):
                if calls:
                    break
                QTest.qWait(20)

        self.assertIn("timeout", self.request_kwargs)
        self.assertEqual(calls, [("v99.0.0", threading.main_thread())])


if __name__ == "__main__":
    unittest.main()
