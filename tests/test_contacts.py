import unittest

from pipeline.contacts import detect_contacts


class ContactDetectionTest(unittest.TestCase):
    def test_detects_direction_change(self):
        records = []
        for index in range(60):
            if index < 30:
                x = 1.0 + index * 0.15
            else:
                x = 1.0 + (59 - index) * 0.15
            records.append(
                {
                    "t": index / 30.0,
                    "balls": [
                        {
                            "court": [x, 4.5],
                            "score": 0.9,
                        }
                    ],
                }
            )
        contacts = detect_contacts(records)
        self.assertTrue(contacts)
        self.assertTrue(any(0.8 <= contact["t"] <= 1.3 for contact in contacts))
