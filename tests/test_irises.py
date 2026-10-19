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


if __name__ == "__main__":
    unittest.main()
