import os
import threading
import time
import unittest
from unittest import mock

from PyQt6 import QtWidgets
from PyQt6.QtTest import QTest

from autosplit64.core import updater
from autosplit64.gui import app as app_module, updates
from autosplit64.gui.app import App
from tests.qt import answering, close_window, qml

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

RELEASE = updater.Release("0.5.0", "AutoSplit64plusplus-v0.5.0-macos-arm64.zip", "https://example.com/app.zip",
                          "https://example.com/SHA256SUMS", "https://example.com/release")


class UpdatesTestCase(unittest.TestCase):
    def setUp(self):
        real_get = app_module.config.get
        for patcher in [mock.patch.object(app_module.config, "get", side_effect=lambda section, key=None:
                                          self.check_on_launch if (section, key) == ("general", "update_check") else real_get(section, key)),
                        mock.patch.object(app_module.constants, "VERSION", "0.4.0"),
                        mock.patch.object(QtWidgets.QMessageBox, "information"),
                        # Until the window is closed, which installs an update left for when the app quits
                        mock.patch.object(updater, "install_on_exit")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.check_on_launch = False

    def open_app(self):
        app = App()
        self.addCleanup(close_window, app)
        return app

    def wait_for(self, predicate):
        for _ in range(150):
            if predicate():
                return True
            QTest.qWait(20)
        return False


class LaunchCheckTest(UpdatesTestCase):
    def test_window_opens_without_waiting_and_offers_the_update(self):
        self.check_on_launch = True
        release_ready = threading.Event()
        prompts = []

        def slow_github(repo, version):
            release_ready.wait(3)
            return RELEASE

        with mock.patch.object(updater, "newer_release", side_effect=slow_github), \
             mock.patch.object(updates.Updates, "_ask", lambda self, text, yes, no: prompts.append((text, threading.current_thread())) and False):
            started = time.time()
            app = self.open_app()
            self.assertLess(time.time() - started, 2)
            release_ready.set()
            self.assertTrue(self.wait_for(lambda: prompts))

        self.assertEqual(prompts, [("AutoSplit64++ v0.5.0 is available. You have v0.4.0.", threading.main_thread())])
        version = qml(app.view, "version").property("text")
        self.assertIn("v0.4.0", version)
        self.assertIn("●", version)
        self.assertEqual(app.main.values["versionTip"], "Update available: v0.5.0\nClick to update")

    def test_no_check_when_turned_off(self):
        with mock.patch.object(updater, "newer_release") as newer_release:
            app = self.open_app()
            QTest.qWait(100)
        newer_release.assert_not_called()
        # The version, without the update dot
        version = qml(app.view, "version").property("text")
        self.assertIn(">v0.4.0<", version)
        self.assertNotIn("●", version)

    def test_latest_version_is_shown_without_asking(self):
        self.check_on_launch = True
        with mock.patch.object(updater, "newer_release", return_value=None):
            app = self.open_app()
            self.assertTrue(self.wait_for(lambda: app.update_badge.latest))
        QtWidgets.QMessageBox.information.assert_not_called()
        self.assertEqual(app.main.values["versionTip"], "You're on the latest version\nClick to open the changelog")


class BadgeTest(UpdatesTestCase):
    def test_up_to_date(self):
        app = self.open_app()
        with mock.patch.object(updater, "newer_release", return_value=None):
            app.update_badge.clicked.emit()
            self.assertTrue(self.wait_for(lambda: QtWidgets.QMessageBox.information.called))
        self.assertIn("v0.4.0 is the latest version", QtWidgets.QMessageBox.information.call_args.args[2])

    def test_latest_version_opens_its_changelog(self):
        app = self.open_app()
        with mock.patch.object(updater, "newer_release", return_value=None):
            app.update_badge.clicked.emit()
            self.assertTrue(self.wait_for(lambda: QtWidgets.QMessageBox.information.called))
        self.assertEqual(app.main.values["versionTip"], "You're on the latest version\nClick to open the changelog")

        with mock.patch.object(updater, "newer_release") as newer_release, \
             mock.patch.object(updates.QtGui.QDesktopServices, "openUrl") as open_url:
            app.update_badge.clicked.emit()
            QTest.qWait(50)
        newer_release.assert_not_called()
        self.assertEqual(open_url.call_args.args[0].toString(),
                         "https://github.com/florence-wolfe/AutoSplit64plusplus/releases/tag/v0.4.0")

    def test_development_version(self):
        app = self.open_app()
        with mock.patch.object(app_module.constants, "VERSION", "dev"), \
             mock.patch.object(updater, "latest_release") as latest_release:
            app.update_badge.clicked.emit()
            self.assertTrue(self.wait_for(lambda: QtWidgets.QMessageBox.information.called))
        latest_release.assert_not_called()
        self.assertIn("development version (dev)", QtWidgets.QMessageBox.information.call_args.args[2])
        # It has no release with a changelog
        self.assertEqual(app.main.values["versionTip"], "Click to check for updates")

    def test_running_from_source_opens_the_release_page(self):
        app = self.open_app()
        app.updates._release = RELEASE
        with mock.patch.object(updater, "can_install", return_value=False), \
             mock.patch.object(updates.QtGui.QDesktopServices, "openUrl") as open_url:
            app.update_badge.clicked.emit()
        self.assertEqual(open_url.call_args.args[0].toString(), "https://example.com/release")


class InstallTest(UpdatesTestCase):
    def download_and_answer(self, choice, started_during_download=False):
        app = self.open_app()
        app.updates._release = RELEASE
        buttons = []

        def download(release, directory, progress):
            if started_during_download:
                app._set_start_state("stop")
            return "/tmp/update.zip"

        with mock.patch.object(updater, "can_install", return_value=True), \
             mock.patch.object(updater, "download", side_effect=download), \
             mock.patch.object(updater, "install_on_exit") as install, \
             mock.patch.object(QtWidgets.QApplication, "quit") as quit_app, \
             answering(choice, buttons):
            app.update_badge.clicked.emit()
            self.assertTrue(self.wait_for(lambda: buttons))
            QTest.qWait(50)
            app.updates.on_quit()
        return install, quit_app, buttons

    def test_restart_now(self):
        install, quit_app, _ = self.download_and_answer("Restart Now")
        install.assert_called_once_with("/tmp/update.zip", relaunch=True)
        quit_app.assert_called_once()

    def test_when_i_quit(self):
        install, quit_app, _ = self.download_and_answer("When I Quit")
        install.assert_called_once_with("/tmp/update.zip", relaunch=False)
        quit_app.assert_not_called()

    def test_clicking_again_during_the_download(self):
        app = self.open_app()
        app.updates._release = RELEASE
        finish = threading.Event()
        downloads = []

        def slow_download(release, directory, progress):
            downloads.append(release)
            finish.wait(3)
            return "/tmp/update.zip"

        with mock.patch.object(updater, "can_install", return_value=True), \
             mock.patch.object(updater, "download", side_effect=slow_download), \
             mock.patch.object(updater, "install_on_exit"), answering("When I Quit"):
            app.update_badge.clicked.emit()
            app.update_badge.clicked.emit()
            finish.set()
            self.assertTrue(self.wait_for(lambda: app.updates._install_on_quit))
        self.assertEqual(len(downloads), 1)

    def test_failed_download_is_told_and_leaves_no_folder(self):
        app = self.open_app()
        app.updates._release = RELEASE
        directories = []

        def failing_download(release, directory, progress):
            directories.append(directory)
            raise updater.UpdateError("The download of app.zip doesn't match its checksum.")

        with mock.patch.object(updater, "can_install", return_value=True), \
             mock.patch.object(updater, "download", side_effect=failing_download), \
             self.assertLogs(".log", "WARNING"):
            app.update_badge.clicked.emit()
            self.assertTrue(self.wait_for(lambda: QtWidgets.QMessageBox.information.called))
        self.assertIn("doesn't match its checksum", QtWidgets.QMessageBox.information.call_args.args[2])
        self.assertFalse(os.path.exists(directories[0]))
        self.assertFalse(app.updates._downloading)

    def test_no_update_while_splitting(self):
        # In case of an active run, split detection has to be stopped first
        app = self.open_app()
        app.updates._release = RELEASE
        app._set_start_state("stop")
        with mock.patch.object(updater, "can_install", return_value=True), \
             mock.patch.object(updater, "download") as download:
            app.update_badge.clicked.emit()
            QTest.qWait(50)
        download.assert_not_called()
        self.assertIn("Stop split detection", QtWidgets.QMessageBox.information.call_args.args[2])

    def test_no_restart_when_split_detection_started_during_the_download(self):
        _, _, buttons = self.download_and_answer("When I Quit", started_during_download=True)
        self.assertEqual(buttons, [{"Restart Now": False, "When I Quit": True}])


if __name__ == "__main__":
    unittest.main()
