import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import db as db_module
from app.routes import api
from app.serializers import match_dict


class SavedClipsQueryTest(unittest.TestCase):
    def test_lists_only_saved_clips_with_match_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(db_module, "DB_PATH", Path(tmp) / "test.db"):
                db_module.init_db()
                match_id = db_module.create_match("APAV x MAC", "video.mp4")
                saved_id = db_module.add_clip(
                    match_id,
                    10.0,
                    18.0,
                    8.0,
                    "saved.mp4",
                    status="saved",
                )
                db_module.add_clip(
                    match_id,
                    30.0,
                    38.0,
                    8.0,
                    "new.mp4",
                    status="new",
                )
                rows = db_module.list_saved_clips()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["id"], saved_id)
                self.assertEqual(rows[0]["match_title"], "APAV x MAC")
                self.assertIn("match_video_path", rows[0].keys())


class MatchVideoAvailabilityTest(unittest.TestCase):
    def test_video_available_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"video")
            row = {
                "video_path": str(video),
                "calibration": None,
                "result": None,
            }
            self.assertTrue(match_dict(row)["video_available"])
            row["video_path"] = ""
            self.assertFalse(match_dict(row)["video_available"])


class RemoveMatchVideoTest(unittest.TestCase):
    def _row(self, video: Path, source: str = "upload") -> dict:
        return {
            "status": "done",
            "video_path": str(video),
            "source": source,
        }

    def test_uploaded_video_is_deleted_and_clips_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "video.mp4"
            video.write_bytes(b"video")
            row = self._row(video)
            with patch.object(api, "_require_match", return_value=row), patch.object(
                api, "list_clips", return_value=[object(), object()]
            ), patch.object(api, "update_match") as update, patch.object(
                api, "VIDEO_DIR", root
            ):
                result = api.remove_match_video(1, confirm=True)

            self.assertTrue(result["deleted"])
            self.assertEqual(result["saved_clips"], 2)
            self.assertFalse(video.exists())
            update.assert_called_once()
            fields = update.call_args.kwargs
            self.assertEqual(fields["video_path"], "")
            self.assertEqual(fields["status"], "done")

    def test_requires_confirmation(self):
        with self.assertRaises(HTTPException) as caught:
            api.remove_match_video(1, confirm=False)
        self.assertEqual(caught.exception.status_code, 400)

    def test_external_video_requires_extra_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"video")
            row = self._row(video, source="local")
            with patch.object(api, "_require_match", return_value=row), patch.object(
                api, "list_clips", return_value=[]
            ), patch.object(api, "update_match"):
                with self.assertRaises(HTTPException) as caught:
                    api.remove_match_video(1, confirm=True)
                self.assertEqual(caught.exception.status_code, 400)
                self.assertTrue(video.exists())

                result = api.remove_match_video(
                    1, confirm=True, allow_external=True
                )
                self.assertTrue(result["deleted"])
                self.assertFalse(video.exists())
