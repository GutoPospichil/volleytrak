import unittest

from pipeline.events import derive_touches


class TouchDerivationTest(unittest.TestCase):
    def test_deduplicates_same_track(self):
        candidates = [
            {"t": 1.0, "track_id": 1},
            {"t": 1.2, "track_id": 1},
            {"t": 1.9, "track_id": 1},
        ]
        touches = derive_touches(candidates)
        self.assertEqual([touch["t"] for touch in touches], [1.0, 1.9])

    def test_keeps_different_tracks(self):
        candidates = [
            {"t": 1.0, "track_id": 1},
            {"t": 1.4, "track_id": 2},
            {"t": 2.0, "track_id": 3},
        ]
        touches = derive_touches(candidates)
        self.assertEqual(len(touches), 3)

    def test_ignores_missing_track(self):
        touches = derive_touches([{"t": 1.0, "track_id": None}])
        self.assertEqual(touches, [])


if __name__ == "__main__":
    unittest.main()
