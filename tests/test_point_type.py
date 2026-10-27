import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db as db_module
from app.constants import learning_example_weight
from app.routes import api
from app.schemas import ClipStatusIn


class PointTypeWeightTest(unittest.TestCase):
    def test_rally_is_the_default_weight(self):
        self.assertEqual(learning_example_weight("good"), 1.0)
        self.assertEqual(learning_example_weight("good", starred=True), 2.0)

    def test_serve_has_a_lower_weight(self):
        self.assertEqual(learning_example_weight("good", point_type="serve"), 0.7)
        self.assertEqual(
            learning_example_weight("good", starred=True, point_type="serve"),
            1.4,
        )

    def test_unwanted_serve_point_is_a_weak_negative(self):
        self.assertEqual(learning_example_weight("bad", "serve_point"), 0.3)


class SavePointTypeTest(unittest.TestCase):
    def test_saving_as_serve_keeps_clip_and_lowers_weight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(db_module, "DB_PATH", root / "test.db"), patch.object(
                api, "JOB_DIR", root / "jobs"
            ):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                clip_id = db_module.add_clip(
                    match_id, 10.0, 18.0, 8.0, "clip.mp4", status="new"
                )

                result = api.update_clip_status(
                    clip_id,
                    ClipStatusIn(status="saved", point_type="serve"),
                )

                self.assertEqual(result["point_type"], "serve")
                clip = db_module.get_clip(clip_id)
                self.assertEqual(clip["status"], "saved")
                self.assertEqual(clip["point_type"], "serve")

                with db_module.db() as conn:
                    example = conn.execute(
                        "SELECT * FROM learning_examples WHERE match_id = ?",
                        (match_id,),
                    ).fetchone()
                self.assertIsNotNone(example)
                self.assertEqual(example["label"], "good")
                self.assertAlmostEqual(example["weight"], 0.7)
                features = json.loads(example["features"])
                self.assertEqual(features["point_type"], "serve")

    def test_returning_to_new_preserves_point_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(db_module, "DB_PATH", root / "test.db"), patch.object(
                api, "JOB_DIR", root / "jobs"
            ):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                clip_id = db_module.add_clip(
                    match_id,
                    10.0,
                    18.0,
                    8.0,
                    "clip.mp4",
                    status="new",
                    point_type="serve",
                )
                api.update_clip_status(
                    clip_id, ClipStatusIn(status="new")
                )
                clip = db_module.get_clip(clip_id)
                self.assertEqual(clip["status"], "new")
                self.assertEqual(clip["point_type"], "serve")
