import time
import json
import logging
from pathlib import Path


# Processor files, which refer to each other relative to it
LOGIC_DIR = Path(__file__).resolve().parent.parent / "logic"

log = logging.getLogger(".log")

processes = {}


def register_process(name, process):
    processes[name] = process


class ProcessorGenerator(object):
    INITIAL_PROCESS = "initial_process"
    INHERIT = "inherit"
    OVERRIDE = "override"
    TRANSITIONS = "transitions"
    SUB_PROCESSORS = "sub_processors"

    @staticmethod
    def generate(file_path):
        # Load processor file
        file = ProcessorGenerator._open_file(file_path)
        if not file:
            log.error("Unable to read processor %s", file_path)
            return None

        transitions = {}

        #
        sub_processors = {}

        for sub_processor_key in file[ProcessorGenerator.SUB_PROCESSORS]:
            sub_processor = ProcessorGenerator.generate(file[ProcessorGenerator.SUB_PROCESSORS][sub_processor_key])

            if not sub_processor:
                log.error("Unable to generate sub-processor %s of %s", sub_processor_key, file_path)
                return None

            sub_processors[sub_processor_key] = sub_processor

        def find(name):
            """ A registered process, or a sub-processor of this file """
            return processes.get(name) or sub_processors.get(name)

        # Create blank processor instance
        processor = Processor()

        # Set initial process
        initial_process = find(file[ProcessorGenerator.INITIAL_PROCESS])
        if not initial_process:
            log.error("Unknown initial process %s in %s", file[ProcessorGenerator.INITIAL_PROCESS], file_path)
            return None
        processor.initial_process = initial_process

        # Copy all transitions from inherited processor (single inheritance only)
        if file[ProcessorGenerator.INHERIT]:
            inherit_file = ProcessorGenerator._open_file(file[ProcessorGenerator.INHERIT])

            if not inherit_file:
                log.error("Unable to read processor %s, which %s inherits", file[ProcessorGenerator.INHERIT], file_path)
                return None

            transitions = inherit_file[ProcessorGenerator.TRANSITIONS]

        # Set/override with all local transitions
        for transition in file[ProcessorGenerator.TRANSITIONS]:
            transitions[transition] = file[ProcessorGenerator.TRANSITIONS][transition]

        # Add transitions to processor
        for process_key in transitions:
            for signal in transitions[process_key]:
                signal_location = signal.split(".")[0]
                signal_value = signal.split(".")[1]

                # Define Transition
                t_process = find(process_key)
                if not t_process:
                    log.error("Unknown process %s in %s", process_key, file_path)
                    return None

                signal_process = find(signal_location)
                t_signal = signal_process.signals.get(signal_value) if signal_process else None
                if not t_signal:
                    log.error("Unknown signal %s in %s", signal, file_path)
                    return None

                t_next = find(transitions[process_key][signal])
                if not t_next:
                    log.error("Unknown process %s in %s", transitions[process_key][signal], file_path)
                    return None

                t = Transition(t_process, t_signal, t_next)

                # Add Transition
                processor.add_transition(t)

        return processor

    @staticmethod
    def _open_file(file_path):
        try:
            with open(LOGIC_DIR / file_path) as file:
                data = json.load(file)
        except FileNotFoundError:
            return None
        except PermissionError:
            return None

        return data


class Signal(object):
    """
    Object used to define transition relationships between processes
    """
    def __init__(self, name=""):
        self._name = name

    def name(self):
        return self._name


class Transition(object):
    """
    Define state transition behaviour between two processes given a Signal object
    """
    def __init__(self, process, signal, next_process):
        self.process = process
        self.signal = signal
        self.next_process = next_process

    def valid(self, process, signal):
        return self.process == process and self.signal == signal


class Process(object):
    def __init__(self):
        self.signals = {"LOOP": Signal()}
        self._transition_time = time.time()

    def execute(self):
        return self.signals["LOOP"]

    def on_transition(self):
        self._transition_time = time.time()

    def relinquish(self):
        return True

    def loop_time(self):
        return time.time() - self._transition_time

    def register_signal(self, name):
        self.signals[name] = Signal()


class Processor(Process):
    def __init__(self):
        super().__init__()

        # Processor
        self._initial_process = None
        self._prev_process = None
        self._current_process = None
        self._transitions = []

    @property
    def initial_process(self):
        return self._initial_process

    @initial_process.setter
    def initial_process(self, process):
        self._initial_process = process
        self._current_process = process

    def execute(self):
        if not self._current_process:
            return

        # If transitioning from a different process, call on_transition
        if self._current_process != self._prev_process:
            self._current_process.on_transition()
            print("Transition:", type(self._current_process).__name__)

        # Execute current process
        result = self._current_process.execute()

        next_process = None

        # Process LOOP signals, setting the next process to be the current process, otherwise check for transitions
        if result == self._current_process.signals["LOOP"]:
            next_process = self._current_process
        else:
            for transition in self._transitions:
                if transition.valid(self._current_process, result):
                    next_process = transition.next_process
                    break

        # Set processes for next execution
        self._prev_process = self._current_process
        self._current_process = next_process

        # If no valid transition is found, return result up processor chain
        if not next_process:
            return result
        else:
            return self.signals["LOOP"]

    def on_transition(self):
        """ On transition ensure processor is started from its initial process. """
        self._prev_process = None
        self._current_process = self._initial_process

    def add_transition(self, t):
        self._transitions.append(t)

    def relinquish(self):
        try:
            return self._current_process.relinquish()
        except AttributeError:
            return True


class ProcessorSwitch(object):
    def __init__(self):
        self._processors = {}
        self._current_processor = ""
        self._prev_processor = ""
        self._last_error = None

    def execute(self, process_name):
        # Skip split types without a processor, or whose processor failed to generate
        if self._processors.get(process_name) is None or self._processors.get(self._current_processor) is None:
            return

        try:
            if process_name != self._current_processor:
                if self._processors[self._current_processor].relinquish():
                    self._current_processor = process_name

            if process_name != self._prev_processor:
                self._processors[process_name].on_transition()

            self._processors[self._current_processor].execute()

            self._prev_processor = process_name
        except ConnectionAbortedError:
            raise
        except Exception as e:
            # Keep splitting, but log bugs in the processes, once rather than every frame
            if repr(e) != self._last_error:
                logging.getLogger(".log").exception("Split processor %s failed", self._current_processor)
            self._last_error = repr(e)

    def register_processor(self, name, processor):
        self._processors[name] = processor
