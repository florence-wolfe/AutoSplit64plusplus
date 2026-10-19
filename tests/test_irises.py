import unittest

import numpy as np

from autosplit64.core import irises


def closing(iris, after=0.0, fps=30):
    """
    Looks at an iris closing over a lit, textured scene, drawn as the game draws it: half a second of the scene, then
    the iris frame by frame on its schedule, then black, as (time, brightness)
    """
    rng = np.random.default_rng(1)
    scene = rng.uniform(60, 220, (irises.H, irises.W)).astype(np.float32)
    looks = [(t / fps, scene) for t in range(round(0.5 * fps))]
    start = 0.5
    for n in range(round((iris.frames / irises.GAME_FPS + after) * fps)):
        time = start + n / fps
        frame = min(round((time - start) * irises.GAME_FPS), iris.frames - 1)
        looks.append((time, scene * irises.render(iris, iris.radius(frame))))
    looks.append((looks[-1][0] + 1 / fps, np.zeros_like(scene)))
    return looks


class ClassifyTest(unittest.TestCase):
    def test_each_iris_is_told_from_the_others(self):
        for iris in irises.IRISES:
            with self.subTest(iris.name):
                self.assertEqual(irises.classify(closing(iris)).iris, iris.name)

    def test_from_looks_at_a_60_fps_capture(self):
        bowser = next(iris for iris in irises.IRISES if iris.name == "bowser")
        self.assertEqual(irises.classify(closing(bowser, fps=60)).iris, "bowser")

    def test_a_plain_fade_is_no_iris(self):
        rng = np.random.default_rng(1)
        scene = rng.uniform(60, 220, (irises.H, irises.W)).astype(np.float32)
        looks = [(n / 30, scene * max(0.0, 1 - max(0, n - 15) / 20)) for n in range(60)]
        self.assertEqual(irises.classify(looks).iris, "unknown")


def reference_fit(iris, looks, early_frames=irises.EARLY):
    """ fit() as it was written look by look, before it worked out every look's pixels at once: what it must equal """
    from autosplit64.core.irises import BLACK_LEVEL, GAME_FPS, HUD, LATE, LIT, TELLING_RADII, _windows, render

    def observe(brightness, before):
        lit, black = brightness >= LIT, brightness < BLACK_LEVEL
        lit_before, black_before = before >= LIT, before < BLACK_LEVEL
        visible = lit | (~lit_before & ~black)
        outside = black & ~black_before
        return visible.astype(np.float32), (visible | outside).astype(np.float32) * HUD

    def overlap(expected, visible, weight):
        union = (np.maximum(expected, visible) * weight).sum()
        return float((np.minimum(expected, visible) * weight).sum() / union) if union else 0.0

    times = [time for time, _ in looks]
    best = (0.0, 0.0, 0.0)
    for early in range(-LATE, early_frames + 1):
        start = times[-1] - (iris.frames - 1 - early) / GAME_FPS
        before_looks = [b for t, b in looks if start - 0.1 <= t < start] or [b for t, b in looks if t < start][-1:]
        if not before_looks:
            continue
        before = np.max(before_looks, axis=0)
        rings, windows = [], []
        previous_look = None
        for index, (time, brightness) in enumerate(looks):
            if time < start:
                continue
            while previous_look is None or (previous_look + 1 < index and times[previous_look + 1] <= time - 0.9 / GAME_FPS):
                previous_look = index - 1 if previous_look is None else previous_look + 1
            frame = round((time - start) * GAME_FPS)
            previous = round((times[previous_look] - start) * GAME_FPS)
            if previous < 1 or frame <= previous or frame > iris.frames - 1:
                continue
            radius = iris.radius(frame)
            if not TELLING_RADII[0] <= radius <= TELLING_RADII[1]:
                continue
            ring = _windows(iris, iris.radius(previous - 1)) & ~_windows(iris, iris.radius(frame + 1)) & (HUD > 0)
            went_black = (looks[previous_look][1] >= BLACK_LEVEL) & (brightness < BLACK_LEVEL) & (HUD > 0)
            union = (ring | went_black).sum()
            rings.append(float((ring & went_black).sum() / union) if union else 0.0)
            windows.append(overlap(render(iris, radius), *observe(brightness, before)))
        if len(rings) >= 3:
            ring = float(np.mean(rings))
            best = max(best, (ring * float(np.mean(windows)), times[-1] - start, ring))
    return best


class FitTest(unittest.TestCase):
    """ fit() works out every look's pixels at once, for speed, and must score exactly as look by look """

    def cases(self):
        rng = np.random.default_rng(2)
        for iris in irises.IRISES:
            yield f"{iris.name} at 30 fps", closing(iris)
            yield f"{iris.name} at 60 fps", closing(iris, fps=60)
            yield f"{iris.name} every other look", closing(iris, fps=60)[::2]
            yield f"{iris.name} every fifth look", closing(iris, fps=60)[::5]
            # A dark stage: patches already black before the iris, and the rest dim
            dark = [(t, b * np.where(rng.uniform(size=b.shape) < 0.3, 0.02, 0.4).astype(np.float32))
                    for t, b in closing(iris, after=0.1)]
            yield f"{iris.name} over a dark stage", dark
        scene = rng.uniform(60, 220, (irises.H, irises.W)).astype(np.float32)
        yield "a plain fade", [(n / 30, scene * max(0.0, 1 - max(0, n - 15) / 20)) for n in range(60)]

    def test_scores_exactly_as_look_by_look(self):
        for name, looks in self.cases():
            stacked = irises.Looks.of(looks)
            for iris in irises.IRISES:
                for early in (irises.SHORT_EARLY, irises.EARLY):
                    with self.subTest(name, iris=iris.name, early=early):
                        self.assertEqual(irises.fit(iris, stacked, early), reference_fit(iris, looks, early))


if __name__ == "__main__":
    unittest.main()
