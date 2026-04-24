#!/usr/bin/env python3
"""
Convierte un vídeo (tipo Instagram/Reels con campo + chapas) en un "clip" del simulador.

Salida: JSON compatible con "Importar clip" (incluye `steps`) + `pro` (Timeline Pro con keyframes).

Uso:
  python3 scripts/ig_video_to_clip.py \
    --input "/ruta/video.mp4" \
    --output "/ruta/clip.json" \
    --name "IG · Partido condicionado"
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PIL import Image


WORLD_W = 1054
WORLD_H = 684


def _run(cmd: List[str]) -> str:
    proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return (proc.stdout or "").strip()


def _ffprobe_duration_seconds(path: str) -> float:
    try:
        out = _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                path,
            ]
        )
        return max(0.0, float(out or 0.0))
    except Exception:
        return 0.0


def _extract_frames(input_path: str, output_dir: str, fps: int, max_frames: int, scale_w: int) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    pattern = os.path.join(output_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-vf",
        f"fps={fps},scale={scale_w}:-2",
        "-frames:v",
        str(max_frames),
        "-q:v",
        "3",
        pattern,
    ]
    _run(cmd)
    frames = []
    for name in sorted(os.listdir(output_dir)):
        if name.lower().endswith(".jpg") and name.startswith("frame_"):
            frames.append(os.path.join(output_dir, name))
    return frames


def _is_grass(r: int, g: int, b: int) -> bool:
    return g > 70 and g > r + 14 and g > b + 14


def _crop_to_grass(img: Image.Image) -> Image.Image:
    """
    Recorta el área dominante verde (campo) para eliminar barras negras/márgenes.
    """
    rgb = img.convert("RGB")
    w0, h0 = rgb.size
    if w0 <= 0 or h0 <= 0:
        return rgb
    probe_max = 320
    scale = min(1.0, float(probe_max) / float(max(w0, h0)))
    probe = rgb
    if scale < 1.0:
        probe = rgb.resize(
            (max(1, int(round(w0 * scale))), max(1, int(round(h0 * scale)))),
            Image.BILINEAR,
        )
    pw, ph = probe.size
    px = probe.load()
    minx, miny = pw, ph
    maxx, maxy = -1, -1
    green_count = 0
    for y in range(ph):
        for x in range(pw):
            r, g, b = px[x, y]
            if _is_grass(r, g, b):
                green_count += 1
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if maxx <= minx or maxy <= miny:
        return rgb
    area = float((maxx - minx + 1) * (maxy - miny + 1))
    total = float(max(1, pw * ph))
    if area / total < 0.10 or (green_count / total) < 0.08:
        return rgb
    pad = int(round(0.05 * float(max(pw, ph))))
    minx = max(0, minx - pad)
    miny = max(0, miny - pad)
    maxx = min(pw - 1, maxx + pad)
    maxy = min(ph - 1, maxy + pad)
    sx = 1.0 / max(scale, 1e-6)
    box = (
        max(0, min(int(minx * sx), w0 - 1)),
        max(0, min(int(miny * sx), h0 - 1)),
        max(1, min(int((maxx + 1) * sx), w0)),
        max(1, min(int((maxy + 1) * sx), h0)),
    )
    if box[2] <= box[0] + 20 or box[3] <= box[1] + 20:
        return rgb
    return rgb.crop(box)


@dataclass
class DetectedToken:
    x: float  # 0..1
    y: float  # 0..1
    team: str  # "local" | "rival"
    score: float


def _lum(r: float, g: float, b: float) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _detect_tokens(img: Image.Image) -> List[DetectedToken]:
    """
    Detección rápida por blobs (sin OCR): busca componentes no-verdes con forma de "chapa" (bbox casi cuadrado).
    """
    rgb = img.convert("RGB")
    # Reduce para acelerar.
    w0, h0 = rgb.size
    max_side = 520
    scale = min(1.0, float(max_side) / float(max(w0, h0)))
    if scale < 1.0:
        rgb = rgb.resize((max(1, int(round(w0 * scale))), max(1, int(round(h0 * scale)))), Image.BILINEAR)
    w, h = rgb.size
    px = rgb.load()

    # Máscara binaria: todo lo que NO es césped (incluye blancos/negros/rojos/azules).
    mask = bytearray(w * h)
    for yy in range(h):
        row = yy * w
        for xx in range(w):
            r, g, b = px[xx, yy]
            if _is_grass(r, g, b):
                continue
            # Evita "casi blanco puro" (bordes/antialias) sin perder chapas blancas.
            if r >= 252 and g >= 252 and b >= 252:
                continue
            mask[row + xx] = 1

    visited = bytearray(w * h)
    tokens: List[DetectedToken] = []

    def idx(x: int, y: int) -> int:
        return y * w + x

    for y in range(h):
        for x in range(w):
            i = idx(x, y)
            if not mask[i] or visited[i]:
                continue
            # BFS 4-neigh.
            stack = [(x, y)]
            visited[i] = 1
            count = 0
            minx = maxx = x
            miny = maxy = y
            sumx = 0.0
            sumy = 0.0
            sumr = 0.0
            sumg = 0.0
            sumb = 0.0
            while stack:
                cx, cy = stack.pop()
                count += 1
                if cx < minx:
                    minx = cx
                if cx > maxx:
                    maxx = cx
                if cy < miny:
                    miny = cy
                if cy > maxy:
                    maxy = cy
                sumx += cx
                sumy += cy
                rr, gg, bb = px[cx, cy]
                sumr += rr
                sumg += gg
                sumb += bb
                if count > 12_000:
                    break
                if cx > 0:
                    ni = idx(cx - 1, cy)
                    if mask[ni] and not visited[ni]:
                        visited[ni] = 1
                        stack.append((cx - 1, cy))
                if cx + 1 < w:
                    ni = idx(cx + 1, cy)
                    if mask[ni] and not visited[ni]:
                        visited[ni] = 1
                        stack.append((cx + 1, cy))
                if cy > 0:
                    ni = idx(cx, cy - 1)
                    if mask[ni] and not visited[ni]:
                        visited[ni] = 1
                        stack.append((cx, cy - 1))
                if cy + 1 < h:
                    ni = idx(cx, cy + 1)
                    if mask[ni] and not visited[ni]:
                        visited[ni] = 1
                        stack.append((cx, cy + 1))

            bw = max(1, maxx - minx + 1)
            bh = max(1, maxy - miny + 1)
            bbox_area = float(bw * bh)
            density = float(count) / max(1.0, bbox_area)
            aspect = float(bw) / float(max(1, bh))

            # Filtros para chapas típicas (descarta líneas del campo, textos grandes, etc.).
            if count < 70 or count > 6000:
                continue
            if bw < 10 or bh < 10 or bw > 70 or bh > 70:
                continue
            if aspect < 0.55 or aspect > 1.75:
                continue
            if density < 0.24:
                continue

            cx = (sumx / max(1.0, float(count))) / float(w)
            cy = (sumy / max(1.0, float(count))) / float(h)
            ar = sumr / max(1.0, float(count))
            ag = sumg / max(1.0, float(count))
            ab = sumb / max(1.0, float(count))
            mx = max(ar, ag, ab)
            mn = min(ar, ag, ab)
            sat = mx - mn
            l = _lum(ar, ag, ab)

            team = "local"
            if ar >= 120 and (ar - ag) >= 32 and (ar - ab) >= 22:
                team = "rival"
            elif l >= 200 and sat <= 26:
                team = "local"
            elif l <= 78:
                team = "local"

            score = density * 1.4 + min(1.0, float(count) / 1800.0)
            tokens.append(DetectedToken(x=cx, y=cy, team=team, score=score))

    # Mantén los mejores (evita ruido).
    tokens.sort(key=lambda t: t.score, reverse=True)
    return tokens[:28]


@dataclass
class Track:
    uid: str
    team: str
    positions: List[Tuple[int, float, float]]  # (t_ms, x, y) in world coords


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _assign_tracks(
    tracks: List[Track],
    detections: List[DetectedToken],
    t_ms: int,
    next_local: int,
    next_rival: int,
    max_dist_world: float,
) -> Tuple[List[Track], int, int, Dict[str, Tuple[float, float]]]:
    # Convert to world coords.
    det_world = []
    for det in detections:
        left = float(det.x) * float(WORLD_W)
        top = float(det.y) * float(WORLD_H)
        det_world.append((det, left, top))

    # Greedy matching by distance per team.
    used_det = set()
    used_track = set()
    assignments: List[Tuple[float, int, int, float, float]] = []
    for ti, tr in enumerate(tracks):
        if not tr.positions:
            continue
        _, lastx, lasty = tr.positions[-1]
        for di, (det, xw, yw) in enumerate(det_world):
            if det.team != tr.team:
                continue
            d = _distance((lastx, lasty), (xw, yw))
            if d <= max_dist_world:
                assignments.append((d, ti, di, xw, yw))
    assignments.sort(key=lambda it: it[0])
    frame_positions: Dict[str, Tuple[float, float]] = {}

    for d, ti, di, xw, yw in assignments:
        if ti in used_track or di in used_det:
            continue
        used_track.add(ti)
        used_det.add(di)
        tracks[ti].positions.append((t_ms, xw, yw))
        frame_positions[tracks[ti].uid] = (xw, yw)

    # Create new tracks for unassigned detections.
    for di, (det, xw, yw) in enumerate(det_world):
        if di in used_det:
            continue
        if det.team == "rival":
            uid = f"R{next_rival}"
            next_rival += 1
        else:
            uid = f"L{next_local}"
            next_local += 1
        tracks.append(Track(uid=uid, team=det.team, positions=[(t_ms, xw, yw)]))
        frame_positions[uid] = (xw, yw)
        if len(tracks) >= 26:
            break

    return tracks, next_local, next_rival, frame_positions


def _token_object(uid: str, team: str, left: float, top: float) -> dict:
    # Minimal "token" fabric group pero marcando roles para evitar conversión legacy (y preservar layer_uid).
    if team == "rival":
        fill = "#dc2626"
        stroke = "#fff7ed"
        token_kind = "player_rival"
    else:
        fill = "#1d4ed8"
        stroke = "#eff6ff"
        token_kind = "player_local"

    objects = [
        {
            "type": "circle",
            "left": 0,
            "top": 0,
            "originX": "center",
            "originY": "center",
            "radius": 16,
            "fill": fill,
            "stroke": stroke,
            "strokeWidth": 2,
            "objectCaching": False,
            "data": {"role": "token_circle"},
        }
    ]
    # player_local: añade un marcador "token_stripes" para evitar la conversión legacy.
    if token_kind == "player_local":
        objects.append(
            {
                "type": "rect",
                "left": 0,
                "top": 0,
                "originX": "center",
                "originY": "center",
                "width": 1,
                "height": 1,
                "fill": "rgba(0,0,0,0)",
                "stroke": "rgba(0,0,0,0)",
                "strokeWidth": 0,
                "selectable": False,
                "evented": False,
                "data": {"role": "token_stripes"},
            }
        )

    return {
        "type": "group",
        "left": float(left),
        "top": float(top),
        "originX": "center",
        "originY": "center",
        "objectCaching": False,
        "data": {
            "kind": "token",
            "token_kind": token_kind,
            "layer_uid": uid,
            "playerName": "",
            "playerNumber": "",
        },
        "objects": objects,
    }


def build_clip_from_video(
    input_path: str,
    name: str,
    fps: int,
    max_frames: int,
    scale_w: int,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="ig_frames_") as tmp:
        frames = _extract_frames(input_path, tmp, fps=fps, max_frames=max_frames, scale_w=scale_w)
        if not frames:
            raise SystemExit("No se pudieron extraer frames del vídeo.")

        tracks: List[Track] = []
        next_local = 1
        next_rival = 1
        steps = []
        frame_uid_pos: List[Dict[str, Tuple[float, float]]] = []

        # Distancia máxima entre frames (en coords world). Ajuste “suave” para cambios rápidos.
        max_dist_world = float(WORLD_W) * 0.16

        for i, frame_path in enumerate(frames):
            t_ms = int(round((1000.0 / float(max(1, fps))) * float(i)))
            with Image.open(frame_path) as raw:
                cropped = _crop_to_grass(raw)
                detections = _detect_tokens(cropped)
            tracks, next_local, next_rival, pos_map = _assign_tracks(
                tracks,
                detections,
                t_ms=t_ms,
                next_local=next_local,
                next_rival=next_rival,
                max_dist_world=max_dist_world,
            )
            frame_uid_pos.append(pos_map)

        # Consolidar lista de UIDs final (en orden estable).
        def uid_sort(u: str) -> Tuple[int, int]:
            if u.startswith("R"):
                return (0, int(u[1:] or "0"))
            if u.startswith("L"):
                return (1, int(u[1:] or "0"))
            return (2, 0)

        uids = sorted({tr.uid for tr in tracks}, key=uid_sort)[:26]
        team_by_uid = {tr.uid: tr.team for tr in tracks}

        # Construye steps (duración mínima 1s).
        for idx_frame, pos_map in enumerate(frame_uid_pos):
            objects = []
            for uid in uids:
                team = team_by_uid.get(uid, "local")
                # Posición del frame: si falta, usa última conocida de ese track.
                if uid in pos_map:
                    left, top = pos_map[uid]
                else:
                    # busca hacia atrás
                    left = None
                    top = None
                    for back in range(idx_frame - 1, -1, -1):
                        prev = frame_uid_pos[back]
                        if uid in prev:
                            left, top = prev[uid]
                            break
                    if left is None or top is None:
                        continue
                objects.append(_token_object(uid, team, left, top))

            steps.append(
                {
                    "title": f"Paso {idx_frame + 1}",
                    "duration": 1,
                    "canvas_state": {"version": "5.3.0", "objects": objects},
                    "canvas_width": WORLD_W,
                    "canvas_height": WORLD_H,
                    "moves": [],
                    "routes": {},
                    "ball_follow_uid": "",
                }
            )

        # Timeline Pro: keyframes por uid (left/top).
        tracks_payload: Dict[str, list] = {}
        for tr in tracks:
            if tr.uid not in uids:
                continue
            kfs = []
            for t_ms, left, top in tr.positions:
                kfs.append(
                    {
                        "t_ms": int(t_ms),
                        "easing": "linear",
                        "props": {
                            "left": float(left),
                            "top": float(top),
                            "angle": 0,
                            "scaleX": 1,
                            "scaleY": 1,
                            "opacity": 1,
                        },
                    }
                )
            kfs.sort(key=lambda k: int(k.get("t_ms") or 0))
            if len(kfs) >= 2:
                # reduce a un máximo razonable
                tracks_payload[tr.uid] = kfs[:240]

        pro = {"v": 1, "enabled": True, "loop": True, "updated_at": dt.datetime.utcnow().isoformat() + "Z", "tracks": tracks_payload}

        return {
            "v": 1,
            "name": str(name or "Clip importado").strip()[:120],
            "created_at": dt.datetime.utcnow().isoformat() + "Z",
            "source": {"kind": "video", "fps": fps, "max_frames": max_frames, "scale_w": scale_w, "duration_s": _ffprobe_duration_seconds(input_path)},
            "steps": steps,
            "pro": pro,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convierte un vídeo tipo IG a clip JSON (simulador).")
    parser.add_argument("--input", required=True, help="Ruta al MP4")
    parser.add_argument("--output", required=True, help="Ruta de salida .json")
    parser.add_argument("--name", default="", help="Nombre del clip")
    parser.add_argument("--fps", type=int, default=1, help="Frames por segundo a muestrear (1 recomendado)")
    parser.add_argument("--max-frames", type=int, default=45, help="Máximo frames a procesar")
    parser.add_argument("--scale-w", type=int, default=640, help="Ancho al extraer frames (reduce ruido)")
    args = parser.parse_args()

    input_path = os.path.expanduser(args.input)
    output_path = os.path.expanduser(args.output)
    name = args.name or os.path.splitext(os.path.basename(input_path))[0]

    payload = build_clip_from_video(
        input_path=input_path,
        name=name,
        fps=max(1, int(args.fps)),
        max_frames=max(1, int(args.max_frames)),
        scale_w=max(320, int(args.scale_w)),
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(output_path)


if __name__ == "__main__":
    main()

