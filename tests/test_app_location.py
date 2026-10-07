import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from as64core import app_location


class NeedsMoveTest(unittest.TestCase):
    def reason(self, path, frozen=True, platform="darwin"):
        with mock.patch.object(app_location.sys, "platform", platform), \
             mock.patch.object(app_location.sys, "frozen", frozen, create=True):
            return app_location.move_reason(Path(path))

    def test_translocated(self):
        path = "/private/var/folders/xy/T/AppTranslocation/1234-ABCD/d/AutoSplit64++.app"
        self.assertEqual(self.reason(path), app_location.TRANSLOCATED)

    def test_downloads(self):
        self.assertEqual(self.reason(Path.home() / "Downloads" / "AutoSplit64++.app"), app_location.DOWNLOADS)
        self.assertEqual(self.reason(Path.home() / "Downloads" / "as64" / "AutoSplit64++.app"), app_location.DOWNLOADS)

    def test_applications_or_a_chosen_folder(self):
        for path in ("/Applications/AutoSplit64++.app", Path.home() / "Applications" / "AutoSplit64++.app",
                     Path.home() / "Speedrunning" / "AutoSplit64++.app"):
            self.assertIsNone(self.reason(path), path)

    def test_only_the_macos_app(self):
        downloads = Path.home() / "Downloads" / "AutoSplit64++.app"
        self.assertIsNone(self.reason(downloads, frozen=False))
        self.assertIsNone(self.reason(downloads, platform="win32"))


@unittest.skipUnless(sys.platform == "darwin", "moves a macOS app")
class MoveTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.app = self.dir / "Downloads" / "AutoSplit64++.app"
        self.write(self.app / "Contents" / "MacOS" / "AutoSplit64++", "new")
        # Downloaded apps carry this attribute, which makes macOS translocate them
        subprocess.run(["xattr", "-w", "com.apple.quarantine", "0081;00000000;Safari;", str(self.app)], check=True)
        self.applications = self.dir / "Applications"
        self.applications.mkdir()
        self.trashed = []
        patcher = mock.patch.object(app_location, "_trash", side_effect=lambda path: (self.trashed.append(path.name), shutil.rmtree(path)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_copies_the_app_without_the_downloaded_flag(self):
        moved = app_location.move_to(self.app, self.applications)
        self.assertEqual(moved, self.applications / "AutoSplit64++.app")
        self.assertEqual((moved / "Contents" / "MacOS" / "AutoSplit64++").read_text(), "new")
        attributes = subprocess.run(["xattr", "-r", str(moved)], capture_output=True, text=True).stdout
        self.assertNotIn("com.apple.quarantine", attributes)

    def test_replaces_an_older_copy_via_the_trash(self):
        self.write(self.applications / "AutoSplit64++.app" / "Contents" / "MacOS" / "AutoSplit64++", "old")
        moved = app_location.move_to(self.app, self.applications)
        self.assertEqual(self.trashed, ["AutoSplit64++.app"])
        self.assertEqual((moved / "Contents" / "MacOS" / "AutoSplit64++").read_text(), "new")

    def test_applications_folder(self):
        with mock.patch.object(app_location.os, "access", return_value=True):
            self.assertEqual(app_location.applications_folder(), Path("/Applications"))
        # Without permission to /Applications, the user's own
        with mock.patch.object(app_location.os, "access", return_value=False), \
             mock.patch.object(app_location.Path, "home", return_value=self.dir):
            self.assertEqual(app_location.applications_folder(), self.dir / "Applications")

    def test_reopens_after_quitting(self):
        with mock.patch.object(app_location.subprocess, "Popen") as popen:
            app_location.reopen_after_exit(self.applications / "AutoSplit64++.app", pid=123)
        command = popen.call_args.args[0]
        self.assertIn('kill -0 "$1"', command[2])
        self.assertIn('open "$2"', command[2])
        self.assertEqual(command[-2:], ["123", str(self.applications / "AutoSplit64++.app")])


if __name__ == "__main__":
    unittest.main()
