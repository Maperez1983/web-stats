from __future__ import annotations

import math
import shutil
import subprocess
import time
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
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=6).decode('utf-8', errors='ignore').strip()
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
        # Si solo necesitamos los primeros X segundos, pedimos a FFmpeg que corte (evita CPU extra).
        *(['-t', str(float(max_seconds) + 0.5)] if max_seconds is not None else []),
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
    started = time.monotonic()
    try:
        while proc.stdout:
            # Guardrail: evita bucles infinitos si FFmpeg se queda colgado (archivos corruptos).
            if time.monotonic() - started > 90:
                break
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
    # Fast path: usa FFmpeg para muestrear frames (mucho más rápido que decodificar frame-a-frame en Python).
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        fps = max(0.25, float(sample_fps or 2.0))
        w = int(resize_w or 160)
        h = int(resize_h or 90)
        frame_size = max(1, w * h)
        vf = f'fps={fps},scale={w}:{h}:flags=fast_bilinear,format=gray'
        cmd = [
            ffmpeg,
            '-nostdin',
            '-hide_banner',
            '-loglevel',
            'error',
            # Decodifica solo keyframes cuando sea posible (acelera mucho en partidos largos).
            '-skip_frame',
            'nokey',
            '-i',
            str(video_path),
            *(['-t', str(float(max_seconds) + 0.5)] if max_seconds is not None else []),
            '-an',
            '-sn',
            '-vf',
            vf,
            '-f',
            'rawvideo',
            '-pix_fmt',
            'gray',
            'pipe:1',
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # noqa: S603
        out: list[tuple[float, float]] = []
        prev = None
        idx = 0
        started = time.monotonic()
        try:
            while proc.stdout:
                if time.monotonic() - started > 120:
                    break
                buf = proc.stdout.read(frame_size)
                if not buf or len(buf) < frame_size:
                    break
                frame = np.frombuffer(buf, dtype=np.uint8)
                if frame.size != frame_size:
                    break
                frame = frame.reshape((h, w))
                t = float(idx) / float(fps)
                idx += 1
                if max_seconds is not None and t >= float(max_seconds):
                    break
                if prev is None:
                    prev = frame
                    continue
                diff = cv2.absdiff(frame, prev)
                prev = frame
                motion = float(np.mean(diff) / 255.0)
                out.append((float(t), float(motion)))
        finally:
            try:
                proc.kill()
            except Exception:
                pass
        return out

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


def extract_field_context_series(
    video_path: str,
    *,
    sample_fps: float = 1.0,
    resize_w: int = 160,
    resize_h: int = 90,
    max_seconds: float | None = None,
) -> list[tuple[float, float, float]]:
    """
    Serie temporal ligera para ayudar a refinar cortes:
    - green_ratio: % de píxeles "césped" (HSV)
    - cut_score: diferencia frame-to-frame (proxy de corte/replay/cambio plano)

    Devuelve: [(time_s, green_ratio, cut_score)].
    """
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return []
    fps = max(0.25, float(sample_fps or 1.0))
    w = int(resize_w or 160)
    h = int(resize_h or 90)
    frame_size = max(1, w * h * 3)  # rgb24
    vf = f'fps={fps},scale={w}:{h}:flags=fast_bilinear,format=rgb24'
    cmd = [
        ffmpeg,
        '-nostdin',
        '-hide_banner',
        '-loglevel',
        'error',
        '-i',
        str(video_path),
        *(['-t', str(float(max_seconds) + 0.5)] if max_seconds is not None else []),
        '-an',
        '-sn',
        '-vf',
        vf,
        '-f',
        'rawvideo',
        '-pix_fmt',
        'rgb24',
        'pipe:1',
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # noqa: S603
    out: list[tuple[float, float, float]] = []
    prev_gray = None
    idx = 0
    started = time.monotonic()
    try:
        while proc.stdout:
            if time.monotonic() - started > 120:
                break
            buf = proc.stdout.read(frame_size)
            if not buf or len(buf) < frame_size:
                break
            frame = np.frombuffer(buf, dtype=np.uint8)
            if frame.size != frame_size:
                break
            frame = frame.reshape((h, w, 3))
            t = float(idx) / float(fps)
            idx += 1
            if max_seconds is not None and t >= float(max_seconds):
                break

            # Green ratio in HSV.
            try:
                hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                # Hue rango césped (aprox). S/V > 40 filtra grises.
                lower = np.array([35, 40, 40], dtype=np.uint8)
                upper = np.array([95, 255, 255], dtype=np.uint8)
                mask = cv2.inRange(hsv, lower, upper)
                green_ratio = float(np.mean(mask > 0))
            except Exception:
                green_ratio = 0.0

            # Cut score: mean abs diff in grayscale.
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                if prev_gray is None:
                    cut_score = 0.0
                else:
                    diff = cv2.absdiff(gray, prev_gray)
                    cut_score = float(np.mean(diff) / 255.0)
                prev_gray = gray
            except Exception:
                cut_score = 0.0

            out.append((float(t), float(green_ratio), float(cut_score)))
    finally:
        try:
            proc.kill()
        except Exception:
            pass
    return out


def _ball_in_play_series(
    ctx: list[tuple[float, float, float]],
    *,
    green_lo: float = 0.14,
    green_hi: float = 0.34,
    cut_penalty_thr: float = 0.22,
) -> list[tuple[float, float]]:
    """
    Devuelve [(time_s, in_play_score)] en [0..1].

    - Score alto si hay césped y no hay corte de plano.
    """
    out: list[tuple[float, float]] = []
    for t, green, cut in ctx:
        g = _clamp((float(green) - float(green_lo)) / max(1e-6, float(green_hi - green_lo)), 0.0, 1.0)
        c = float(cut)
        if c >= float(cut_penalty_thr):
            # Penaliza cerca de cortes / replays.
            g *= float(_clamp(1.0 - ((c - float(cut_penalty_thr)) / 0.25), 0.0, 1.0))
        out.append((float(t), float(_clamp(g, 0.0, 1.0))))
    return out


def _scene_cut_times(ctx: list[tuple[float, float, float]]) -> list[float]:
    """
    Lista de tiempos (s) donde hay probabilidad de corte de plano.
    """
    if not ctx:
        return []
    cuts = [float(c) for (_t, _g, c) in ctx]
    thr = max(0.20, _percentile(cuts, 95.0))
    return [float(t) for (t, _g, c) in ctx if float(c) >= float(thr)]


def _refine_clip_bounds(
    *,
    kind: str,
    t_peak: float,
    clip_in_s: float,
    clip_out_s: float,
    in_play: list[tuple[float, float]],
    cut_times: list[float],
    step_s: float = 1.0,
) -> tuple[float, float, dict]:
    """
    Refina IN/OUT para que el clip represente acción real (no post-gol / paseos / replay).
    """
    k = str(kind or 'tag').strip().lower()
    tp = float(max(0.0, t_peak))
    start0 = float(max(0.0, clip_in_s))
    end0 = float(max(start0 + 0.2, clip_out_s))

    # Ventanas por tipo.
    if k == 'goal':
        # Para goles el "pico" suele venir tarde (celebración). Forzamos buscar IN más atrás
        # y evitar quedarse con el saque de centro.
        in_a, in_b = tp - 55.0, tp - 12.0
        out_a, out_b = tp + 1.0, tp + 12.0
        min_dur = 10.0
    elif k == 'shot':
        in_a, in_b = tp - 20.0, tp - 5.0
        out_a, out_b = tp + 0.6, tp + 10.0
        min_dur = 8.0
    elif k == 'abp':
        in_a, in_b = tp - 22.0, tp - 6.0
        out_a, out_b = tp + 2.0, tp + 20.0
        min_dur = 12.0
    elif k == 'press' or k == 'turnover':
        in_a, in_b = tp - 20.0, tp - 5.0
        out_a, out_b = tp + 1.0, tp + 14.0
        min_dur = 10.0
    else:
        in_a, in_b = tp - 18.0, tp - 5.0
        out_a, out_b = tp + 1.0, tp + 14.0
        min_dur = 10.0

    # Índices en serie in_play (asumimos paso ~step_s).
    times = [float(t) for (t, _s) in in_play]
    scores = [float(s) for (_t, s) in in_play]
    if not times or len(times) != len(scores):
        return (start0, end0, {'refined': False, 'reason': 'no_series'})

    def _idx_for_time(t: float) -> int:
        # Aproximación: series uniformes.
        i = int(round(float(t) / float(step_s)))
        return max(0, min(len(times) - 1, i))

    # Helper: busca runs de in_play >= thr durante run_len segundos.
    def _find_run_start_latest(a: float, b: float, thr: float, run_len_s: float) -> float | None:
        ia = _idx_for_time(max(0.0, a))
        ib = _idx_for_time(max(0.0, b))
        if ib <= ia:
            return None
        need = max(2, int(round(run_len_s / float(step_s))))
        latest = None
        # Iteramos hacia atrás para quedarnos con el inicio más cercano al desenlace.
        for i in range(ib, ia, -1):
            ok = True
            # run que termine en i (incluye i)
            for j in range(need):
                kx = i - j
                if kx < ia:
                    ok = False
                    break
                if float(scores[kx]) < float(thr):
                    ok = False
                    break
            if ok:
                # inicio del run
                latest = float(times[i - (need - 1)])
                break
        return latest

    def _first_cut_after(t0: float, t1: float) -> float | None:
        for ct in cut_times:
            if float(ct) >= float(t0) and float(ct) <= float(t1):
                return float(ct)
        return None

    # IN: último run estable de bola en juego.
    in_thr = 0.60 if k == 'goal' else 0.62
    run_len = 6.0 if k == 'goal' else (5.0 if k == 'abp' else 4.0)
    in_run = _find_run_start_latest(in_a, in_b, thr=in_thr, run_len_s=run_len)
    refined_in = start0
    in_reason = 'keep'
    if in_run is not None:
        refined_in = max(0.0, float(in_run))
        in_reason = 'ball_in_play_run'

    # Si es gol y encontramos un corte fuerte cercano al pico, evitamos el post-evento:
    # - si hay corte en (tp-3 .. tp+10), asumimos que el juego se rompe ahí (replay/celebración)
    #   y hacemos OUT antes de ese corte.
    if k == 'goal':
        near_cut = _first_cut_after(tp - 3.0, tp + 10.0)
        if near_cut is not None:
            refined_out = min(refined_out, float(near_cut))
            out_reason = f'{out_reason}|goal_near_cut'

    # OUT: primer corte fuerte o caída de bola en juego, con guardrail de tiempo.
    refined_out = end0
    out_reason = 'keep'
    cut_t = _first_cut_after(out_a, out_b)
    if cut_t is not None:
        refined_out = float(cut_t)
        out_reason = 'scene_cut'
    else:
        # caída de in_play sostenida tras out_a
        ia = _idx_for_time(out_a)
        ib = _idx_for_time(out_b)
        low_need = max(2, int(round(2.0 / float(step_s))))
        for i in range(ia, ib):
            ok_low = True
            for j in range(low_need):
                kx = i + j
                if kx >= ib:
                    ok_low = False
                    break
                if float(scores[kx]) >= 0.35:
                    ok_low = False
                    break
            if ok_low:
                refined_out = float(times[i])
                out_reason = 'ball_out_play'
                break

    # Guardrails.
    if refined_out <= refined_in + 4.0:
        refined_out = max(refined_in + float(min_dur), refined_out, end0)
        out_reason = f'{out_reason}|min_dur'
    # Recorta para no irse a paseos.
    max_len = 65.0 if k == 'abp' else 50.0
    if refined_out - refined_in > max_len:
        refined_out = refined_in + max_len
        out_reason = f'{out_reason}|cap'

    return (
        float(refined_in),
        float(max(refined_in + 0.2, refined_out)),
        {
            'refined': True,
            'in_reason': in_reason,
            'out_reason': out_reason,
            'in_play_thr': 0.62,
            'out_low_thr': 0.35,
        },
    )

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


def _moving_average(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    w = max(1, int(window or 1))
    if w <= 1:
        return [float(v) for v in values]
    out: list[float] = []
    acc = 0.0
    q: list[float] = []
    for v in values:
        fv = float(v)
        q.append(fv)
        acc += fv
        if len(q) > w:
            acc -= q.pop(0)
        out.append(float(acc / max(1, len(q))))
    return out


def _segments_from_series(
    times: list[float],
    scores: list[float],
    *,
    thr_high: float,
    thr_low: float,
    min_len_s: float = 2.0,
    max_len_s: float = 60.0,
    merge_gap_s: float = 3.0,
) -> list[tuple[float, float, float, float]]:
    """
    Extrae segmentos continuos de alta intensidad usando histéresis (high/low).

    Devuelve lista: (start_s, end_s, peak_t, peak_score).
    """
    if not times or not scores or len(times) != len(scores):
        return []
    hi = float(thr_high or 0.0)
    lo = float(thr_low or 0.0)
    if lo > hi:
        lo, hi = hi, lo

    started = False
    start_t = 0.0
    peak_t = 0.0
    peak_s = -1.0
    raw: list[tuple[float, float, float, float]] = []
    # Python 3.9 compat: `zip(..., strict=...)` no existe.
    for t, s in zip(times, scores):
        tt = float(t)
        ss = float(s)
        if not started:
            if ss >= hi:
                started = True
                start_t = tt
                peak_t = tt
                peak_s = ss
            continue
        if ss > peak_s:
            peak_s = ss
            peak_t = tt
        if ss < lo:
            started = False
            raw.append((float(start_t), float(tt), float(peak_t), float(peak_s)))
    if started:
        raw.append((float(start_t), float(times[-1]), float(peak_t), float(peak_s)))

    cleaned: list[tuple[float, float, float, float]] = []
    for a, b, pt, ps in raw:
        if b < a:
            a, b = b, a
        dur = float(b - a)
        if dur < float(min_len_s or 0.0):
            continue
        if float(max_len_s or 0.0) > 0 and dur > float(max_len_s):
            half = float(max_len_s) / 2.0
            a2 = max(float(a), float(pt) - half)
            b2 = min(float(b), float(pt) + half)
            if b2 - a2 >= float(min_len_s or 0.0):
                a, b = a2, b2
        cleaned.append((float(a), float(b), float(pt), float(ps)))

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: float(x[0]))
    merged: list[tuple[float, float, float, float]] = []
    cur_a, cur_b, cur_pt, cur_ps = cleaned[0]
    for a, b, pt, ps in cleaned[1:]:
        if float(a) - float(cur_b) <= float(merge_gap_s or 0.0):
            cur_b = max(float(cur_b), float(b))
            if float(ps) > float(cur_ps):
                cur_ps = float(ps)
                cur_pt = float(pt)
            continue
        merged.append((float(cur_a), float(cur_b), float(cur_pt), float(cur_ps)))
        cur_a, cur_b, cur_pt, cur_ps = float(a), float(b), float(pt), float(ps)
    merged.append((float(cur_a), float(cur_b), float(cur_pt), float(cur_ps)))
    return merged


def suggest_autocuts(
    video_path: str,
    *,
    profile: str = 'balanced',
    include_kinds: Iterable[str] | None = None,
    max_moments: int = 18,
    min_gap_s: float = 25.0,
    pre_s: float = 8.0,
    post_s: float = 8.0,
    max_seconds_scan: float | None = None,
    refine: bool = True,
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
    # `sample_fps` bajo = más rápido. 1 fps suele ser suficiente para detectar cambios de ritmo
    # (celebraciones, saques, reinicios, etc.) sin tardar minutos en un partido completo.
    motion = extract_motion_series(video_path, sample_fps=1.0, max_seconds=scan_limit)
    ctx = extract_field_context_series(video_path, sample_fps=1.0, max_seconds=scan_limit) if refine else []
    in_play = _ball_in_play_series(ctx) if ctx else []
    cut_times = _scene_cut_times(ctx) if ctx else []
    # sample_fps fijo en extract_field_context_series
    step_s = 1.0

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

    prof = str(profile or 'balanced').strip().lower()
    if prof not in {'balanced', 'highlights', 'tactical'}:
        prof = 'balanced'
    if prof == 'highlights':
        p_hi = 92.0
        min_score = 0.62
        seg_min_len = 3.0
        merge_gap = 4.0
    elif prof == 'tactical':
        p_hi = 80.0
        min_score = 0.50
        seg_min_len = 4.0
        merge_gap = 2.5
    else:
        p_hi = 86.0
        min_score = 0.55
        seg_min_len = 3.0
        merge_gap = 3.0

    times = [t for (t, _s, _a, _m) in combined]
    scores = [s for (_t, s, _a, _m) in combined]
    scores_sm = _moving_average(scores, window=5)
    thr_high = _percentile(scores_sm, p_hi)
    thr_low = max(0.25, thr_high * 0.72)

    segments = _segments_from_series(
        times,
        scores_sm,
        thr_high=float(thr_high),
        thr_low=float(thr_low),
        min_len_s=float(seg_min_len),
        max_len_s=80.0 if prof != 'highlights' else 55.0,
        merge_gap_s=float(merge_gap),
    )
    seg_peaks = [(pt, ps) for (_a, _b, pt, ps) in segments]
    chosen = _pick_top_times(seg_peaks, top_n=int(max_moments), min_gap_s=float(min_gap_s), min_score=float(min_score))
    chosen_set = _pick_top_times(set_pieces, top_n=max(4, int(max_moments // 4)), min_gap_s=35.0, min_score=0.72)

    seg_by_peak: dict[float, tuple[float, float, float, float]] = {float(seg[2]): seg for seg in segments}

    def _nearest_features(tt: float) -> tuple[float, float]:
        if not combined:
            return (0.0, 0.0)
        best = 10**9
        hit_a = 0.0
        hit_m = 0.0
        for t0, _s0, a0, m0 in combined:
            d = abs(float(t0) - float(tt))
            if d < best:
                best = d
                hit_a = float(a0)
                hit_m = float(m0)
        return (float(hit_a), float(hit_m))

    def _classify(a: float, m: float, s: float) -> tuple[str, str]:
        # Nota: el pico suele estar DESPUÉS del desenlace (celebración / reacción).
        # 'goal' se usa como hipótesis para activar reglas de recorte fino.
        if a >= 0.93 and s >= 0.84:
            return ('goal', 'Auto · Gol (posible)')
        if m >= 0.84 and s >= 0.70:
            return ('shot', 'Auto · Finalización (posible)')
        # Turnover/press (ritmo alto pero sin explosión de audio).
        if m >= 0.90 and a <= 0.62 and s >= 0.68:
            return ('press', 'Auto · Presión / transición (posible)')
        return ('tag', 'Auto · Acción (revisar)')

    moments: list[AutoCutMoment] = []
    for t, s in chosen:
        a, m = _nearest_features(float(t))
        kind, label = _classify(float(a), float(m), float(s))
        moments.append(
            AutoCutMoment(
                time_s=float(t),
                kind=str(kind),
                score=float(s),
                label=str(label),
                meta={'source': 'segment_peak', 'pre_s': float(pre_s), 'post_s': float(post_s), 'a': float(a), 'm': float(m), 'profile': prof},
            )
        )
    for t, s in chosen_set:
        moments.append(
            AutoCutMoment(
                time_s=float(t),
                kind='abp',
                score=float(s),
                label='Auto · ABP / reinicio (posible)',
                meta={'source': 'motion_transition', 'pre_s': float(pre_s), 'post_s': float(post_s), 'profile': prof},
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

    allowed = {'tag', 'abp', 'goal', 'shot', 'press', 'turnover', 'note'}
    include_set = None
    if include_kinds is not None:
        try:
            include_set = {str(x or '').strip().lower() for x in include_kinds if str(x or '').strip()}
            include_set = {k for k in include_set if k in allowed}
        except Exception:
            include_set = None
        if not include_set:
            include_set = None

    # Clip ranges.
    out_moments = []
    for m in dedup:
        if include_set is not None and str(m.kind).lower() not in include_set:
            continue
        t = float(m.time_s)
        seg = seg_by_peak.get(float(m.time_s)) if 'seg_by_peak' in locals() else None
        if seg:
            seg_a, seg_b, _pt, _ps = seg
            start = max(0.0, float(seg_a) - float(pre_s))
            end = float(seg_b) + float(post_s)
        else:
            start = max(0.0, t - float(pre_s))
            end = t + float(post_s)
        if scan_limit and scan_limit > 0:
            end = min(float(scan_limit), end)

        refine_meta = {'refined': False}
        if refine and in_play:
            try:
                r_in, r_out, refine_meta = _refine_clip_bounds(
                    kind=str(m.kind),
                    t_peak=float(t),
                    clip_in_s=float(start),
                    clip_out_s=float(end),
                    in_play=in_play,
                    cut_times=cut_times,
                    step_s=float(step_s),
                )
                start, end = float(r_in), float(r_out)
            except Exception:
                refine_meta = {'refined': False, 'reason': 'refine_error'}

        # Confianza simple (v1): score + refinamiento.
        try:
            conf = float(_clamp(0.35 + (0.65 * float(m.score)), 0.0, 1.0))
            if refine_meta.get('refined'):
                conf = float(_clamp(conf + 0.08, 0.0, 1.0))
        except Exception:
            conf = 0.5

        out_moments.append(
            {
                'time_s': float(t),
                'kind': str(m.kind),
                'score': float(m.score),
                'label': str(m.label),
                'clip_in_s': float(start),
                'clip_out_s': float(max(start + 0.2, end)),
                'meta': dict(m.meta or {}) | {'refine': refine_meta, 'confidence': float(conf)},
            }
        )

    return {
        'ok': True,
        'duration_s': float(dur or 0.0),
        'scan_limit_s': float(scan_limit or 0.0) if scan_limit else 0.0,
        'moments': out_moments,
    }
