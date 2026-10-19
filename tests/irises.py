"""
Measures split detection's iris matcher (autosplit64/core/irises.py) over recordings.

    uv run python -m tests.irises flo_bitdw_fall_ares [RECORDING...]
    uv run python -m tests.irises --score [--rate 6] [--phase 0.5 | --detection] [RECORDING...]

The first prints the verdict for each transition. The second checks them against tests/recordings/irises.json, the
irises labelled by eye, looking at every frame or, with --rate, that many a second, or as split detection looks.
"""
import json
import sys
from collections import deque

import numpy as np

from autosplit64.core import route_loader
from autosplit64.core.constants import GAME_REGION, LIFE_REGION, RESET_REGION, STAR_REGION
from autosplit64.core.image_utils import is_black
from autosplit64.core.irises import BLACK_LEVEL, HUD, IRISES, brightness_of, classify
from tests.replay import DEFAULTS, Clock, Recording, VideoCapture

# The game is black once less than this share of it is brighter than the iris's black, besides the HUD, and lit
# again from this share
BLACK, LIT_AGAIN = 0.01, 0.2
# The longest iris (a death's 1.6 s) and the frames before it, to know what was lit before it started
HISTORY = 2.4
# How often split detection looks while counting stars (the default star_process_frame_rate) and during a fadeout
STAR_RATE, FADEOUT_RATE = 6, 29.97


def lit_share(visible):
    return float((visible * HUD).sum() / HUD.sum())


def transitions(recording, rate=None, phase=0.0, detection=False):
    """
    (time, Verdict) for each transition in the recording.

    Looks at every frame, or `rate` times a second starting `phase` of a look in, and decides when the game goes
    black: the end of an iris, which in a dark stage comes after the centre goes black.

    With `detection`, looks as split detection does over a death: STAR_RATE times a second while the HUD shows, as in
    its star count process, and 29.97 once both HUD corners are black, as in its fadeout process. It decides when the
    centre goes black, which is when a fadeout splits.
    """
    version = route_loader.load(recording.route_path).version
    black_threshold = json.loads(DEFAULTS.read_text())["thresholds"]["black_threshold"]
    fps = recording.fps()
    first = phase / STAR_RATE if detection else phase / rate if rate else 0.5 / fps
    clock = Clock(first, recording.length())
    capture = VideoCapture(recording.video, clock, recording.game_region, version)
    history = deque()
    armed = False
    try:
        while clock.now < recording.length():
            capture.capture()
            brightness = brightness_of(capture.get_region(GAME_REGION))
            history.append((capture.frame_time, brightness))
            while history[0][0] < capture.frame_time - HISTORY:
                history.popleft()
            if detection:
                hud_black = (is_black(capture.get_region(STAR_REGION), black_threshold)
                             and is_black(capture.get_region(LIFE_REGION), black_threshold))
                ended = is_black(capture.get_region(RESET_REGION), black_threshold)
                lit = not ended
                clock.now += 1 / (FADEOUT_RATE if hud_black else STAR_RATE)
            else:
                share = lit_share((brightness >= BLACK_LEVEL).astype(np.float32))
                ended, lit = share < BLACK, share > LIT_AGAIN
                clock.now += 1 / (rate or fps)
            if lit:
                armed = True
            elif armed and ended and history[0][0] <= capture.frame_time - HISTORY + 0.1:
                armed = False
                yield capture.frame_time, classify(list(history))
    finally:
        capture.release()


LABELS = __import__("pathlib").Path(__file__).parent / "recordings" / "irises.json"
# How far a label's time can be from when the game goes black
NEAR = 1.0
# What a verdict should be for each label
EXPECTED = {"none": "unknown"}


def _row(time, verdict):
    cells = "  ".join(f"{verdict.scores[name]:6.2f}" for name in [i.name for i in IRISES] + ["fade"])
    return f"{time:9.3f}  {verdict.iris:7} {verdict.started:5.2f}s  {cells}"


def score(names, rate=None, phase=0.0, detection=False):
    """ Each labelled transition's verdict against its label, and any Bowser called where none is labelled """
    labels = json.loads(LABELS.read_text())
    right = wrong = 0
    for name in names or [name for name in labels if name != "about"]:
        found = list(transitions(Recording.load(name), rate, phase, detection))
        print(f"== {name}")
        for time, kind, about, *unseen in labels[name]:
            near = [(abs(t - time), t, v) for t, v in found if abs(t - time) <= NEAR]
            if not near:
                # No iris, and the game never went black there, is right for none
                ok = kind == "none" or bool(unseen)
                right, wrong = right + ok, wrong + (not ok)
                print(f"  {'✓' if ok else '✗'} {kind:7} {time:9.1f}  no transition found  {about}")
                continue
            _, t, verdict = min(near, key=lambda n: n[0])
            # An iris that closes on a black screen leaves little to see: unknown is right too
            ok = verdict.iris == EXPECTED.get(kind, kind) or (bool(unseen) and verdict.iris == "unknown")
            right, wrong = right + ok, wrong + (not ok)
            print(f"  {'✓' if ok else '✗'} {kind:7} {_row(t, verdict)}  {about}")
        labelled = [label[0] for label in labels[name]]
        for t, verdict in found:
            if verdict.iris == "bowser" and not any(abs(t - time) <= NEAR for time in labelled):
                wrong += 1
                print(f"  ✗ unlabelled Bowser {_row(t, verdict)}")
    print(f"{right} of {right + wrong} right")


def main(names):
    for name in names:
        print(f"== {name}")
        print(f"{'black':>9}  {'iris':7} {'start':>6}  " + "  ".join(f"{name:>6}" for name in [i.name for i in IRISES] + ["fade"]))
        for time, verdict in transitions(Recording.load(name)):
            print(_row(time, verdict), flush=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--score"]:
        arguments = sys.argv[2:]
        # --rate 6 and --phase 0.5: look 6 times a second, half a look in, as split detection does
        options = {}
        if "--detection" in arguments:
            arguments.remove("--detection")
            options["detection"] = True
        for option in ("--rate", "--phase"):
            if option in arguments:
                at = arguments.index(option)
                options[option[2:]] = float(arguments[at + 1])
                del arguments[at:at + 2]
        score(arguments, **options)
    else:
        main(sys.argv[1:])
