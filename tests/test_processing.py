import unittest
from unittest import mock

from as64core.processing import ProcessorGenerator, ProcessorSwitch


class GenerateTest(unittest.TestCase):
    def test_missing_processor_file(self):
        self.assertIsNone(ProcessorGenerator.generate("logic/missing.processor"))


class ProcessorSwitchTest(unittest.TestCase):
    def setUp(self):
        self.switch = ProcessorSwitch()
        self.processor = mock.Mock(relinquish=mock.Mock(return_value=True))
        self.switch.register_processor("Normal", self.processor)
        self.switch._current_processor = "Normal"

    def test_runs_processor(self):
        self.switch.execute("Normal")
        self.processor.execute.assert_called_once()

    def test_split_types_without_processor_are_skipped(self):
        self.switch.register_processor("Failed", None)
        self.switch.execute("Unregistered")
        self.switch.execute("Failed")
        self.processor.execute.assert_not_called()

    def test_errors_in_processes_are_logged_once_and_splitting_continues(self):
        self.processor.execute.side_effect = KeyError("bug")
        with self.assertLogs(".log", "ERROR") as logs:
            self.switch.execute("Normal")
            self.switch.execute("Normal")
        self.assertEqual(len(logs.records), 1)
        self.assertIn("KeyError", logs.output[0])
        self.assertEqual(self.processor.execute.call_count, 2)

    def test_lost_timer_connection_reaches_the_run_loop(self):
        self.processor.execute.side_effect = ConnectionAbortedError
        with self.assertRaises(ConnectionAbortedError):
            self.switch.execute("Normal")


if __name__ == "__main__":
    unittest.main()
