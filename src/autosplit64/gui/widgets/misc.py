from PyQt6 import QtCore, QtWidgets, QtGui

from autosplit64.gui.widgets import PictureButton
from autosplit64.gui import constants


class HLine(QtWidgets.QFrame):
    """ A divider: a line a little darker than the background """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(0, self.height() // 2, self.width(), 1, self.palette().color(QtGui.QPalette.ColorRole.Window).darker(140))


class StarCountDisplay(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.slash_lb = QtWidgets.QLabel("/")
        self.left_lb = QtWidgets.QLabel("-")
        self.right_lb = QtWidgets.QLabel("-")

        self.initialize()

    def initialize(self):
        # Configure Layout
        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        # Configure Widgets
        self.left_lb.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.right_lb.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        self.left_lb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.slash_lb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum)
        self.right_lb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)

        layout.addWidget(self.left_lb)
        layout.addWidget(self.slash_lb)
        layout.addWidget(self.right_lb)

    def setFont(self, font):
        self.left_lb.setFont(font)
        self.slash_lb.setFont(font)
        self.right_lb.setFont(font)

    @property
    def star_count(self):
        return int(self.left_lb.text())

    @star_count.setter
    def star_count(self, count):
        self.left_lb.setText(str(count))

    @property
    def split_star(self):
        return int(self.right_lb.text())

    @split_star.setter
    def split_star(self, split):
        if split != -1:
            self.right_lb.setText(str(split))
        else:
            self.right_lb.setText("-")


