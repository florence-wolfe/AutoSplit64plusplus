import contextlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from autosplit64.core.processing import LOGIC_DIR, Process, Processor, ProcessorGenerator, ProcessorSwitch


class GenerateTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.a, self.b = Process(None), Process(None)
        self.a.register_signal("DONE")
        self.b.register_signal("NEXT")
        self.processes = {"A": self.a, "B": self.b}

    def write(self, name, initial, transitions, sub_processors=None):
        path = self.dir / f"{name}.processor"
        path.write_text(json.dumps({"name": name, "initial_process": initial, "inherit": None,
                                    "sub_processors": sub_processors or {}, "transitions": transitions}))
        return str(path)

    def test_missing_processor_file(self):
        self.assertIsNone(ProcessorGenerator.generate("missing.processor", self.processes))

    def test_processor_with_sub_processor(self):
        child = self.write("child", "A", {"A": {"A.DONE": "B"}})
        parent = self.write("parent", "CHILD", {"CHILD": {"B.NEXT": "A"}}, {"CHILD": child})

        processor = ProcessorGenerator.generate(parent, self.processes)

        sub_processor = processor.initial_process
        self.assertIsInstance(sub_processor, Processor)
        self.assertIs(sub_processor.initial_process, self.a)
        [(process, signal, next_process)] = [(t.process, t.signal, t.next_process) for t in sub_processor._transitions]
        self.assertEqual((process, signal, next_process), (self.a, self.a.signals["DONE"], self.b))
        [(process, signal, next_process)] = [(t.process, t.signal, t.next_process) for t in processor._transitions]
        self.assertEqual((process, signal, next_process), (sub_processor, self.b.signals["NEXT"], self.a))

    def test_unknown_names(self):
        for transitions in [{"UNKNOWN": {"A.DONE": "B"}}, {"A": {"A.UNKNOWN": "B"}}, {"A": {"A.DONE": "UNKNOWN"}}]:
            with self.subTest(transitions):
                self.assertIsNone(ProcessorGenerator.generate(self.write("p", "A", transitions), self.processes))
        self.assertIsNone(ProcessorGenerator.generate(self.write("p", "UNKNOWN", {}), self.processes))

    def test_failures_are_logged_with_their_reason(self):
        for transitions, reason in [({"UNKNOWN": {"A.DONE": "B"}}, "UNKNOWN"), ({"A": {"A.UNKNOWN": "B"}}, "A.UNKNOWN"),
                                    ({"A": {"A.DONE": "UNKNOWN"}}, "UNKNOWN")]:
            with self.subTest(transitions), self.assertLogs(".log", "ERROR") as logs:
                ProcessorGenerator.generate(self.write("p", "A", transitions), self.processes)
            self.assertIn("p.processor", logs.output[0])
            self.assertIn(reason, logs.output[0])

    def test_missing_file_is_logged(self):
        with self.assertLogs(".log", "ERROR") as logs:
            ProcessorGenerator.generate("missing.processor", self.processes)
        self.assertIn("missing.processor", logs.output[0])


class ShippedProcessorsTest(unittest.TestCase):
    """ Every processor in logic/ generates, with stand-ins for the processes main.py makes """

    def test_all_generate(self):
        files = sorted(LOGIC_DIR.rglob("*.processor"))
        names = {}
        for path in files:
            data = json.loads(path.read_text())
            for process, signals in data["transitions"].items():
                names.setdefault(process, set())
                for signal in signals:
                    owner, name = signal.split(".")
                    names.setdefault(owner, set()).add(name)
                    names.setdefault(signals[signal], set())
        sub_processor_names = {key for path in files for key in json.loads(path.read_text())["sub_processors"]}

        stand_ins = {}
        for name, signals in names.items():
            if name in sub_processor_names:
                continue
            stand_ins[name] = Process(None)
            for signal in signals:
                stand_ins[name].register_signal(signal)

        # Processors are found in the package, whatever the working directory
        with contextlib.chdir(tempfile.gettempdir()):
            for path in files:
                with self.subTest(str(path)):
                    self.assertIsNotNone(ProcessorGenerator.generate(path.relative_to(LOGIC_DIR).as_posix(), stand_ins))


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
