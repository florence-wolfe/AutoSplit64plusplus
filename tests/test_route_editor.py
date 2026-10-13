import dataclasses
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PyQt6 import QtCore, QtWidgets

from autosplit64.core import config, route_loader
from autosplit64.gui.dialogs.route_editor_dialog import RouteEditor
from tests.qt import qml, wait_until

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

ROUTE = Path(__file__).parent.parent / "routes" / "16_lblj.as64"


class RouteEditorTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = str(self.dir / "route.as64")
        shutil.copy(ROUTE, self.path)
        self.saved = []
        for patcher in [mock.patch.object(config, "_config", {"route": {"path": self.path}}),
                        mock.patch.object(config, "save_config"),
                        mock.patch.object(route_loader, "save", lambda route, path: self.saved.append((route, path))),
                        mock.patch.object(RouteEditor, "display_error_message")]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.editor = RouteEditor()
        self.addCleanup(self.editor.deleteLater)

    def rows(self):
        """ Each split's title, star count, fadeout, fadein, X-Cam and type, as shown """
        return [[row[key] for key in ("title", "star_count", "fadeout", "fadein", "xcam", "split_type")]
                for row in self.editor.splits.rows]

    def editable(self, row):
        """ Whether the star count, fadeout, fadein and X-Cam can be edited """
        splits = self.editor.splits
        unused = splits.data(splits.index(row), QtCore.Qt.ItemDataRole.UserRole + splits.KEYS.index("unused"))
        return [key not in unused for key in ("star_count", "fadeout", "fadein", "xcam")]

    def details(self):
        values = self.editor.editor.values
        return tuple(values[key] for key in ("title", "category", "initialStar", "version", "timing"))

    def show(self):
        """ The table makes its rows once it's shown """
        self.editor.show()
        self.addCleanup(self.editor.close)

    def qml(self, name):
        """ Once the table shows the rows """
        wait_until(lambda: qml(self.editor.view, name) is not None)
        return qml(self.editor.view, name)

    def save(self):
        self.saved.clear()
        result = self.editor.save()
        return dataclasses.asdict(self.saved[0][0]) if self.saved else result

    def test_saving_keeps_the_route(self):
        self.editor.load_route()
        expected = dataclasses.asdict(route_loader.load(self.path))
        self.assertEqual(self.save(), expected)
        self.assertEqual(self.saved[0][1], self.path)

    def test_shows_the_route(self):
        self.editor.load_route()
        self.assertEqual(self.details(), ("16 LBLJ", "16 Star", "0", "US", "RTA"))
        self.assertEqual(self.rows()[:2], [["LBLJ", "0", "2", "0", "-", "Normal"], ["DW", "1", "2", "0", "-", "Normal"]])

    def test_the_window_shows_the_route(self):
        self.show()
        self.assertEqual([self.qml(name).property(prop) for name, prop in [
            ("title", "text"), ("category", "editText"), ("initialStar", "text"), ("version", "currentText"),
            ("timing", "currentText")]], ["16 LBLJ", "16 Star", "0", "US", "RTA"])
        self.assertEqual(qml(self.editor.view, "splits").property("count"), len(self.rows()))
        self.assertEqual((self.qml("stars1").property("text"), self.qml("type1").property("currentText")), ("1", "Normal"))

    def test_choosing_a_split_type_in_the_window(self):
        self.show()
        combo = self.qml("type0")
        combo.setProperty("currentIndex", RouteEditor.SPLIT_TYPES.index("Fade"))
        QtCore.QMetaObject.invokeMethod(combo, "activated", QtCore.Q_ARG(int, combo.property("currentIndex")))
        self.assertEqual(self.rows()[0], ["LBLJ", "-", "1", "0", "-", "Fade"])
        self.assertFalse(self.qml("stars0").property("enabled"))

    def test_split_type_sets_the_editable_columns(self):
        self.editor.load_route()
        expected = {"Normal": [True, True, True, False], "Fade": [False, True, True, False],
                    "Mips": [True, False, False, False], "Mips-X": [True, False, False, False],
                    "X-Cam": [True, True, True, True], "Final": [True, False, False, False]}
        for split_type, editable in expected.items():
            with self.subTest(split_type):
                self.editor.splits.set_type(0, split_type)
                self.assertEqual(self.editable(0), editable)

    def test_moving_and_removing_splits(self):
        self.editor.load_route()
        first, second = self.rows()[:2]
        self.editor.splits.select(0, "only")
        self.editor.moveCurrentRow(RouteEditor.DOWN)
        self.assertEqual(self.rows()[:2], [second, first])
        self.assertEqual(self.editor.splits.selected, {1})
        count = len(self.rows())
        self.editor.remove_clicked()
        self.assertEqual(len(self.rows()), count - 1)
        self.assertEqual(self.rows()[1], self.rows()[1])

    def test_selecting_several_splits(self):
        self.editor.load_route()
        self.editor.splits.select(1, "only")
        self.editor.splits.select(3, "range")
        self.editor.splits.select(2, "toggle")
        self.assertEqual(self.editor.splits.selected, {1, 3})
        names = [row[0] for row in self.rows()]
        self.editor.moveCurrentRow(RouteEditor.UP)
        self.assertEqual([row[0] for row in self.rows()][:4], [names[1], names[0], names[3], names[2]])
        self.assertEqual(self.editor.splits.selected, {0, 2})

    def test_inserted_split(self):
        self.editor.new()
        self.editor._insert_row(title="WF", star_count="1")
        self.assertEqual(self.rows(), [["WF", "1", "1", "0", "-", "Normal"]])

    def test_invalid_counts_are_errors(self):
        for column, split_type, message in [("star_count", "Normal", "Invalid Star Count - Row: 1"),
                                            ("fadeout", "Normal", "Invalid Fadeout - Row: 1"),
                                            ("fadein", "Normal", "Invalid Fadein - Row: 1"),
                                            ("xcam", "X-Cam", "Invalid XCam - Row: 1")]:
            with self.subTest(message):
                self.editor.load_route()
                self.editor.splits.set_type(0, split_type)
                self.editor.splits.set(0, column, "x")
                self.editor.display_error_message.reset_mock()
                self.assertEqual(self.save(), -1)
                self.editor.display_error_message.assert_called_once_with(message, "Route Error")

    def test_counts_a_split_type_doesnt_use_are_saved_as_none(self):
        self.editor.load_route()
        self.editor.splits.set_type(0, "Mips")
        split = self.save()["splits"][0]
        self.assertEqual((split["on_fadeout"], split["on_fadein"], split["on_xcam"]), (-1, -1, -1))

    def convert(self, names):
        lss = self.dir / "splits.lss"
        lss.write_text("<Run><Segments>" + "".join(f"<Segment><Name>{n}</Name></Segment>" for n in names)
                       + "</Segments></Run>")
        self.editor.convert_lss(str(lss))
        category, initial_star, version = self.details()[1:4]
        return (category, version, initial_star), self.rows()

    def test_converts_livesplit_splits(self):
        # What the conversion guessed when it was refactored, as a reference
        cases = [
            (["LBLJ", "WF 1", "-CCM 3", "Key 1 Dark World 8", "SSL 10", "Mips 12", "Fire Sea", "BLJs", "Bowser"],
             ("", "JP", "0"),
             [["LBLJ", "0", "2", "0", "-", "Normal"], ["WF 1", "1", "1", "0", "-", "Normal"],
              ["-CCM 3", "3", "1", "0", "-", "Normal"], ["Key 1 Dark World 8", "8", "2", "0", "-", "Normal"],
              ["SSL 10", "10", "1", "0", "-", "Normal"], ["Mips 12", "12", "-", "-", "-", "Mips"],
              ["Fire Sea", "12", "2", "0", "-", "Normal"], ["BLJs", "12", "4", "0", "-", "Normal"],
              ["Bowser", "12", "-", "-", "-", "Final"]]),
            (["BoB 5", "WF 12", "Key 1", "Mips 26", "BitFS 31", "/Upstairs 50", "69", "BitS"],
             ("70 Star", "US", "0"),
             [["BoB 5", "5", "1", "0", "-", "Normal"], ["WF 12", "12", "1", "0", "-", "Normal"],
              ["Key 1", "1", "2", "0", "-", "Normal"], ["Mips 26", "26", "-", "-", "-", "Mips"],
              ["BitFS 31", "31", "2", "0", "-", "Normal"], ["/Upstairs 50", "50", "4", "0", "-", "Normal"],
              ["69", "69", "1", "0", "-", "Normal"], ["BitS", "70", "-", "-", "-", "Final"]]),
            (["119", "Final"], ("120 Star", "JP", "0"),
             [["119", "119", "1", "0", "-", "Normal"], ["Final", "120", "-", "-", "-", "Final"]]),
            (["Fire Sea 12", "Bowser 16"], ("", "JP", "0"),
             [["Fire Sea 12", "12", "3", "0", "-", "Normal"], ["Bowser 16", "16", "-", "-", "-", "Final"]]),
            (["Start", "End"], ("", "JP", "0"),
             [["Start", "0", "1", "0", "-", "Normal"], ["End", "0", "-", "-", "-", "Final"]]),
        ]
        for names, header, rows in cases:
            with self.subTest(names[0]):
                self.editor = RouteEditor()
                self.addCleanup(self.editor.deleteLater)
                self.assertEqual(self.convert(names), (header, rows))


if __name__ == "__main__":
    unittest.main()
