from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from app.config import JOB_DIR
from app.constants import CLIP_REJECTION_LABELS
from app.db import get_match, list_clip_rejections

KEYWORDS = {
    "ball_on_floor": [
        "chao",
        "no chao",
        "quicou",
        "parada",
        "parou",
        "rolando",
        "rola",
        "bola no chao",
        "bola no chão",
    ],
    "dead_time": [
        "tempo morto",
        "demorou",
        "continua",
        "apito",
        "final",
        "fim",
        "celebra",
        "comemora",
        "nao parou",
        "não parou",
    ],
    "half_rally": [
        "pela metade",
        "rally pela metade",
        "comeca no meio",
        "começa no meio",
        "comeca depois",
        "começa depois",
        "termina antes",
        "acaba antes",
        "cortou o comeco",
        "cortou o começo",
        "cortou o fim",
        "faltou o comeco",
        "faltou o começo",
        "incompleto",
    ],
    "bad_cut": [
        "corte",
        "cortou",
        "comeca",
        "começa",
        "termina",
        "antes",
        "depois",
        "inicio",
        "início",
    ],
    "not_rally": [
        "aquecimento",
        "warmup",
        "treino",
        "nao e rally",
        "não é rally",
        "nao rally",
        "sem rally",
    ],
    "duplicate": ["duplicado", "repetido", "mesmo clipe", "repetida"],
}


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def infer_reason(reason: str, note: str) -> str:
    if reason and reason != "other":
        return reason
    text = normalize(note)
    for candidate, words in KEYWORDS.items():
        if any(word in text for word in words):
            return candidate
    return reason or "other"


def build_profile(
    rejections: list, min_examples: int = 3, baseline: dict | None = None
) -> dict:
    counts: Counter[str] = Counter()
    inferred_counts: Counter[str] = Counter()
    features: dict[str, list[float]] = defaultdict(list)
    notes_used = 0
    for row in rejections:
        original = row["reason"] or "other"
        inferred = infer_reason(original, row["note"] or "")
        counts[original] += 1
        inferred_counts[inferred] += 1
        if original == "other" and inferred != original:
            notes_used += 1
        if not row["features"]:
            continue
        try:
            payload = json.loads(row["features"])
        except (TypeError, json.JSONDecodeError):
            continue
        for key in ("ball_pct", "max_speed", "contacts", "score", "saved_score", "duration"):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                features[key].append(float(value))

    baseline_trim = (baseline or {}).get("trim", {})
    pre_roll = float(baseline_trim.get("pre_roll", 1.0))
    post_roll = float(baseline_trim.get("post_roll", 1.8))
    active_speed = float(baseline_trim.get("active_speed", 2.5))
    dead = inferred_counts.get("dead_time", 0) + inferred_counts.get("ball_on_floor", 0)
    if dead >= min_examples:
        post_roll = min(post_roll, max(0.8, round(1.8 - 0.15 * dead, 2)))
        active_speed = max(active_speed, min(4.0, round(2.5 + 0.1 * dead, 2)))

    bad_cut_notes = [
        normalize(row["note"] or "")
        for row in rejections
        if infer_reason(row["reason"] or "other", row["note"] or "") == "bad_cut"
    ]
    start_hits = sum(
        1
        for note in bad_cut_notes
        if any(word in note for word in ("comeca", "começa", "antes", "inicio", "início"))
    )
    end_hits = sum(
        1
        for note in bad_cut_notes
        if any(word in note for word in ("termina", "terminou", "depois", "fim", "final"))
    )
    bad_cut = inferred_counts.get("bad_cut", 0)
    if bad_cut >= min_examples:
        if start_hits > end_hits:
            pre_roll = max(pre_roll, min(2.5, round(1.0 + 0.25 * bad_cut, 2)))
        elif end_hits > start_hits:
            post_roll = min(post_roll, max(0.8, round(1.8 - 0.15 * end_hits, 2)))
        else:
            pre_roll = max(pre_roll, min(2.0, round(1.0 + 0.15 * bad_cut, 2)))

    half_rally = inferred_counts.get("half_rally", 0)
    if half_rally >= min_examples:
        pre_roll = max(pre_roll, min(4.0, round(1.0 + 0.25 * half_rally, 2)))
        post_roll = max(post_roll, min(4.0, round(1.8 + 0.20 * half_rally, 2)))

    min_ball_pct = float((baseline or {}).get("min_ball_pct", 0.10))
    if inferred_counts.get("not_rally", 0) >= min_examples:
        min_ball_pct = max(
            min_ball_pct,
            min(0.30, round(0.10 + 0.02 * inferred_counts["not_rally"], 2)),
        )

    averages = {
        key: round(sum(values) / len(values), 2)
        for key, values in features.items()
        if values
    }
    return {
        "counts": dict(counts),
        "inferred_counts": dict(inferred_counts),
        "features": averages,
        "notes_used": notes_used,
        "trim": {
            "pre_roll": pre_roll,
            "post_roll": post_roll,
            "active_speed": active_speed,
        },
        "min_ball_pct": min_ball_pct,
    }


def build_profile_for_match(match_id: int) -> dict:
    rejections = list_clip_rejections(match_id)
    baseline = None
    global_path = JOB_DIR.parent / "feedback_profile.json"
    if global_path.is_file():
        try:
            baseline = json.loads(global_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            baseline = None
    profile = build_profile(rejections, baseline=baseline)
    job_dir = JOB_DIR / f"match-{match_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "feedback_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    rejections = list_clip_rejections(args.match_id)
    if not rejections:
        print("nenhuma exclusão registrada")
        return 0

    profile = build_profile_for_match(args.match_id)
    print(f"exclusões: {len(rejections)}")
    for reason, count in Counter(profile["inferred_counts"]).most_common():
        label = CLIP_REJECTION_LABELS.get(reason, reason)
        print(f"  {label}: {count}")
    if profile["notes_used"]:
        print(f"notas usadas para inferir motivo: {profile['notes_used']}")
    if profile["features"]:
        print("médias dos clipes excluídos:")
        for key, value in profile["features"].items():
            print(f"  {key}: {value}")
    print(
        "perfil aplicado na próxima geração: "
        f"pré-roll={profile['trim']['pre_roll']}s "
        f"pós-roll={profile['trim']['post_roll']}s "
        f"velocidade ativa={profile['trim']['active_speed']}m/s "
        f"bola mínima={profile['min_ball_pct']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
