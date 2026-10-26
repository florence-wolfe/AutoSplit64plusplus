import tempfile
import unittest
from pathlib import Path

from PyQt6 import QtGui, QtWidgets

from autosplit64.gui import theme
from autosplit64.gui.qml_view import QML_DIR, qml_view
from tests.qt import qapp, run_queued

Role = QtGui.QPalette.ColorRole

# The tokens as the other QML files get them, from the directory they're in
PROBE = """
import QtQuick
import "%s" as UI

Item {
    property color ground: UI.Tokens.ground
    property color panel: UI.Tokens.panel
    property color raised: UI.Tokens.raised
    property color line: UI.Tokens.line
    property color text: UI.Tokens.text
    property color muted: UI.Tokens.muted
    property color accent: UI.Tokens.accent
    property color accentText: UI.Tokens.accentText
    property int radiusCard: UI.Tokens.radiusCard
}
"""


class TokensTest(unittest.TestCase):
    def setUp(self):
        palette = qapp.palette()
        self.addCleanup(qapp.setPalette, palette)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        (Path(directory.name) / "Probe.qml").write_text(PROBE % QML_DIR.as_uri())
        self.window = QtWidgets.QWidget()
        self.addCleanup(self.window.deleteLater)
        self.view = qml_view(self.window, f"{directory.name}/Probe")

    def colors(self):
        root = self.view.rootObject()
        return {name: root.property(name).getRgb()[:3] for name in
                ["ground", "panel", "raised", "line", "text", "muted", "accent", "accentText"]}

    def test_colors_are_the_themes_palette_roles(self):
        for name in ["as64_dark", "as64_light"]:
            with self.subTest(name):
                theme.apply(name)
                run_queued()
                palette = qapp.palette()
                colors = self.colors()
                self.assertEqual(colors["ground"], palette.color(Role.Base).getRgb()[:3])
                self.assertEqual(colors["panel"], palette.color(Role.Window).getRgb()[:3])
                self.assertEqual(colors["raised"], palette.color(Role.Mid).getRgb()[:3])
                self.assertEqual(colors["line"], palette.color(Role.Dark).getRgb()[:3])
                self.assertEqual(colors["text"], palette.color(Role.Text).getRgb()[:3])
                self.assertEqual(colors["accent"], palette.color(Role.Highlight).getRgb()[:3])
                self.assertEqual(colors["accentText"], palette.color(Role.HighlightedText).getRgb()[:3])
                self.assertEqual(colors["muted"], theme.muted(palette).getRgb()[:3])

    def test_colors_follow_a_theme_chosen_later(self):
        theme.apply("as64_dark")
        run_queued()
        dark = self.colors()
        theme.apply("as64_light")
        run_queued()
        self.assertNotEqual(self.colors()["panel"], dark["panel"])

    def test_sizes(self):
        self.assertEqual(self.view.rootObject().property("radiusCard"), 12)


class FontTest(unittest.TestCase):
    def test_the_bundled_font_is_the_tokens_family(self):
        from PyQt6 import QtGui
        from autosplit64.gui.constants import FONT_PATH
        families = QtGui.QFontDatabase.applicationFontFamilies(QtGui.QFontDatabase.addApplicationFont(FONT_PATH))
        self.assertIn("Inter Variable", families)
