import json
import tempfile
import unittest
from pathlib import Path

from pipeline.ball_track import track_ball


class BallTrackTest(unittest.TestCase):
    def test_smooths_track_interpolates_short_gap_and_rejects_outlier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "ball.jsonl"
            output_path = root / "ball_track.jsonl"
            records = []
            for index in range(40):
                t = round(index * 0.1, 2)
                if 15 <= index <= 17:
                    records.append({"frame": index, "t": t, "balls": []})
                    continue
                x = round(1.0 + index * 0.15, 3)
                if index == 20:
                    x = 17.0  # outlier
                records.append(
                    {
                        "frame": index,
                        "t": t,
                        "balls": [
                            {
                                "center": [x * 10, 100],
                                "box": [x * 10 - 5, 95, x * 10 + 5, 105],
                                "score": 0.9,
                                "court": [x, 4.5],
                            }
                        ],
                    }
                )
            input_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            result = track_ball(1, input_path, output_path)

            self.assertGreater(result["frames_with_ball"], 20)
            self.assertGreater(result["interpolated"], 0)
            self.assertGreaterEqual(result["tracks_confirmed"], 1)
            tracked = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(tracked), len(records))
            outlier = tracked[20]["balls"]
            if outlier:
                self.assertLess(outlier[0]["court"][0], 8.0)
            gap = [record for record in tracked if 1.5 <= record["t"] <= 1.7]
            self.assertTrue(any(record["balls"] for record in gap))
