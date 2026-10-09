import logging
import platform
import shutil
import tempfile
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


if __name__ == "__main__":
    unittest.main()
