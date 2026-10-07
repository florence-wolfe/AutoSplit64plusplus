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



class TimingSetupTest(unittest.TestCase):
    def test_each_timing(self):
        self.assertEqual(AutoSplit64.timing_setup("RTA"), ("logic/standard/initial.processor", True))
        self.assertEqual(AutoSplit64.timing_setup("Up RTA"), ("logic/up_rta/initial_up_rta.processor", False))
        self.assertEqual(AutoSplit64.timing_setup("File Select"), ("logic/file_select/initial_file_select_start.processor", False))
        self.assertEqual(AutoSplit64.timing_setup(None), ("logic/standard/initial.processor", True))

    def test_switching_back_to_rta_restarts_on_reset_again(self):
        # Start with an Up RTA route, then with an RTA route, in the same session
        for timing, start_on_reset in [("Up RTA", False), ("RTA", True)]:
            with mock.patch.object(AutoSplit64, "route_timing", return_value=timing), \
                 mock.patch.object(AutoSplit64.ProcessorGenerator, "generate"):
                AutoSplit64.set_up_timing()
            self.assertIs(AutoSplit64.as64core.start_on_reset, start_on_reset)

if __name__ == "__main__":
    unittest.main()
