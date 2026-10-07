import contextlib
import os
import tempfile
import unittest
from unittest import mock

from autosplit64.core.constants import MODEL_PATH, MODEL_PATH_LEGACY
from autosplit64.core.resource_utils import abs_to_rel, base_path
from autosplit64.gui.constants import FONT_PATH


class AbsToRelTest(unittest.TestCase):
    def test_path_inside_working_directory(self):
        self.assertEqual(abs_to_rel(os.path.join(os.getcwd(), "routes", "16.as64")), "routes/16.as64")

    def test_path_outside_working_directory(self):
        self.assertEqual(abs_to_rel("/somewhere/else/16.as64"), "/somewhere/else/16.as64")

    def test_working_directory_inside_another_path(self):
        path = "/Volumes/Backup" + os.getcwd() + "/16.as64"
        self.assertEqual(abs_to_rel(path), path)

    def test_relative_path(self):
        self.assertEqual(abs_to_rel("routes/16.as64"), "routes/16.as64")


class BasePathTest(unittest.TestCase):
    def test_source_run_uses_working_directory(self):
        # `python -m autosplit64` puts the package's __main__.py in argv[0]
        with mock.patch("sys.argv", ["/repo/src/autosplit64/__main__.py"]):
            self.assertEqual(base_path(), os.getcwd())
            self.assertEqual(base_path("routes"), os.path.join(os.getcwd(), "routes").replace("\\", "/"))


class PackageDataTest(unittest.TestCase):
    def test_found_from_any_working_directory(self):
        with contextlib.chdir(tempfile.gettempdir()):
            for path in (MODEL_PATH, MODEL_PATH_LEGACY, FONT_PATH):
                with self.subTest(path):
                    self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
