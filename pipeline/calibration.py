from __future__ import annotations

import cv2
import numpy as np

from app.constants import CALIBRATION_MODES


def reference_points(mode: str = "full") -> np.ndarray:
    configuration = CALIBRATION_MODES.get(mode, CALIBRATION_MODES["full"])
    return np.array(configuration["court_points"], dtype=np.float32)


def homography_from_points(
    points: list[list[float]], frame_size: tuple[int, int], mode: str = "full"
) -> np.ndarray:
    if len(points) != 4:
        raise ValueError("a calibração exige exatamente 4 pontos")
    width, height = frame_size
    source = np.array(
        [[point[0] * width, point[1] * height] for point in points], dtype=np.float32
    )
    matrix, _ = cv2.findHomography(source, reference_points(mode))
    if matrix is None:
        raise ValueError("não foi possível calcular a homografia")
    return matrix


def project_point(matrix: np.ndarray | None, point: tuple[float, float]) -> list[float] | None:
    if matrix is None:
        return None
    vector = np.array([point[0], point[1], 1.0], dtype=np.float32)
    projected = matrix @ vector
    if abs(float(projected[2])) < 1e-9:
        return None
    return [float(projected[0] / projected[2]), float(projected[1] / projected[2])]


def project_foot(
    matrix: np.ndarray | None, bbox: list[float]
) -> list[float] | None:
    if matrix is None:
        return None
    x1, _, x2, y2 = bbox
    return project_point(matrix, ((x1 + x2) / 2.0, y2))


def inside_court(point: list[float] | None, margin: float = 1.5) -> bool:
    if point is None:
        return False
    return -margin <= point[0] <= 18.0 + margin and -margin <= point[1] <= 9.0 + margin


def image_court_polygon(
    points: list[list[float]],
    frame_size: tuple[int, int],
    mode: str = "full",
    margin: float = 0.0,
) -> np.ndarray:
    matrix = homography_from_points(points, frame_size, mode)
    inverse = np.linalg.inv(matrix)
    corners = [
        (-margin, -margin),
        (18.0 + margin, -margin),
        (18.0 + margin, 9.0 + margin),
        (-margin, 9.0 + margin),
    ]
    polygon = []
    for x, y in corners:
        value = inverse @ np.array([x, y, 1.0], dtype=np.float64)
        polygon.append([value[0] / value[2], value[1] / value[2]])
    return np.array(polygon, dtype=np.float32)


def point_in_polygon(polygon: np.ndarray | None, point: tuple[float, float]) -> bool:
    if polygon is None:
        return True
    contour = polygon.reshape(-1, 1, 2)
    return cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False) >= 0
