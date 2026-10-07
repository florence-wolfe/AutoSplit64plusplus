import importlib
import pkgutil
import sys
import unittest

import as64core
import as64gui
import as64processes


class ImportTest(unittest.TestCase):
    """ Every module imports, so nothing refers to a removed name when it loads """

    def test_all_modules_import(self):
        for package in (as64core, as64gui, as64processes):
            for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
                if module.name.endswith("_mac") and sys.platform != "darwin":
                    continue
                if module.name == "as64core.capture_window" and sys.platform != "win32":
                    continue
                with self.subTest(module.name):
                    importlib.import_module(module.name)

    def test_app_imports(self):
        importlib.import_module("AutoSplit64")


if __name__ == "__main__":
    unittest.main()
