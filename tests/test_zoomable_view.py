import unittest

from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.gui.graphics import RectangleSelector, ZoomableGraphicsView

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ZoomableGraphicsViewTest(unittest.TestCase):
    def setUp(self):
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.addRect(0, 0, 1920, 1080)
        self.view = ZoomableGraphicsView(self.scene)
        self.view.resize(400, 300)
        self.addCleanup(self.view.deleteLater)

    def wheel(self, modifiers):
        center = QtCore.QPointF(200, 150)
        event = QtGui.QWheelEvent(center, self.view.mapToGlobal(center), QtCore.QPoint(), QtCore.QPoint(0, 120),
                                  QtCore.Qt.MouseButton.NoButton, modifiers, QtCore.Qt.ScrollPhase.NoScrollPhase, False)
        QtWidgets.QApplication.sendEvent(self.view.viewport(), event)

    def test_zoom_in_and_out(self):
        self.view.zoom_in()
        self.assertGreater(self.view.zoom(), 1)
        self.view.zoom_out()
        self.assertAlmostEqual(self.view.zoom(), 1)

    def test_zoom_is_limited(self):
        for _ in range(100):
            self.view.zoom_out()
        self.assertAlmostEqual(self.view.zoom(), ZoomableGraphicsView.MIN_ZOOM)
        for _ in range(100):
            self.view.zoom_in()
        self.assertAlmostEqual(self.view.zoom(), ZoomableGraphicsView.MAX_ZOOM)

    def test_fit_shows_the_whole_rect(self):
        self.view.fit(QtCore.QRectF(0, 0, 1920, 1080))
        shown = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        self.assertTrue(shown.contains(QtCore.QRectF(0, 0, 1920, 1080)))
        self.assertLess(self.view.zoom(), 1)

    def test_reports_the_zoom(self):
        zooms = []
        self.view.zoom_changed.connect(zooms.append)
        self.view.zoom_in()
        self.assertEqual(zooms, [self.view.zoom()])

    def test_ctrl_scroll_zooms(self):
        self.wheel(QtCore.Qt.KeyboardModifier.ControlModifier)
        self.assertGreater(self.view.zoom(), 1)

    def test_scroll_without_ctrl_doesnt_zoom(self):
        self.wheel(QtCore.Qt.KeyboardModifier.NoModifier)
        self.assertEqual(self.view.zoom(), 1)

    def test_zoom_doesnt_change_the_region(self):
        selector = RectangleSelector(0, 0, 50, 50)
        self.scene.addItem(selector)
        selector.setPos(100, 200)
        before = selector.get_view_space_rect()
        self.view.zoom_in()
        self.view.fit(QtCore.QRectF(0, 0, 1920, 1080))
        self.assertEqual(selector.get_view_space_rect(), before)


if __name__ == "__main__":
    unittest.main()
