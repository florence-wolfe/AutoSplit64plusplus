from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.gui import theme


class MenuButton(QtWidgets.QAbstractButton):
    """ Hamburger button: three horizontal lines """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedSize(18, 14)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Menu")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        color = self.palette().color(QtGui.QPalette.ColorRole.Text) if self.underMouse() else theme.muted(self.palette())
        pen = QtGui.QPen(color, 2)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for y in (2, 7, 12):
            painter.drawLine(QtCore.QPointF(2, y), QtCore.QPointF(self.width() - 2, y))

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)
