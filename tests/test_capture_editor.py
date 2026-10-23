import sys
import unittest
from unittest import mock

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtTest import QTest

from autosplit64.core import config
from tests.qt import qml, wait_until


@unittest.skipUnless(sys.platform == "darwin", "macOS capture sources")
class CaptureEditorTest(unittest.TestCase):
    """ The editor capturing an emulator window, with a stand-in for the window capture """

    def editor(self, granted=True, frame=None, process="Emulator"):
        from autosplit64.gui.dialogs import capture_editor_dialog
        window = capture_editor_dialog.capture_window
        self.settings = {"game": {"capture_source": "window", "game_region": [10, 20, 300, 200], "process_name": process}}
        patches = [mock.patch.object(config, "_config", self.settings),
                   mock.patch.object(config, "save_config"),
                   mock.patch.object(window, "has_permission_quietly", mock.Mock(return_value=granted)),
                   mock.patch.object(window, "has_permission", mock.Mock(side_effect=AssertionError("would show the prompt")),
                                     create=True),
                   mock.patch.object(window, "get_visible_processes",
                                     mock.Mock(return_value=[(mock.Mock(**{"name.return_value": process}), 7)])),
                   mock.patch.object(window, "capture", mock.Mock(return_value=frame)),
                   mock.patch.object(window, "get_capture_size", mock.Mock(return_value=[640, 480])),
                   mock.patch.object(window, "request_permission")]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        editor = capture_editor_dialog.CaptureEditor()
        self.addCleanup(editor.deleteLater)
        editor.show()
        self.addCleanup(editor.close)
        return editor, window


class ScreenRecordingPermissionTest(CaptureEditorTest):
    """ Waiting for the Screen Recording permission never shows macOS's prompt, only Allow Screen Recording does """

    def test_waiting_for_the_permission(self):
        editor, window = self.editor(granted=False)
        for _ in range(3):
            editor._permission_timer.timeout.emit()

        self.assertTrue(qml(editor.view, "permission").property("visible"))
        # Listing the windows asks ScreenCaptureKit, which shows the prompt too
        window.get_visible_processes.assert_not_called()
        window.request_permission.assert_not_called()

    def test_with_the_permission(self):
        editor, window = self.editor(granted=True)

        self.assertFalse(qml(editor.view, "permission").property("visible"))
        window.get_visible_processes.assert_called()


class GameRegionTest(CaptureEditorTest):
    def test_shows_the_capture(self):
        frame = np.full((300, 400, 3), 90, np.uint8)
        editor, _ = self.editor(frame=frame)
        self.assertEqual((editor.preview.width(), editor.preview.height()), (400, 300))
        self.assertEqual(editor.preview.pixelColor(5, 5).red(), 90)

    def test_shows_black_without_a_capture(self):
        editor, _ = self.editor(frame=None)
        self.assertEqual((editor.preview.width(), editor.preview.height()), (640, 480))
        self.assertEqual(editor.preview.pixelColor(5, 5).red(), 0)

    def test_shows_the_saved_region(self):
        editor, _ = self.editor()
        self.assertEqual(editor.capture.values["region"], [10, 20, 300, 200])
        self.assertEqual([qml(editor.view, f"region{i}").property("text") for i in range(4)], ["10", "20", "300", "200"])

    def test_typed_region_moves_the_selector(self):
        editor, _ = self.editor()
        for i, value in enumerate(("30", "40", "320", "240")):
            field = qml(editor.view, f"region{i}")
            field.setProperty("text", value)
            QtCore.QMetaObject.invokeMethod(field, "editingFinished")
        selector = qml(editor.view, "selector")
        self.assertEqual([selector.x(), selector.y(), selector.width(), selector.height()], [30, 40, 320, 240])

    def test_apply_saves_the_capture_settings(self):
        editor, _ = self.editor()
        editor.capture.set_region(30, 40, 320, 240)
        editor.capture.choose("vcFix", True)
        editor.apply_clicked()
        game = self.settings["game"]
        self.assertEqual((game["game_region"], game["process_name"], game["capture_source"], game["capture_size"],
                          game["vc_fix"], game["use_obs"]),
                         ([30, 40, 320, 240], "Emulator", "window", [640, 480], True, False))
        config.save_config.assert_called_once()

    def test_cancel_keeps_the_settings_as_they_were(self):
        editor, _ = self.editor()
        editor.capture.set_region(30, 40, 320, 240)
        config.set_key("game", "vc_fix", True)
        editor.cancel_clicked()
        self.assertEqual(config.get("game", "game_region"), [10, 20, 300, 200])
        self.assertIsNone(config.get("game").get("vc_fix"))

    def test_auto_detect_finds_the_game_inside_black_borders(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[40:440, 60:580] = 200
        editor, _ = self.editor(frame=frame)
        editor.auto_detect_region()
        self.assertEqual(editor.capture.values["region"], [62, 42, 516, 396])

    def test_auto_detect_ignores_amarectvs_top_bar(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[0:60, :] = 200
        frame[100:400, 100:500] = 200
        editor, _ = self.editor(frame=frame, process="AmaRecTV.exe")
        editor.auto_detect_region()
        self.assertEqual(editor.capture.values["region"], [102, 102, 396, 296])


class PreviewTest(unittest.TestCase):
    """ Zooming and moving the game region over the capture, which is black 640×480 without one """

    def setUp(self):
        from autosplit64.gui.dialogs import capture_editor_dialog
        for patcher in [mock.patch.object(config, "_config", {"game": {"game_region": [100, 200, 50, 50]}}),
                        mock.patch.object(config, "save_config")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.editor = capture_editor_dialog.CaptureEditor()
        self.addCleanup(self.editor.deleteLater)
        self.editor.capture.set_region(100, 200, 50, 50)
        self.editor.resize(1100, 640)
        # On screen without starting a capture, which show() does
        QtWidgets.QDialog.show(self.editor)
        self.addCleanup(self.editor.hide)
        self.preview = qml(self.editor.view, "preview")
        wait_until(lambda: self.preview.width() > 0)

    def click(self, name, times=1):
        for _ in range(times):
            QtCore.QMetaObject.invokeMethod(qml(self.editor.view, name), "clicked")

    def zoom(self):
        return self.preview.property("zoom")

    def wheel(self, modifiers):
        center = self.preview.mapToScene(QtCore.QPointF(self.preview.width() / 2, self.preview.height() / 2))
        event = QtGui.QWheelEvent(center, self.editor.view.mapToGlobal(center), QtCore.QPoint(), QtCore.QPoint(0, 120),
                                  QtCore.Qt.MouseButton.NoButton, modifiers, QtCore.Qt.ScrollPhase.NoScrollPhase, False)
        QtWidgets.QApplication.sendEvent(self.editor.view, event)

    def test_zoom_in_and_out(self):
        self.click("zoomIn")
        self.assertAlmostEqual(self.zoom(), 1.25)
        self.click("zoomOut")
        self.assertAlmostEqual(self.zoom(), 1)

    def test_zoom_is_limited(self):
        self.click("zoomOut", 100)
        self.assertAlmostEqual(self.zoom(), 0.1)
        self.click("zoomIn", 100)
        self.assertAlmostEqual(self.zoom(), 10)

    def test_fit_shows_the_whole_capture(self):
        self.click("zoomIn", 3)
        self.click("fit")
        self.assertLessEqual(640 * self.zoom(), self.preview.width() + 0.5)
        self.assertLessEqual(480 * self.zoom(), self.preview.height() + 0.5)
        self.assertTrue(abs(640 * self.zoom() - self.preview.width()) < 1 or abs(480 * self.zoom() - self.preview.height()) < 1)

    def test_shows_the_zoom(self):
        self.click("zoomIn")
        self.assertEqual(qml(self.editor.view, "zoom").property("text"), "125%")

    def test_ctrl_scroll_zooms(self):
        self.wheel(QtCore.Qt.KeyboardModifier.ControlModifier)
        self.assertGreater(self.zoom(), 1)

    def test_scroll_without_ctrl_doesnt_zoom(self):
        self.wheel(QtCore.Qt.KeyboardModifier.NoModifier)
        self.assertEqual(self.zoom(), 1)

    def test_zoom_doesnt_change_the_region(self):
        self.click("zoomIn", 2)
        self.click("fit")
        self.assertEqual(self.editor.capture.values["region"], [100, 200, 50, 50])

    def drag(self, item_name, x, y, dx, dy):
        """ Drag from x, y in the item by dx, dy pixels on screen """
        item = qml(self.editor.view, item_name)
        start = item.mapToScene(QtCore.QPointF(x, y)).toPoint()
        QTest.mousePress(self.editor.view, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, start)
        for step in range(1, 11):
            QTest.mouseMove(self.editor.view, start + QtCore.QPoint(dx * step // 10, dy * step // 10))
        QTest.mouseRelease(self.editor.view, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier,
                           start + QtCore.QPoint(dx, dy))

    def test_dragging_the_region_moves_it_in_the_captures_pixels(self):
        self.click("zoomIn", 3)
        zoom = self.zoom()
        # Back to the top left, where the region is
        self.preview.setProperty("contentX", 0)
        self.preview.setProperty("contentY", 0)
        self.drag("selector", 25, 25, 40, 20)
        x, y, width, height = self.editor.capture.values["region"]
        self.assertEqual((x, y, width, height), (100 + round(40 / zoom), 200 + round(20 / zoom), 50, 50))

    def test_dragging_a_corner_resizes_it(self):
        self.drag("selector", 50, 50, 30, 10)
        self.assertEqual(self.editor.capture.values["region"], [100, 200, 80, 60])


if __name__ == "__main__":
    unittest.main()
