from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from app.config import DATA_DIR

MODEL_PATH = DATA_DIR / "feedback_ranker.json"
FEATURES = ["ball_pct", "max_speed", "contacts", "duration", "base_score", "crossings", "audio"]


def _payload(row) -> dict:
    if not row["features"]:
        return {}
    try:
        return json.loads(row["features"])
    except (TypeError, json.JSONDecodeError):
        return {}


def feature_vector(payload: dict, duration: float = 0.0, source: str = "") -> list[float]:
    def number(key: str, default: float = 0.0) -> float:
        value = payload.get(key)
        return float(value) if isinstance(value, (int, float)) else default

    return [
        number("ball_pct"),
        number("max_speed"),
        number("contacts"),
        float(payload.get("duration", duration) or duration),
        number("base_score", number("score")),
        number("crossings"),
        1.0 if (payload.get("source") or source) == "audio" else 0.0,
    ]


def load_training_data() -> tuple[np.ndarray, np.ndarray]:
    rows: list[tuple[list[float], int]] = []
    # saved de todas as partidas
    from app.db import connect

    with connect() as conn:
        saved = conn.execute(
            "SELECT features, duration, source FROM clips WHERE status = 'saved'"
        ).fetchall()
        rejected = conn.execute(
            "SELECT features, end - start AS duration, '' AS source FROM clip_rejections"
        ).fetchall()
    for row in saved:
        payload = _payload(row)
        if not payload:
            continue
        rows.append((feature_vector(payload, float(row["duration"]), row["source"] or ""), 1))
    for row in rejected:
        payload = _payload(row)
        if not payload:
            continue
        rows.append((feature_vector(payload, float(row["duration"]), ""), 0))
    if not rows:
        return np.empty((0, len(FEATURES))), np.empty((0,))
    x = np.array([row[0] for row in rows], dtype=float)
    y = np.array([row[1] for row in rows], dtype=float)
    return x, y


def sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -40, 40)
    return 1.0 / (1.0 + np.exp(-z))


def train_logistic(
    x: np.ndarray, y: np.ndarray, iterations: int = 4000, lr: float = 0.08, l2: float = 0.02
) -> dict:
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std < 1e-6] = 1.0
    xs = (x - mean) / std
    bias = np.ones((xs.shape[0], 1))
    design = np.hstack([bias, xs])
    weights = np.zeros(design.shape[1])
    positive = max(1.0, y.sum())
    negative = max(1.0, len(y) - y.sum())
    sample_weight = np.where(y > 0.5, negative / positive, 1.0)
    for _ in range(iterations):
        probabilities = sigmoid(design @ weights)
        gradient = design.T @ ((probabilities - y) * sample_weight) / len(y)
        gradient[1:] += l2 * weights[1:]
        weights -= lr * gradient
    return {
        "features": FEATURES,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "weights": weights.tolist(),
        "cv_auc": None,
        "n_positive": int(y.sum()),
        "n_negative": int(len(y) - y.sum()),
    }


def predict_probability(model: dict, features: list[float]) -> float:
    mean = np.array(model["mean"])
    std = np.array(model["std"])
    weights = np.array(model["weights"])
    value = np.array(features, dtype=float)
    design = np.concatenate([[1.0], (value - mean) / std])
    return float(sigmoid(design @ weights))


def auc_score(y: np.ndarray, probabilities: np.ndarray) -> float:
    positives = probabilities[y > 0.5]
    negatives = probabilities[y <= 0.5]
    if not len(positives) or not len(negatives):
        return 0.0
    wins = 0.0
    for p in positives:
        wins += float(np.sum(p > negatives)) + 0.5 * float(np.sum(p == negatives))
    return wins / (len(positives) * len(negatives))


def cross_validate(x: np.ndarray, y: np.ndarray, folds: int = 5) -> float:
    if len(y) < 10:
        return 0.0
    rng = np.random.default_rng(42)
    indices = rng.permutation(len(y))
    probabilities = np.zeros(len(y))
    for fold in range(folds):
        test_mask = np.zeros(len(y), dtype=bool)
        test_mask[indices[fold::folds]] = True
        train_x, train_y = x[~test_mask], y[~test_mask]
        if train_y.sum() == 0 or train_y.sum() == len(train_y):
            continue
        model = train_logistic(train_x, train_y, iterations=1500, lr=0.1, l2=0.03)
        for i in np.where(test_mask)[0]:
            probabilities[i] = predict_probability(model, x[i].tolist())
    return auc_score(y, probabilities)


def train_and_save(path: Path = MODEL_PATH) -> dict:
    x, y = load_training_data()
    if len(y) < 10:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        model = {
            "features": FEATURES,
            "mean": [0.0] * len(FEATURES),
            "std": [1.0] * len(FEATURES),
            "weights": [0.0] * (len(FEATURES) + 1),
            "cv_auc": None,
            "n_positive": int(y.sum()) if len(y) else 0,
            "n_negative": int(len(y) - y.sum()) if len(y) else 0,
        }
    else:
        model = train_logistic(x, y)
        model["cv_auc"] = round(cross_validate(x, y), 4)
        path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    return model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--match-id", type=int, default=0)
    args = parser.parse_args()
    if args.train:
        model = train_and_save()
        print(json.dumps({k: v for k, v in model.items() if k not in {"mean", "std", "weights"}}, ensure_ascii=False))
        print("modelo:", MODEL_PATH)
        return 0
    print("use --train")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
