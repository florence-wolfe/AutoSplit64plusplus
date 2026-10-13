from PyQt6 import QtCore, QtWidgets

from autosplit64.gui.qml_view import qml_view


class Changes(QtCore.QObject):
    """ The offered settings changes for SettingsChangesDialog.qml, and which of them are checked """
    applied = QtCore.pyqtSignal()
    kept = QtCore.pyqtSignal()

    def __init__(self, offered):
        super().__init__()
        self.checked = [True] * len(offered)
        self._items = [{"text": f"{step['name']}: {step['from']} → {step['to']}", "reason": step["reason"]}
                       for step in offered]

    @QtCore.pyqtProperty("QVariantList", constant=True)
    def items(self):
        return self._items

    @QtCore.pyqtSlot(int, bool)
    def set_checked(self, index, checked):
        self.checked[index] = checked

    @QtCore.pyqtSlot()
    def apply(self):
        self.applied.emit()

    @QtCore.pyqtSlot()
    def keep(self):
        self.kept.emit()


class SettingsChangesDialog(QtWidgets.QDialog):
    """ Offers the settings changes of an update, each with why, to apply or not """

    def __init__(self, offered, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("AutoSplit64++")
        self._offered = offered

        self.changes = Changes(offered)
        self.changes.applied.connect(self.accept)
        self.changes.kept.connect(self.reject)
        self.view = qml_view(self, "SettingsChangesDialog", changes=self.changes)
        root = self.view.rootObject()
        self.setFixedSize(int(root.property("implicitWidth")), int(root.property("implicitHeight")))

    def accepted_steps(self):
        if self.result() != QtWidgets.QDialog.DialogCode.Accepted:
            return []
        return [step for step, checked in zip(self._offered, self.changes.checked) if checked]


def choose(offered):
    """ For config.load_config: asks which of the offered settings changes to apply """
    dialog = SettingsChangesDialog(offered)
    dialog.exec()
    return dialog.accepted_steps()
