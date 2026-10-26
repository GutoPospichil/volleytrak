import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import clip_paths
from app import db as db_module


class SettingsTest(unittest.TestCase):
    def test_set_get_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(db_module, "DB_PATH", Path(tmp) / "test.db"):
                db_module.init_db()
                self.assertIsNone(db_module.get_setting("clip_output_dir"))
                db_module.set_setting("clip_output_dir", r"D:\Clipes")
                self.assertEqual(db_module.get_setting("clip_output_dir"), r"D:\Clipes")
                db_module.set_setting("clip_output_dir", r"E:\Clipes")
                self.assertEqual(db_module.get_setting("clip_output_dir"), r"E:\Clipes")
                db_module.delete_setting("clip_output_dir")
                self.assertIsNone(db_module.get_setting("clip_output_dir"))


class ClipPathsTest(unittest.TestCase):
    def test_default_and_configured_clip_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(db_module, "DB_PATH", root / "test.db"), patch.object(
                clip_paths, "JOB_DIR", root / "jobs"
            ):
                db_module.init_db()
                self.assertEqual(
                    clip_paths.clip_dir_for_match(4),
                    root / "jobs" / "match-4" / "clips",
                )
                db_module.set_setting("clip_output_dir", str(root / "saida"))
                self.assertEqual(
                    clip_paths.clip_dir_for_match(4),
                    root / "saida" / "match-4",
                )

    def test_actual_folder_uses_existing_clip_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(db_module, "DB_PATH", root / "test.db"), patch.object(
                clip_paths, "JOB_DIR", root / "jobs"
            ):
                db_module.init_db()
                match_id = db_module.create_match("Teste", "video.mp4")
                folder = root / "clipes"
                folder.mkdir()
                for index in range(3):
                    db_module.add_clip(
                        match_id,
                        index * 10.0,
                        index * 10.0 + 5.0,
                        5.0,
                        str(folder / f"clip-{index}.mp4"),
                    )
                self.assertEqual(clip_paths.clip_folder_for_match(match_id), folder)
