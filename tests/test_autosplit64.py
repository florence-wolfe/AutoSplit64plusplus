import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from autosplit64 import main
from autosplit64.core import config

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
            return main.route_timing()

    def test_valid_route(self):
        self.assertEqual(self.timing_of_route_file(ROUTE.read_bytes()), "RTA")

    def test_invalid_route_file(self):
        self.assertIsNone(self.timing_of_route_file(b"{ not json"))



class TimingSetupTest(unittest.TestCase):
    def test_each_timing(self):
        self.assertEqual(main.timing_setup("RTA"), ("standard/initial.processor", True))
        self.assertEqual(main.timing_setup("Up RTA"), ("up_rta/initial_up_rta.processor", False))
        self.assertEqual(main.timing_setup("File Select"), ("file_select/initial_file_select_start.processor", False))
        self.assertEqual(main.timing_setup(None), ("standard/initial.processor", True))

    def test_switching_back_to_rta_restarts_on_reset_again(self):
        # Start with an Up RTA route, then with an RTA route, in the same session
        for timing, start_on_reset in [("Up RTA", False), ("RTA", True)]:
            with mock.patch.object(main, "route_timing", return_value=timing), \
                 mock.patch.object(main.ProcessorGenerator, "generate"):
                main.set_up_timing()
            self.assertIs(main.core.start_on_reset, start_on_reset)

if __name__ == "__main__":
    unittest.main()
