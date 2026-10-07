import sys
import unittest
from unittest import mock

import numpy as np
from PyQt6 import QtWidgets

from autosplit64.core import config

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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

        self.assertFalse(editor.permission_panel.isHidden())
        # Listing the windows asks ScreenCaptureKit, which shows the prompt too
        window.get_visible_processes.assert_not_called()
        window.request_permission.assert_not_called()

    def test_with_the_permission(self):
        editor, window = self.editor(granted=True)

        self.assertTrue(editor.permission_panel.isHidden())
        window.get_visible_processes.assert_called()


class GameRegionTest(CaptureEditorTest):
    def test_shows_the_capture(self):
        frame = np.full((300, 400, 3), 90, np.uint8)
        editor, _ = self.editor(frame=frame)
        self.assertEqual((editor.preview_pixmap.width(), editor.preview_pixmap.height()), (400, 300))
        self.assertEqual(editor.preview_pixmap.toImage().pixelColor(5, 5).red(), 90)

    def test_shows_black_without_a_capture(self):
        editor, _ = self.editor(frame=None)
        self.assertEqual((editor.preview_pixmap.width(), editor.preview_pixmap.height()), (640, 480))
        self.assertEqual(editor.preview_pixmap.toImage().pixelColor(5, 5).red(), 0)

    def test_shows_the_saved_region(self):
        editor, _ = self.editor()
        self.assertEqual(editor.game_region_panel.get_data(), [10, 20, 300, 200])

    def test_typed_region_moves_the_selector(self):
        editor, _ = self.editor()
        editor.game_region_panel.update_text("30", "40", "320", "240")
        editor.game_region_panel.xoffset_le.editingFinished.emit()
        self.assertEqual([round(v) for v in editor.game_region_selector.get_view_space_rect()], [30, 40, 320, 240])

    def test_apply_saves_the_capture_settings(self):
        editor, _ = self.editor()
        editor.game_region_panel.update_text("30", "40", "320", "240")
        editor.vc_fix_cb.setChecked(True)
        editor.apply_clicked()
        game = self.settings["game"]
        self.assertEqual((game["game_region"], game["process_name"], game["capture_source"], game["capture_size"],
                          game["vc_fix"], game["use_obs"]),
                         ([30, 40, 320, 240], "Emulator", "window", [640, 480], True, False))
        config.save_config.assert_called_once()

    def test_auto_detect_finds_the_game_inside_black_borders(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[40:440, 60:580] = 200
        editor, _ = self.editor(frame=frame)
        editor.auto_detect_region()
        self.assertEqual(editor.game_region_panel.get_data(), [62, 42, 516, 396])

    def test_auto_detect_ignores_amarectvs_top_bar(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[0:60, :] = 200
        frame[100:400, 100:500] = 200
        editor, _ = self.editor(frame=frame, process="AmaRecTV.exe")
        editor.auto_detect_region()
        self.assertEqual(editor.game_region_panel.get_data(), [102, 102, 396, 296])


if __name__ == "__main__":
    unittest.main()
