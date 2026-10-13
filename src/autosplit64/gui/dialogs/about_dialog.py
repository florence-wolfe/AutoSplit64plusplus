from PyQt6 import QtCore, QtGui, QtWidgets

from ..constants import (
    VERSION,
    AUTHOR,
    ICON_PATH,
    TITLE,
    GITHUB_REPO,
)
from ..qml_view import qml_view
from autosplit64.core import resource_utils


class Links(QtCore.QObject):
    @QtCore.pyqtSlot(str)
    def open(self, url):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setFixedSize(460, 260)
        self.setWindowTitle("About AutoSplit64++")

        self.view = qml_view(self, "AboutDialog", links=Links(), title=TITLE, version=VERSION, authors=AUTHOR,
                             icon=QtCore.QUrl.fromLocalFile(resource_utils.resource_path(ICON_PATH)),
                             githubUrl=f"https://github.com/{GITHUB_REPO}")
