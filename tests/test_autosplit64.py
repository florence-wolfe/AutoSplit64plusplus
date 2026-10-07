import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import AutoSplit64
from as64core import config

ROUTE = Path(__file__).parent.parent / "routes" / "16_lblj.as64"


class RouteTimingTest(unittest.TestCase):
    def timing_of_route_file(self, content):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        path = directory / "route.as64"
        path.write_bytes(content)
        real_get = config.get
        with mock.patch.object(config, "get", side_effect=lambda section, key=None:
                               str(path) if (section, key) == ("route", "path") else real_get(section, key)):
            return AutoSplit64.route_timing()

    def test_valid_route(self):
        self.assertEqual(self.timing_of_route_file(ROUTE.read_bytes()), "RTA")

    def test_invalid_route_file(self):
        self.assertIsNone(self.timing_of_route_file(b"{ not json"))


if __name__ == "__main__":
    unittest.main()
