import os
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtQuickWidgets, QtWidgets

from autosplit64.core import resource_utils
from autosplit64.core import config
from autosplit64.gui import theme
from autosplit64.gui.constants import (
    ICON_PATH
)

# Material's compact sizes, which suit a desktop window. Read when the style is first loaded.
os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_VARIANT", "Dense")

QML = Path(__file__).parent.parent / "qml" / "SettingsDialog.qml"


def show_theme(name):
    if name != theme.current():
        theme.apply(name)


def like(saved, value):
    """ value from QML as the type of the setting's saved value: QML has only one kind of number """
    if isinstance(saved, list):
        return [type(old)(new) for old, new in zip(saved, value)]
    return type(saved)(value)


class Settings(QtCore.QObject):
    """ The settings for SettingsDialog.qml: their saved values, with the changes made since they were loaded """
    loaded = QtCore.pyqtSignal()
    applied = QtCore.pyqtSignal()
    cancelled = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._changes = {}

    @QtCore.pyqtProperty("QVariantList", constant=True)
    def themes(self):
        return [{"text": theme.display_name(name), "value": name} for name in theme.themes()]

    def load(self):
        """ Forget the changes, and have the fields show the saved values """
        self._changes.clear()
        self.loaded.emit()

    @QtCore.pyqtSlot(str, str, result="QVariant")
    def get(self, section, key):
        return self._changes.get((section, key), config.get(section, key))

    @QtCore.pyqtSlot(str, str, "QVariant")
    def set(self, section, key, value):
        self._changes[section, key] = like(config.get(section, key), value)

    @QtCore.pyqtSlot(str, str, str)
    def set_path(self, section, key, path):
        self._changes[section, key] = resource_utils.abs_to_rel(path)

    @QtCore.pyqtSlot(str, result=str)
    def browse(self, title):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self.parent(), title, "")
        return file_name

    @QtCore.pyqtSlot(str)
    def show_theme(self, name):
        show_theme(name)

    @QtCore.pyqtSlot()
    def apply(self):
        for (section, key), value in self._changes.items():
            config.set_key(section, key, value)
        config.save_config()
        self.applied.emit()

    @QtCore.pyqtSlot()
    def cancel(self):
        self.cancelled.emit()


class SettingsDialog(QtWidgets.QDialog):
    applied = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.WindowType.WindowSystemMenuHint | QtCore.Qt.WindowType.WindowCloseButtonHint)

        self.setWindowTitle("Settings")
        self.setWindowIcon(QtGui.QIcon(resource_utils.resource_path(ICON_PATH)))
        self.resize(780, 640)

        self.view = QtQuickWidgets.QQuickWidget()
        self.view.setResizeMode(QtQuickWidgets.QQuickWidget.ResizeMode.SizeRootObjectToView)
        # The view's child: the view deletes its QML before its children, so the QML never sees it deleted
        self.settings = Settings(self.view)
        self.settings.applied.connect(self._applied)
        self.settings.cancelled.connect(self.hide)
        self.view.rootContext().setContextProperty("settings", self.settings)
        self.view.setSource(QtCore.QUrl.fromLocalFile(str(QML)))
        if self.view.status() == QtQuickWidgets.QQuickWidget.Status.Error:
            raise RuntimeError("\n".join(error.toString() for error in self.view.errors()))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def show(self):
        self.settings.load()
        super().show()

    def hideEvent(self, event):
        # Applying saved the theme shown, otherwise go back to the saved one
        if not event.spontaneous():
            show_theme(config.get("general", "theme"))
        super().hideEvent(event)

    def apply_clicked(self):
        self.settings.apply()

    def _applied(self):
        self.hide()
        self.applied.emit()
