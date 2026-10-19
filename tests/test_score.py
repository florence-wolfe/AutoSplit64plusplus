import json
import tempfile
import unittest
from pathlib import Path

from tests import score
from tests.score import Event


class ParseTraceTest(unittest.TestCase):
    def test_events_from_the_trace_lines_detection_logs_them_in(self):
        trace = [
            "0.000 Started: route greensuigi 16 Star No LBLJ",
            "4.133 Reset the timer: split 1 of 12, BOB 1 (needs 1 stars, fadeout 1, fade-in 0), star count 0",
            "65.700 Fadeout 1: split 1 of 12, BOB 1 (needs 1 stars, fadeout 1, fade-in 0), star count 0",
            "78.067 Fade-in 1: split 1 of 12, BOB 1 (needs 1 stars, fadeout 1, fade-in 0), star count 0",
            "94.267 Star count 0 -> 1, prediction 1 at 0.99",
            "100.000 Death, Bowser's iris, fadeouts 3 -> 1",
            "361.867 Grand Star grabbed",
            "362.000 Running ProcessReset",
        ]
        self.assertEqual(score.parse_trace(trace), [
            Event("reset", 4.133), Event("fadeout", 65.7), Event("fade_in", 78.067), Event("star_grab", 94.267),
            Event("death", 100.0), Event("grand_star", 361.867)])

    def test_only_a_star_count_going_up_by_one_is_a_star_grab(self):
        # Down is a correction, and a jump is detection finding its place, e.g. starting mid-run
        for message in ("Star count 3 -> 2, prediction 2 at 0.95", "Star count 0 -> 16, prediction 16 at 0.99"):
            with self.subTest(message):
                self.assertEqual(score.parse_trace([f"10.000 {message}"]), [])


class ScoreTest(unittest.TestCase):
    def test_matches_each_event_to_the_nearest_of_its_type_within_the_tolerance(self):
        labelled = [Event("fadeout", 10.0), Event("fadeout", 20.0), Event("death", 30.0)]
        detected = [Event("fadeout", 10.1), Event("fadeout", 20.4), Event("death", 31.0)]
        result = score.score(detected, labelled, tolerance=0.5)
        self.assertEqual((result["fadeout"].found, result["fadeout"].missed, result["fadeout"].extra), (2, 0, 0))
        self.assertEqual([round(error, 3) for error in result["fadeout"].errors], [0.1, 0.4])
        # Out of tolerance is a miss and an extra, not a match
        self.assertEqual((result["death"].found, result["death"].missed, result["death"].extra), (0, 1, 1))

    def test_an_event_matches_only_one_label(self):
        result = score.score([Event("fadeout", 10.0)], [Event("fadeout", 9.9), Event("fadeout", 10.2)], tolerance=0.5)
        self.assertEqual((result["fadeout"].found, result["fadeout"].missed, result["fadeout"].extra), (1, 1, 0))
        # The nearer label matched
        self.assertEqual([round(error, 3) for error in result["fadeout"].errors], [0.1])

    def test_an_event_type_is_scored_separately(self):
        result = score.score([Event("fade_in", 10.0)], [Event("fadeout", 10.0)], tolerance=0.5)
        self.assertEqual((result["fadeout"].found, result["fadeout"].missed), (0, 1))
        self.assertEqual((result["fade_in"].found, result["fade_in"].extra), (0, 1))

    def test_precision_and_recall(self):
        result = score.score([Event("fadeout", 10.0), Event("fadeout", 50.0)], [Event("fadeout", 10.0), Event("fadeout", 20.0), Event("fadeout", 30.0)], tolerance=0.5)
        fadeout = result["fadeout"]
        self.assertEqual((fadeout.found, fadeout.missed, fadeout.extra), (1, 2, 1))
        self.assertAlmostEqual(fadeout.recall, 1 / 3)
        self.assertAlmostEqual(fadeout.precision, 1 / 2)

    def test_only_events_inside_the_scored_range_count(self):
        labelled = [Event("fadeout", 5.0), Event("fadeout", 15.0)]
        detected = [Event("fadeout", 5.0), Event("fadeout", 15.0)]
        result = score.score(detected, labelled, tolerance=0.5, start=10, end=20)
        self.assertEqual((result["fadeout"].found, result["fadeout"].missed, result["fadeout"].extra), (1, 0, 0))

    def test_only_the_given_types_are_scored(self):
        result = score.score([Event("fadeout", 10.0), Event("death", 11.0)], [Event("fadeout", 10.0)], tolerance=0.5, types=["fadeout"])
        self.assertEqual(list(result), ["fadeout"])
        self.assertEqual((result["fadeout"].found, result["fadeout"].extra), (1, 0))

    def test_no_precision_or_recall_without_events(self):
        result = score.score([], [Event("key_grab", 10.0)], tolerance=0.5)
        self.assertEqual(result["key_grab"].recall, 0)
        self.assertIsNone(result["key_grab"].precision)
        self.assertIsNone(result["fadeout"].recall)


class LabelFileTest(unittest.TestCase):
    def test_loads_the_events_of_a_label_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps({"reviewed": True, "mode": "run", "start": 0, "end": 100,
                                        "events": [{"event": "death", "time": 5.5}, {"event": "fadeout", "time": 3.0}]}))
            labels = score.load_labels(path)
        self.assertTrue(labels.reviewed)
        self.assertEqual((labels.start, labels.end), (0, 100))
        # Every type, unless the file says which it labels
        self.assertEqual(labels.types, list(score.EVENTS))
        self.assertEqual(labels.events, [Event("fadeout", 3.0), Event("death", 5.5)])

    def test_a_label_file_says_which_types_it_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps({"reviewed": True, "mode": "ending", "start": 0, "end": 1, "types": ["grand_star"], "events": []}))
            self.assertEqual(score.load_labels(path).types, ["grand_star"])
            path.write_text(json.dumps({"reviewed": True, "mode": "ending", "start": 0, "end": 1, "types": ["nap"], "events": []}))
            with self.assertRaisesRegex(ValueError, "nap"):
                score.load_labels(path)

    def test_an_unknown_event_type_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps({"reviewed": False, "mode": "run", "start": 0, "end": 1, "events": [{"event": "nap", "time": 0}]}))
            with self.assertRaisesRegex(ValueError, "nap"):
                score.load_labels(path)


if __name__ == "__main__":
    unittest.main()
