import unittest
from unittest import mock

from as64core import config


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


if __name__ == "__main__":
    unittest.main()
