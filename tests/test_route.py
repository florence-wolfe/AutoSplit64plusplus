import unittest

from autosplit64.core.route import Route, Split


class RouteTest(unittest.TestCase):
    def test_identical_splits_are_told_apart(self):
        # Split detection finds the current split with list.index
        first, second = Split("Mips", 15), Split("Mips", 15)
        route = Route("route.as64", "Route", [first, second])
        self.assertEqual(route.splits.index(second), 1)

    def test_length_follows_splits(self):
        route = Route("route.as64", "Route", [Split("BoB", 1)])
        route.insert_split(1)
        self.assertEqual(route.length, 2)
        route.remove_split(0)
        self.assertEqual(route.length, 1)

    def test_defaults(self):
        route = Route("route.as64", "Route", [Split()])
        self.assertEqual((route.initial_star, route.version, route.category, route.timing), (0, "JP", "", "RTA"))
        split = route.splits[0]
        self.assertEqual((split.title, split.star_count, split.on_fadeout, split.on_fadein, split.on_xcam, split.split_type, split.icon_path),
                         ("", 0, 0, 0, -1, "Normal", None))


if __name__ == "__main__":
    unittest.main()
