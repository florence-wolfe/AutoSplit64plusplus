import os
import unittest
from unittest import mock

from PyQt6 import QtCore, QtGui, QtWidgets

from autosplit64.gui import theme

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
Role = QtGui.QPalette.ColorRole


class ThemeTest(unittest.TestCase):
    def setUp(self):
        palette = _app.palette()
        self.addCleanup(_app.setPalette, palette)

    def window_color(self):
        return _app.palette().color(Role.Window).getRgb()[:3]

    def test_current(self):
        theme.apply("nord")
        self.assertEqual(theme.current(), "nord")

    def test_default_theme_is_the_original_palette(self):
        theme.apply(theme.DEFAULT)
        self.assertEqual(self.window_color(), (60, 63, 65))
        self.assertEqual(_app.palette().color(Role.Highlight).getRgb()[:3], (75, 110, 175))

    def test_themes(self):
        names = theme.themes()
        self.assertEqual(names[0], theme.DEFAULT)
        self.assertIn("dracula", names)
        theme.apply("dracula")
        dracula = self.window_color()
        theme.apply("github_light")
        self.assertNotEqual(self.window_color(), dracula)

    def test_unknown_theme_is_the_default(self):
        theme.apply("removed_theme")
        self.assertEqual(self.window_color(), (60, 63, 65))

    def test_display_names(self):
        self.assertEqual(theme.display_name("github_dark"), "Github Dark")
        self.assertEqual(theme.display_name(theme.DEFAULT), "Default")


class StyleTest(unittest.TestCase):
    def test_style(self):
        with mock.patch.dict(os.environ):
            theme.use_style("Fusion")
            self.assertEqual(os.environ["QT_QUICK_CONTROLS_STYLE"], "Fusion")

    def test_unknown_style_is_the_default(self):
        with mock.patch.dict(os.environ):
            theme.use_style("Removed")
            self.assertEqual(os.environ["QT_QUICK_CONTROLS_STYLE"], "Material")

    def test_other_platforms_style_is_the_default(self):
        # e.g. settings copied from a Mac to Windows
        with mock.patch.dict(os.environ), mock.patch.object(theme.sys, "platform", "win32"):
            theme.use_style("macOS")
            self.assertEqual(os.environ["QT_QUICK_CONTROLS_STYLE"], "Material")

    def test_styles_of_each_platform(self):
        for platform, own in [("darwin", ["macOS"]), ("win32", ["Windows", "FluentWinUI3"]), ("linux", [])]:
            with self.subTest(platform), mock.patch.object(theme.sys, "platform", platform):
                self.assertEqual(theme.styles(), ["Material", "Fusion", "Universal"] + own)


class StatusColorTest(unittest.TestCase):
    def setUp(self):
        palette = _app.palette()
        self.addCleanup(_app.setPalette, palette)

    def test_themes_status_colors(self):
        import qt_themes
        theme.apply("dracula")
        self.assertEqual(theme.status_color("green"), qt_themes.get_themes()["dracula"].green)
        theme.apply(theme.DEFAULT)
        self.assertEqual(theme.status_color("green").getRgb()[:3], (76, 175, 80))
        self.assertEqual(theme.status_color("red").getRgb()[:3], (244, 67, 54))


class ThemedWidgetsTest(unittest.TestCase):
    """ The UI's colors come from the theme, also after switching to another one """

    def setUp(self):
        from unittest import mock
        from autosplit64.gui.app import App
        from tests.qt import close_window
        palette = _app.palette()
        self.addCleanup(_app.setPalette, palette)
        theme.apply("dracula")
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.window = App()
        self.addCleanup(close_window, self.window)
        self.window.main.update(splits=[{"title": title, "icon": ""} for title in ("A", "B", "C")], current=0)
        # Switched after the window was made
        theme.apply("github_light")
        _app.processEvents()
        self.palette = _app.palette()

    def pixel(self, x, y):
        """ The color at x, y in the main window's QML """
        image = self.window.view.grabWindow()
        ratio = image.devicePixelRatio()
        return image.pixelColor(int(x * ratio), int(y * ratio)).getRgb()[:3]

    def item(self, name):
        from tests.qt import qml
        item = qml(self.window.view, name)
        return item.mapToScene(QtCore.QPointF(0, 0))

    def color(self, role):
        return self.palette.color(role).getRgb()[:3]

    def test_main_window_background(self):
        panel = self.item("rightPanel")
        self.assertEqual(self.pixel(panel.x() + 2, panel.y() + 2), self.color(Role.Base))

    def test_current_split_is_the_themes_highlight_with_or_without_focus(self):
        # During a run, the game or LiveSplit has focus, not AutoSplit64++: always the Active group's
        highlight = self.palette.color(QtGui.QPalette.ColorGroup.Active, Role.Highlight).getRgb()[:3]
        self.assertEqual(self.pixel(2, 2), highlight)

    def test_split_list(self):
        second, third = self.pixel(2, 37 + 2), self.pixel(2, 2 * 37 + 2)
        self.assertNotEqual(second, third)
        # Both rows are shades of the theme's background
        for row in (second, third):
            self.assertLess(max(abs(a - b) for a, b in zip(row, self.color(Role.Base))), 60)

    def test_menu_button_and_version_follow_the_text_color(self):
        muted = theme.muted(self.palette).getRgb()[:3]
        button = self.item("menuButton")
        # The middle of its middle line, at its center
        self.assertEqual(self.pixel(button.x() + 16, button.y() + 16), muted)
        self.assertEqual(self.window.main.values["muted"], theme.muted(self.palette).name())

    def test_update_dot_is_the_themes_green(self):
        self.window.update_badge.show_update("9.9.9")
        theme.apply("dracula")
        _app.processEvents()
        self.assertEqual(self.window.main.values["green"], theme.status_color("green").name())
        self.assertTrue(self.window.main.values["update"])


if __name__ == "__main__":
    unittest.main()
