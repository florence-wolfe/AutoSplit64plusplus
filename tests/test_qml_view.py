import tempfile
import unittest
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

from autosplit64.gui.qml_view import qml_view
from tests.qt import qml, wait_until

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# A button with a tooltip, at x
BUTTON = """
import QtQuick
import QtQuick.Controls.Material

Item {
    width: 400
    height: 200
    property var tip: button.ToolTip.toolTip
    Button { id: button; objectName: "button"; x: %d; y: 80; text: "Button"; ToolTip.text: "%s"; ToolTip.visible: true }
}
"""


class ToolTipTest(unittest.TestCase):
    def setUp(self):
        self.messages = []
        previous = QtCore.qInstallMessageHandler(lambda kind, context, message: self.messages.append(message))
        self.addCleanup(QtCore.qInstallMessageHandler, previous)

    def view(self, x, text="A tooltip"):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        (Path(directory.name) / "Button.qml").write_text(BUTTON % (x, text))
        window = QtWidgets.QWidget()
        self.addCleanup(window.deleteLater)
        window.resize(400, 200)
        # An absolute name is that file, instead of one in gui/qml
        view = qml_view(window, f"{directory.name}/Button")
        window.show()
        tip = view.rootObject().property("tip")
        wait_until(lambda: tip.property("opened"))
        self.assertTrue(tip.property("opened"))
        return tip, qml(view, "button")

    def test_left_of_what_its_about(self):
        tip, button = self.view(300)
        self.assertLess(tip.property("x") + tip.property("width"), 0)
        self.assertAlmostEqual(tip.property("y") + tip.property("height") / 2, button.property("height") / 2)

    def test_above_where_the_left_has_no_room(self):
        tip, button = self.view(10)
        self.assertLess(tip.property("y") + tip.property("height"), 0)

    def test_no_binding_loop(self):
        # Wider than the room on the left, which Qt narrows tooltips to
        for text in ("A tooltip", "A tooltip " * 20):
            with self.subTest(text):
                self.view(300, text)
                self.assertEqual([message for message in self.messages if "loop" in message], [])


if __name__ == "__main__":
    unittest.main()
