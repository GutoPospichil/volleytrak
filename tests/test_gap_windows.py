import math
import unittest

from pipeline.clips import find_clip_gaps, gap_windows, recovered_windows


def records_for(duration=120):
    return [
        {
            "t": float(t),
            "balls": [{"court": [9.0 + 4.0 * math.sin(t / 3.0), 4.5], "score": 0.9}],
        }
        for t in range(duration + 1)
    ]


def contacts_at(times):
    return [
        {"t": float(t), "court": [9.0, 4.5], "speed": 3.0, "turn_deg": 90.0, "accel": 10.0, "score": 200.0}
        for t in times
    ]


class GapWindowsTest(unittest.TestCase):
    def test_finds_long_gap_between_clips(self):
        clips = [
            {"start": 0.0, "end": 30.0, "status": "saved"},
            {"start": 90.0, "end": 120.0, "status": "new"},
        ]
        gaps = find_clip_gaps(clips, 120.0)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["start"], 30.0)
        self.assertEqual(gaps[0]["end"], 90.0)

    def test_gap_windows_stay_inside_gap(self):
        gaps = [{"start": 30.0, "end": 90.0, "duration": 60.0}]
        windows = gap_windows(
            gaps,
            contacts_at([40, 42, 44, 70, 72, 74]),
            records_for(),
            120.0,
            max_total=10,
        )
        self.assertEqual(len(windows), 2)
        for window in windows:
            self.assertEqual(window["source"], "gap")
            self.assertTrue(window["gap"])
            self.assertGreaterEqual(window["start"], 30.0)
            self.assertLessEqual(window["end"], 90.0)

    def test_gap_windows_returns_empty_without_gaps(self):
        self.assertEqual(gap_windows([], contacts_at([40]), records_for(), 120.0), [])


class RecoveredWindowsTest(unittest.TestCase):
    def test_expands_bad_cut_with_learned_padding(self):
        rejections = [
            {"start": 40.0, "end": 50.0, "reason": "bad_cut", "detail": "start_late"}
        ]
        windows = recovered_windows(
            rejections,
            records_for(),
            [42.0, 46.0],
            120.0,
            pre_roll=2.5,
            post_roll=1.5,
        )
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["source"], "recovered")
        self.assertAlmostEqual(windows[0]["start"], 37.5)
        self.assertAlmostEqual(windows[0]["end"], 50.0)

    def test_ignores_other_rejection_reasons(self):
        rejections = [
            {"start": 40.0, "end": 50.0, "reason": "dead_time", "detail": ""}
        ]
        self.assertEqual(
            recovered_windows(
                rejections, records_for(), [], 120.0, pre_roll=2.5, post_roll=1.5
            ),
            [],
        )
