"""
Which iris a transition closes with, by fitting the game's own irises to the frames split detection saw.

The game closes the screen on a warp with an iris whose shape says why (level_update.c in the SM64 decompilation):

    star    pipes, trapdoors, warp objects    20 frames
    circle  falls (warp floors), warp doors   20 frames
    mario   star and key exits                32 frames
    bowser  deaths                            48 frames

How it draws one is fixed (area.c and screen_transition.c): a 64x64 texture whose transparent part is the window, on a
square reaching `radius` each way from the middle of the N64's 320x240 screen, with nothing else drawn. The radius
starts at 320 and shrinks by the same step every game frame, to 0 for a star or circle and to 16 for a head, and the
square never moves or turns. So each frame of an iris blackens a ring of known shape and size, and all that's unknown
is the frame it starts on, which is its own length before the screen is black. Each iris is scored by how well the
pixels that go black frame to frame match its rings, at the starts it could have, and the best wins by a margin.

tests/irises.py measures it over recordings, against the irises labelled by eye in tests/recordings/irises.json.
"""
from dataclasses import dataclass
from functools import cached_property

import cv2
import numpy as np

from .constants import DATA_DIR

# The N64's screen, which the game region shows, and where the iris is centred (area.c)
SCREEN_W, SCREEN_H = 320, 240
CENTRE = (SCREEN_W / 2, SCREEN_H / 2)
# GFX_DIMENSIONS_FULL_RADIUS: the screen's height times its 4:3 aspect ratio
FULL_RADIUS = 320
GAME_FPS = 30
# Frames are compared at a quarter of the N64's resolution, 4 screen units to a pixel
SCALE = 4
W, H = SCREEN_W // SCALE, SCREEN_H // SCALE
# Brighter than LIT is lit, darker than BLACK is the iris's black: the screen once an iris has closed is 4 at most,
# while BitDW's dark void is mostly 8 and up. In between is a dim scene, or a lit one dimming at the iris's blurred edge.
LIT = 24
BLACK_LEVEL = 8
# The HUD, which the fall's circle doesn't cover: the top band with the lives, power meter and stars, and the camera icon
HUD = np.ones((H, W), np.float32)
HUD[:round(H * 0.22), :] = 0
HUD[round(H * 0.84):, round(W * 0.80):] = 0


@dataclass(frozen=True)
class Iris:
    name: str
    # Game frames from the full radius to the end radius
    frames: int
    end_radius: int
    # Where the window shows through, 1 inside, at the texture's 64x64 texels
    window: np.ndarray

    def radius(self, frame):
        """ The radius on game frame `frame` of the iris, as calc_tex_transition_radius rounds it """
        frame = min(max(frame, 0), self.frames - 1)
        return int(FULL_RADIUS + frame * (self.end_radius - FULL_RADIUS) / (self.frames - 1) + 0.5)

    @cached_property
    def radii(self):
        """ The radius on each of its frames """
        return np.array([self.radius(frame) for frame in range(self.frames)])


def _window(name, mirror=False):
    alpha = cv2.imread(str(DATA_DIR / "irises" / f"{name}.png"), cv2.IMREAD_UNCHANGED)[:, :, 3]
    if mirror:
        # The game draws the right half of the texture, its first column in the middle, and mirrors it
        alpha = np.hstack([alpha[:, 32:][:, ::-1], alpha[:, 32:]])
    return 1 - alpha.astype(np.float32) / 255


IRISES = [
    Iris("star", 20, 0, _window("star")),
    Iris("circle", 20, 0, _window("circle")),
    Iris("mario", 32, 16, _window("mario")),
    Iris("bowser", 48, 16, _window("bowser", mirror=True)),
]


_renders = {}


def render(iris, radius):
    """ How much of each pixel the iris's window shows at `radius`, drawn once per size """
    key = (iris.name, radius)
    if key not in _renders:
        _renders[key] = _render(iris, radius)
    return _renders[key]


_masks = {}


def _windows(iris, radius):
    """ Where the window shows at `radius`, as a mask """
    key = (iris.name, radius)
    if key not in _masks:
        _masks[key] = render(iris, radius) > 0.5
    return _masks[key]


def _render(iris, radius):
    texel = 2 * radius / SCALE / 64
    cx, cy = CENTRE
    matrix = np.float32([[texel, 0, (cx - radius) / SCALE], [0, texel, (cy - radius) / SCALE]])
    # Outside the square is the iris's solid colour
    return cv2.warpAffine(iris.window, matrix, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


@dataclass
class Verdict:
    iris: str
    # Each iris's score at its best start, and "fade", how bright the still-lit pixels stay
    scores: dict
    # When the winning iris started, in seconds before the centre went black
    started: float = 0


# Only frames where the window is this size tell the shapes apart: bigger, and every shape covers the screen; smaller,
# and the window is a blur of a few pixels
TELLING_RADII = (40, 240)
# The iris is the best fit only if its ring matches at least MIN_SCORE, and its score is this many times the next
# best's; otherwise it's unknown. Rings are a pixel or two wide at the quarter resolution, so even the right iris
# matches only part of each, and no iris's ring matched a fade or a cut above 0.08. Over the labelled recordings and
# greensuigi's and NoraSM64's runs, 91 transitions:
#   bowser  at least 1.73 times the next in the 7 deaths, and at most 0.32 elsewhere
#   mario   ahead of the circle in all 32 star exits, but by only 1.31 at least, as a head is roundish; calling one is
#           harmless, as an exit changes nothing
#   star and circle  at least 2.24 and 2.55 times the next, kept at 1.5 as a circle can mean a fall
MIN_SCORE = 0.1
MIN_RATIO = {"star": 1.5, "circle": 1.5, "mario": 1.1, "bowser": 1.25}


# The game goes black within a few frames of the iris's last frame: up to EARLY frames before it, as the capture's blur
# hides the last pixels of a closing window, and split detection judges once the centre is black, which over a dark
# stage is up to 4 frames before the game is (a death in BitFS), and up to LATE after it, as a head's iris holds a small
# window until the warp. Over the labelled recordings, judged as split detection does, 3 frames got 31 of 34 right and
# 5 frames 33, the one wrong a fade called Mario's head, which changes nothing; judged at every frame, 34 either way.
# The detection models other than AS64++ keep 0.8.0's 3, SHORT_EARLY.
EARLY, LATE = 5, 3
SHORT_EARLY = 3


@dataclass
class Looks:
    """ The looks at a transition, (time, brightness), stacked once for all the irises fitted to them """
    times: list
    time_array: np.ndarray
    brightness: np.ndarray
    black: np.ndarray
    lit: np.ndarray

    @classmethod
    def of(cls, looks):
        brightness = np.stack([b for _, b in looks])
        times = [t for t, _ in looks]
        return cls(times, np.array(times, np.float64), brightness, brightness < BLACK_LEVEL, brightness >= LIT)


_rings = {}


def _ring(iris, outer, inner):
    """ Where the window shows at radius `outer` and not at `inner`, besides the HUD, drawn once per pair """
    key = (iris.name, outer, inner)
    if key not in _rings:
        _rings[key] = _windows(iris, outer) & ~_windows(iris, inner) & (HUD > 0)
    return _rings[key]


def _sums(values):
    """ Each of the stacked arrays' sum, as each one's own sum() would add it up """
    return values.reshape(len(values), -1).sum(axis=1)


def fit(iris, looks, early_frames=EARLY):
    """
    The iris's best (score, seconds it started before the last look, ring score), from `looks`, a Looks, up to the
    game going black, at whatever times split detection looked. It starts its own length before the last look, give or
    take `early_frames` or LATE frames. Each look is scored two ways, multiplied:
    - Its ring: each game frame an iris blackens the ring between its last size and its new one, so how well the pixels
      that went black since the look before match the rings since then. The camera can move and the scene can be
      dark, but nothing else blackens those rings.
    - Its window: how well what's visible matches the window, against the looks just before the start. Lit now, or dim
      now in a scene that was dim: visible. Black now from anything but black: outside the window. Lit before and dim
      now: at the window's blurred edge, so it doesn't count, nor does black before and now, which could be either.
      Alone it barely tells the shapes apart, but always the right way, so it widens the rings' leads.
    Which looks count is decided look by look; what they show is worked out for all of them at once.
    """
    return _best_start(lambda early: _score_at(iris, looks, early), range(-LATE, early_frames + 1))


def _best_start(score, starts):
    """
    The best of score(start) over the starts, from every other one and then the neighbours of the best of those: a
    score rises and falls around the start that fits, so this finds its peak with 7 of 9 tries. Over the recordings'
    155 transitions it changed 8 scores, by 0.002 at most, and no verdict.
    """
    starts = list(starts)
    tried = {start: score(start) for start in starts[::2]}
    best = max(tried, key=tried.get)
    for start in (best - 1, best + 1):
        if start in starts and start not in tried:
            tried[start] = score(start)
    return max(tried.values())


def _score_at(iris, looks, early):
    """ fit() for the iris starting its own length before the last look, `early` frames early: (0, 0, 0) for none """
    times = looks.times
    hud = HUD > 0
    start = times[-1] - (iris.frames - 1 - early) / GAME_FPS
    # What was lit just before the iris: the looks in the tenth of a second before it, or the last one
    before_looks = [i for i, t in enumerate(times) if start - 0.1 <= t < start] or \
        [i for i, t in enumerate(times) if t < start][-1:]
    if not before_looks:
        return 0.0, 0.0, 0.0
    before = looks.brightness[before_looks].max(axis=0)
    # Each look from the start counts against the latest look a game frame or more before it, as a 60 fps video
    # shows each frame twice, but never one before the look just before the start
    first = int(np.searchsorted(looks.time_array, start, side="left"))
    indices = np.arange(first, len(times))
    latest = np.searchsorted(looks.time_array, looks.time_array[first:] - 0.9 / GAME_FPS, side="right") - 1
    previous_looks = np.maximum(np.minimum(latest, indices - 1), first - 1)
    # The iris's frames at both, rounded half to even as round() does
    frames = np.rint((looks.time_array[indices] - start) * GAME_FPS).astype(int)
    previous_frames = np.rint((looks.time_array[previous_looks] - start) * GAME_FPS).astype(int)
    radii = iris.radii[np.clip(frames, 0, iris.frames - 1)]
    keep = ((previous_frames >= 1) & (frames > previous_frames) & (frames <= iris.frames - 1)
            & (radii >= TELLING_RADII[0]) & (radii <= TELLING_RADII[1]))
    if keep.sum() < 3:
        return 0.0, 0.0, 0.0
    indices, previous_looks = indices[keep], previous_looks[keep]
    counted = list(zip(indices, previous_looks, frames[keep], previous_frames[keep]))

    # The rings the iris blackened since the last look, a game frame either side, as a capture can drop or
    # repeat a frame and the start can be a frame off
    ring = np.stack([_ring(iris, iris.radius(previous - 1), iris.radius(frame + 1)) for _, _, frame, previous in counted])
    went_black = ~looks.black[previous_looks] & looks.black[indices] & hud
    ring_union = np.count_nonzero(ring | went_black, axis=(1, 2))
    rings = [float(both / union) if union else 0.0
             for both, union in zip(np.count_nonzero(ring & went_black, axis=(1, 2)), ring_union)]

    # How much of what the window shows is visible, weighted by what counts: as visible and the weight are each
    # 0 or 1, the smaller of the two is the window where both are 1, and the larger is 1 where visible, else the window
    black, lit = looks.black[indices], looks.lit[indices]
    visible = lit | (~(before >= LIT) & ~black)
    weight = (visible | (black & ~(before < BLACK_LEVEL))) & hud
    expected = np.stack([render(iris, iris.radius(frame)) for _, _, frame, _ in counted])
    window_union = _sums(np.where(visible, np.float32(1), expected) * weight)
    windows = [float(shared / union) if union else 0.0
               for shared, union in zip(_sums(expected * (visible & weight)), window_union)]

    ring_score = float(np.mean(rings))
    return ring_score * float(np.mean(windows)), times[-1] - start, ring_score


def dimming(brightnesses, before):
    """
    How bright the pixels still lit are against before, in the middle of the transition: a plain fade to black
    (FADE_INTO_COLOR) darkens the whole screen together, while an iris leaves its window as bright as it was
    """
    ratios = []
    for brightness in brightnesses:
        lit = (brightness >= LIT) & (before >= LIT) & (HUD > 0)
        share = lit.sum() / max(((before >= LIT) & (HUD > 0)).sum(), 1)
        if 0.2 < share < 0.8:
            ratios.append(float(np.median(brightness[lit] / before[lit])))
    return float(np.median(ratios)) if ratios else 1.0


def classify(looks, early=EARLY):
    """
    The iris of a transition, from (time, brightness) of the looks up to the game going black, which can come `early`
    frames after the last: unknown when nothing fits well enough or far enough ahead. Also how much the still-lit pixels
    dimmed, against the first third of a second.
    """
    stacked = Looks.of(looks)
    fits = {iris.name: fit(iris, stacked, early) for iris in IRISES}
    scores = {name: score for name, (score, _, _) in fits.items()}
    first = [b for t, b in looks if t < looks[0][0] + 1 / 3]
    scores["fade"] = dimming([b for _, b in looks], np.max(first, axis=0))
    ranked = sorted((name for name in scores if name != "fade"), key=scores.get, reverse=True)
    best, second = ranked[0], ranked[1]
    started = fits[best][1]
    if fits[best][2] < MIN_SCORE or scores[best] < MIN_RATIO[best] * scores[second]:
        return Verdict("unknown", scores, started)
    return Verdict(best, scores, started)




def brightness_of(game):
    """ A look at the game region, as the matcher takes it: its brightest channel, at a quarter of the N64's resolution """
    return cv2.resize(game, (W, H), interpolation=cv2.INTER_AREA).max(axis=2).astype(np.float32)
