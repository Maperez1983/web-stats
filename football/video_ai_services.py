from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path


COCO_PERSON_CLASS_ID = 0
COCO_SPORTS_BALL_CLASS_ID = 32


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def color_signature_from_bgr(frame, det: dict) -> dict:
    try:
        import cv2  # noqa: WPS433
        import numpy as np  # noqa: WPS433
    except Exception:
        return {}
    try:
        h, w = frame.shape[:2]
        xc = clamp01(float(det.get("x_rel") or 0.0))
        yc = clamp01(float(det.get("y_rel") or 0.0))
        bw = max(0.01, min(0.5, float(det.get("w_rel") or 0.0)))
        bh = max(0.01, min(0.6, float(det.get("h_rel") or 0.0)))
        x0 = max(0, min(w - 1, int(round((xc - bw * 0.5) * w))))
        y0 = max(0, min(h - 1, int(round((yc - bh * 0.5) * h))))
        x1 = max(x0 + 1, min(w, int(round((xc + bw * 0.5) * w))))
        y1 = max(y0 + 1, min(h, int(round((yc + bh * 0.5) * h))))
        crop = frame[y0:y1, x0:x1]
        if crop.size <= 0:
            return {}
        # Zona central/torso: más estable que piernas/fondo.
        ch, cw = crop.shape[:2]
        torso = crop[int(ch * 0.18): int(ch * 0.62), int(cw * 0.20): int(cw * 0.80)]
        if torso.size <= 0:
            torso = crop
        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        pixels = hsv.reshape((-1, 3))
        if len(pixels) > 3000:
            idx = np.linspace(0, len(pixels) - 1, 3000).astype(int)
            pixels = pixels[idx]
        mean = pixels.mean(axis=0)
        hist_h = cv2.calcHist([hsv], [0], None, [12], [0, 180]).reshape(-1)
        hist_s = cv2.calcHist([hsv], [1], None, [8], [0, 256]).reshape(-1)
        hist_v = cv2.calcHist([hsv], [2], None, [8], [0, 256]).reshape(-1)
        hist = np.concatenate([hist_h, hist_s, hist_v]).astype("float32")
        total = float(hist.sum() or 0.0)
        if total > 0:
            hist = hist / total
        return {
            "h": float(mean[0]),
            "s": float(mean[1]),
            "v": float(mean[2]),
            "hist": [float(x) for x in hist.tolist()],
            "aspect": float(bw / max(0.001, bh)),
            "area": float(bw * bh),
        }
    except Exception:
        return {}


def color_distance(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    dh = abs(float(a.get("h") or 0.0) - float(b.get("h") or 0.0))
    dh = min(dh, 180.0 - dh) / 90.0
    ds = abs(float(a.get("s") or 0.0) - float(b.get("s") or 0.0)) / 255.0
    dv = abs(float(a.get("v") or 0.0) - float(b.get("v") or 0.0)) / 255.0
    return math.sqrt((dh * dh * 1.5) + (ds * ds * 0.8) + (dv * dv * 0.5))


def appearance_distance(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.5
    base = color_distance(a, b)
    hist_a = a.get("hist") if isinstance(a.get("hist"), list) else []
    hist_b = b.get("hist") if isinstance(b.get("hist"), list) else []
    hist_d = 0.0
    if hist_a and hist_b and len(hist_a) == len(hist_b):
        hist_d = 0.5 * sum(abs(float(x) - float(y)) for x, y in zip(hist_a, hist_b))
    try:
        aspect_d = min(1.0, abs(float(a.get("aspect") or 0.0) - float(b.get("aspect") or 0.0)) / 0.8)
    except Exception:
        aspect_d = 0.0
    try:
        area_a = float(a.get("area") or 0.0)
        area_b = float(b.get("area") or 0.0)
        area_d = min(1.0, abs(area_a - area_b) / max(0.001, max(area_a, area_b)))
    except Exception:
        area_d = 0.0
    return max(0.0, min(2.0, (base * 0.48) + (hist_d * 0.38) + (aspect_d * 0.08) + (area_d * 0.06)))


def ffmpeg_cut_to_proxy(*, src: Path, out: Path, start_s: float, end_s: float, fps: int = 30, height: int = 720) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg no disponible.")
    duration = max(0.1, float(end_s) - float(start_s))
    vf = []
    if height:
        vf.append(f"scale=-2:{int(height)}")
    if fps:
        vf.append(f"fps={int(fps)}")
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{float(start_s):.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(src),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        ",".join(vf) or "null",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        str(out),
    ]
    subprocess.check_call(cmd)  # noqa: S603


def yolo_track_video(
    *,
    source: Path,
    model_path: Path,
    start_s: float,
    end_s: float,
    conf: float = 0.25,
    imgsz: int = 960,
    tracker: str = "bytetrack.yaml",
    include_ball: bool = True,
) -> dict:
    from ultralytics import YOLO  # noqa: WPS433

    if not model_path.exists():
        raise RuntimeError(f"No existe modelo YOLO: {model_path}")
    if not source.exists():
        raise RuntimeError(f"No existe vídeo: {source}")

    tmp_path = None
    track_source = source
    try:
        if end_s > start_s + 0.05:
            tmp = tempfile.NamedTemporaryFile(prefix="2j-yolo-track-", suffix=".mp4", delete=False)
            tmp_path = Path(tmp.name)
            tmp.close()
            ffmpeg_cut_to_proxy(src=source, out=tmp_path, start_s=start_s, end_s=end_s)
            track_source = tmp_path

        classes = [COCO_PERSON_CLASS_ID]
        if include_ball:
            classes.append(COCO_SPORTS_BALL_CLASS_ID)
        model = YOLO(str(model_path))
        result_iter = model.track(
            source=str(track_source),
            classes=classes,
            conf=max(0.01, min(0.95, float(conf))),
            imgsz=max(320, min(1920, int(imgsz))),
            tracker=tracker,
            persist=True,
            stream=True,
            save=False,
            verbose=False,
        )

        frames = []
        for frame_idx, result in enumerate(result_iter):
            boxes = result.boxes
            frame_items = []
            frame = getattr(result, "orig_img", None)
            frame_h = 0
            frame_w = 0
            try:
                if frame is not None:
                    frame_h, frame_w = frame.shape[:2]
            except Exception:
                frame_h = 0
                frame_w = 0
            if boxes is not None and len(boxes):
                xywhn = boxes.xywhn.cpu().numpy().tolist() if boxes.xywhn is not None else []
                confs = boxes.conf.cpu().numpy().tolist() if boxes.conf is not None else []
                ids = boxes.id.cpu().numpy().tolist() if boxes.id is not None else [None] * len(xywhn)
                clss = boxes.cls.cpu().numpy().tolist() if boxes.cls is not None else [0] * len(xywhn)
                for idx, box in enumerate(xywhn):
                    class_id = int(clss[idx]) if idx < len(clss) else 0
                    det = {
                        "track_id": int(ids[idx]) if ids[idx] is not None else None,
                        "class_id": class_id,
                        "class_name": "ball" if class_id == COCO_SPORTS_BALL_CLASS_ID else "person",
                        "conf": float(confs[idx]) if idx < len(confs) else 0.0,
                        "x_rel": float(box[0]),
                        "y_rel": float(box[1]),
                        "w_rel": float(box[2]),
                        "h_rel": float(box[3]),
                    }
                    if class_id == COCO_PERSON_CLASS_ID and frame is not None:
                        det["color"] = color_signature_from_bgr(frame, det)
                    frame_items.append(det)
            frames.append(
                {
                    "frame": int(frame_idx),
                    "t": float(start_s + (frame_idx / 30.0)),
                    "width": int(frame_w or 0),
                    "height": int(frame_h or 0),
                    "detections": frame_items,
                }
            )
        return {
            "ok": True,
            "source": str(source),
            "model": str(model_path),
            "tracker": tracker,
            "conf": float(conf),
            "imgsz": int(imgsz),
            "start_s": float(start_s),
            "end_s": float(end_s),
            "frames": frames,
        }
    finally:
        if tmp_path:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass


def write_track_json(payload: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
