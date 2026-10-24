import unittest

from pipeline.feedback import infer_reason


class FeedbackReasonTest(unittest.TestCase):
    def test_merges_legacy_reasons(self):
        self.assertEqual(infer_reason("ball_on_floor", ""), "dead_time")
        self.assertEqual(infer_reason("half_rally", ""), "bad_cut")

    def test_infers_merged_reason_from_note(self):
        self.assertEqual(infer_reason("other", "a bola ficou no chão"), "dead_time")
        self.assertEqual(infer_reason("other", "rally pela metade"), "bad_cut")
