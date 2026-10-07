import importlib
import pkgutil
import sys
import unittest

import autosplit64


class ImportTest(unittest.TestCase):
    """ Every module imports, so nothing refers to a removed name when it loads """

    def test_all_modules_import(self):
        for module in pkgutil.walk_packages(autosplit64.__path__, "autosplit64."):
            if module.name == "autosplit64.__main__":
                continue
            if module.name.endswith("_mac") and sys.platform != "darwin":
                continue
            if (module.name.endswith("_win") or module.name == "autosplit64.core.capture_window") and sys.platform != "win32":
                continue
            with self.subTest(module.name):
                importlib.import_module(module.name)


if __name__ == "__main__":
    unittest.main()
