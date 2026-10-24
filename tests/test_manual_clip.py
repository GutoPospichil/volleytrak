import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app import db as db_module
from app.schemas import ManualClipIn


class ManualClipSchemaTest(unittest.TestCase):
    def test_accepts_valid_range(self):
        payload = ManualClipIn(start=10.0, end=25.5)
        self.assertAlmostEqual(payload.end - payload.start, 15.5)

    def test_rejects_inverted_range(self):
        with self.assertRaises(ValidationError):
            ManualClipIn(start=30.0, end=20.0)

    def test_rejects_too_long_range(self):
        with self.assertRaises(ValidationError):
            ManualClipIn(start=0.0, end=200.0)


class ClearClipsTest(unittest.TestCase):
    def test_manual_new_clip_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch.object(db_module, "DB_PATH", db_path):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                db_module.add_clip(
                    match_id, 10.0, 20.0, 10.0, "normal.mp4", source="speed"
                )
                manual_id = db_module.add_clip(
                    match_id, 30.0, 40.0, 10.0, "manual.mp4", source="manual"
                )
                cleared = db_module.clear_unreviewed_clips(match_id)
                self.assertEqual(len(cleared), 1)
                self.assertEqual(cleared[0]["source"], "speed")
                self.assertIsNotNone(db_module.get_clip(manual_id))
