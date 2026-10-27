from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import JOB_DIR
from app.db import get_match


def load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * fraction))
    return ordered[max(0, min(len(ordered) - 1, index))]


def activity_stats(activity: dict | None, start: float, end: float) -> dict:
    samples = (activity or {}).get("samples") or []
    values = [
        float(sample.get("motion") or 0.0)
        for sample in samples
        if start <= float(sample.get("t") or 0.0) <= end
    ]
    if not values:
        return {"activity_mean": 0.0, "activity_max": 0.0, "activity_active_pct": 0.0}
    floor = 4.0
    return {
        "activity_mean": round(sum(values) / len(values), 2),
        "activity_max": round(max(values), 2),
        "activity_active_pct": round(
            sum(1 for value in values if value >= floor) / len(values), 3
        ),
    }


def ball_stats(records: list[dict], start: float, end: float) -> dict:
    subset = [
        record
        for record in records
        if start <= float(record.get("t") or 0.0) <= end
    ]
    if not subset:
        return {"ball_pct": 0.0, "max_speed": 0.0}
    detected = sum(1 for record in subset if record.get("balls"))
    speeds = []
    previous = None
    for record in subset:
        balls = record.get("balls") or []
        if not balls:
            previous = None
            continue
        court = balls[0].get("court")
        if not court:
            continue
        if previous is not None:
            previous_t, previous_court = previous
            dt = float(record.get("t") or 0.0) - previous_t
            if 0 < dt <= 0.25:
                speed = (
                    (float(court[0]) - previous_court[0]) ** 2
                    + (float(court[1]) - previous_court[1]) ** 2
                ) ** 0.5 / dt
                if 0 < speed <= 45.0:
                    speeds.append(speed)
        previous = (float(record.get("t") or 0.0), [float(court[0]), float(court[1])])
    return {
        "ball_pct": round(detected / len(subset), 4),
        "max_speed": round(max(speeds), 2) if speeds else 0.0,
    }


def first_contact(contacts: list[dict], start: float, end: float) -> dict | None:
    for contact in contacts:
        t = float(contact.get("t") or 0.0)
        if start <= t <= end:
            return contact
    return None


def contacts_between(contacts: list[dict], start: float, end: float) -> list[dict]:
    return [
        contact
        for contact in contacts
        if start <= float(contact.get("t") or 0.0) <= end
    ]


def is_near_baseline(contact: dict) -> bool:
    court = contact.get("court")
    if not court or len(court) < 2:
        return False
    x = float(court[0])
    return x <= 3.0 or x >= 15.0


def ball_crosses_net(
    ball_records: list[dict], start: float, end: float, net_x: float = 9.0
) -> bool:
    values = []
    for record in ball_records:
        t = float(record.get("t") or 0.0)
        if not (start <= t <= end):
            continue
        for ball in record.get("balls") or []:
            court = ball.get("court")
            if court:
                values.append(float(court[0]))
    if not values:
        return False
    return min(values) < net_x < max(values)


def build_anchors(
    contacts: list[dict],
    rallies: list[dict],
    ball_records: list[dict],
    duration: float,
    dead_gap: float = 5.0,
) -> list[dict]:
    anchors: list[dict] = []
    for rally in rallies:
        start = float(rally.get("start") or 0.0)
        end = float(rally.get("end") or start + 5.0)
        whistle_start = float(rally.get("whistle_start") or start)
        whistle_end = float(rally.get("whistle_end") or end)
        contact = first_contact(contacts, start - 1.5, start + 5.0)
        serve = float(contact["t"]) if contact else max(start, whistle_start)
        anchors.append(
            {
                "serve": serve,
                "start_hint": start,
                "end_hint": end,
                "whistle": True,
                "source": "whistle",
                "near_baseline": bool(contact and is_near_baseline(contact)),
                "crosses_net": ball_crosses_net(
                    ball_records, serve - 0.5, min(duration, serve + 3.0)
                ),
            }
        )

    previous = None
    for contact in contacts:
        t = float(contact.get("t") or 0.0)
        gap = t - previous if previous is not None else 999.0
        if previous is None or gap >= dead_gap:
            if not any(abs(t - anchor["serve"]) < 2.5 for anchor in anchors):
                anchors.append(
                    {
                        "serve": t,
                        "start_hint": max(0.0, t - 3.0),
                        "end_hint": min(duration, t + 8.0),
                        "whistle": False,
                        "source": "contact",
                        "near_baseline": is_near_baseline(contact),
                        "crosses_net": ball_crosses_net(
                            ball_records, t - 0.5, min(duration, t + 3.0)
                        ),
                    }
                )
        previous = t

    anchors.sort(key=lambda item: item["serve"])
    deduped: list[dict] = []
    for anchor in anchors:
        if deduped and abs(anchor["serve"] - deduped[-1]["serve"]) < 3.0:
            if anchor.get("whistle") and not deduped[-1].get("whistle"):
                deduped[-1] = anchor
            continue
        deduped.append(anchor)
    return deduped


def build_points(
    match_id: int,
    ball_records: list[dict],
    contacts: list[dict],
    rallies: list[dict],
    activity: dict | None,
    profile: dict | None,
    output_path: Path,
) -> list[dict]:
    duration = float(ball_records[-1].get("t") or 0.0) if ball_records else 0.0
    if duration <= 0:
        return []
    trim = (profile or {}).get("trim", {}) if isinstance(profile, dict) else {}
    pre_serve = clamp(float(trim.get("pre_roll", 3.0)), 2.0, 3.0)
    post_end = clamp(float(trim.get("post_roll", 2.0)), 1.5, 3.0)
    anchors = build_anchors(contacts, rallies, ball_records, duration)

    points: list[dict] = []
    for index, anchor in enumerate(anchors):
        serve = anchor["serve"]
        next_serve = (
            anchors[index + 1]["serve"] if index + 1 < len(anchors) else duration
        )
        start = max(0.0, serve - pre_serve)
        limit = min(
            duration,
            next_serve - 1.0 if index + 1 < len(anchors) else duration,
            serve + 20.0,
        )
        if limit <= start:
            continue

        window_contacts = contacts_between(contacts, serve - 0.3, limit)
        last_contact = window_contacts[-1] if window_contacts else None

        if anchor.get("whistle"):
            end = max(
                float(anchor["end_hint"]) + 0.5,
                (float(last_contact["t"]) if last_contact else serve) + post_end,
            )
            end = min(end, limit)
            end_reason = "whistle"
        elif last_contact:
            end = min(limit, float(last_contact["t"]) + post_end)
            end_reason = "last_contact"
        else:
            end = min(limit, serve + 6.5)
            end_reason = "serve_short"

        if end - start < 4.0:
            end = min(duration, start + 4.0)
        if end - start > 20.0:
            end = start + 20.0
        if end <= serve:
            end = min(duration, serve + 1.0)
        if end <= start:
            continue

        contacts_after = contacts_between(contacts, serve - 0.3, end)
        short_point = len(contacts_after) <= 1 and (end - serve) <= 7.5
        serve_evidence = bool(anchor.get("near_baseline") and anchor.get("crosses_net"))
        if short_point and serve_evidence:
            point_type = "serve"
        elif not contacts_after and anchor.get("whistle") and (end - serve) <= 5.0:
            point_type = "serve"
        else:
            point_type = "rally"
        if point_type == "rally" and (end - start) < 7.0:
            end = min(limit, duration, start + 7.0)
            contacts_after = contacts_between(contacts, serve - 0.3, end)
        ball = ball_stats(ball_records, start, end)
        activity_data = activity_stats(activity, start, end)
        sources = []
        if ball["ball_pct"] > 0:
            sources.append("ball")
        if contacts_after:
            sources.append("contacts")
        if anchor.get("whistle"):
            sources.append("whistle")
        if point_type == "serve":
            sources.append("serve")
        if activity_data["activity_mean"] >= 2.0:
            sources.append("activity")
        agreement = len(sources)
        score = 66.0
        score += min(12.0, len(contacts_after) * 2.0)
        score += min(8.0, agreement * 2.0)
        if point_type == "rally":
            score += 4.0

        points.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(end - start, 2),
                "score": round(min(100.0, score), 1),
                "source": "point",
                "point_type": point_type,
                "sources": sources,
                "agreement": agreement,
                "serve_time": round(serve, 2),
                "end_reason": end_reason,
                "contacts": len(contacts_after),
                "ball_pct": ball["ball_pct"],
                "max_speed": ball["max_speed"],
                "whistle_start": (
                    float(anchor.get("start_hint")) if anchor.get("whistle") else None
                ),
                "whistle_end": (
                    float(anchor.get("end_hint")) if anchor.get("whistle") else None
                ),
                **activity_data,
            }
        )

    points.sort(key=lambda item: item["start"])
    filtered: list[dict] = []
    for point in points:
        if filtered:
            previous = filtered[-1]
            if point["start"] < previous["end"] - 0.5:
                adjusted_end = point["start"] - 0.6
                if adjusted_end - previous["start"] >= 4.0:
                    previous["end"] = round(adjusted_end, 2)
                    previous["duration"] = round(previous["end"] - previous["start"], 2)
                else:
                    filtered.pop()
        filtered.append(point)

    output_path.write_text(
        json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    serve_count = sum(1 for point in filtered if point["point_type"] == "serve")
    print(
        f"pontos: {len(filtered)} ({len(filtered) - serve_count} rallies, "
        f"{serve_count} saques/aces), {len(anchors)} âncoras"
    )
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--ball", default="ball_track.jsonl")
    parser.add_argument("--contacts", default="contacts.json")
    parser.add_argument("--rallies", default="rallies_audio.json")
    parser.add_argument("--activity", default="activity.json")
    parser.add_argument("--profile", default="feedback_profile.json")
    parser.add_argument("--output", default="points.json")
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    job_dir = JOB_DIR / f"match-{args.match_id}"
    ball_path = job_dir / args.ball
    if not ball_path.is_file():
        ball_path = job_dir / "ball_vballnet.jsonl"
    if not ball_path.is_file():
        print("trajetória da bola não encontrada")
        return 1
    ball_records = load_jsonl(ball_path)
    contacts = load_json(job_dir / args.contacts, [])
    rallies = load_json(job_dir / args.rallies, [])
    activity = load_json(job_dir / args.activity, None)
    profile = load_json(job_dir / args.profile, None)
    build_points(
        args.match_id,
        ball_records,
        contacts,
        rallies,
        activity,
        profile,
        job_dir / args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
