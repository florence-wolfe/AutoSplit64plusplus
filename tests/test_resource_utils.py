import os
import unittest

from as64core.resource_utils import abs_to_rel


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


if __name__ == "__main__":
    unittest.main()
