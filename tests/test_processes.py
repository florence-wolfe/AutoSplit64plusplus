import unittest
from unittest import mock

from autosplit64 import core
from autosplit64.core.processing import Process
from autosplit64.processes import standard
from tests.test_standard_processes import patch_detection


def make_process(cls, *signals):
    """ A process without the reset templates its __init__ loads from disk """
    process = cls.__new__(cls)
    Process.__init__(process)
    for signal in signals:
        process.register_signal(signal)
    return process


class FadeoutNoStarResetTest(unittest.TestCase):
    def setUp(self):
        self.process = make_process(standard.ProcessFadeoutNoStar, "RESET", "COMPLETE")
        self.process._black_threshold = 0.1
        self.process._split_occurred = False
        self.process._reset_template = "template one"
        self.process._reset_template_2 = "template two"
        self.process._reset = mock.Mock()

        patch_detection(self, fade_status=core.FADEOUT_COMPLETE)
        for name, value in [("get_region", mock.Mock(return_value="reset region")),
                            ("incoming_split", mock.Mock(return_value=False)),
                            ("enable_predictions", mock.Mock())]:
            patcher = mock.patch.object(core, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(standard, "is_black", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_with_matching_template(self, template):
        self.process._is_reset = lambda region, t: t == template
        return self.process.execute()

    def test_first_reset_template_resets(self):
        self.assertIs(self.run_with_matching_template("template one"), self.process.signals["RESET"])
        self.process._reset.assert_called_once()

    def test_second_reset_template_resets(self):
        self.assertIs(self.run_with_matching_template("template two"), self.process.signals["RESET"])
        self.process._reset.assert_called_once()


if __name__ == "__main__":
    unittest.main()
