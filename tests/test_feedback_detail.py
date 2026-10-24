import unittest

from pipeline.feedback import build_profile


class FeedbackDetailTest(unittest.TestCase):
    def _rows(self, detail):
        return [
            {"reason": "bad_cut", "detail": detail, "note": "", "features": None}
            for _ in range(3)
        ]

    def test_start_late_increases_pre_roll(self):
        profile = build_profile(
            self._rows("start_late"),
            baseline={"trim": {"pre_roll": 2.5, "post_roll": 0.8, "active_speed": 4.0}, "min_ball_pct": 0.16},
        )
        self.assertGreater(profile["trim"]["pre_roll"], 2.5)
        self.assertEqual(profile["trim"]["post_roll"], 0.8)

    def test_end_early_increases_post_roll(self):
        profile = build_profile(
            self._rows("end_early"),
            baseline={"trim": {"pre_roll": 2.5, "post_roll": 0.8, "active_speed": 4.0}, "min_ball_pct": 0.16},
        )
        self.assertGreater(profile["trim"]["post_roll"], 0.8)
