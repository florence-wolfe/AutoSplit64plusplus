from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.core import resource_utils
from autosplit64.core import config, detection_model
from autosplit64.gui import theme
from autosplit64.gui.qml_view import qml_view
from autosplit64.gui.constants import (
    ICON_PATH
)


# The styles' names where they aren't the ones Qt gives them
STYLE_NAMES = {"FluentWinUI3": "Fluent", "AutoSplit64": "AutoSplit64++"}


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

    @QtCore.pyqtProperty("QVariantList", constant=True)
    def styles(self):
        return [{"text": STYLE_NAMES.get(name, name), "value": name,
                 "about": "Its controls take the system's accent color, not the theme's." if name in theme.SYSTEM_STYLES else ""}
                for name in theme.styles()]

    @QtCore.pyqtProperty(str, constant=True)
    def warningColor(self):
        return theme.status_color("yellow").name()

    def load(self):
        """ Forget the changes, and have the fields show the saved values """
        self._changes.clear()
        self.loaded.emit()

    @QtCore.pyqtSlot(str, str, result="QVariant")
    def get(self, section, key):
        if (section, key) == ("model", "detection") and (section, key) not in self._changes:
            return detection_model.get()
        return self._changes.get((section, key), config.get(section, key))

    @QtCore.pyqtSlot(str, str, "QVariant")
    def set(self, section, key, value):
        self._changes[section, key] = like(config.get(section, key), value)
        # Releases before it read the model from model.legacy
        if (section, key) == ("model", "detection"):
            self._changes["model", "legacy"] = detection_model.legacy(value)

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

        self.settings = Settings()
        self.settings.applied.connect(self._applied)
        self.settings.cancelled.connect(self.hide)
        self.view = qml_view(self, "SettingsDialog", settings=self.settings)

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
