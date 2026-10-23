import unittest

from app.timeline import build_timeline


class TimelineTest(unittest.TestCase):
    def test_coverage_and_gaps(self):
        clips = [
            {"start": 0, "end": 30, "status": "new"},
            {"start": 60, "end": 90, "status": "saved"},
            {"start": 240, "end": 300, "status": "saved"},
        ]
        timeline = build_timeline(clips, duration=300, bin_seconds=60)
        self.assertEqual(len(timeline["bins"]), 5)
        self.assertEqual(timeline["coverage_pct"], 40.0)
        self.assertEqual(len(timeline["gaps"]), 1)
        self.assertEqual(timeline["gaps"][0]["start"], 90)
        self.assertEqual(timeline["gaps"][0]["duration"], 150)
        self.assertTrue(timeline["bins"][1]["has_saved"])
