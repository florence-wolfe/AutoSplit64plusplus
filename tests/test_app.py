import unittest
from unittest import mock

from PyQt6 import QtWidgets

from as64gui.app import App
from tests.qt import close_window

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class StartButtonTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("as64gui.updates.Updates.check")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = App()
        self.addCleanup(close_window, self.app)
        self.stopped = mock.Mock()
        self.app.stop.connect(self.stopped)

    def test_cancel_starting_without_route(self):
        # e.g. autostart retrying while no route is set
        self.app.route = None
        self.app.start_btn.set_state("init")

        self.app.start_clicked()

        self.assertEqual(self.app.start_btn.get_state(), "start")
        self.stopped.assert_called_once()


if __name__ == "__main__":
    unittest.main()
