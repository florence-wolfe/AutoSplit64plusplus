import unittest
from unittest import mock

import numpy as np

from autosplit64.core.model import Model


class PredictTest(unittest.TestCase):
    def test_failure_is_raised(self):
        # Not taken for a prediction of star 0
        model = Model.__new__(Model)
        model.model = mock.Mock(run=mock.Mock(side_effect=RuntimeError("Invalid input")))
        model.input_name, model.output_name, model.legacy = "input", "output", False
        with self.assertRaisesRegex(RuntimeError, "Invalid input"):
            model.predict(np.zeros((40, 67, 3), np.uint8))
