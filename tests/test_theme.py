import unittest

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
        self.window.split_list.clear()
        for title in ("A", "B", "C"):
            self.window.split_list.add_split(title, None)
        self.window.split_list.set_selected_index(0)
        # Switched after the window was made. Widgets get the palette once events are processed.
        theme.apply("github_light")
        _app.processEvents()
        self.palette = _app.palette()

    def pixel(self, widget, x, y):
        """ The color at x, y in the window, or in widget if it has no window """
        window = widget.window() if widget.parent() else widget
        point = widget.mapTo(window, QtCore.QPoint(x, y))
        image = window.grab().toImage()
        ratio = image.devicePixelRatio()
        return image.pixelColor(int(point.x() * ratio), int(point.y() * ratio)).getRgb()[:3]

    def color(self, role):
        return self.palette.color(role).getRgb()[:3]

    def test_main_window_background(self):
        self.assertEqual(self.pixel(self.window.right_panel, 2, 2), self.color(Role.Base))

    def split_list_pixel(self, group, x, y):
        """ A pixel of the split list, painted as when its window has focus or not: the Active or Inactive group """
        from unittest import mock
        rows = self.window.split_list
        palette = QtGui.QPalette(rows.palette())
        palette.setCurrentColorGroup(group)
        with mock.patch.object(rows, "palette", return_value=palette):
            return self.pixel(rows, x, y)

    def test_current_split_is_the_themes_highlight_with_or_without_focus(self):
        # During a run, the game or LiveSplit has focus, not AutoSplit64++
        highlight = self.palette.color(QtGui.QPalette.ColorGroup.Active, Role.Highlight).getRgb()[:3]
        for group in (QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorGroup.Inactive):
            with self.subTest(group):
                self.assertEqual(self.split_list_pixel(group, 2, 2), highlight)

    def test_split_list(self):
        rows = self.window.split_list
        second, third = self.pixel(rows, 2, 37 + 2), self.pixel(rows, 2, 2 * 37 + 2)
        self.assertNotEqual(second, third)
        # Both rows are shades of the theme's background
        for row in (second, third):
            self.assertLess(max(abs(a - b) for a, b in zip(row, self.color(Role.Base))), 60)

    def test_divider_line(self):
        from autosplit64.gui.widgets import HLine
        line = HLine()
        line.resize(50, 3)
        self.assertEqual(self.pixel(line, 25, 1), self.palette.color(Role.Window).darker(140).getRgb()[:3])

    def test_menu_button_and_version_follow_the_text_color(self):
        muted = theme.muted(self.palette).getRgb()[:3]
        self.assertEqual(self.pixel(self.window.menu_button, 9, 7), muted)
        self.assertIn(theme.muted(self.palette).name(), self.window.update_badge.text())

    def test_update_dot_is_the_themes_green(self):
        self.window.update_badge.show_update("9.9.9")
        theme.apply("dracula")
        _app.processEvents()
        self.assertIn(theme.status_color("green").name(), self.window.update_badge.text())


if __name__ == "__main__":
    unittest.main()
