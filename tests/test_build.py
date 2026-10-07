import importlib
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import build


class VersionTest(unittest.TestCase):
    def test_tag_from_ci(self):
        with mock.patch.dict(os.environ, {"AS64_VERSION": "v0.4.0"}):
            self.assertEqual(build.release_version(), "0.4.0")

    def test_local_build_uses_git_describe(self):
        described = subprocess.run(["git", "describe", "--tags", "--match", "v[0-9]*", "--dirty"],
                                   capture_output=True, text=True).stdout.strip()
        # Keep PATH, which Windows needs to find git
        with mock.patch.dict(os.environ):
            os.environ.pop("AS64_VERSION", None)
            self.assertEqual(build.release_version(), described.removeprefix("v") or "dev")

    def test_version_file_exists_only_for_the_build(self):
        path = Path("as64gui/_version.py")
        self.assertFalse(path.exists())
        with build.version_file("0.4.0"):
            self.assertEqual(path.read_text(), 'VERSION = "0.4.0"\n')
            import as64gui.constants
            self.assertEqual(importlib.reload(as64gui.constants).VERSION, "0.4.0")
        self.assertFalse(path.exists())
        sys.modules.pop("as64gui._version", None)
        self.assertEqual(importlib.reload(as64gui.constants).VERSION, "dev")


if __name__ == "__main__":
    unittest.main()
