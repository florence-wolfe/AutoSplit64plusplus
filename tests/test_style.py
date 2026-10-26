"""
AutoSplit64++'s Qt Quick Controls style. Qt takes the style when the first QML window opens, and the tests' windows
are Material's, so each check runs in a process of its own with the style.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent

# A QML window with the controls, which the script below reads the colors of
PROBE = """
import QtQuick
import QtQuick.Controls

Item {
    id: root
    width: 400; height: 300
    // Which QML reads, as Python can't read a background's border
    property var borders: ({button: button.background.border.width, highlighted: highlighted.background.border.width,
                            flat: flat.background.border.width})
    Column {
        Button { id: button; objectName: "button"; text: "Button" }
        Button { id: highlighted; objectName: "highlighted"; text: "Highlighted"; highlighted: true }
        Button { id: flat; objectName: "flat"; text: "Flat"; flat: true }
        Button { objectName: "plain"; text: "Plain" }
        Switch { objectName: "switchOn"; checked: true }
        Switch { objectName: "switchOff" }
        CheckBox { objectName: "checked"; checked: true }
        CheckBox { objectName: "unchecked" }
        Label { objectName: "label"; text: "Label" }
        TextField { objectName: "field"; text: "Field" }
        ComboBox { objectName: "combo"; model: ["A", "B"] }
        SpinBox { objectName: "spin"; from: 0; to: 10; value: 3 }
        ItemDelegate { objectName: "row"; text: "Row" }
        ItemDelegate { objectName: "chosen"; text: "Chosen"; highlighted: true }
    }
}
"""

SCRIPT = """
import json, sys, tempfile
from pathlib import Path
from PyQt6 import QtGui, QtWidgets
from tests.qt import qapp, qml, run_queued
from autosplit64.gui import theme
theme.use_style("AutoSplit64")
theme.apply(sys.argv[1])
from autosplit64.gui.qml_view import qml_view
directory = tempfile.TemporaryDirectory()
(Path(directory.name) / "Probe.qml").write_text(sys.stdin.read())
window = QtWidgets.QWidget()
view = qml_view(window, f"{directory.name}/Probe")
window.show()
run_queued()
Role = QtGui.QPalette.ColorRole
palette = qapp.palette()

def rgb(color):
    return list(color.getRgb()[:3])

out = {
    "palette": {name: rgb(palette.color(role)) for name, role in
                [("raised", Role.Mid), ("accent", Role.Highlight), ("accentText", Role.HighlightedText), ("text", Role.Text),
                 ("ground", Role.Base), ("line", Role.Dark)]},
    "button": rgb(qml(view, "button").property("background").property("color")),
    "highlighted": rgb(qml(view, "highlighted").property("background").property("color")),
    "flat": qml(view, "flat").property("background").property("color").alpha(),
    "borders": view.rootObject().property("borders").toVariant(),
    "switchOn": rgb(qml(view, "switchOn").property("indicator").property("color")),
    "checked": rgb(qml(view, "checked").property("indicator").property("color")),
    "unchecked": qml(view, "unchecked").property("indicator").property("color").alpha(),
    "field": rgb(qml(view, "field").property("background").property("color")),
    "combo": rgb(qml(view, "combo").property("background").property("color")),
    "spin": rgb(qml(view, "spin").property("background").property("color")),
    "spinValue": qml(view, "spin").property("value"),
    "row": qml(view, "row").property("background").property("color").alpha(),
    "chosen": rgb(qml(view, "chosen").property("background").property("color")),
    "labelFont": qml(view, "label").property("font").family(),
    "buttonHeight": qml(view, "button").property("implicitHeight"),
}
print(json.dumps(out))
"""


def probe(theme_name):
    result = subprocess.run([sys.executable, "-c", SCRIPT, theme_name], input=PROBE, capture_output=True, text=True,
                            cwd=ROOT, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


class StyleTest(unittest.TestCase):
    def test_controls_are_drawn_in_the_themes_colors(self):
        for name in ["as64_dark", "as64_light"]:
            with self.subTest(name):
                out = probe(name)
                palette = out["palette"]
                # A raised button, an accent one with no fill when flat, a switch and a check box in the accent when on
                self.assertEqual(out["button"], palette["raised"])
                self.assertEqual(out["highlighted"], palette["accent"])
                self.assertEqual(out["flat"], 0)
                self.assertEqual(out["switchOn"], palette["accent"])
                self.assertEqual(out["checked"], palette["accent"])
                self.assertEqual(out["unchecked"], 0)

    def test_buttons_come_in_three_levels(self):
        # A raised one with a border, an accent one with none, and a flat one with no fill or border
        self.assertEqual(probe("as64_dark")["borders"], {"button": 1, "highlighted": 0, "flat": 0})

    def test_fields_are_on_the_ground_and_a_chosen_row_is_raised(self):
        for name in ["as64_dark", "as64_light"]:
            with self.subTest(name):
                out = probe(name)
                palette = out["palette"]
                for field in ("field", "combo", "spin"):
                    self.assertEqual(out[field], palette["ground"], field)
                self.assertEqual(out["chosen"], palette["raised"])
                self.assertEqual(out["row"], 0)
                self.assertEqual(out["spinValue"], 3)

    def test_text_is_in_the_bundled_font_and_buttons_are_compact(self):
        out = probe("as64_dark")
        self.assertEqual(out["labelFont"], "Inter Variable")
        self.assertEqual(out["buttonHeight"], 32)


CAPTURE_SCRIPT = """
import json, sys
from PyQt6 import QtGui
from tests.qt import qapp, qml, run_queued
from autosplit64.gui import theme
theme.use_style("AutoSplit64")
theme.apply("as64_dark")
from tests.test_capture_editor import CaptureEditorTest
test = CaptureEditorTest("editor")
editor, window = test.editor()
run_queued()
buttons = {name: qml(editor.view, name) for name in ("zoomOut", "fit", "zoomIn")}
print(json.dumps({name: {"text": button.property("text"), "truncated": button.property("contentItem").property("truncated"),
                         "flat": button.property("flat")} for name, button in buttons.items()}))
"""


@unittest.skipUnless(sys.platform == "darwin", "macOS capture sources")
class CaptureEditorButtonsTest(unittest.TestCase):
    def test_zoom_buttons_show_their_whole_text_and_are_buttons(self):
        result = subprocess.run([sys.executable, "-c", CAPTURE_SCRIPT], capture_output=True, text=True, cwd=ROOT,
                                timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout.strip().splitlines()[-1])
        for name, text in [("zoomOut", "−"), ("fit", "Fit"), ("zoomIn", "+")]:
            with self.subTest(name):
                self.assertEqual(out[name]["text"], text)
                self.assertFalse(out[name]["truncated"])
                # Secondary: not flat
                self.assertFalse(out[name]["flat"])


if __name__ == "__main__":
    unittest.main()
