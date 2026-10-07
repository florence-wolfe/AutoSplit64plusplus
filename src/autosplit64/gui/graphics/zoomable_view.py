from PyQt6 import QtCore, QtWidgets


class ZoomableGraphicsView(QtWidgets.QGraphicsView):
    """
    A view that zooms with zoom_in(), zoom_out() and fit(), Ctrl+scroll (Cmd+scroll on macOS)
    and pinching on a trackpad. Zooming only changes the view, never the scene's coordinates.
    """
    MIN_ZOOM = 0.1
    MAX_ZOOM = 10.0
    STEP = 1.25

    zoom_changed = QtCore.pyqtSignal(float)

    def __init__(self, *args):
        super().__init__(*args)
        # Zoom towards the mouse, or the view's center when the zoom buttons are used
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def zoom(self):
        return self.transform().m11()

    def set_zoom(self, zoom):
        zoom = min(max(zoom, self.MIN_ZOOM), self.MAX_ZOOM)
        self.scale(zoom / self.zoom(), zoom / self.zoom())
        self.zoom_changed.emit(self.zoom())

    def zoom_in(self):
        self.set_zoom(self.zoom() * self.STEP)

    def zoom_out(self):
        self.set_zoom(self.zoom() / self.STEP)

    def fit(self, rect):
        """ Zooms to show all of rect """
        self.fitInView(rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        self.set_zoom(self.zoom())

    def wheelEvent(self, event):
        if not event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            return super().wheelEvent(event)
        if event.angleDelta().y() > 0:
            self.zoom_in()
        elif event.angleDelta().y() < 0:
            self.zoom_out()

    def viewportEvent(self, event):
        if event.type() == QtCore.QEvent.Type.NativeGesture and \
                event.gestureType() == QtCore.Qt.NativeGestureType.ZoomNativeGesture:
            self.set_zoom(self.zoom() * (1 + event.value()))
            return True
        return super().viewportEvent(event)
