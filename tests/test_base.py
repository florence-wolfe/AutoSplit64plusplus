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


if __name__ == "__main__":
    unittest.main()
