import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app import db as db_module
from app.schemas import ClipEditIn
from pipeline import feedback as feedback_module


class ClipEditSchemaTest(unittest.TestCase):
    def test_accepts_extension(self):
        payload = ClipEditIn(start=10.0, end=25.0, save=True)
        self.assertAlmostEqual(payload.end - payload.start, 15.0)

    def test_rejects_inverted_range(self):
        with self.assertRaises(ValidationError):
            ClipEditIn(start=30.0, end=20.0)

    def test_rejects_too_short(self):
        with self.assertRaises(ValidationError):
            ClipEditIn(start=10.0, end=10.5)


class ClipEditDatabaseTest(unittest.TestCase):
    def test_records_edit_and_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch.object(db_module, "DB_PATH", db_path):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                clip_id = db_module.add_clip(
                    match_id, 10.0, 20.0, 10.0, "clip.mp4", score=70.0
                )
                db_module.add_clip_edit(
                    match_id,
                    clip_id,
                    10.0,
                    20.0,
                    8.0,
                    21.0,
                    old_score=70.0,
                    new_score=82.0,
                    score_delta=12.0,
                    start_delta=-2.0,
                    end_delta=1.0,
                    reason="bad_cut",
                    detail="both",
                    features={"ball_pct": 0.4, "score": 70.0},
                )
                stats = db_module.clip_edit_stats()
                self.assertEqual(stats["total"], 1)
                self.assertEqual(stats["improved"], 1)
                self.assertAlmostEqual(stats["avg_start_delta"], -2.0)
                self.assertAlmostEqual(stats["avg_end_delta"], 1.0)
                recent = db_module.list_recent_clip_edits(5)
                self.assertEqual(len(recent), 1)
                self.assertEqual(recent[0]["clip_id"], clip_id)


class ClipEditProfileTest(unittest.TestCase):
    def test_bad_cut_edit_increases_pre_roll(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.db"
            job_dir = root / "jobs"
            with patch.object(db_module, "DB_PATH", db_path), patch.object(
                feedback_module, "JOB_DIR", job_dir
            ):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                for index in range(3):
                    clip_id = db_module.add_clip(
                        match_id,
                        10.0 + index * 30,
                        20.0 + index * 30,
                        10.0,
                        f"clip-{index}.mp4",
                    )
                    db_module.add_clip_edit(
                        match_id,
                        clip_id,
                        10.0 + index * 30,
                        20.0 + index * 30,
                        8.0 + index * 30,
                        20.0 + index * 30,
                        old_score=70.0,
                        new_score=80.0,
                        score_delta=10.0,
                        start_delta=-2.0,
                        end_delta=0.0,
                        reason="bad_cut",
                        detail="start_late",
                        features={"ball_pct": 0.4, "score": 70.0},
                    )
                profile = feedback_module.build_profile_for_match(match_id)
                self.assertGreater(profile["trim"]["pre_roll"], 2.5)
