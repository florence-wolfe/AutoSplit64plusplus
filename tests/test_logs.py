import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest import mock

from autosplit64.core import logs


class SessionLogTest(unittest.TestCase):
    """ A log for each session, and the previous session's """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        root = logging.getLogger()
        self.addCleanup(root.setLevel, root.level)

    def start(self, version="1.2.3"):
        handler = logs.start_session(version, self.dir)
        self.addCleanup(logging.getLogger().removeHandler, handler)
        self.addCleanup(handler.close)
        return handler

    def read(self, name):
        for handler in logging.getLogger().handlers:
            handler.flush()
        return (self.dir / name).read_text(encoding="utf-8")

    def test_first_session(self):
        self.start()
        logging.getLogger(".log").warning("Something happened")
        self.assertIn("Something happened", self.read(logs.LOG_FILE))
        self.assertFalse((self.dir / logs.OLD_LOG_FILE).exists())

    def test_the_previous_session_becomes_the_old_log(self):
        (self.dir / logs.OLD_LOG_FILE).write_text("two sessions ago")
        (self.dir / logs.LOG_FILE).write_text("last session")
        self.start()
        self.assertEqual(self.read(logs.OLD_LOG_FILE), "last session")
        self.assertNotIn("last session", self.read(logs.LOG_FILE))

    def test_starts_with_the_version_and_system(self):
        self.start("1.2.3")
        log = self.read(logs.LOG_FILE)
        self.assertIn("AutoSplit64++ 1.2.3", log)
        self.assertIn(platform.platform(), log)
        self.assertIn(platform.python_version(), log)

    def test_logs_information_not_only_warnings(self):
        self.start()
        logging.getLogger(".log").info("Installing the update")
        self.assertIn("Installing the update", self.read(logs.LOG_FILE))

    def test_log_in_use_by_another_session(self):
        # Windows doesn't rename a file another AutoSplit64++ has open
        (self.dir / logs.LOG_FILE).write_text("the other session\n")
        with mock.patch.object(logs.os, "replace", side_effect=PermissionError("in use")):
            self.start()
        logging.getLogger(".log").warning("This session")
        log = self.read(logs.LOG_FILE)
        self.assertTrue(log.startswith("the other session\n"))
        self.assertIn("This session", log)


class CrashTest(unittest.TestCase):
    """ What nothing else handled, in the session log: exceptions, and crashes that end AutoSplit64++ """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def run_session(self, code):
        """ Run code in a new process, as a session in self.dir. Returns the process and its log. """
        script = textwrap.dedent('''
            import sys
            from autosplit64.core import logs
            handler = logs.start_session("1.2.3", sys.argv[1])
            errors = []
            logs.install_crash_handlers(handler, errors.append)
        ''') + textwrap.dedent(code)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        process = subprocess.run([sys.executable, "-c", script, str(self.dir)], env=env, capture_output=True, text=True, timeout=60)
        log = (self.dir / logs.LOG_FILE).read_text(encoding="utf-8")
        return process, log

    def test_exception_in_the_gui_is_logged_and_the_app_keeps_running(self):
        process, log = self.run_session('''
            from PyQt6 import QtCore, QtWidgets
            app = QtWidgets.QApplication([])
            def broken():
                raise ValueError("a bug in a slot")
            QtCore.QTimer.singleShot(0, broken)
            QtCore.QTimer.singleShot(100, app.quit)
            app.exec()
            print("still running, errors:", errors)
        ''')
        # Without a hook, PyQt6 aborts on an exception in a slot
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("still running, errors: [ValueError('a bug in a slot')]", process.stdout)
        self.assertIn("ValueError: a bug in a slot", log)
        self.assertIn("in broken", log)

    def test_exception_in_a_thread_is_logged(self):
        process, log = self.run_session('''
            import threading
            def broken():
                raise KeyError("in a thread")
            thread = threading.Thread(target=broken, name="Detection")
            thread.start()
            thread.join()
        ''')
        self.assertIn("Detection", log)
        self.assertIn("KeyError: 'in a thread'", log)

    def test_native_crash_is_in_the_log_and_found_the_next_session(self):
        process, log = self.run_session('''
            import faulthandler
            def capture_frame():
                faulthandler._sigsegv()
            capture_frame()
        ''')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("Fatal Python error", log)
        self.assertIn("capture_frame", log)
        self.assertFalse(logs.previous_session_crashed(self.dir))
        logs.start_session("1.2.3", self.dir).close()
        logging.getLogger().handlers.pop()
        self.assertTrue(logs.previous_session_crashed(self.dir))

    def test_no_crash(self):
        self.run_session("pass")
        logs.start_session("1.2.3", self.dir).close()
        logging.getLogger().handlers.pop()
        self.assertFalse(logs.previous_session_crashed(self.dir))


if __name__ == "__main__":
    unittest.main()
