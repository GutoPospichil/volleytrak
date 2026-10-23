import unittest

from pipeline.clip_score import score_clip


class ClipScoreTest(unittest.TestCase):
    def test_scores_saved_clip(self):
        clip = {
            "id": 1,
            "start": 0.0,
            "end": 10.0,
            "duration": 10.0,
            "score": 80.0,
            "source": "audio",
            "starred": 0,
            "features": '{"ball_pct": 0.4, "max_speed": 18.0, "contacts": 4}',
        }
        quality, features = score_clip(clip, [], [], [])
        self.assertGreaterEqual(quality, 0.0)
        self.assertLessEqual(quality, 100.0)
        self.assertEqual(features["source"], "audio")

        clip["starred"] = 1
        starred_quality, _ = score_clip(clip, [], [], [])
        self.assertGreaterEqual(starred_quality, quality)
