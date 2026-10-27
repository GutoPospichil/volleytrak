import json
import tempfile
import unittest
from pathlib import Path

from pipeline.points import build_points


class PointsStateMachineTest(unittest.TestCase):
    def test_builds_rally_and_ace_with_whistle_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "points.json"
            ball_records = []
            for index in range(301):
                t = round(index * 0.1, 2)
                x = 1.0 + (index % 100) * 0.12
                ball_records.append(
                    {
                        "frame": index,
                        "t": t,
                        "balls": [
                            {
                                "court": [min(18.0, x), 4.5],
                                "box": [100, 100, 110, 110],
                                "score": 0.9,
                            }
                        ],
                    }
                )
            contacts = [
                {"t": 2.0, "court": [1.0, 4.5], "score": 200.0},
                {"t": 3.0, "court": [8.0, 4.0], "score": 180.0},
                {"t": 4.0, "court": [10.0, 5.0], "score": 180.0},
                {"t": 5.0, "court": [12.0, 4.0], "score": 180.0},
                {"t": 15.0, "court": [17.0, 4.5], "score": 210.0},
            ]
            rallies = [
                {"start": 1.0, "end": 8.0, "whistle_start": 1.2, "whistle_end": 8.0},
                {"start": 14.0, "end": 18.0, "whistle_start": 14.2, "whistle_end": 18.0},
            ]
            activity = {
                "samples": [
                    {"t": float(t), "motion": 8.0} for t in range(0, 31)
                ]
            }
            profile = {"trim": {"pre_roll": 3.0, "post_roll": 2.0}}

            points = build_points(
                1,
                ball_records,
                contacts,
                rallies,
                activity,
                profile,
                output,
            )

            self.assertEqual(len(points), 2)
            self.assertEqual(points[0]["point_type"], "rally")
            self.assertEqual(points[1]["point_type"], "serve")
            self.assertLessEqual(points[0]["start"], 2.0)
            self.assertGreater(points[0]["end"], 6.0)
            self.assertEqual(points[1]["serve_time"], 15.0)
            self.assertTrue(output.is_file())
            self.assertGreater(points[1]["agreement"], 0)
            for previous, current in zip(points, points[1:]):
                self.assertLessEqual(previous["end"], current["start"])

    def test_contact_gap_creates_anchor_without_whistle(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "points.json"
            ball_records = [
                {
                    "t": round(index * 0.5, 1),
                    "balls": [{"court": [9.0, 4.5], "score": 0.9}],
                }
                for index in range(0, 80)
            ]
            contacts = [
                {"t": 5.0, "court": [9.0, 4.5], "score": 180.0},
                {"t": 20.0, "court": [9.0, 4.5], "score": 180.0},
            ]
            points = build_points(
                1,
                ball_records,
                contacts,
                [],
                None,
                {"trim": {"pre_roll": 3.0, "post_roll": 2.0}},
                output,
            )
            self.assertEqual(len(points), 2)
            self.assertTrue(all(point["source"] == "point" for point in points))
            self.assertLess(points[0]["start"], points[0]["serve_time"])
            self.assertLess(points[0]["end"], points[1]["start"])
