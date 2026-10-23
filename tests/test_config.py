import json
import os
import tempfile
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


class RollbackTest(unittest.TestCase):
    """ What Configure Capture's Cancel and closing it go back to: the settings as they were when it opened """

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for patcher in [mock.patch.object(config, "_config", {"game": {"vc_fix": False, "game_region": [0, 0, 4, 3]}}),
                        mock.patch.object(config, "_rollback", None),
                        mock.patch.object(config, "_CONFIG_FILE_NAME", os.path.join(directory.name, "config.ini"))]:
            patcher.start()
            self.addCleanup(patcher.stop)
        config.create_rollback()

    def test_rollback_undoes_changes(self):
        config.set_key("game", "vc_fix", True)
        config.get("game", "game_region").append(5)
        config.set_key("general", "on_top", True)
        config.rollback()
        self.assertEqual(config._config, {"game": {"vc_fix": False, "game_region": [0, 0, 4, 3]}})

    def test_saved_changes_are_kept(self):
        # Apply saves, then closes, which rolls back
        config.set_key("game", "vc_fix", True)
        config.save_config()
        config.rollback()
        self.assertIs(config.get("game", "vc_fix"), True)

    def test_rolling_back_twice(self):
        config.set_key("game", "vc_fix", True)
        config.rollback()
        config.set_key("game", "vc_fix", True)
        config.rollback()
        self.assertIs(config.get("game", "vc_fix"), False)



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

class PeekTest(unittest.TestCase):
    """ A saved setting before the settings are loaded, which may ask about them in a window """

    def peek(self, saved):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.ini")
            if saved is not None:
                with open(path, "w") as file:
                    json.dump(saved, file)
            with mock.patch.object(config, "_CONFIG_FILE_NAME", path), mock.patch.object(config, "_config", {}):
                value = config.peek("general", "style")
                self.assertEqual(config._config, {})
        return value

    def test_saved_value(self):
        self.assertEqual(self.peek({"general": {"style": "Fusion"}}), "Fusion")

    def test_default_without_it(self):
        self.assertEqual(self.peek({"general": {}}), config.get_default("general", "style"))
        self.assertEqual(self.peek(None), config.get_default("general", "style"))


if __name__ == "__main__":
    unittest.main()
