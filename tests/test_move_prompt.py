import copy
import unittest
from pathlib import Path
from unittest import mock

from PyQt6 import QtWidgets
from PyQt6.QtTest import QTest

from autosplit64.core import app_location, config
from autosplit64.gui.app import App
from tests.qt import close_window
from tests.test_updates import answering

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

DOWNLOADED = Path("/private/var/folders/xy/T/AppTranslocation/1234/d/AutoSplit64++.app")


class MovePromptTest(unittest.TestCase):
    def open_app(self, reason, choice=None, move=None):
        texts = []
        patches = [mock.patch("autosplit64.gui.updates.Updates.check"),
                   mock.patch.object(app_location, "running_app", return_value=DOWNLOADED),
                   mock.patch.object(app_location, "move_reason", return_value=reason),
                   mock.patch.object(app_location, "applications_folder", return_value=Path("/Applications")),
                   mock.patch.object(app_location, "move_to", side_effect=move or (lambda app, folder: folder / app.name)),
                   mock.patch.object(app_location, "reopen_after_exit"),
                   mock.patch.object(QtWidgets.QApplication, "quit"),
                   mock.patch.object(QtWidgets.QMessageBox, "warning"),
                   # Settings changes stay in this test
                   mock.patch.object(config, "_config", copy.deepcopy(config._config)),
                   mock.patch.object(config, "save_config")]
        if choice:
            def exec_(box):
                texts.append(box.text() + "\n" + box.informativeText())
                next(b for b in box.buttons() if b.text() == choice).click()
                return 0
            patches.append(mock.patch.object(QtWidgets.QMessageBox, "exec", exec_))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        app = App()
        self.addCleanup(close_window, app)
        QTest.qWait(50)
        return app, texts

    def test_move(self):
        _, texts = self.open_app(app_location.TRANSLOCATED, "Move to Applications")
        self.assertIn("Move it to your Applications folder?", texts[0])
        self.assertIn("updates can't be installed", texts[0])
        app_location.move_to.assert_called_once_with(DOWNLOADED, Path("/Applications"))
        app_location.reopen_after_exit.assert_called_once_with(Path("/Applications/AutoSplit64++.app"))
        QtWidgets.QApplication.quit.assert_called_once()

    def test_not_now(self):
        _, texts = self.open_app(app_location.DOWNLOADS, "Not Now")
        self.assertIn("Downloads folder", texts[0])
        app_location.move_to.assert_not_called()
        QtWidgets.QApplication.quit.assert_not_called()

    def test_failed_move_keeps_running(self):
        def fail(app, folder):
            raise OSError("Permission denied")
        self.open_app(app_location.DOWNLOADS, "Move to Applications", move=fail)
        self.assertIn("Permission denied", QtWidgets.QMessageBox.warning.call_args.args[2])
        app_location.reopen_after_exit.assert_not_called()
        QtWidgets.QApplication.quit.assert_not_called()

    def test_dont_ask_again(self):
        self.open_app(app_location.TRANSLOCATED, "Don't Ask Again")
        app_location.move_to.assert_not_called()
        self.assertIs(config.get("general", "ask_to_move"), False)
        config.save_config.assert_called()

        with mock.patch.object(QtWidgets.QMessageBox, "exec") as exec_:
            app = App()
            self.addCleanup(close_window, app)
            QTest.qWait(50)
        exec_.assert_not_called()

    def test_no_prompt_elsewhere(self):
        with mock.patch.object(QtWidgets.QMessageBox, "exec") as exec_:
            self.open_app(None)
        exec_.assert_not_called()


if __name__ == "__main__":
    unittest.main()
