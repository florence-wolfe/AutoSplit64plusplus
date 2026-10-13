from PyQt6 import QtWidgets, QtGui


class HLine(QtWidgets.QFrame):
    """ A divider: a line a little darker than the background """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.HLine)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(0, self.height() // 2, self.width(), 1, self.palette().color(QtGui.QPalette.ColorRole.Window).darker(140))
