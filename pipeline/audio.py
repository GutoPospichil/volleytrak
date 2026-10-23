from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from app.config import JOB_DIR
from app.db import get_match


def extract_audio(video_path: Path, wav_path: Path) -> None:
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(wav_path),
    ]
    subprocess.run(command, check=True, timeout=600)


def detect_whistles(
    wav_path: Path,
    threshold: float = 0.015,
    min_distance: float = 1.2,
) -> list[dict]:
    sample_rate, samples = wavfile.read(str(wav_path))
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    samples = samples.astype(np.float32) / 32768.0
    win = 1024
    hop = 256
    frequencies, times, spectrum = signal.stft(
        samples,
        fs=sample_rate,
        nperseg=win,
        noverlap=win - hop,
        boundary=None,
    )
    magnitude = np.abs(spectrum)
    fundamental = (frequencies >= 2400) & (frequencies <= 3900)
    harmonic = (frequencies >= 4800) & (frequencies <= 7000)
    audible = (frequencies >= 200) & (frequencies <= 7000)

    fundamental_band = magnitude[fundamental]
    harmonic_band = magnitude[harmonic]
    fundamental_mean = fundamental_band.mean(axis=0) + 1e-9
    harmonic_mean = harmonic_band.mean(axis=0) + 1e-9
    rms = np.sqrt(np.mean(magnitude[audible] ** 2, axis=0))
    tonality = np.minimum(
        fundamental_band.max(axis=0) / fundamental_mean,
        harmonic_band.max(axis=0) / harmonic_mean,
    )
    score = np.clip(tonality - 5.0, 0, None) * np.clip(rms - 0.0015, 0, None)
    score = np.convolve(score, np.ones(3) / 3, mode="same")

    frame_step = float(times[1] - times[0])
    peaks, _ = signal.find_peaks(
        score,
        distance=max(1, int(round(min_distance / frame_step))),
        prominence=max(float(np.percentile(score, 99)) * 0.2, 1e-9),
    )
    selected = [
        {
            "t": round(float(times[index]), 3),
            "score": round(float(score[index]), 5),
            "tonality": round(float(tonality[index]), 2),
        }
        for index in peaks
        if score[index] >= threshold
    ]
    selected.sort(key=lambda item: item["t"])
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", type=int, required=True)
    parser.add_argument("--threshold", type=float, default=0.015)
    parser.add_argument("--output", default="whistles.json")
    args = parser.parse_args()

    match = get_match(args.match_id)
    if match is None:
        print("partida não encontrada")
        return 1
    video_path = Path(match["video_path"])
    if not video_path.is_file():
        print("vídeo não encontrado")
        return 1
    job_dir = JOB_DIR / f"match-{args.match_id}"
    wav_path = job_dir / "audio.wav"
    if not wav_path.is_file():
        print("extraindo áudio...", flush=True)
        extract_audio(video_path, wav_path)

    whistles = detect_whistles(wav_path, threshold=args.threshold)
    output_path = job_dir / args.output
    output_path.write_text(
        json.dumps(whistles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"apitos candidatos: {len(whistles)}")
    for whistle in whistles[:40]:
        print(f"  {whistle['t']:.2f}s score={whistle['score']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
