import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.routes import api


class ReprocessMatchTest(unittest.TestCase):
    def _match_row(self, tmp: str) -> dict:
        video = Path(tmp) / "video.mp4"
        video.write_bytes(b"video")
        return {
            "status": "done",
            "video_path": str(video),
            "calibration": '{"mode": "full", "points": []}',
        }

    def test_reprocess_without_whistle_starts_reuse_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self._match_row(tmp)
            with patch.object(api, "JOB_DIR", Path(tmp) / "jobs"), patch.object(
                api, "_require_match", return_value=row
            ), patch.object(api, "update_match") as update, patch.object(
                api, "popen_hidden"
            ) as popen:
                result = api.reprocess_match(7, "without")

        self.assertTrue(result["ok"])
        self.assertEqual(result["whistle_mode"], "without")
        update.assert_called_once()
        fields = update.call_args.kwargs
        self.assertEqual(fields["whistle_mode"], "without")
        self.assertEqual(fields["status"], "processing")
        command = popen.call_args.args[0]
        self.assertIn("pipeline.clip_job", command)
        self.assertIn("--reuse-detections", command)

    def test_reprocess_rejects_invalid_mode(self):
        with self.assertRaises(HTTPException) as caught:
            api.reprocess_match(7, "sometimes")
        self.assertEqual(caught.exception.status_code, 400)

    def test_reprocess_rejects_match_already_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self._match_row(tmp)
            row["status"] = "processing"
            with patch.object(api, "_require_match", return_value=row):
                with self.assertRaises(HTTPException) as caught:
                    api.reprocess_match(7, "without")
        self.assertEqual(caught.exception.status_code, 409)
