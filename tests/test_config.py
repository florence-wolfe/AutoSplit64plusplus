import unittest
from unittest import mock

from autosplit64.core import config


class SetKeyTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(config, "_config", {"general": {"on_top": True}})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_overwrites_key(self):
        config.set_key("general", "on_top", False)
        self.assertIs(config.get("general", "on_top"), False)

    def test_adds_key_to_existing_section(self):
        config.set_key("general", "new_key", 1)
        self.assertEqual(config.get("general"), {"on_top": True, "new_key": 1})

    def test_adds_section(self):
        config.set_key("new_section", "key", "value")
        self.assertEqual(config.get("new_section", "key"), "value")



class DefaultConnectionModeTest(unittest.TestCase):
    """ Named pipes only exist on Windows, and LiveSplit desktop only runs there """

    def default_mode(self, platform):
        with mock.patch.object(config, "_defaults", None), mock.patch.object(config.sys, "platform", platform):
            return config.get_default("connection", "ls_connection_type")

    def test_windows_uses_named_pipe(self):
        self.assertEqual(self.default_mode("win32"), 0)

    def test_elsewhere_uses_livesplit_one(self):
        self.assertEqual(self.default_mode("darwin"), 2)
        self.assertEqual(self.default_mode("linux"), 2)

if __name__ == "__main__":
    unittest.main()
