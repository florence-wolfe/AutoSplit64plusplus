import unittest
from types import SimpleNamespace
from unittest import mock

from as64core import base
from as64core.base import Base
from as64core.model import PredictionInfo


def make_base(star_counts=(1, 2, 3, 4, 5, 6), current=3):
    """ A Base with a route of splits with the given star counts, without capture, model or timer """
    b = Base.__new__(Base)
    b._route = SimpleNamespace(splits=[SimpleNamespace(star_count=s) for s in star_counts], initial_star=0)
    b._current_split = b._route.splits[current]
    return b


class SyncSplitIndexTest(unittest.TestCase):
    def setUp(self):
        self.base = make_base(current=3)
        self.base.set_split_index = mock.Mock()

    def test_no_answer_from_timer_keeps_split(self):
        self.base._sync_split_index(False)
        self.base.set_split_index.assert_not_called()

    def test_not_running_goes_to_first_split(self):
        self.base._sync_split_index(-1)
        self.base.set_split_index.assert_called_once_with(0)

    def test_follows_timer(self):
        self.base._sync_split_index(5)
        self.base.set_split_index.assert_called_once_with(5)

    def test_same_split_does_nothing(self):
        self.base._sync_split_index(3)
        self.base.set_split_index.assert_not_called()


class ValidityCheckTest(unittest.TestCase):
    def setUp(self):
        self.base = make_base()
        self.base._error_occurred = mock.Mock()
        self.base._ls_socket = None
        size = base.config.get("game", "capture_size")
        self.base._game_capture = mock.Mock(get_capture_size=mock.Mock(return_value=list(size)))
        self.base._model = mock.Mock(valid=mock.Mock(return_value=False))
        patcher = mock.patch.object(base.livesplit, "check_connection", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_model_that_failed_to_load_is_reported(self):
        self.assertFalse(self.base.validity_check())
        message = self.base._error_occurred.call_args.args[0]
        self.assertIn("Unable to load prediction model", message)
        self.assertIn(".onnx", message)



class RunTest(unittest.TestCase):
    def test_failed_start_checks_end_the_run(self):
        b = make_base()
        b._route, b._current_split = None, None
        b._processor_switch = mock.Mock()
        b.logger = mock.Mock()
        # A failing check reports the error, which also stops split detection
        b.validity_check = mock.Mock(return_value=False)
        b.stop = mock.Mock()

        with mock.patch.object(base.livesplit, "connect"):
            b.run()

        b.logger.error.assert_not_called()
        b.stop.assert_not_called()


class FirstSplitsTest(unittest.TestCase):
    """ Lookups of earlier splits at the start of the route mustn't wrap around to its end """

    def setUp(self):
        self.as64 = SimpleNamespace(star_count=5, prediction_info=PredictionInfo(4, 0.9), xcam_count=0,
                                    previous_split_initial_star=0, next_split_split_star=0)
        patcher = mock.patch.object(base, "as64", self.as64, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.base = make_base(star_counts=(5, 8, 10, 120), current=0)
        self.base.undo = mock.Mock()
        self.base._update_occurred = mock.Mock()

    def test_undo_check_at_first_split(self):
        b = self.base
        b._minimum_undo_count, b._undo_prediction_threshold = 3, 0.85
        b._star_skip_enabled, b._previous_prediction = False, None
        # Confident predictions of one star less than counted
        b._predictions = [PredictionInfo(4, 0.95)] * 3
        b.set_star_count = mock.Mock(side_effect=lambda count: setattr(self.as64, "star_count", count))

        b._star_error_check()

        b.set_star_count.assert_called_once_with(4)
        b.undo.assert_not_called()

    def test_star_skip_window_at_second_split(self):
        self.base._reset_fade_count = mock.Mock()
        self.base.set_split_index(1)
        self.assertEqual(self.as64.previous_split_initial_star, 0)

if __name__ == "__main__":
    unittest.main()
