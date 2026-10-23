import unittest

from tests import replay


class RecordingsTest(unittest.TestCase):
    def test_every_recording_without_the_iris_labels(self):
        # Downloading them stopped at irises.json, before the recordings after it
        names = [recording.name for recording in replay.recordings()]
        self.assertIn("ronc3na_70_star", names)
        self.assertNotIn("irises", names)


if __name__ == "__main__":
    unittest.main()
