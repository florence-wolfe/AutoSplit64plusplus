import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import dev


class ChangesTest(unittest.TestCase):
    """ The files whose change restarts the app """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / "gui").mkdir()
        for name in ("main.py", "gui/app.py", "logic.processor", "notes.txt"):
            (self.dir / name).write_text("before")
        self.before = dev.snapshot(self.dir)

    def touch(self, name, text="after"):
        path = self.dir / name
        path.write_text(text)
        # Later than before, also on file systems that only keep seconds
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 2_000_000_000))

    def test_nothing_changed(self):
        self.assertEqual(dev.changes(self.before, dev.snapshot(self.dir)), [])

    def test_changed_code_and_processors(self):
        self.touch("gui/app.py")
        self.touch("logic.processor")
        self.assertEqual(dev.changes(self.before, dev.snapshot(self.dir)), ["gui/app.py", "logic.processor"])

    def test_new_and_deleted_files(self):
        self.touch("gui/new.py")
        (self.dir / "main.py").unlink()
        self.assertEqual(dev.changes(self.before, dev.snapshot(self.dir)), ["gui/new.py", "main.py"])

    def test_other_files_are_ignored(self):
        self.touch("notes.txt")
        self.assertEqual(dev.changes(self.before, dev.snapshot(self.dir)), [])


class OpenWindowTest(unittest.TestCase):
    def setUp(self):
        dialogs = ("debug_dialog", "route_editor", "settings_dialog", "reset_dialog", "about_dialog")
        self.app = mock.Mock(dialogs={name: mock.Mock() for name in dialogs})

    def test_each_window(self):
        for name, dialog in (("debug", "debug_dialog"), ("route-editor", "route_editor"), ("settings", "settings_dialog"),
                             ("reset-templates", "reset_dialog"), ("about", "about_dialog")):
            with self.subTest(name):
                dev.open_window(self.app, name)
                self.app.dialogs[dialog].show.assert_called()

    def test_capture_editor_like_the_menu(self):
        dev.open_window(self.app, "capture")
        self.app._edit_coordinates.assert_called_once()

    def test_names_are_the_windows(self):
        self.assertEqual(sorted(dev.WINDOWS), ["about", "capture", "debug", "reset-templates", "route-editor", "settings"])


if __name__ == "__main__":
    unittest.main()
