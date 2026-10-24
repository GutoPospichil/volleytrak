import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db as db_module


class LearningDatabaseTest(unittest.TestCase):
    def test_backfill_upsert_remove_and_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch.object(db_module, "DB_PATH", db_path):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                db_module.add_clip(
                    match_id,
                    10.0,
                    20.0,
                    10.0,
                    "good.mp4",
                    status="saved",
                    source="audio",
                    features={"ball_pct": 0.5, "score": 80.0},
                )
                db_module.add_clip_rejection(
                    match_id,
                    30.0,
                    40.0,
                    reason="dead_time",
                    features={"ball_pct": 0.05, "score": 50.0},
                )
                imported = db_module.backfill_learning_examples()
                self.assertEqual(imported, 2)
                stats = db_module.learning_stats()
                self.assertEqual(stats["total"], 2)
                self.assertEqual(stats["good"], 1)
                self.assertEqual(stats["bad"], 1)
                self.assertEqual(stats["reasons"]["dead_time"], 1)

                db_module.upsert_learning_example(
                    match_id,
                    30.0,
                    40.0,
                    "good",
                    source="contact",
                    features={"ball_pct": 0.4, "score": 70.0},
                    weight=2.0,
                )
                stats = db_module.learning_stats()
                self.assertEqual(stats["total"], 2)
                self.assertEqual(stats["good"], 2)
                self.assertEqual(stats["bad"], 0)

                db_module.remove_learning_example(match_id, 10.0, 20.0)
                self.assertEqual(db_module.learning_stats()["total"], 1)
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db as db_module
from pipeline.ranker import load_training_data


class RankerDatasetTest(unittest.TestCase):
    def test_trains_from_learning_examples_with_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch.object(db_module, "DB_PATH", db_path):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                db_module.upsert_learning_example(
                    match_id,
                    10.0,
                    20.0,
                    "good",
                    source="audio",
                    features={"ball_pct": 0.6, "score": 80.0, "duration": 10.0},
                    weight=2.0,
                )
                db_module.upsert_learning_example(
                    match_id,
                    30.0,
                    40.0,
                    "bad",
                    reason="dead_time",
                    source="speed",
                    features={"ball_pct": 0.05, "score": 45.0, "duration": 10.0},
                    weight=1.2,
                )
                x, y, weights = load_training_data()
                self.assertEqual(x.shape, (2, 7))
                self.assertEqual(sorted(y.tolist()), [0.0, 1.0])
                self.assertEqual(sorted(weights.tolist()), [1.2, 2.0])
