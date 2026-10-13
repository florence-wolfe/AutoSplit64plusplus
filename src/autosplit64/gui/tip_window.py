from PyQt6 import QtCore, QtGui, QtQuick

from .qml_view import QML_DIR

# Between a tooltip and what it's about
GAP = 8


class TipWindow(QtCore.QObject):
    """
    A tooltip that's a window of its own, to the left of what it's about, or to its right where the screen has no
    room. Unlike a QML ToolTip, which stays inside its window, it's also beside a menu that's a window, see
    MainWindow.qml, and it doesn't close that menu like a popup window would.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QtQuick.QQuickView()
        self.view.setFlags(QtCore.Qt.WindowType.ToolTip | QtCore.Qt.WindowType.FramelessWindowHint)
        # For its rounded corners
        self.view.setColor(QtGui.QColor(0, 0, 0, 0))
        self.view.setSource(QtCore.QUrl.fromLocalFile(str(QML_DIR / "TipWindow.qml")))
        if self.view.errors():
            raise RuntimeError("\n".join(error.toString() for error in self.view.errors()))

    @QtCore.pyqtSlot(str, int, int, int, int)
    def show(self, text, x, y, width, height):
        """ Shows text beside the screen's rectangle x, y, width, height """
        root = self.view.rootObject()
        root.setProperty("text", text)
        tip_width, tip_height = int(root.property("implicitWidth")), int(root.property("implicitHeight"))
        screen = QtGui.QGuiApplication.screenAt(QtCore.QPoint(x, y)) or QtGui.QGuiApplication.primaryScreen()
        left = x - GAP - tip_width
        if left < screen.availableGeometry().left():
            left = x + width + GAP
        self.view.setGeometry(left, y + (height - tip_height) // 2, tip_width, tip_height)
        self.view.show()

    @QtCore.pyqtSlot()
    def hide(self):
        self.view.hide()
