"""
Starts the labels of a recording (tests/score.py) from what split detection detected over it, and draws the frames
around each event, so labelling means correcting the times, deleting what isn't an event, and adding what detection
missed, rather than finding everything in the video. Fadeouts and fade-ins come from every frame of the video instead,
each time the game is all black or all white, which finds those detection doesn't count too, at their exact frame.

    uv run python -m tests.label greensuigi_16_star [run|ending]
    uv run python -m tests.label flo_bitdw_fall_ares split 3
    uv run python -m tests.label at greensuigi_16_star 65.7

The second draws 12 video frames in a row from just before a time, to set it to the first frame that shows an event.
The first writes tests/recordings/events/<recording>.json, with "reviewed": false, and a picture for each event in
tests/recordings/cache/sheets/<recording>/, which the file names list. It won't overwrite a labels file.

To review: look at each picture, which shows 12 frames from 1 s before the time detection logged the event to 1 s
after, each captioned with its time, which finds the event. Then `at` its time to see frames one by one, and set the
event's time to the first frame that shows it. Delete events that didn't happen. Add
events detection missed, which are the point of this: look for them wherever the run does something detection hasn't
logged, e.g. every death, key grab and fade. Then set "reviewed" to true.

What counts as each event, by the first frame it shows:
    fadeout     the game is all black, for a level change, a death or a reset, anything detection counts: a split
                on a fadeout happens as the centre goes black, a frame or two before, and detection counts it as the
                HUD goes black, which is up to a second before, as the iris closes
    fade_in     the game is all white, which is what detection and a route's fade-ins count
    death       the game is all black for Mario's death, which is its fadeout's time: the iris that shows it closes a
                second or more after he starts dying, and the lives show it only once he respawns
    star_grab   the star count goes up
    key_grab    the key goes, in the white puff when Mario touches it
    reset       the SM64 logo shows after a console reset
    grand_star  Mario grabs the Grand Star
"""
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from tests import score
from tests.replay import CACHE, Recording, generate_reset_templates

SHEETS = CACHE / "sheets"
# The part of the game that's black, or white, for it to be a fade, and how dark and bright that is: split detection's
# default black and white thresholds
FULL = 0.99
# How far from all black (or white) the game has to get, for the next time it is to be another fade: a course's intro
# shows its title on white, between the painting's white and the course's
UNTIL = 0.9
BLACK, WHITE = 0.1 * 255, 0.8 * 255
# The frames of a picture, in a grid, and a coarse picture's seconds before the event and between frames
FRAMES, COLUMNS, WIDTH = 12, 4, 240
BEFORE, APART = 1.0, 1 / 6


def sheet(recording, first, step, path):
    """ Draws 12 frames from the video's frame `first`, `step` frames apart, each with its time, to `path` """
    fps = recording.fps()
    video = cv2.VideoCapture(str(recording.video))
    tiles = []
    try:
        video.set(cv2.CAP_PROP_POS_FRAMES, first)
        for number in range(first, first + FRAMES * step):
            ok, frame = video.read()
            if not ok:
                break
            if (number - first) % step:
                continue
            height = round(frame.shape[0] * WIDTH / frame.shape[1])
            tile = cv2.resize(frame, (WIDTH, height), interpolation=cv2.INTER_AREA)
            caption = f"{number / fps:.3f}"
            cv2.putText(tile, caption, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(tile, caption, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
    finally:
        video.release()
    if not tiles:
        return False
    blank = np.zeros_like(tiles[0])
    tiles += [blank] * (-len(tiles) % COLUMNS)
    rows = [np.hstack(tiles[i:i + COLUMNS]) for i in range(0, len(tiles), COLUMNS)]
    cv2.imwrite(str(path), np.vstack(rows))
    return True


def fade_frames(fractions, full=FULL, until=UNTIL):
    """
    The frame of each fade, given each frame's part of the game that's black (or white): the first that's `full`, once
    it was below `until` since the last
    """
    frames, ended = [], True
    for frame, fraction in enumerate(fractions):
        if fraction >= full and ended:
            frames.append(frame)
            ended = False
        elif fraction < until:
            ended = True
    return frames


def fades(recording):
    """ The fadeouts and fade-ins in every frame of the video, as score.Events """
    x, y, width, height = recording.game_region
    black, white = [], []
    video = cv2.VideoCapture(str(recording.video))
    try:
        while True:
            ok, frame = video.read()
            if not ok:
                break
            game = frame[y:y + height, x:x + width]
            black.append(np.count_nonzero(game < BLACK) / game.size)
            white.append(np.count_nonzero(game > WHITE) / game.size)
    finally:
        video.release()
    fps = recording.fps()
    events = [score.Event("fadeout", round(frame / fps, 3)) for frame in fade_frames(black)]
    events += [score.Event("fade_in", round(frame / fps, 3)) for frame in fade_frames(white)]
    return events


def at(name, time):
    """ Frames in a row from five before the time, which a coarse picture's times are within a few frames of """
    recording = Recording.load(name)
    if not recording.available():
        sys.exit("Needs the recording, from: uv run python -m tests.replay")
    folder = SHEETS / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"at_{float(time):.3f}.png"
    if not sheet(recording, max(0, round(float(time) * recording.fps()) - 5), 1, path):
        sys.exit(f"The video ends before {time} s")
    print(path)


def main(name, mode="run", split=None):
    recording = Recording.load(name)
    if not recording.available():
        sys.exit("Needs the recording, from: uv run python -m tests.replay")
    path = score.EVENTS_DIR / f"{name}.json"
    if path.exists():
        sys.exit(f"{path} exists, and may have reviewed labels: delete it to start again")
    start, end = (recording.ending or (0, recording.length())) if mode == "ending" else (0, recording.length())
    with tempfile.TemporaryDirectory() as directory:
        templates = generate_reset_templates(recording, directory) if mode == "run" else None
        split = None if split is None else int(split)
        result = score.replay_recording(recording, mode, end, templates, split)
    detected = [event for event in score.parse_trace(result.trace) if event.event not in ("fadeout", "fade_in")]
    events = sorted((event for event in detected + fades(recording) if start <= event.time <= end),
                    key=lambda event: event.time)

    folder = SHEETS / name
    folder.mkdir(parents=True, exist_ok=True)
    listed = []
    for number, event in enumerate(events, 1):
        picture = f"{number:03d}_{event.event}_{event.time:.3f}.png"
        fps = recording.fps()
        sheet(recording, max(0, round((event.time - BEFORE) * fps)), max(1, round(APART * fps)), folder / picture)
        listed.append({"event": event.event, "time": event.time})
    path.parent.mkdir(exist_ok=True)
    # One event to a line, to read and edit
    lines = ",\n".join(f"        {json.dumps(item)}" for item in listed)
    split_line = "" if split is None else f'    "split": {split},\n'
    path.write_text(f'{{\n    "reviewed": false,\n    "mode": "{mode}",\n{split_line}    "start": {start},\n    "end": {end},\n'
                    f'    "events": [\n{lines}\n    ]\n}}\n')
    print(f"{len(events)} events detected: labels in {path}, pictures in {folder}")


if __name__ == "__main__":
    if sys.argv[1] == "at":
        at(*sys.argv[2:])
    else:
        main(*sys.argv[1:])
