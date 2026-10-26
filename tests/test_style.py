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
    width: 400; height: 300
    Column {
        Button { objectName: "button"; text: "Button" }
        Button { objectName: "highlighted"; text: "Highlighted"; highlighted: true }
        Button { objectName: "flat"; text: "Flat"; flat: true }
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


if __name__ == "__main__":
    unittest.main()
