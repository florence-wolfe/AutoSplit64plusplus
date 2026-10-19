"""
Scores what split detection detected over a recording against the events labelled in it, per type of event.

Labels are in tests/recordings/events/<recording>.json:
    {"reviewed": true, "mode": "run", "start": 0, "end": 400, "types": ["fadeout"],
     "events": [{"event": "fadeout", "time": 13.033}, ...]}
`mode` is "run" for a recording of a run from the console reset, "ending" for one of a run's ending, which is replayed
like tests/test_replay.py does: from the last split, with the default reset templates and AS64++'s final split, or
"split" for one of part of a run, replayed from its start with the timer on the split in `"split"`, the index in the
route, and the default reset templates. Times are seconds in the video, of the first frame that shows the event. `start` and `end` are the part of the video
that's labelled: detections outside it aren't scored. `types` are the types of event the file labels completely, so a file can start with one, e.g. the Grand Star, and the
others aren't scored; it's all of them when missing. `reviewed` is false until a person has checked every label
against the video, as tests/label.py writes them from what detection did, and `checked` says who checked them meanwhile.

What detection detected is read from its trace (tests/replay.py), which logs each event with the time of its frame.
Only events it logs can be scored: it counts fadeouts and fade-ins only while a run is going, and logs no key grabs.
Those show as misses, which is true.

    uv run python -m tests.score greensuigi_16_star
"""
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

EVENTS_DIR = Path(__file__).parent / "recordings" / "events"
MODES = ("run", "ending", "split")
EVENTS = ("fadeout", "fade_in", "death", "star_grab", "key_grab", "reset", "grand_star")
# How far apart a detection and a label can be to be the same event. Timing errors are reported within it.
TOLERANCE = 0.5
# How much earlier and later than its label an event can be detected, for the types that aren't within TOLERANCE:
# a fadeout counts as the HUD goes black, up to a second before the screen is all black, as the death's iris closes
# slowly, and a death can show only in the lives, once Mario respawns, which is in time before the next fadeout
WINDOWS = {"fadeout": (1.0, TOLERANCE), "death": (TOLERANCE, 5.0)}

# The trace lines each event is detected by
_TRACE_LINE = re.compile(r"(?P<time>\d+(?:\.\d+)?) (?P<message>.*)")
_STAR_COUNT = re.compile(r"Star count (\d+) -> (\d+)")
_PREFIXES = (
    ("Reset the timer", "reset"),
    ("Fadeout ", "fadeout"),
    ("Fade-in ", "fade_in"),
    # By Bowser's iris, or a life lost
    ("Death, ", "death"),
    ("Grand Star grabbed", "grand_star"),
)


@dataclass(frozen=True)
class Event:
    event: str
    time: float


@dataclass
class Labels:
    reviewed: bool
    mode: str
    start: float
    end: float
    types: list
    events: list
    # The split index a recording of part of a run starts on
    split: int = None
    # Who checked the labels against the video, until a person reviewed them
    checked: str = None


@dataclass
class TypeScore:
    found: int = 0
    missed: int = 0
    extra: int = 0
    # Detected time minus labelled time of each found event: positive is late
    errors: list = field(default_factory=list)

    @property
    def recall(self):
        """ The part of the labelled events detected, or None without any labelled """
        total = self.found + self.missed
        return self.found / total if total else None

    @property
    def precision(self):
        """ The part of the detections that were labelled events, or None without any detected """
        total = self.found + self.extra
        return self.found / total if total else None


def parse_trace(trace):
    """ The events in a replay's trace lines, in the order detection logged them """
    events = []
    for line in trace:
        match = _TRACE_LINE.fullmatch(line)
        if not match:
            continue
        time, message = float(match["time"]), match["message"]
        star_count = _STAR_COUNT.match(message)
        if star_count:
            # Down is a correction, and a bigger jump is detection finding its place, e.g. starting mid-run
            if int(star_count[2]) == int(star_count[1]) + 1:
                events.append(Event("star_grab", time))
            continue
        for prefix, event in _PREFIXES:
            if message.startswith(prefix):
                events.append(Event(event, time))
                break
    return events


def load_labels(path):
    data = json.loads(Path(path).read_text())
    events = [Event(item["event"], float(item["time"])) for item in data["events"]]
    for event in events:
        if event.event not in EVENTS:
            raise ValueError(f"Unknown event {event.event!r} in {path}, which are {EVENTS}")
    types = data.get("types", list(EVENTS))
    for kind in types:
        if kind not in EVENTS:
            raise ValueError(f"Unknown event {kind!r} in the types of {path}, which are {EVENTS}")
    if data["mode"] not in MODES:
        raise ValueError(f"Unknown mode {data['mode']!r} in {path}, which are {MODES}")
    if data["mode"] == "split" and "split" not in data:
        raise ValueError(f"No split in {path}, which a recording of part of a run starts on")
    return Labels(data["reviewed"], data["mode"], data["start"], data["end"], types,
                  sorted(events, key=lambda event: event.time), data.get("split"), data.get("checked"))


def score(detected, labelled, tolerance=TOLERANCE, start=None, end=None, types=EVENTS, windows=WINDOWS):
    """
    A TypeScore for each of the types of event. Each detection matches at most one label, the nearest first, from
    `tolerance` before it to `tolerance` after, or within the (before, after) `windows` has for its type.
    """
    def inside(event):
        return (start is None or event.time >= start) and (end is None or event.time <= end)

    detected = [event for event in detected if inside(event)]
    labelled = [event for event in labelled if inside(event)]
    result = {}
    for kind in types:
        found = sorted(event.time for event in detected if event.event == kind)
        truth = sorted(event.time for event in labelled if event.event == kind)
        early, late = windows.get(kind, (tolerance, tolerance))
        pairs = sorted((abs(f - t), i, j) for i, f in enumerate(found) for j, t in enumerate(truth)
                       if -early <= f - t <= late)
        used_found, used_truth, matches = set(), set(), []
        for _, i, j in pairs:
            if i not in used_found and j not in used_truth:
                used_found.add(i)
                used_truth.add(j)
                matches.append((truth[j], found[i] - truth[j]))
        type_score = TypeScore(len(matches), len(truth) - len(matches), len(found) - len(matches))
        type_score.errors = [error for _, error in sorted(matches)]
        result[kind] = type_score
    return result


def report(result):
    """ A table of the scores, one line per type of event that was labelled or detected """
    lines = [f"{'event':10} {'found':>5} {'missed':>6} {'extra':>5} {'recall':>7} {'precision':>9} {'median s':>9} {'worst s':>8}"]
    for kind, type_score in result.items():
        if not (type_score.found or type_score.missed or type_score.extra):
            continue
        errors = sorted(type_score.errors)
        median = f"{errors[len(errors) // 2]:+.3f}" if errors else "-"
        worst = f"{max(errors, key=abs):+.3f}" if errors else "-"
        ratio = lambda value: "-" if value is None else f"{value:.0%}"
        lines.append(f"{kind:10} {type_score.found:5} {type_score.missed:6} {type_score.extra:5} "
                     f"{ratio(type_score.recall):>7} {ratio(type_score.precision):>9} {median:>9} {worst:>8}")
    return "\n".join(lines)


def replay_recording(recording, mode, end, templates, split=None):
    """
    Replays the recording up to `end`, as its mode says. `templates` are the reset templates of a run's console reset,
    and `split` the split index a recording of part of a run starts on.
    """
    from autosplit64.core import detection_model, route_loader
    from tests.replay import DEFAULTS, Variant, replay

    if mode == "run":
        # Detection needs to start before the first event to know where in the run it is, so from the video's start
        return replay(recording, 0, end, templates)
    advanced = json.loads(DEFAULTS.read_text())["advanced"]
    default_templates = [DEFAULTS.parent / advanced["reset_frame_one"], DEFAULTS.parent / advanced["reset_frame_two"]]
    # The detection model that waits for Bowser's last speech before it looks for the Grand Star
    as64pp = Variant("as64pp", settings={("model", "detection"): detection_model.AS64PP})
    if mode == "split":
        return replay(recording, 0, end, default_templates, split_index=split)
    start = recording.ending[0] if recording.ending else 0
    last_split = len(route_loader.load(recording.route_path).splits) - 1
    return replay(recording, start, end, default_templates, split_index=last_split, variant=as64pp)


def score_recording(recording, labels, templates):
    """ Replays the recording over the labelled part, and scores what detection detected """
    result = replay_recording(recording, labels.mode, labels.end, templates, labels.split)
    return score(parse_trace(result.trace), labels.events, start=labels.start, end=labels.end, types=labels.types), result


def main(name):
    import tempfile

    from tests.replay import Recording, generate_reset_templates

    recording = Recording.load(name)
    if not recording.available():
        sys.exit("Needs the recording, from: uv run python -m tests.replay")
    labels = load_labels(EVENTS_DIR / f"{name}.json")
    if not labels.reviewed and labels.checked:
        print(f"{name}: the labels aren't reviewed by a person yet, only checked {labels.checked}")
    elif not labels.reviewed:
        print(f"{name}: the labels aren't reviewed yet, so this scores detection against itself where they came from it")
    with tempfile.TemporaryDirectory() as directory:
        templates = generate_reset_templates(recording, directory) if labels.mode == "run" else None
        result, _ = score_recording(recording, labels, templates)
    print(report(result))


if __name__ == "__main__":
    main(sys.argv[1])
