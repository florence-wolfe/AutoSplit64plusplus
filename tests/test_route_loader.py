import json
import os
import shutil
import tempfile
import unittest
from json import JSONDecodeError
from pathlib import Path
from unittest import mock

from PyQt6 import QtWidgets

from as64core import route_loader
from as64gui.app import App
from tests.qt import close_window

ROUTE = Path(__file__).parent.parent / "routes" / "16_lblj.as64"

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def test_path_is_kept_whatever_its_characters(self):
        path = self.dir / 'my "best" route \\ 16.as64'
        shutil.copy(ROUTE, path)
        route = route_loader.load(str(path))
        self.assertEqual(route.file_path, str(path))
        self.assertEqual(len(route.splits), len(route_loader.load(str(ROUTE)).splits))

    def test_byte_order_mark(self):
        path = self.dir / "bom.as64"
        path.write_bytes(b"\xef\xbb\xbf" + ROUTE.read_bytes())
        self.assertIsNotNone(route_loader.load(str(path)))

    def test_route_from_before_x_cam_and_timing(self):
        data = json.loads(ROUTE.read_text())
        del data["timing"]
        for split in data["splits"]:
            del split["xcam"]
        path = self.dir / "old.as64"
        path.write_text(json.dumps(data))
        route = route_loader.load(str(path))
        self.assertEqual(route.timing, "RTA")
        self.assertEqual({split.on_xcam for split in route.splits}, {-1})

    def test_missing_file(self):
        self.assertIsNone(route_loader.load(str(self.dir / "missing.as64")))

    def test_invalid_file_raises_for_the_route_editor(self):
        path = self.dir / "broken.as64"
        path.write_text("{ not json")
        with self.assertRaises(JSONDecodeError):
            route_loader.load(str(path))

    def test_load_or_none_on_invalid_file(self):
        path = self.dir / "broken.as64"
        for content in ["{ not json", '{"some": "other file"}', '{"__route__": true}']:
            path.write_text(content)
            self.assertIsNone(route_loader.load_or_none(str(path)), content)


class EncoderTest(unittest.TestCase):
    def test_route_round_trip(self):
        route = route_loader.load(str(ROUTE))
        decoded = json.loads(json.dumps(route, cls=route_loader.RouteEncoder))
        self.assertEqual(len(decoded["splits"]), len(route.splits))

    def test_other_objects_are_not_serializable(self):
        with self.assertRaisesRegex(TypeError, "not JSON serializable"):
            json.dumps(object(), cls=route_loader.RouteEncoder)


class RouteDirectoryTest(unittest.TestCase):
    def test_invalid_route_file_is_skipped(self):
        with mock.patch.object(App, "update_check"):
            app = App()
        self.addCleanup(close_window, app)

        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        (work / "routes").mkdir()
        shutil.copy(ROUTE, work / "routes" / "good.as64")
        (work / "routes" / "broken.as64").write_text("{ not json")

        cwd = os.getcwd()
        os.chdir(work)
        self.addCleanup(os.chdir, cwd)
        app._load_route_dir()

        self.assertEqual([path for routes in app._routes.values() for _, path in routes], ["routes/good.as64"])


if __name__ == "__main__":
    unittest.main()
