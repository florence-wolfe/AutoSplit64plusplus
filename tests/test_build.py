import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import build


class VersionTest(unittest.TestCase):
    def test_tag_from_ci(self):
        with mock.patch.dict(os.environ, {"AS64_VERSION": "v0.4.0"}):
            self.assertEqual(build.release_version(), "0.4.0")

    def test_local_build_uses_git_describe(self):
        for described, version in [("v0.4.0\n", "0.4.0"), ("v0.4.0-3-gabc1234-dirty\n", "0.4.0-3-gabc1234-dirty"),
                                   # No tag, or no git
                                   ("", "dev")]:
            with self.subTest(described), mock.patch.dict(os.environ), \
                 mock.patch.object(build.subprocess, "run", return_value=mock.Mock(stdout=described)) as run:
                os.environ.pop("AS64_VERSION", None)
                self.assertEqual(build.release_version(), version)
            self.assertEqual(run.call_args.args[0][:2], ["git", "describe"])

    def test_version_file_exists_only_for_the_build(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "_version.py"
            with mock.patch.object(build, "VERSION_FILE", path):
                with build.version_file("0.4.0"):
                    self.assertEqual(path.read_text(), 'VERSION = "0.4.0"\n')
                self.assertFalse(path.exists())

    def test_the_app_shows_the_version_file(self):
        import autosplit64.gui.constants
        self.assertEqual(build.VERSION_FILE.resolve(), Path(autosplit64.gui.constants.__file__).parent / "_version.py")
        self.addCleanup(importlib.reload, autosplit64.gui.constants)
        with mock.patch.dict(sys.modules, {"autosplit64.gui._version": types.SimpleNamespace(VERSION="0.4.0")}):
            self.assertEqual(importlib.reload(autosplit64.gui.constants).VERSION, "0.4.0")
        self.assertEqual(importlib.reload(autosplit64.gui.constants).VERSION, "dev")

if __name__ == "__main__":
    unittest.main()
