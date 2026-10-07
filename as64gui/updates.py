"""
The app's update flow: checking for a newer release, offering it, downloading it with progress,
and installing it with a restart now or when the app quits. The network work runs on threads,
which report back through signals, so the dialogs are shown on the GUI thread.
"""
import logging
import tempfile
import threading

from PyQt6 import QtCore, QtGui, QtWidgets

from as64core import updater
from . import constants


class Updates(QtCore.QObject):
    _checked = QtCore.pyqtSignal(object, bool)  # newer release or None, whether the user asked
    _check_failed = QtCore.pyqtSignal(str, bool)
    _progress = QtCore.pyqtSignal(int, int)
    _downloaded = QtCore.pyqtSignal(object)
    _download_failed = QtCore.pyqtSignal(str)

    def __init__(self, window, badge, is_running):
        """ is_running() tells whether split detection is running, when the app shouldn't restart """
        super().__init__(window)
        self._window = window
        self._badge = badge
        self._is_running = is_running
        self._release = None
        self._install_on_quit = None
        self._progress_dialog = None
        self._downloading = False

        self._checked.connect(self._on_checked)
        self._check_failed.connect(self._on_check_failed)
        self._progress.connect(self._on_progress)
        self._downloaded.connect(self._on_downloaded)
        self._download_failed.connect(self._on_download_failed)
        badge.clicked.connect(self._on_badge_clicked)

    def check(self, asked=False):
        """ Check for a newer release in the background. On launch (not asked) it's offered in a prompt. """
        threading.Thread(target=self._check, args=(asked,), daemon=True).start()

    def _check(self, asked):
        try:
            self._checked.emit(updater.newer_release(constants.GITHUB_REPO, constants.VERSION), asked)
        except Exception as e:
            logging.getLogger(".log").warning("Update check failed", exc_info=True)
            self._check_failed.emit(str(e), asked)

    def _on_checked(self, release, asked):
        if release is None:
            if asked:
                if updater.parse_version(constants.VERSION) is None:
                    self._message(f"This is a development version ({constants.VERSION}). Updates are for released versions.")
                else:
                    self._message(f"AutoSplit64++ v{constants.VERSION} is the latest version.")
            return

        self._release = release
        self._badge.show_update(release.version)
        if asked or self._ask(f"AutoSplit64++ v{release.version} is available. You have v{constants.VERSION}.",
                              "Update", "Later"):
            self.update()

    def _on_check_failed(self, error, asked):
        if asked:
            self._message(f"Couldn't check for updates:\n\n{error}")

    def _on_badge_clicked(self):
        if self._release:
            self.update()
        else:
            self.check(asked=True)

    def update(self):
        """ Download the newer release, then offer to install it """
        # e.g. the badge clicked again during the download
        if self._downloading:
            return
        if not updater.can_install():
            # Running from source: the release page has the app
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._release.page_url))
            return
        if self._is_running():
            self._message("Split detection is running. Stop split detection first, in case you're in a run, "
                          "then click the version to update.")
            return

        self._progress_dialog = QtWidgets.QProgressDialog(f"Downloading AutoSplit64++ v{self._release.version}...", None, 0, 0, self._window)
        self._progress_dialog.setWindowTitle("Update")
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.show()
        self._downloading = True
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        try:
            path = updater.download(self._release, tempfile.mkdtemp(prefix="as64-download-"), self._progress.emit)
            self._downloaded.emit(path)
        except Exception as e:
            logging.getLogger(".log").warning("Update download failed", exc_info=True)
            self._download_failed.emit(str(e))

    def _on_progress(self, done, total):
        self._progress_dialog.setMaximum(total)
        self._progress_dialog.setValue(done)

    def _on_download_failed(self, error):
        self._downloading = False
        self._progress_dialog.close()
        self._message(f"Couldn't download the update:\n\n{error}")

    def _on_downloaded(self, path):
        self._downloading = False
        self._progress_dialog.close()
        box = QtWidgets.QMessageBox(self._window)
        box.setWindowTitle("Update")
        box.setText(f"AutoSplit64++ v{self._release.version} is ready to install.")
        restart = box.addButton("Restart Now", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton("When I Quit", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        # Split detection was started during the download
        if self._is_running():
            restart.setEnabled(False)
            box.setInformativeText("Split detection is running, so it will be installed when you quit.")
        box.exec()

        if box.clickedButton() is restart:
            updater.install_on_exit(path, relaunch=True)
            self._window.close()
            QtWidgets.QApplication.quit()
        else:
            self._install_on_quit = path

    def on_quit(self):
        """ Install a downloaded update now that the app is quitting """
        if self._install_on_quit:
            updater.install_on_exit(self._install_on_quit, relaunch=False)
            self._install_on_quit = None

    def _ask(self, text, yes, no):
        box = QtWidgets.QMessageBox(self._window)
        box.setWindowTitle("Update Available")
        box.setText(text)
        yes_button = box.addButton(yes, QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton(no, QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is yes_button

    def _message(self, text):
        QtWidgets.QMessageBox.information(self._window, "Update", text)
