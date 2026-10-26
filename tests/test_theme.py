import os
import unittest
from unittest import mock

from PyQt6 import QtCore, QtGui

from autosplit64.gui import theme
from tests.qt import qapp

Role = QtGui.QPalette.ColorRole


class ThemeTest(unittest.TestCase):
    def setUp(self):
        palette = qapp.palette()
        self.addCleanup(qapp.setPalette, palette)

    def window_color(self):
        return qapp.palette().color(Role.Window).getRgb()[:3]

    def test_current(self):
        theme.apply("nord")
        self.assertEqual(theme.current(), "nord")

    def test_default_theme_is_the_original_palette(self):
        theme.apply(theme.DEFAULT)
        self.assertEqual(self.window_color(), (60, 63, 65))
        self.assertEqual(qapp.palette().color(Role.Highlight).getRgb()[:3], (75, 110, 175))

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

    def test_own_themes_come_after_the_default(self):
        self.assertEqual(theme.themes()[:3], [theme.DEFAULT, "as64_dark", "as64_light"])
        self.assertEqual(theme.display_name("as64_dark"), "AS64++ Dark")
        self.assertEqual(theme.display_name("as64_light"), "AS64++ Light")

    def test_own_themes_colors(self):
        for name, window, highlight in [("as64_dark", (25, 27, 32), (245, 184, 61)),
                                        ("as64_light", (255, 255, 255), (47, 97, 204))]:
            with self.subTest(name):
                theme.apply(name)
                self.assertEqual(theme.current(), name)
                self.assertEqual(self.window_color(), window)
                self.assertEqual(qapp.palette().color(Role.Highlight).getRgb()[:3], highlight)

    def test_own_themes_are_readable(self):
        # WCAG AA for normal text
        def luminance(color):
            channels = [c / 255 for c in color.getRgb()[:3]]
            r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        def contrast(a, b):
            a, b = sorted([luminance(a), luminance(b)], reverse=True)
            return (a + 0.05) / (b + 0.05)

        for name in ["as64_dark", "as64_light"]:
            theme.apply(name)
            palette = qapp.palette()
            for text, ground in [(Role.Text, Role.Window), (Role.Text, Role.Base), (Role.HighlightedText, Role.Highlight),
                                 (Role.PlaceholderText, Role.Base), (Role.ToolTipText, Role.ToolTipBase)]:
                with self.subTest(name=name, text=text.name, ground=ground.name):
                    self.assertGreaterEqual(contrast(palette.color(text), palette.color(ground)), 4.5)


class StyleTest(unittest.TestCase):
    def test_style(self):
        with mock.patch.dict(os.environ):
            theme.use_style("Fusion")
            self.assertEqual(os.environ["QT_QUICK_CONTROLS_STYLE"], "Fusion")

    def test_own_style_is_found_in_its_directory(self):
        with mock.patch.dict(os.environ):
            theme.use_style("AutoSplit64")
            self.assertEqual(os.environ["QT_QUICK_CONTROLS_STYLE"], "AutoSplit64")
            self.assertIn(str(theme.STYLES_DIR), os.environ["QML2_IMPORT_PATH"].split(os.pathsep))
            self.assertTrue((theme.STYLES_DIR / "AutoSplit64" / "qmldir").is_file())

    def test_the_import_path_keeps_the_ones_it_had(self):
        with mock.patch.dict(os.environ, {"QML2_IMPORT_PATH": "/elsewhere"}):
            theme.use_style("Fusion")
            theme.use_style("Fusion")
            self.assertEqual(os.environ["QML2_IMPORT_PATH"].split(os.pathsep), ["/elsewhere", str(theme.STYLES_DIR)])

    def test_unknown_style_is_the_default(self):
        with mock.patch.dict(os.environ):
            theme.use_style("Removed")
            self.assertEqual(os.environ["QT_QUICK_CONTROLS_STYLE"], "AutoSplit64")

    def test_other_platforms_style_is_the_default(self):
        # e.g. settings copied from a Mac to Windows
        with mock.patch.dict(os.environ), mock.patch.object(theme.sys, "platform", "win32"):
            theme.use_style("macOS")
            self.assertEqual(os.environ["QT_QUICK_CONTROLS_STYLE"], "AutoSplit64")

    def test_styles_of_each_platform(self):
        for platform, own in [("darwin", ["macOS"]), ("win32", ["Windows", "FluentWinUI3"]), ("linux", [])]:
            with self.subTest(platform), mock.patch.object(theme.sys, "platform", platform):
                self.assertEqual(theme.styles(), ["AutoSplit64", "Material", "Fusion", "Universal"] + own)


class StatusColorTest(unittest.TestCase):
    def setUp(self):
        palette = qapp.palette()
        self.addCleanup(qapp.setPalette, palette)

    def test_themes_status_colors(self):
        import qt_themes
        theme.apply("dracula")
        self.assertEqual(theme.status_color("green"), qt_themes.get_themes()["dracula"].green)
        theme.apply("as64_dark")
        self.assertEqual(theme.status_color("green").getRgb()[:3], (76, 175, 80))
        theme.apply(theme.DEFAULT)
        self.assertEqual(theme.status_color("green").getRgb()[:3], (76, 175, 80))
        self.assertEqual(theme.status_color("red").getRgb()[:3], (244, 67, 54))


class ThemedWidgetsTest(unittest.TestCase):
    """ The UI's colors come from the theme, also after switching to another one """

    def setUp(self):
        from unittest import mock
        from autosplit64.gui.app import App
        from tests.qt import close_window
        palette = qapp.palette()
        self.addCleanup(qapp.setPalette, palette)
        theme.apply("dracula")
        with mock.patch("autosplit64.gui.updates.Updates.check"):
            self.window = App()
        self.addCleanup(close_window, self.window)
        self.window.main.update(splits=[{"title": title, "icon": ""} for title in ("A", "B", "C")], current=0)
        # Switched after the window was made
        theme.apply("github_light")
        qapp.processEvents()
        self.palette = qapp.palette()

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
        self.assertEqual(self.pixel(panel.x() + 2, panel.y() + 2), self.color(Role.Window))

    def row(self, index):
        """ The scene's x and y of a split's row, and its height """
        from tests.qt import qml
        splits = qml(self.window.view, "splitList")
        origin = self.item("splitList")
        height = splits.property("rowHeight")
        return origin.x(), origin.y() + index * height, height, splits.property("width")

    def test_split_list(self):
        # The current row is raised, the others are the theme's background. Always the Active group's colors: during
        # a run, the game or LiveSplit has focus, not AutoSplit64++.
        raised, second, third = [self.pixel(self.row(i)[0] + self.row(i)[3] - 12, self.row(i)[1] + self.row(i)[2] / 2)
                                 for i in range(3)]
        self.assertEqual(raised, self.color(Role.Mid))
        self.assertEqual(second, self.color(Role.Base))
        self.assertEqual(third, self.color(Role.Base))

    def test_divider_between_the_splits_and_the_rest_is_the_themes_border(self):
        from tests.qt import qml
        divider = qml(self.window.view, "divider")
        origin = divider.mapToScene(QtCore.QPointF(0, 0))
        self.assertEqual(divider.property("width"), 1)
        self.assertEqual(self.pixel(origin.x() + 0.5, origin.y() + divider.property("height") / 2), self.color(Role.Dark))

    def test_menu_button_and_version_follow_the_text_color(self):
        muted = theme.muted(self.palette).getRgb()[:3]
        button = self.item("menuButton")
        # The middle of its middle line, at its center
        self.assertEqual(self.pixel(button.x() + 16, button.y() + 16), muted)
        self.assertEqual(self.window.main.values["muted"], theme.muted(self.palette).name())

    def test_update_dot_is_the_themes_green(self):
        self.window.update_badge.show_update("9.9.9")
        theme.apply("dracula")
        qapp.processEvents()
        self.assertEqual(self.window.main.values["green"], theme.status_color("green").name())
        self.assertTrue(self.window.main.values["update"])


if __name__ == "__main__":
    unittest.main()
