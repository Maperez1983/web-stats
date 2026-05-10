from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class AutoCutMoment:
    time_s: float
    kind: str
    score: float
    label: str
    meta: dict


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    arr = np.array(values, dtype=np.float32)
    return float(np.percentile(arr, p))


def _normalize_series(values: list[float]) -> list[float]:
    """
    Normaliza a [0..1] usando percentiles (robusto a outliers).
    """
    if not values:
        return []
    p10 = _percentile(values, 10)
    p90 = _percentile(values, 90)
    span = max(1e-6, p90 - p10)
    return [float(_clamp((v - p10) / span, 0.0, 1.0)) for v in values]


def _get_duration_seconds(video_path: str) -> float:
    ffprobe = shutil.which('ffprobe')
    if ffprobe:
        try:
            cmd = [
                ffprobe,
                '-v',
                'error',
                '-show_entries',
                'format=duration',
                '-of',
                'default=noprint_wrappers=1:nokey=1',
                str(video_path),
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
            val = float(out or 0.0)
            if math.isfinite(val) and val > 0:
                return float(val)
        except Exception:
            pass
    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 0.0
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) or 0.0
        if fps > 0 and frames > 0:
            return float(frames / fps)
    except Exception:
        pass
    finally:
        try:
            cap.release()
        except Exception:
            pass
    return 0.0


def extract_audio_dbfs_series(
    video_path: str,
    *,
    sample_rate: int = 8000,
    window_s: float = 0.5,
    max_seconds: float | None = None,
) -> list[tuple[float, float]]:
    """
    Extrae una serie temporal de dBFS (RMS) desde el audio del vídeo usando FFmpeg.

    Devuelve: [(time_s, dbfs)] donde dbfs es negativo y valores mayores (menos negativos) = más volumen.
    """
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return []
    sr = int(sample_rate or 8000)
    win_s = float(window_s or 0.5)
    win_samples = max(1, int(round(sr * win_s)))
    bytes_per_window = win_samples * 2  # s16le mono

    cmd = [
        ffmpeg,
        '-nostdin',
        '-hide_banner',
        '-loglevel',
        'error',
        '-i',
        str(video_path),
        '-vn',
        '-ac',
        '1',
        '-ar',
        str(sr),
        '-f',
        's16le',
        'pipe:1',
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # noqa: S603
    out: list[tuple[float, float]] = []
    buf = b''
    idx = 0
    try:
        while proc.stdout:
            chunk = proc.stdout.read(64 * 1024)
            if not chunk:
                break
            buf += chunk
            while len(buf) >= bytes_per_window:
                window = buf[:bytes_per_window]
                buf = buf[bytes_per_window:]
                samples = np.frombuffer(window, dtype=np.int16).astype(np.float32)
                # RMS en dBFS
                rms = float(np.sqrt(np.mean(samples * samples) + 1e-9))
                dbfs = 20.0 * math.log10((rms / 32768.0) + 1e-9)
                time_s = (idx * win_s) + (win_s / 2.0)
                out.append((float(time_s), float(dbfs)))
                idx += 1
                if max_seconds is not None and time_s >= float(max_seconds):
                    return out
    finally:
        try:
            proc.kill()
        except Exception:
            pass
    return out


def extract_motion_series(
    video_path: str,
    *,
    sample_fps: float = 2.0,
    resize_w: int = 160,
    resize_h: int = 90,
    max_seconds: float | None = None,
) -> list[tuple[float, float]]:
    """
    Serie temporal de movimiento basada en diferencia frame-to-frame (media abs diff).
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap or not cap.isOpened():
        return []
    out: list[tuple[float, float]] = []
    try:
        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 25.0
        every = max(1, int(round(src_fps / max(0.25, float(sample_fps or 2.0)))))
        prev = None
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            idx += 1
            if idx % every != 0:
                continue
            t = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
            if max_seconds is not None and t >= float(max_seconds):
                break
            try:
                small = cv2.resize(frame, (int(resize_w), int(resize_h)), interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            except Exception:
                continue
            if prev is None:
                prev = gray
                continue
            diff = cv2.absdiff(gray, prev)
            prev = gray
            motion = float(np.mean(diff) / 255.0)
            out.append((float(t), float(motion)))
    finally:
        try:
            cap.release()
        except Exception:
            pass
    return out


def _pick_top_times(points: list[tuple[float, float]], *, top_n: int, min_gap_s: float, min_score: float) -> list[tuple[float, float]]:
    """
    Selección greedy por score, respetando separación temporal.
    """
    sorted_pts = sorted(points, key=lambda x: (-float(x[1]), float(x[0])))
    chosen: list[tuple[float, float]] = []
    gap = float(min_gap_s or 0.0)
    for t, s in sorted_pts:
        if len(chosen) >= int(top_n):
            break
        if float(s) < float(min_score):
            continue
        if any(abs(float(t) - float(ct)) < gap for ct, _ in chosen):
            continue
        chosen.append((float(t), float(s)))
    chosen.sort(key=lambda x: float(x[0]))
    return chosen


def suggest_autocuts(
    video_path: str,
    *,
    max_moments: int = 18,
    min_gap_s: float = 25.0,
    pre_s: float = 8.0,
    post_s: float = 8.0,
    max_seconds_scan: float | None = None,
) -> dict:
    """
    Genera momentos candidatos (timeline + clips) a partir de señales básicas:
    - audio: RMS dBFS (picos de emoción)
    - motion: diferencias frame-to-frame (subidas de ritmo)
    - set pieces: transición reposo→acción (proxy de ABP / reinicios)

    Nota: esto NO “entiende” táctica. Es un generador de candidatos para revisión rápida.
    """
    dur = _get_duration_seconds(video_path)
    if max_seconds_scan is not None:
        dur = min(dur or float(max_seconds_scan), float(max_seconds_scan))
    scan_limit = dur if dur and dur > 0 else max_seconds_scan

    audio = extract_audio_dbfs_series(video_path, window_s=0.5, max_seconds=scan_limit)
    motion = extract_motion_series(video_path, sample_fps=2.0, max_seconds=scan_limit)

    audio_t = [t for t, _ in audio]
    audio_db = [v for _, v in audio]
    motion_t = [t for t, _ in motion]
    motion_v = [v for _, v in motion]

    audio_norm = _normalize_series(audio_db)
    motion_norm = _normalize_series(motion_v)

    # Map a timeline base: usamos los timestamps de motion (más “sparse”) y aproximamos audio con nearest.
    audio_idx = 0
    combined: list[tuple[float, float, float, float]] = []  # (t, score, a, m)
    for i, t in enumerate(motion_t):
        # avanza audio_idx hasta que audio_t[audio_idx] ~ t
        while audio_idx + 1 < len(audio_t) and float(audio_t[audio_idx + 1]) < float(t):
            audio_idx += 1
        a = float(audio_norm[audio_idx]) if audio_idx < len(audio_norm) else 0.0
        m = float(motion_norm[i]) if i < len(motion_norm) else 0.0
        score = (0.55 * a) + (0.45 * m)
        combined.append((float(t), float(score), float(a), float(m)))

    # Set piece candidates: ventana con poco movimiento seguida de subida clara.
    set_pieces: list[tuple[float, float]] = []
    if combined:
        low_thr = 0.16
        high_thr = 0.62
        idle_count = 0
        last_idle_t = 0.0
        for t, score, a, m in combined:
            if m < low_thr:
                idle_count += 1
                last_idle_t = float(t)
                continue
            # subida tras reposo
            if idle_count >= 8 and m >= high_thr:
                set_pieces.append((float(t), float(0.7 + 0.3 * m)))
            idle_count = 0

    # Top general moments.
    peaks = [(t, s) for (t, s, _a, _m) in combined]
    chosen = _pick_top_times(peaks, top_n=int(max_moments), min_gap_s=float(min_gap_s), min_score=0.55)
    chosen_set = _pick_top_times(set_pieces, top_n=max(4, int(max_moments // 4)), min_gap_s=35.0, min_score=0.72)

    moments: list[AutoCutMoment] = []
    for t, s in chosen:
        moments.append(
            AutoCutMoment(
                time_s=float(t),
                kind='tag',
                score=float(s),
                label='Auto · Momento clave',
                meta={'source': 'audio+motion', 'pre_s': float(pre_s), 'post_s': float(post_s)},
            )
        )
    for t, s in chosen_set:
        moments.append(
            AutoCutMoment(
                time_s=float(t),
                kind='abp',
                score=float(s),
                label='Auto · ABP / reinicio (posible)',
                meta={'source': 'motion_transition', 'pre_s': float(pre_s), 'post_s': float(post_s)},
            )
        )

    # Dedup final por cercanía temporal.
    moments.sort(key=lambda m: (-float(m.score), float(m.time_s)))
    dedup: list[AutoCutMoment] = []
    for m in moments:
        if any(abs(float(m.time_s) - float(x.time_s)) < float(min_gap_s) for x in dedup):
            continue
        dedup.append(m)
        if len(dedup) >= int(max_moments):
            break
    dedup.sort(key=lambda m: float(m.time_s))

    # Clip ranges.
    out_moments = []
    for m in dedup:
        t = float(m.time_s)
        start = max(0.0, t - float(pre_s))
        end = t + float(post_s)
        if scan_limit and scan_limit > 0:
            end = min(float(scan_limit), end)
        out_moments.append(
            {
                'time_s': float(t),
                'kind': str(m.kind),
                'score': float(m.score),
                'label': str(m.label),
                'clip_in_s': float(start),
                'clip_out_s': float(max(start + 0.2, end)),
                'meta': dict(m.meta or {}),
            }
        )

    return {
        'ok': True,
        'duration_s': float(dur or 0.0),
        'scan_limit_s': float(scan_limit or 0.0) if scan_limit else 0.0,
        'moments': out_moments,
    }

