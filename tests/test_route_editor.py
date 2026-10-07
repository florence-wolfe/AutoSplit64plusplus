import dataclasses
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PyQt6 import QtWidgets

from autosplit64.core import config, route_loader
from autosplit64.gui.dialogs.route_editor_dialog import RouteEditor

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
        table = self.editor.split_table
        return [[table.item(row, column).text() for column in range(1, 6)] + [table.cellWidget(row, 6).currentText()]
                for row in range(table.rowCount())]

    def editable(self, row):
        """ Whether the star count, fadeout, fadein and X-Cam can be edited """
        table = self.editor.split_table
        return [bool(table.item(row, column).flags() & table.item(row, column).flags().ItemIsEditable)
                for column in range(2, 6)]

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
        self.assertEqual((self.editor.title_le.text(), self.editor.category_combo.currentText(),
                          self.editor.init_star_le.text(), self.editor.version_combo.currentText(),
                          self.editor.timing_combo.currentText()), ("16 LBLJ", "16 Star", "0", "US", "RTA"))
        self.assertEqual(self.rows()[:2], [["LBLJ", "0", "2", "0", "-", "Normal"], ["DW", "1", "2", "0", "-", "Normal"]])

    def test_split_type_sets_the_editable_columns(self):
        self.editor.load_route()
        combo = self.editor.split_table.cellWidget(0, 6)
        expected = {"Normal": [True, True, True, False], "Fade": [False, True, True, False],
                    "Mips": [True, False, False, False], "Mips-X": [True, False, False, False],
                    "X-Cam": [True, True, True, True], "Final": [True, False, False, False]}
        for split_type, editable in expected.items():
            with self.subTest(split_type):
                combo.setCurrentText(split_type)
                self.assertEqual(self.editable(0), editable)

    def test_moving_and_removing_splits(self):
        self.editor.load_route()
        first, second = self.rows()[:2]
        self.editor.split_table.selectRow(0)
        self.editor.moveCurrentRow(RouteEditor.DOWN)
        self.assertEqual(self.rows()[:2], [second, first])
        self.assertEqual(self.editor.split_table.selectedItems()[0].row(), 1)
        count = len(self.rows())
        self.editor.remove_clicked()
        self.assertEqual(len(self.rows()), count - 1)
        self.assertEqual(self.rows()[1], self.rows()[1])

    def test_inserted_split(self):
        self.editor.new()
        self.editor._insert_row(title="WF", star_count="1")
        self.assertEqual(self.rows(), [["WF", "1", "1", "0", "-", "Normal"]])

    def test_invalid_counts_are_errors(self):
        for column, split_type, message in [(2, "Normal", "Invalid Star Count - Row: 1"),
                                            (3, "Normal", "Invalid Fadeout - Row: 1"),
                                            (4, "Normal", "Invalid Fadein - Row: 1"),
                                            (5, "X-Cam", "Invalid XCam - Row: 1")]:
            with self.subTest(message):
                self.editor.load_route()
                self.editor.split_table.cellWidget(0, 6).setCurrentText(split_type)
                self.editor.split_table.item(0, column).setText("x")
                self.editor.display_error_message.reset_mock()
                self.assertEqual(self.save(), -1)
                self.editor.display_error_message.assert_called_once_with(message, "Route Error")

    def test_counts_a_split_type_doesnt_use_are_saved_as_none(self):
        self.editor.load_route()
        self.editor.split_table.cellWidget(0, 6).setCurrentText("Mips")
        split = self.save()["splits"][0]
        self.assertEqual((split["on_fadeout"], split["on_fadein"], split["on_xcam"]), (-1, -1, -1))

    def convert(self, names):
        lss = self.dir / "splits.lss"
        lss.write_text("<Run><Segments>" + "".join(f"<Segment><Name>{n}</Name></Segment>" for n in names)
                       + "</Segments></Run>")
        self.editor.convert_lss(str(lss))
        return (self.editor.category_combo.currentText(), self.editor.version_combo.currentText(),
                self.editor.init_star_le.text()), self.rows()

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
