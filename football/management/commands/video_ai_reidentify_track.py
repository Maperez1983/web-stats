from __future__ import annotations

import json
import math
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from football.models import VideoClip
from football.video_ai_services import appearance_distance, color_distance


def _dist(a: dict, b: dict) -> float:
    return math.hypot(float(a.get("x_rel", 0.0)) - float(b.get("x_rel", 0.0)), float(a.get("y_rel", 0.0)) - float(b.get("y_rel", 0.0)))


def _nearest_frame(frames: list[dict], t: float) -> dict | None:
    if not frames:
        return None
    return min(frames, key=lambda row: abs(float(row.get("t") or 0.0) - float(t)))


def _ocr_score(det: dict, expected_number: str = "") -> float:
    expected = str(expected_number or "").strip()
    if not expected:
        return 0.0
    ocr = det.get("ocr") if isinstance(det.get("ocr"), dict) else {}
    best = str(ocr.get("best") or "").strip()
    if not best:
        return 0.0
    if best == expected:
        return -0.045
    ranked = ocr.get("ranked") if isinstance(ocr.get("ranked"), list) else []
    for row in ranked[:5]:
        if str((row or {}).get("number") or "").strip() == expected:
            return -0.025
    return 0.035


def _avg_signature(signatures: list[dict]) -> dict:
    rows = [s for s in signatures if isinstance(s, dict)]
    if not rows:
        return {}
    out = {}
    for key in ("h", "s", "v", "aspect", "area"):
        vals = []
        for row in rows:
            try:
                vals.append(float(row.get(key)))
            except Exception:
                continue
        if vals:
            out[key] = sum(vals) / len(vals)
    hist_rows = [row.get("hist") for row in rows if isinstance(row.get("hist"), list) and row.get("hist")]
    if hist_rows:
        size = len(hist_rows[0])
        valid = [h for h in hist_rows if len(h) == size]
        if valid:
            out["hist"] = [sum(float(h[i]) for h in valid) / len(valid) for i in range(size)]
    return out


def _blend_signature(a: dict, b: dict, alpha: float = 0.12) -> dict:
    if not a:
        return dict(b or {})
    if not b:
        return dict(a or {})
    alpha = max(0.0, min(0.5, float(alpha)))
    out = dict(a)
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


def _velocity_predict(last_point: dict | None, prev_point: dict | None, t: float) -> dict | None:
    if not last_point:
        return None
    if not prev_point:
        return {"t": t, "x_rel": float(last_point.get("x_rel") or 0.0), "y_rel": float(last_point.get("y_rel") or 0.0)}
    dt = max(0.001, float(last_point.get("t") or 0.0) - float(prev_point.get("t") or 0.0))
    lead = max(0.0, float(t) - float(last_point.get("t") or 0.0))
    vx = (float(last_point.get("x_rel") or 0.0) - float(prev_point.get("x_rel") or 0.0)) / dt
    vy = (float(last_point.get("y_rel") or 0.0) - float(prev_point.get("y_rel") or 0.0)) / dt
    return {
        "t": t,
        "x_rel": max(0.0, min(1.0, float(last_point.get("x_rel") or 0.0) + (vx * lead))),
        "y_rel": max(0.0, min(1.0, float(last_point.get("y_rel") or 0.0) + (vy * lead))),
    }


def _best_detection_for_anchor(frame: dict, anchor: dict, max_dist: float, expected_number: str = "") -> dict | None:
    selected_track_id = anchor.get("selected_track_id")
    if selected_track_id is not None:
        try:
            selected_track_id = int(selected_track_id)
        except Exception:
            selected_track_id = None
    candidates = []
    for det in frame.get("detections") or []:
        if det.get("track_id") is None:
            continue
        d = _dist(det, anchor)
        if d > max_dist:
            continue
        if selected_track_id is not None and int(det.get("track_id")) == selected_track_id:
            return det
        conf = float(det.get("conf") or 0.0)
        # Preferimos cercanía; la confianza desempata.
        score = d - (conf * 0.015) + _ocr_score(det, expected_number)
        candidates.append((score, det))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _ball_near(frame: dict, point: dict) -> float | None:
    balls = [d for d in (frame.get("detections") or []) if int(d.get("class_id") or 0) == 32]
    if not balls:
        return None
    return min(_dist(ball, point) for ball in balls)


def _interpolate_anchor(anchors: list[dict], t: float) -> dict | None:
    if not anchors:
        return None
    if t <= float(anchors[0]["t"]):
        return anchors[0]
    if t >= float(anchors[-1]["t"]):
        return anchors[-1]
    for idx in range(len(anchors) - 1):
        a = anchors[idx]
        b = anchors[idx + 1]
        ta = float(a["t"])
        tb = float(b["t"])
        if ta <= t <= tb:
            span = max(0.001, tb - ta)
            u = (t - ta) / span
            return {
                "t": t,
                "x_rel": float(a["x_rel"]) + (float(b["x_rel"]) - float(a["x_rel"])) * u,
                "y_rel": float(a["y_rel"]) + (float(b["y_rel"]) - float(a["y_rel"])) * u,
            }
    return anchors[-1]


def _smooth_points(points: list[dict], strength: float = 0.25) -> list[dict]:
    if len(points) < 3 or strength <= 0:
        return points
    strength = max(0.0, min(0.8, float(strength)))
    out = []
    for idx, point in enumerate(points):
        if idx == 0 or idx == len(points) - 1:
            out.append(dict(point))
            continue
        prev = points[idx - 1]
        nxt = points[idx + 1]
        out.append(
            {
                "t": float(point["t"]),
                "x_rel": max(
                    0.0,
                    min(
                        1.0,
                        (float(point["x_rel"]) * (1.0 - strength))
                        + (((float(prev["x_rel"]) + float(nxt["x_rel"])) / 2.0) * strength),
                    ),
                ),
                "y_rel": max(
                    0.0,
                    min(
                        1.0,
                        (float(point["y_rel"]) * (1.0 - strength))
                        + (((float(prev["y_rel"]) + float(nxt["y_rel"])) / 2.0) * strength),
                    ),
                ),
            }
        )
    return out


class Command(BaseCommand):
    help = "Une IDs YOLO/ByteTrack usando anclajes del analista y guarda una pista reidentificada."

    def add_arguments(self, parser):
        parser.add_argument("--track-json", required=True, help="JSON generado por video_ai_track_yolo.")
        parser.add_argument("--clip-id", type=int, required=True, help="VideoClip con anclajes del analista.")
        parser.add_argument("--marker-uid", default="", help="UID del marker con anchors. Si vacío, usa el primero con anchors.")
        parser.add_argument("--output-uid", default="winger-11", help="UID de salida para overlay.tracking.tracks.")
        parser.add_argument("--out", default="", help="Ruta JSON salida. Opcional.")
        parser.add_argument("--save-to-clip", action="store_true", help="Actualiza overlay.tracking del clip.")
        parser.add_argument("--max-anchor-dist", type=float, default=0.14, help="Distancia máxima a anclaje para asignar ID.")
        parser.add_argument("--max-frame-dist", type=float, default=0.16, help="Distancia máxima por frame para fallback.")
        parser.add_argument("--expected-number", type=str, default="", help="Dorsal esperado para metadatos/OCR asistido.")
        parser.add_argument("--team-color-weight", type=float, default=0.08, help="Peso de similitud de color/equipo.")
        parser.add_argument("--identity-lock", action="store_true", help="Bloquea identidad visual y evita cambios de jugador si baja la confianza.")
        parser.add_argument("--identity-threshold", type=float, default=0.74, help="Score mínimo para aceptar cambio/detección con Identity Lock.")
        parser.add_argument("--anchors-json", default="", help="JSON externo de anchors normalizados; si existe prevalece sobre los anchors guardados en el clip.")

    def handle(self, *args, **options):
        track_path = Path(str(options["track_json"])).expanduser().resolve()
        if not track_path.exists():
            raise CommandError(f"No existe track JSON: {track_path}")
        data = json.loads(track_path.read_text(encoding="utf-8"))
        frames = data.get("frames") if isinstance(data.get("frames"), list) else []
        if not frames:
            raise CommandError("El JSON no contiene frames.")

        clip = VideoClip.objects.filter(id=int(options["clip_id"])).first()
        if not clip:
            raise CommandError("VideoClip no encontrado.")
        overlay = clip.overlay if isinstance(getattr(clip, "overlay", None), dict) else {}
        tracking = overlay.get("tracking") if isinstance(overlay.get("tracking"), dict) else {}
        markers = tracking.get("markers") if isinstance(tracking.get("markers"), list) else []
        marker_uid = str(options.get("marker_uid") or "").strip()
        marker = None
        for candidate in markers:
            if not isinstance(candidate, dict):
                continue
            uid = str(candidate.get("uid") or "").strip()
            anchors = candidate.get("anchors") if isinstance(candidate.get("anchors"), list) else []
            if marker_uid and uid == marker_uid:
                marker = candidate
                break
            if not marker_uid and anchors:
                marker = candidate
                break
        if not marker:
            raise CommandError("No se encontró marker con anchors.")

        anchors_source = marker.get("anchors") or []
        anchors_json = str(options.get("anchors_json") or "").strip()
        if anchors_json:
            anchors_path = Path(anchors_json).expanduser()
            if anchors_path.exists():
                try:
                    raw_external = json.loads(anchors_path.read_text(encoding="utf-8"))
                    if isinstance(raw_external, list):
                        anchors_source = raw_external
                except Exception:
                    pass

        anchors = []
        for raw in anchors_source:
            if not isinstance(raw, dict):
                continue
            try:
                row = {
                    "t": float(raw["t"]),
                    "x_rel": max(0.0, min(1.0, float(raw["x_rel"]))),
                    "y_rel": max(0.0, min(1.0, float(raw["y_rel"]))),
                }
                if raw.get("selected_track_id") is not None:
                    try:
                        row["selected_track_id"] = int(raw.get("selected_track_id"))
                    except Exception:
                        pass
                if raw.get("source"):
                    row["source"] = str(raw.get("source"))[:40]
                anchors.append(row)
            except Exception:
                continue
        anchors.sort(key=lambda row: row["t"])
        if not anchors:
            raise CommandError("El marker no tiene anchors válidos.")

        max_anchor_dist = max(0.02, min(0.5, float(options.get("max_anchor_dist") or 0.14)))
        max_frame_dist = max(0.02, min(0.5, float(options.get("max_frame_dist") or 0.16)))
        output_uid = str(options.get("output_uid") or "winger-11").strip() or "winger-11"
        expected_number = str(options.get("expected_number") or "").strip()
        team_color_weight = max(0.0, min(0.5, float(options.get("team_color_weight") or 0.08)))
        identity_lock = bool(options.get("identity_lock"))
        identity_threshold = max(0.25, min(0.95, float(options.get("identity_threshold") or 0.74)))

        anchor_matches = []
        color_refs = []
        appearance_refs = []
        for anchor in anchors:
            frame = _nearest_frame(frames, float(anchor["t"]))
            det = _best_detection_for_anchor(frame or {}, anchor, max_anchor_dist, expected_number)
            if det and isinstance(det.get("color"), dict):
                color_refs.append(det.get("color"))
                appearance_refs.append(det.get("color"))
            anchor_matches.append(
                {
                    "anchor": anchor,
                    "frame": int((frame or {}).get("frame") or 0),
                    "t": float((frame or {}).get("t") or anchor["t"]),
                    "track_id": int(det["track_id"]) if det else None,
                    "dist": _dist(det, anchor) if det else None,
                    "conf": float(det.get("conf") or 0.0) if det else 0.0,
                    "selected_track_id": anchor.get("selected_track_id"),
                }
            )
        identity_signature = _avg_signature(appearance_refs)

        points = []
        used_ids = set()
        confidence_samples = []
        low_confidence_ranges = []
        last_low_start = None
        last_point = None
        prev_point = None
        identity_switches_blocked = 0
        identity_accepts = 0
        identity_memory = dict(identity_signature)
        for frame in frames:
            t = float(frame.get("t") or 0.0)
            expected = _interpolate_anchor(anchors, t)
            if not expected:
                continue
            predicted = _velocity_predict(last_point, prev_point, t) or expected

            # ID activo: último anclaje ya alcanzado que tenga detección.
            active_id = None
            for match in anchor_matches:
                if float(match["anchor"]["t"]) <= t + 0.05 and match.get("track_id") is not None:
                    active_id = int(match["track_id"])
                elif float(match["anchor"]["t"]) > t:
                    break

            detections = [d for d in (frame.get("detections") or []) if d.get("track_id") is not None]
            chosen = None
            chosen_identity_score = 0.0
            if active_id is not None:
                same_id = [d for d in detections if int(d.get("track_id")) == int(active_id)]
                if same_id:
                    chosen = min(same_id, key=lambda d: (_dist(d, predicted), _dist(d, expected)))
                    if _dist(chosen, expected) > max_frame_dist:
                        chosen = None
            if chosen is None:
                candidate_radius = max_frame_dist * (1.45 if identity_lock else 1.0)
                candidates = [d for d in detections if min(_dist(d, expected), _dist(d, predicted)) <= candidate_radius]
                if candidates:
                    def _candidate_score(d):
                        color_penalty = 0.0
                        if color_refs and isinstance(d.get("color"), dict):
                            color_penalty = min(color_distance(ref, d.get("color")) for ref in color_refs)
                        appearance_penalty = 0.0
                        if identity_lock and identity_memory and isinstance(d.get("color"), dict):
                            appearance_penalty = appearance_distance(identity_memory, d.get("color"))
                        pred_d = min(_dist(d, expected), _dist(d, predicted))
                        return (
                            pred_d
                            + (color_penalty * team_color_weight)
                            + (appearance_penalty * (0.16 if identity_lock else 0.0))
                            - (float(d.get("conf") or 0.0) * 0.01)
                            + _ocr_score(d, expected_number)
                        )
                    chosen = min(candidates, key=_candidate_score)
            if chosen is not None and identity_lock:
                geom_d = min(_dist(chosen, expected), _dist(chosen, predicted))
                appearance_d = appearance_distance(identity_memory, chosen.get("color") if isinstance(chosen.get("color"), dict) else {})
                geom_score = max(0.0, 1.0 - (geom_d / max(0.001, max_frame_dist * 1.45)))
                app_score = max(0.0, 1.0 - min(1.0, appearance_d))
                det_conf = max(0.0, min(1.0, float(chosen.get("conf") or 0.0)))
                ocr_bonus = -_ocr_score(chosen, expected_number)
                chosen_identity_score = max(0.0, min(1.0, (geom_score * 0.44) + (app_score * 0.42) + (det_conf * 0.10) + (ocr_bonus * 0.55)))
                if chosen_identity_score < identity_threshold:
                    identity_switches_blocked += 1
                    chosen = None
            if chosen is None:
                # Mejor usar el anclaje/interpolación que saltar a otra identidad.
                chosen = predicted if identity_lock and predicted else expected
                chosen_source = "identity_prediction" if identity_lock else "anchor_interp"
            else:
                used_ids.add(int(chosen["track_id"]))
                if identity_lock and isinstance(chosen.get("color"), dict) and chosen_identity_score >= identity_threshold:
                    identity_accepts += 1
                    identity_memory = _blend_signature(identity_memory, chosen.get("color"), alpha=0.10)
                chosen_source = "detection"

            d_expected = _dist(chosen, expected)
            ball_d = _ball_near(frame, chosen)
            conf_score = max(0.0, min(1.0, 1.0 - (d_expected / max_frame_dist)))
            if chosen_source == "anchor_interp":
                conf_score = min(conf_score, 0.45)
            if chosen_source == "identity_prediction":
                conf_score = min(conf_score, 0.42)
            if identity_lock and chosen_source == "detection":
                conf_score = min(1.0, (conf_score * 0.70) + (chosen_identity_score * 0.30))
            if ball_d is not None and ball_d < 0.09:
                conf_score = min(1.0, conf_score + 0.08)
            confidence_samples.append(conf_score)
            if conf_score < 0.48:
                if last_low_start is None:
                    last_low_start = float(t)
            elif last_low_start is not None:
                low_confidence_ranges.append({"start_s": last_low_start, "end_s": float(t)})
                last_low_start = None

            point = {
                "t": float(t),
                "x_rel": max(0.0, min(1.0, float(chosen.get("x_rel") or 0.0))),
                "y_rel": max(0.0, min(1.0, float(chosen.get("y_rel") or 0.0))),
                "confidence": round(float(conf_score), 4),
                "source": chosen_source,
            }
            if isinstance(chosen.get("ocr"), dict):
                point["ocr"] = chosen.get("ocr")
            if last_point and abs(point["t"] - last_point["t"]) < 0.04:
                continue
            points.append(point)
            prev_point = last_point
            last_point = point

        points = _smooth_points(points, strength=0.18)
        if last_low_start is not None:
            low_confidence_ranges.append({"start_s": last_low_start, "end_s": float(points[-1]["t"]) if points else last_low_start})
        avg_conf = sum(confidence_samples) / len(confidence_samples) if confidence_samples else 0.0
        if avg_conf >= 0.72 and not low_confidence_ranges:
            confidence_label = "high"
        elif avg_conf >= 0.52:
            confidence_label = "medium"
        else:
            confidence_label = "low"
        payload = {
            "ok": True,
            "clip_id": int(clip.id),
            "video_id": int(getattr(clip, "video_id", 0) or 0),
            "source_track_json": str(track_path),
            "marker_uid": str(marker.get("uid") or ""),
            "output_uid": output_uid,
            "anchors": anchors,
            "anchor_matches": anchor_matches,
            "used_track_ids": sorted(used_ids),
            "confidence": {
                "avg": round(float(avg_conf), 4),
                "label": confidence_label,
                "low_ranges": low_confidence_ranges[:20],
            },
            "signals": {
                "team_color_refs": color_refs[:8],
                "expected_number": expected_number,
                "ball_used": True,
                "ocr_number": expected_number,
                "identity_lock": bool(identity_lock),
                "identity_threshold": round(float(identity_threshold), 4),
                "identity_signature": identity_signature,
                "identity_switches_blocked": int(identity_switches_blocked),
                "identity_accepts": int(identity_accepts),
            },
            "points": points,
        }

        out_arg = str(options.get("out") or "").strip()
        if out_arg:
            out_path = Path(out_arg).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            out_path = None

        if bool(options.get("save_to_clip")):
            next_overlay = dict(overlay)
            next_tracking = dict(tracking)
            next_tracks = dict(next_tracking.get("tracks") or {})
            next_tracks[output_uid] = points
            next_tracking["tracks"] = next_tracks
            next_tracking["source"] = "yolo-reid-anchors"
            next_meta = dict(next_tracking.get("meta") or {})
            next_meta[output_uid] = {
                "reid": True,
                "method": "yolo_bytrack_anchor_stitch",
                "identity_lock": bool(identity_lock),
                "anchors": len(anchors),
                "matched_anchors": len([m for m in anchor_matches if m.get("track_id") is not None]),
                "used_track_ids": sorted(used_ids),
                "points": len(points),
                "confidence": payload["confidence"],
                "signals": payload["signals"],
            }
            next_tracking["meta"] = next_meta
            next_overlay["tracking"] = next_tracking
            clip.overlay = next_overlay
            clip.save(update_fields=["overlay", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"ReID OK points={len(points)} anchors={len(anchors)} matched={len([m for m in anchor_matches if m.get('track_id') is not None])} ids={sorted(used_ids)}"
            )
        )
        if out_path:
            self.stdout.write(str(out_path))
