from PyQt6 import QtWidgets


class SettingsChangesDialog(QtWidgets.QDialog):
    """ Offers the settings changes of an update, each with why, to apply or not """

    def __init__(self, offered, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("AutoSplit64++")
        self._offered = offered

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("This version of AutoSplit64++ changes some settings:", parent=self))
        self.checkboxes = []
        for step in offered:
            checkbox = QtWidgets.QCheckBox(f"{step['name']}: {step['from']} → {step['to']}", parent=self)
            checkbox.setChecked(True)
            reason = QtWidgets.QLabel(step["reason"], parent=self)
            reason.setWordWrap(True)
            reason.setContentsMargins(22, 0, 0, 6)
            layout.addWidget(checkbox)
            layout.addWidget(reason)
            self.checkboxes.append(checkbox)

        buttons = QtWidgets.QDialogButtonBox(parent=self)
        buttons.addButton("Keep My Settings", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        buttons.addButton("Apply", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setFixedWidth(420)

    def accepted_steps(self):
        if self.result() != QtWidgets.QDialog.DialogCode.Accepted:
            return []
        return [step for step, checkbox in zip(self._offered, self.checkboxes) if checkbox.isChecked()]


def choose(offered):
    """ For config.load_config: asks which of the offered settings changes to apply """
    dialog = SettingsChangesDialog(offered)
    dialog.exec()
    return dialog.accepted_steps()
