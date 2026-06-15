from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
from django.core.management.base import BaseCommand, CommandError

from football.models import RivalVideo, VideoAiCorrectionExample, VideoClip
from football.video_ai_services import COCO_PERSON_CLASS_ID, appearance_distance, yolo_track_video


class Command(BaseCommand):
    help = "Exporta un corte de prueba con seguimiento de jugador, trayectoria y validacion visual."

    def add_arguments(self, parser):
        parser.add_argument("--video-id", type=int, required=True)
        parser.add_argument("--start", type=float, required=True)
        parser.add_argument("--end", type=float, required=True)
        parser.add_argument("--out", type=str, default="/Volumes/Mac Satecchi/Mac/Downloads/prueba_seguimiento_jugador.mp4")
        parser.add_argument("--report", type=str, default="")
        parser.add_argument("--model", type=str, default="data/video_ai/models/yolo11n.pt")
        parser.add_argument("--track-id", type=int, default=0)
        parser.add_argument("--clip-id", type=int, default=0)
        parser.add_argument("--marker-uid", type=str, default="")
        parser.add_argument("--anchor-x", type=float, default=-1.0, help="x normalizada 0..1 para escoger jugador en el primer frame util.")
        parser.add_argument("--anchor-y", type=float, default=-1.0, help="y normalizada 0..1 para escoger jugador en el primer frame util.")
        parser.add_argument("--conf", type=float, default=0.18)
        parser.add_argument("--imgsz", type=int, default=960)
        parser.add_argument("--visual-tracker", action="store_true", default=True)

    def handle(self, *args, **options):
        video = RivalVideo.objects.filter(id=int(options["video_id"])).first()
        if not video or not getattr(video, "video", None):
            raise CommandError("Video no encontrado o sin archivo.")
        source = Path(video.video.path)
        if not source.exists():
            raise CommandError(f"No existe el archivo: {source}")
        start = max(0.0, float(options["start"]))
        end = max(start + 0.5, float(options["end"]))
        model = Path(str(options["model"])).resolve()
        out_path = Path(str(options["out"])).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        report_path = Path(str(options["report"] or out_path.with_suffix(".json"))).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)

        payload = yolo_track_video(
            source=source,
            model_path=model,
            start_s=start,
            end_s=end,
            conf=float(options["conf"]),
            imgsz=int(options["imgsz"]),
            include_ball=True,
        )
        frames = payload.get("frames") if isinstance(payload.get("frames"), list) else []
        if not frames:
            raise CommandError("YOLO no devolvio frames.")

        target_id = int(options.get("track_id") or 0) or self._choose_target_id(
            frames,
            anchor_x=float(options.get("anchor_x") or -1.0),
            anchor_y=float(options.get("anchor_y") or -1.0),
        )
        if not target_id:
            raise CommandError("No se pudo escoger jugador objetivo.")

        manual_anchors = self._manual_anchors(
            video=video,
            clip_id=int(options.get("clip_id") or 0),
            marker_uid=str(options.get("marker_uid") or ""),
            start=start,
            end=end,
        )
        if manual_anchors and not int(options.get("track_id") or 0):
            first_anchor = manual_anchors[0]
            target_id = self._choose_target_id(frames, anchor_x=float(first_anchor["x_rel"]), anchor_y=float(first_anchor["y_rel"])) or target_id

        track_points = self._track_points(frames, target_id)
        if manual_anchors:
            track_points = self._inject_manual_anchors(track_points, manual_anchors, frames)
        stitched_points = self._stitch_follow_points(frames, track_points, target_id=target_id)
        if len(stitched_points) > len(track_points):
            track_points = stitched_points
        if bool(options.get("visual_tracker")):
            visual_points = self._visual_tracker_points(
                source=source,
                start=start,
                end=end,
                frames=frames,
                seed_points=track_points,
                target_id=target_id,
            )
            if len(visual_points) >= len(track_points):
                track_points = visual_points
        if len(track_points) < 3:
            raise CommandError(f"Track {target_id} insuficiente: {len(track_points)} puntos.")
        interp_points = self._interpolate_points(track_points, frames)
        report = self._quality_report(frames, track_points, interp_points, target_id=target_id, start=start, end=end)
        report["manual_anchors"] = manual_anchors

        self._render_video(
            source=source,
            out_path=out_path,
            start=start,
            end=end,
            target_id=target_id,
            points_by_frame={int(p["frame"]): p for p in interp_points},
            raw_frames=frames,
        )
        report["output"] = str(out_path)
        report["report"] = str(report_path)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))

    def _person_detections(self, frame: dict) -> list[dict]:
        return [
            d for d in (frame.get("detections") or [])
            if int(d.get("class_id") or 0) == COCO_PERSON_CLASS_ID and d.get("track_id") is not None
        ]

    def _manual_anchors(self, *, video: RivalVideo, clip_id: int, marker_uid: str, start: float, end: float) -> list[dict]:
        qs = VideoAiCorrectionExample.objects.filter(video=video, time_ms__gte=int(round(start * 1000)), time_ms__lte=int(round(end * 1000)))
        if clip_id:
            clip = VideoClip.objects.filter(id=int(clip_id), video=video).first()
            if clip:
                qs = qs.filter(clip=clip)
        if marker_uid:
            qs = qs.filter(marker_uid=str(marker_uid)[:100])
        anchors = []
        for row in qs.order_by("time_ms", "id")[:24]:
            anchors.append(
                {
                    "id": int(row.id),
                    "frame": max(0, int(round((float(row.time_ms or 0) / 1000.0 - start) * 30.0))),
                    "t": float(row.time_ms or 0) / 1000.0,
                    "x_rel": max(0.0, min(1.0, float(row.x_rel or 0.0))),
                    "y_rel": max(0.0, min(1.0, float(row.y_rel or 0.0))),
                    "label": str(row.label or ""),
                    "marker_uid": str(row.marker_uid or ""),
                }
            )
        return anchors

    def _inject_manual_anchors(self, points: list[dict], anchors: list[dict], frames: list[dict]) -> list[dict]:
        by_frame = {int(p["frame"]): dict(p) for p in points}
        for anchor in anchors:
            frame_idx = int(anchor.get("frame") or 0)
            nearby = None
            for offset in range(0, 8):
                for candidate_idx in (frame_idx - offset, frame_idx + offset):
                    if candidate_idx in by_frame:
                        nearby = by_frame[candidate_idx]
                        break
                if nearby:
                    break
            row = dict(nearby or {})
            row.update(
                {
                    "frame": frame_idx,
                    "t": float(anchor.get("t") or 0.0),
                    "x_rel": float(anchor.get("x_rel") or 0.0),
                    "y_rel": float(anchor.get("y_rel") or 0.0),
                    "w_rel": float(row.get("w_rel") or 0.05),
                    "h_rel": float(row.get("h_rel") or 0.12),
                    "conf": 1.0,
                    "follow_conf": 1.0,
                    "source": "manual_anchor",
                    "manual_anchor_id": int(anchor.get("id") or 0),
                }
            )
            by_frame[frame_idx] = row
        return [by_frame[k] for k in sorted(by_frame)]

    def _choose_target_id(self, frames: list[dict], *, anchor_x: float, anchor_y: float) -> int:
        has_anchor = 0.0 <= anchor_x <= 1.0 and 0.0 <= anchor_y <= 1.0
        if has_anchor:
            for frame in frames:
                people = self._person_detections(frame)
                if not people:
                    continue
                best = min(people, key=lambda d: math.hypot(float(d.get("x_rel") or 0.0) - anchor_x, float(d.get("y_rel") or 0.0) - anchor_y))
                return int(best.get("track_id") or 0)

        by_id: dict[int, list[dict]] = {}
        for frame in frames:
            for det in self._person_detections(frame):
                by_id.setdefault(int(det.get("track_id")), []).append({"frame": int(frame.get("frame") or 0), **det})
        if not by_id:
            return 0

        def _score(rows: list[dict]) -> float:
            if len(rows) < 3:
                return 0.0
            xs = [float(r.get("x_rel") or 0.0) for r in rows]
            ys = [float(r.get("y_rel") or 0.0) for r in rows]
            movement = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
            avg_area = sum(float(r.get("w_rel") or 0.0) * float(r.get("h_rel") or 0.0) for r in rows) / max(1, len(rows))
            return (len(rows) * 1.0) + (movement * 28.0) + (avg_area * 80.0)

        return int(max(by_id.items(), key=lambda item: _score(item[1]))[0])

    def _track_points(self, frames: list[dict], target_id: int) -> list[dict]:
        points = []
        for frame in frames:
            for det in self._person_detections(frame):
                if int(det.get("track_id") or 0) != int(target_id):
                    continue
                points.append(
                    {
                        "frame": int(frame.get("frame") or 0),
                        "t": float(frame.get("t") or 0.0),
                        "x_rel": float(det.get("x_rel") or 0.0),
                        "y_rel": float(det.get("y_rel") or 0.0),
                        "w_rel": float(det.get("w_rel") or 0.0),
                        "h_rel": float(det.get("h_rel") or 0.0),
                        "conf": float(det.get("conf") or 0.0),
                        "source": "detection",
                    }
                )
                break
        return points

    def _stitch_follow_points(self, frames: list[dict], seed_points: list[dict], *, target_id: int) -> list[dict]:
        seed_by_frame = {int(p["frame"]): p for p in seed_points}
        if not seed_by_frame:
            return seed_points
        first_seed = min(seed_points, key=lambda p: int(p["frame"]))
        identity_ref = None
        # Buscamos la firma visual del primer punto detectado.
        for frame in frames:
            if int(frame.get("frame") or 0) != int(first_seed["frame"]):
                continue
            for det in self._person_detections(frame):
                if int(det.get("track_id") or 0) == int(target_id) and isinstance(det.get("color"), dict):
                    identity_ref = det.get("color")
                    break
        out = []
        last = None
        prev = None
        used_ids = set()
        prediction_streak = 0
        for frame in frames:
            idx = int(frame.get("frame") or 0)
            t = float(frame.get("t") or 0.0)
            people = self._person_detections(frame)
            chosen = None
            source = "detection"
            predicted = self._predict_point(last, prev, t) if last is not None else None
            # Si el ID original sigue vivo, lo usamos.
            for det in people:
                if int(det.get("track_id") or 0) == int(target_id):
                    chosen = det
                    source = "detection_id"
                    break
            if chosen is None and last is not None:
                candidates = []
                for det in people:
                    geom = math.hypot(float(det.get("x_rel") or 0.0) - predicted["x_rel"], float(det.get("y_rel") or 0.0) - predicted["y_rel"])
                    max_geom = 0.14 if prediction_streak <= 6 else 0.24
                    if geom > max_geom:
                        continue
                    app = appearance_distance(identity_ref, det.get("color") if isinstance(det.get("color"), dict) else {}) if identity_ref else 0.45
                    conf = float(det.get("conf") or 0.0)
                    if prediction_streak > 12 and app > 0.62:
                        continue
                    # Geometría manda; apariencia evita saltar a un rival cercano.
                    score = (geom * 0.68) + (app * 0.24) - (conf * 0.03)
                    candidates.append((score, det))
                if candidates:
                    candidates.sort(key=lambda row: row[0])
                    chosen = candidates[0][1]
                    source = "stitched_motion_appearance"
            if chosen is None:
                if predicted is not None:
                    chosen = {
                        "x_rel": predicted["x_rel"],
                        "y_rel": predicted["y_rel"],
                        "w_rel": float(last.get("w_rel") or 0.05),
                        "h_rel": float(last.get("h_rel") or 0.12),
                        "conf": 0.25,
                    }
                    source = "prediction_low_conf"
                else:
                    continue
            if last is not None and chosen is not None:
                jump = math.hypot(float(chosen.get("x_rel") or 0.0) - float(last.get("x_rel") or 0.0), float(chosen.get("y_rel") or 0.0) - float(last.get("y_rel") or 0.0))
                if jump > 0.075 and predicted is not None:
                    chosen = {
                        "x_rel": predicted["x_rel"],
                        "y_rel": predicted["y_rel"],
                        "w_rel": float(last.get("w_rel") or chosen.get("w_rel") or 0.05),
                        "h_rel": float(last.get("h_rel") or chosen.get("h_rel") or 0.12),
                        "conf": 0.22,
                    }
                    source = "prediction_jump_guard"
            if chosen is None:
                continue
            if str(source).startswith("prediction"):
                prediction_streak += 1
            else:
                prediction_streak = 0
            if chosen.get("track_id") is not None:
                used_ids.add(int(chosen.get("track_id")))
            point_conf = float(chosen.get("conf") or 0.0)
            if source == "detection_id":
                follow_conf = min(1.0, 0.72 + point_conf * 0.28)
            elif source == "stitched_motion_appearance":
                follow_conf = min(0.82, 0.48 + point_conf * 0.26)
            elif source == "prediction_jump_guard":
                follow_conf = max(0.12, 0.36 - min(0.22, prediction_streak * 0.012))
            else:
                follow_conf = max(0.10, 0.32 - min(0.22, prediction_streak * 0.014))
            point = {
                "frame": idx,
                "t": t,
                "x_rel": float(chosen.get("x_rel") or 0.0),
                "y_rel": float(chosen.get("y_rel") or 0.0),
                "w_rel": float(chosen.get("w_rel") or 0.0),
                "h_rel": float(chosen.get("h_rel") or 0.0),
                "conf": point_conf,
                "follow_conf": round(float(follow_conf), 4),
                "source": source,
                "track_id": int(chosen.get("track_id") or 0) if chosen.get("track_id") is not None else None,
            }
            if identity_ref and isinstance(chosen.get("color"), dict) and source != "stitched_motion_appearance":
                identity_ref = self._blend_identity(identity_ref, chosen.get("color"), alpha=0.05)
            out.append(point)
            prev = last
            last = point
        # Solo aceptamos el cosido si mejora cobertura claramente.
        if len(out) >= len(seed_points) * 1.35:
            return self._smooth_points(out)
        return seed_points

    def _predict_point(self, last: dict, prev: dict | None, t: float) -> dict:
        if not prev:
            return {"x_rel": float(last.get("x_rel") or 0.0), "y_rel": float(last.get("y_rel") or 0.0)}
        dt = max(0.001, float(last.get("t") or 0.0) - float(prev.get("t") or 0.0))
        lead = max(0.0, float(t) - float(last.get("t") or 0.0))
        vx = (float(last.get("x_rel") or 0.0) - float(prev.get("x_rel") or 0.0)) / dt
        vy = (float(last.get("y_rel") or 0.0) - float(prev.get("y_rel") or 0.0)) / dt
        return {
            "x_rel": max(0.0, min(1.0, float(last.get("x_rel") or 0.0) + vx * lead)),
            "y_rel": max(0.0, min(1.0, float(last.get("y_rel") or 0.0) + vy * lead)),
        }

    def _blend_identity(self, a: dict, b: dict, *, alpha: float) -> dict:
        out = dict(a or {})
        alpha = max(0.0, min(0.4, float(alpha)))
        for key in ("h", "s", "v", "aspect", "area"):
            try:
                out[key] = (float(a.get(key) or 0.0) * (1.0 - alpha)) + (float(b.get(key) or 0.0) * alpha)
            except Exception:
                pass
        ha = a.get("hist") if isinstance(a.get("hist"), list) else []
        hb = b.get("hist") if isinstance(b.get("hist"), list) else []
        if ha and hb and len(ha) == len(hb):
            out["hist"] = [(float(x) * (1.0 - alpha)) + (float(y) * alpha) for x, y in zip(ha, hb)]
        return out

    def _smooth_points(self, points: list[dict]) -> list[dict]:
        if len(points) < 3:
            return points
        out = []
        for idx, point in enumerate(points):
            if idx == 0 or idx == len(points) - 1:
                out.append(dict(point))
                continue
            prev = points[idx - 1]
            nxt = points[idx + 1]
            row = dict(point)
            row["x_rel"] = (float(point["x_rel"]) * 0.72) + (((float(prev["x_rel"]) + float(nxt["x_rel"])) / 2.0) * 0.28)
            row["y_rel"] = (float(point["y_rel"]) * 0.72) + (((float(prev["y_rel"]) + float(nxt["y_rel"])) / 2.0) * 0.28)
            out.append(row)
        return out

    def _visual_tracker_points(self, *, source: Path, start: float, end: float, frames: list[dict], seed_points: list[dict], target_id: int) -> list[dict]:
        if not seed_points or not hasattr(cv2, "TrackerMIL_create"):
            return seed_points
        seed_by_frame = {int(p["frame"]): p for p in seed_points}
        first = min(seed_points, key=lambda p: int(p["frame"]))
        cap = cv2.VideoCapture(str(source))
        if not cap or not cap.isOpened():
            return seed_points
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

        def _bbox_from_point(p: dict) -> tuple[int, int, int, int]:
            bw = max(16, int(round(float(p.get("w_rel") or 0.05) * width)))
            bh = max(24, int(round(float(p.get("h_rel") or 0.12) * height)))
            x = int(round(float(p.get("x_rel") or 0.0) * width)) - bw // 2
            y = int(round(float(p.get("y_rel") or 0.0) * height)) - bh // 2
            x = max(0, min(width - 2, x))
            y = max(0, min(height - 2, y))
            bw = max(8, min(width - x - 1, bw))
            bh = max(8, min(height - y - 1, bh))
            return (x, y, bw, bh)

        tracker = cv2.TrackerMIL_create()
        out = []
        local_idx = 0
        initialized = False
        identity_ref = None
        last_box = None
        try:
            while True:
                if local_idx >= len(frames):
                    break
                pos_s = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
                if pos_s > end:
                    break
                ok, image = cap.read()
                if not ok:
                    break
                frame_meta = frames[local_idx] if local_idx < len(frames) else {"frame": local_idx, "t": start + (local_idx / 30.0), "detections": []}
                seed = seed_by_frame.get(local_idx)
                if seed is not None and seed.get("source") == "manual_anchor" and initialized:
                    box = _bbox_from_point(seed)
                    tracker = cv2.TrackerMIL_create()
                    try:
                        tracker.init(image, box)
                        last_box = box
                    except Exception:
                        pass
                if not initialized and seed is None:
                    local_idx += 1
                    continue
                if not initialized:
                    box = _bbox_from_point(seed)
                    try:
                        tracker.init(image, box)
                    except Exception:
                        return seed_points
                    initialized = True
                    last_box = box
                    identity_ref = self._identity_for_point(frame_meta, target_id)
                else:
                    ok_track, box = tracker.update(image)
                    if ok_track:
                        last_box = tuple(int(round(v)) for v in box)
                    box = last_box
                if not box:
                    local_idx += 1
                    continue
                x, y, bw, bh = box
                cx = (float(x) + float(bw) / 2.0) / max(1, width)
                cy = (float(y) + float(bh) / 2.0) / max(1, height)
                source_label = "visual_tracker"
                follow_conf = 0.54
                # Cuando YOLO encuentra un candidato coherente cerca de la caja visual, lo usamos para corregir deriva.
                candidate = self._best_visual_candidate(frame_meta, cx, cy, identity_ref)
                if candidate is not None:
                    det_cx = float(candidate.get("x_rel") or cx)
                    det_cy = float(candidate.get("y_rel") or cy)
                    d = math.hypot(det_cx - cx, det_cy - cy)
                    if d <= 0.12:
                        cx = (cx * 0.35) + (det_cx * 0.65)
                        cy = (cy * 0.35) + (det_cy * 0.65)
                        bw = int(round(float(candidate.get("w_rel") or (bw / width)) * width))
                        bh = int(round(float(candidate.get("h_rel") or (bh / height)) * height))
                        box = _bbox_from_point({"x_rel": cx, "y_rel": cy, "w_rel": bw / max(1, width), "h_rel": bh / max(1, height)})
                        tracker = cv2.TrackerMIL_create()
                        try:
                            tracker.init(image, box)
                            last_box = box
                        except Exception:
                            pass
                        if isinstance(candidate.get("color"), dict):
                            identity_ref = self._blend_identity(identity_ref or candidate.get("color"), candidate.get("color"), alpha=0.08)
                        source_label = "visual_yolo_corrected"
                        follow_conf = min(0.88, 0.62 + float(candidate.get("conf") or 0.0) * 0.22)
                out.append(
                    {
                        "frame": local_idx,
                        "t": float(frame_meta.get("t") or pos_s),
                        "x_rel": max(0.0, min(1.0, cx)),
                        "y_rel": max(0.0, min(1.0, cy)),
                        "w_rel": max(0.001, min(1.0, float(bw) / max(1, width))),
                        "h_rel": max(0.001, min(1.0, float(bh) / max(1, height))),
                        "conf": round(float(follow_conf), 4),
                        "follow_conf": round(float(follow_conf), 4),
                        "source": source_label,
                        "track_id": int(candidate.get("track_id")) if candidate and candidate.get("track_id") is not None else None,
                    }
                )
                local_idx += 1
        finally:
            try:
                cap.release()
            except Exception:
                pass
        return self._smooth_points(out) if len(out) >= len(seed_points) else seed_points

    def _identity_for_point(self, frame: dict, target_id: int) -> dict | None:
        for det in self._person_detections(frame):
            if int(det.get("track_id") or 0) == int(target_id) and isinstance(det.get("color"), dict):
                return det.get("color")
        return None

    def _best_visual_candidate(self, frame: dict, cx: float, cy: float, identity_ref: dict | None) -> dict | None:
        candidates = []
        for det in self._person_detections(frame):
            dx = float(det.get("x_rel") or 0.0) - float(cx)
            dy = float(det.get("y_rel") or 0.0) - float(cy)
            geom = math.hypot(dx, dy)
            if geom > 0.18:
                continue
            app = appearance_distance(identity_ref, det.get("color") if isinstance(det.get("color"), dict) else {}) if identity_ref else 0.4
            score = (geom * 0.72) + (app * 0.20) - (float(det.get("conf") or 0.0) * 0.03)
            candidates.append((score, det))
        if not candidates:
            return None
        candidates.sort(key=lambda row: row[0])
        return candidates[0][1]

    def _interpolate_points(self, points: list[dict], frames: list[dict]) -> list[dict]:
        by_frame = {int(p["frame"]): p for p in points}
        out = []
        sorted_points = sorted(points, key=lambda p: int(p["frame"]))
        for frame in frames:
            idx = int(frame.get("frame") or 0)
            if idx in by_frame:
                out.append(dict(by_frame[idx]))
                continue
            prev = None
            nxt = None
            for p in sorted_points:
                if int(p["frame"]) < idx:
                    prev = p
                elif int(p["frame"]) > idx:
                    nxt = p
                    break
            if prev and nxt and int(nxt["frame"]) - int(prev["frame"]) <= 18:
                span = max(1, int(nxt["frame"]) - int(prev["frame"]))
                u = (idx - int(prev["frame"])) / span
                out.append(
                    {
                        "frame": idx,
                        "t": float(frame.get("t") or 0.0),
                        "x_rel": float(prev["x_rel"]) + (float(nxt["x_rel"]) - float(prev["x_rel"])) * u,
                        "y_rel": float(prev["y_rel"]) + (float(nxt["y_rel"]) - float(prev["y_rel"])) * u,
                        "w_rel": float(prev["w_rel"]) + (float(nxt["w_rel"]) - float(prev["w_rel"])) * u,
                        "h_rel": float(prev["h_rel"]) + (float(nxt["h_rel"]) - float(prev["h_rel"])) * u,
                        "conf": min(float(prev.get("conf") or 0.0), float(nxt.get("conf") or 0.0), 0.42),
                        "source": "interpolation",
                    }
                )
        return out

    def _quality_report(self, frames: list[dict], raw: list[dict], interp: list[dict], *, target_id: int, start: float, end: float) -> dict:
        total = max(1, len(frames))
        raw_by_frame = {int(p["frame"]) for p in raw}
        interp_by_frame = {int(p["frame"]) for p in interp}
        gaps = []
        gap_start = None
        for frame in frames:
            idx = int(frame.get("frame") or 0)
            if idx not in raw_by_frame:
                if gap_start is None:
                    gap_start = idx
            elif gap_start is not None:
                gaps.append({"start_frame": gap_start, "end_frame": idx - 1})
                gap_start = None
        if gap_start is not None:
            gaps.append({"start_frame": gap_start, "end_frame": int(frames[-1].get("frame") or 0)})
        jumps = []
        source_counts = {}
        low_conf = 0
        confirmed = 0
        for a, b in zip(interp, interp[1:]):
            d = math.hypot(float(b["x_rel"]) - float(a["x_rel"]), float(b["y_rel"]) - float(a["y_rel"]))
            if d > 0.08:
                jumps.append({"frame": int(b["frame"]), "jump": round(d, 4)})
        for row in interp:
            src = str(row.get("source") or "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
            if float(row.get("follow_conf") if row.get("follow_conf") is not None else row.get("conf") or 0.0) < 0.45:
                low_conf += 1
            if src in {"detection_id", "stitched_motion_appearance", "visual_yolo_corrected"}:
                confirmed += 1
        raw_cov = len(raw_by_frame) / total
        drawn_cov = len(interp_by_frame) / total
        confirmed_cov = confirmed / total
        low_conf_ratio = low_conf / max(1, len(interp))
        return {
            "ok": True,
            "target_track_id": int(target_id),
            "window": {"start_s": round(start, 3), "end_s": round(end, 3), "duration_s": round(end - start, 3)},
            "frames": total,
            "raw_detection_frames": len(raw_by_frame),
            "drawn_frames": len(interp_by_frame),
            "raw_coverage": round(raw_cov, 4),
            "drawn_coverage": round(drawn_cov, 4),
            "confirmed_coverage": round(confirmed_cov, 4),
            "low_confidence_ratio": round(low_conf_ratio, 4),
            "source_counts": source_counts,
            "gaps": gaps[:20],
            "large_jumps": jumps[:20],
            "quality": "high" if confirmed_cov >= 0.82 and low_conf_ratio <= 0.12 and not jumps else ("medium" if confirmed_cov >= 0.55 and drawn_cov >= 0.85 else "low"),
        }

    def _render_video(self, *, source: Path, out_path: Path, start: float, end: float, target_id: int, points_by_frame: dict[int, dict], raw_frames: list[dict]) -> None:
        cap = cv2.VideoCapture(str(source))
        if not cap or not cap.isOpened():
            raise CommandError("No se pudo abrir el video.")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer or not writer.isOpened():
            raise CommandError("No se pudo crear el MP4 de salida.")
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)
        local_idx = 0
        trail: list[tuple[int, int]] = []
        try:
            while True:
                pos_s = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
                if pos_s > end:
                    break
                ok, frame = cap.read()
                if not ok:
                    break
                point = points_by_frame.get(local_idx)
                if point:
                    x = int(round(float(point["x_rel"]) * width))
                    y = int(round(float(point["y_rel"]) * height))
                    bw = int(round(float(point.get("w_rel") or 0.05) * width))
                    bh = int(round(float(point.get("h_rel") or 0.12) * height))
                    trail.append((x, y))
                    if len(trail) > 180:
                        trail = trail[-180:]
                    follow_conf = float(point.get("follow_conf") if point.get("follow_conf") is not None else point.get("conf") or 0.0)
                    confirmed = str(point.get("source") or "").startswith("detection") or str(point.get("source") or "") in {"stitched_motion_appearance", "visual_yolo_corrected", "manual_anchor"}
                    for i in range(1, len(trail)):
                        alpha = i / max(1, len(trail))
                        color = (0, int(130 + 110 * alpha), 255) if confirmed else (180, 180, 180)
                        cv2.line(frame, trail[i - 1], trail[i], color, 4 if confirmed else 2, cv2.LINE_AA)
                    x0 = max(0, x - bw // 2)
                    y0 = max(0, y - bh // 2)
                    x1 = min(width - 1, x + bw // 2)
                    y1 = min(height - 1, y + bh // 2)
                    is_manual = str(point.get("source") or "") == "manual_anchor"
                    box_color = (80, 255, 80) if is_manual else ((0, 230, 255) if confirmed else (180, 180, 180))
                    ring_color = (0, 0, 255) if follow_conf >= 0.55 else (0, 165, 255)
                    cv2.rectangle(frame, (x0, y0), (x1, y1), box_color, 4 if confirmed else 2)
                    cv2.circle(frame, (x, y), max(16, int(bh * 0.22)), ring_color, 5 if confirmed else 3, cv2.LINE_AA)
                    cv2.circle(frame, (x, y), max(7, int(bh * 0.08)), (255, 255, 255), -1, cv2.LINE_AA)
                    if is_manual:
                        cv2.putText(frame, "ANCLAJE", (x0, min(height - 12, y1 + 28)), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (0, 0, 0), 5, cv2.LINE_AA)
                        cv2.putText(frame, "ANCLAJE", (x0, min(height - 12, y1 + 28)), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (80, 255, 80), 2, cv2.LINE_AA)
                    label = f"Jugador seguido ID {target_id} · {point.get('source')} · {int(follow_conf * 100)}%"
                    cv2.putText(frame, label, (max(20, x0), max(36, y0 - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.82, (0, 0, 0), 5, cv2.LINE_AA)
                    cv2.putText(frame, label, (max(20, x0), max(36, y0 - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.82, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, f"{pos_s:.2f}s", (30, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5, cv2.LINE_AA)
                cv2.putText(frame, f"{pos_s:.2f}s", (30, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
                writer.write(frame)
                local_idx += 1
        finally:
            try:
                writer.release()
            except Exception:
                pass
            try:
                cap.release()
            except Exception:
                pass
