import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from autosplit64 import main
from autosplit64.core import config

ROUTE = Path(__file__).parent.parent / "routes" / "16_lblj.as64"


class RouteTimingTest(unittest.TestCase):
    def timing_of_route_file(self, content):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        path = directory / "route.as64"
        path.write_bytes(content)
        real_get = config.get
        with mock.patch.object(config, "get", side_effect=lambda section, key=None:
                               str(path) if (section, key) == ("route", "path") else real_get(section, key)):
            return main.route_timing()

    def test_valid_route(self):
        self.assertEqual(self.timing_of_route_file(ROUTE.read_bytes()), "RTA")

    def test_invalid_route_file(self):
        self.assertIsNone(self.timing_of_route_file(b"{ not json"))



class TimingSetupTest(unittest.TestCase):
    def test_each_timing(self):
        self.assertEqual(main.timing_setup("RTA"), ("standard/initial.processor", True))
        self.assertEqual(main.timing_setup("Up RTA"), ("up_rta/initial_up_rta.processor", False))
        self.assertEqual(main.timing_setup("File Select"), ("file_select/initial_file_select_start.processor", False))
        self.assertEqual(main.timing_setup(None), ("standard/initial.processor", True))

    def test_switching_back_to_rta_restarts_on_reset_again(self):
        # Start with an Up RTA route, then with an RTA route, in the same session
        for timing, start_on_reset in [("Up RTA", False), ("RTA", True)]:
            with mock.patch.object(main, "route_timing", return_value=timing), \
                 mock.patch.object(main.ProcessorGenerator, "generate"):
                main.set_up_timing()
            self.assertIs(main.core.start_on_reset, start_on_reset)

class StartTest(unittest.TestCase):
    def test_processor_that_failed_to_generate_stops_the_start(self):
        autosplit64 = main.AutoSplit64.__new__(main.AutoSplit64)
        autosplit64.on_error = mock.Mock()
        autosplit64.app = SimpleNamespace(detection=None)
        generate = lambda path, processes: None if path == "ddd/ddd.processor" else mock.Mock()
        with mock.patch.object(main.core, "init"), mock.patch.object(main.core, "start") as start, \
             mock.patch.object(main, "make_processes"), \
             mock.patch.object(main.os.path, "exists", return_value=True), \
             mock.patch.object(main.ProcessorGenerator, "generate", side_effect=generate):
            autosplit64.start()

        start.assert_not_called()
        self.assertIn("ddd/ddd.processor", autosplit64.on_error.call_args.args[0])


class ErrorMessageTest(unittest.TestCase):
    """ The messages about errors nothing else handled, whose details are in the log """

    def setUp(self):
        from PyQt6 import QtWidgets
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        for patcher in [mock.patch.object(main, "_shown_error", False),
                        mock.patch.object(main.QtWidgets.QMessageBox, "critical"),
                        mock.patch.object(main.QtWidgets.QMessageBox, "warning")]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_first_error_tells_where_the_log_is(self):
        main.show_error(ValueError("a bug"))
        message = main.QtWidgets.QMessageBox.critical.call_args.args[2]
        self.assertIn("a bug", message)
        self.assertIn(str(Path(main.logs.LOG_FILE).absolute()), message)

    def test_only_the_first_error_shows_a_message(self):
        # e.g. an error in painting, which happens again on every repaint
        main.show_error(ValueError("a bug"))
        main.show_error(ValueError("a bug"))
        main.QtWidgets.QMessageBox.critical.assert_called_once()

    def test_errors_in_other_threads_are_only_logged(self):
        import threading
        thread = threading.Thread(target=main.show_error, args=(ValueError("in a thread"),))
        thread.start()
        thread.join()
        main.QtWidgets.QMessageBox.critical.assert_not_called()

    def test_previous_crash(self):
        with mock.patch.object(main.logs, "previous_session_crashed", return_value=True):
            main.tell_about_previous_crash()
        message = main.QtWidgets.QMessageBox.warning.call_args.args[2]
        self.assertIn(str(Path(main.logs.OLD_LOG_FILE).absolute()), message)

    def test_no_previous_crash(self):
        with mock.patch.object(main.logs, "previous_session_crashed", return_value=False):
            main.tell_about_previous_crash()
        main.QtWidgets.QMessageBox.warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
