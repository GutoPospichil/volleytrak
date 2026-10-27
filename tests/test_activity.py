import json
import tempfile
import unittest
from pathlib import Path

from pipeline.activity import court_mask, filter_windows, load_activity


class ActivityFilterTest(unittest.TestCase):
    def test_drops_empty_court_and_keeps_active_window(self):
        activity = {
            "samples": [
                *({"t": float(t), "motion": 0.5} for t in range(0, 11)),
                *({"t": float(t), "motion": 10.0} for t in range(20, 31)),
            ]
        }
        windows = [
            {"start": 0.0, "end": 10.0, "duration": 10.0},
            {"start": 20.0, "end": 30.0, "duration": 10.0},
        ]
        kept, dropped = filter_windows(windows, activity, min_mean=4.0)
        self.assertEqual(dropped, 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["start"], 20.0)
        self.assertEqual(kept[0]["activity_mean"], 10.0)

    def test_keeps_window_without_activity_samples(self):
        windows = [{"start": 40.0, "end": 50.0, "duration": 10.0}]
        kept, dropped = filter_windows(
            windows,
            {"samples": [{"t": 1.0, "motion": 10.0}]},
            min_mean=4.0,
        )
        self.assertEqual(dropped, 0)
        self.assertEqual(kept, windows)

    def test_keeps_point_window_even_with_low_activity(self):
        activity = {
            "samples": [{"t": float(t), "motion": 0.5} for t in range(0, 11)]
        }
        windows = [
            {
                "start": 0.0,
                "end": 10.0,
                "duration": 10.0,
                "source": "point",
            }
        ]
        kept, dropped = filter_windows(windows, activity, min_mean=4.0)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(kept), 1)

    def test_missing_activity_keeps_all(self):
        windows = [{"start": 0.0, "end": 10.0, "duration": 10.0}]
        kept, dropped = filter_windows(windows, None)
        self.assertEqual(dropped, 0)
        self.assertEqual(kept, windows)

    def test_load_activity_accepts_legacy_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "activity.json"
            path.write_text(json.dumps([{"t": 1.0, "motion": 2.0}]), encoding="utf-8")
            payload = load_activity(path)
            self.assertEqual(payload["samples"][0]["motion"], 2.0)

    def test_court_mask_has_pixels(self):
        mask = court_mask([[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]], 100, 100)
        self.assertGreater(int(mask.sum()), 1000)
