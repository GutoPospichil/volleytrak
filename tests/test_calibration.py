import unittest

from pipeline.calibration import (
    homography_from_points,
    image_court_polygon,
    inside_court,
    point_in_polygon,
    project_point,
    reference_points,
)


class CalibrationTest(unittest.TestCase):
    def test_round_trip(self):
        points = [[0.1, 0.2], [0.9, 0.2], [0.85, 0.9], [0.15, 0.9]]
        width, height = 1920, 1080
        matrix = homography_from_points(points, (width, height))
        expected = [(0.0, 0.0), (0.0, 9.0), (18.0, 9.0), (18.0, 0.0)]

        for point, target in zip(points, expected):
            projected = project_point(matrix, (point[0] * width, point[1] * height))
            self.assertIsNotNone(projected)
            self.assertAlmostEqual(projected[0], target[0], places=4)
            self.assertAlmostEqual(projected[1], target[1], places=4)

    def test_requires_four_points(self):
        with self.assertRaises(ValueError):
            homography_from_points([[0.1, 0.1]], (1280, 720))

    def test_inside_court(self):
        self.assertTrue(inside_court([9.0, 4.5]))
        self.assertFalse(inside_court([20.0, 4.5]))
        self.assertFalse(inside_court(None))

    def test_near_attack_reference(self):
        points = [[0.1, 0.2], [0.9, 0.2], [0.85, 0.9], [0.15, 0.9]]
        width, height = 1600, 900
        matrix = homography_from_points(points, (width, height), "near_attack")
        expected = [(0.0, 0.0), (0.0, 9.0), (12.0, 9.0), (12.0, 0.0)]

        for point, target in zip(points, expected):
            projected = project_point(matrix, (point[0] * width, point[1] * height))
            self.assertIsNotNone(projected)
            self.assertAlmostEqual(projected[0], target[0], places=4)
            self.assertAlmostEqual(projected[1], target[1], places=4)

        reference = reference_points("near_attack")
        self.assertEqual(reference.shape, (4, 2))

    def test_court_polygon_filters_bench(self):
        points = [[0.2, 0.2], [0.8, 0.2], [0.9, 0.9], [0.1, 0.9]]
        polygon = image_court_polygon(points, (1600, 900), "full")
        self.assertTrue(point_in_polygon(polygon, (800, 450)))
        self.assertFalse(point_in_polygon(polygon, (50, 50)))


if __name__ == "__main__":
    unittest.main()
