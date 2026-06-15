from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from football.models import RivalVideo, VideoClip, VideoTimelineEvent
from football.video_autocut import suggest_autocuts
from football.views import (
    _video_studio_ai_active_knowledge,
    _video_studio_ai_attack_progression,
    _video_studio_ai_detect_actions_for_clip,
    _video_studio_ai_get_game_calibration,
)


class Command(BaseCommand):
    help = "Genera el maximo numero razonable de cortes IA para revisar jugadas relevantes."

    def add_arguments(self, parser):
        parser.add_argument("--video-id", type=int, required=True)
        parser.add_argument("--max-moments", type=int, default=40)
        parser.add_argument("--min-gap", type=float, default=3.0)
        parser.add_argument("--pre", type=float, default=4.0)
        parser.add_argument("--post", type=float, default=5.0)
        parser.add_argument("--profile", type=str, default="tactical")
        parser.add_argument("--collection", type=str, default="IA MaxCuts")
        parser.add_argument("--out-dir", type=str, default="/Volumes/Mac Satecchi/Mac/Downloads/IA_MaxCuts_video_7")
        parser.add_argument("--export-mp4", type=int, default=24)
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--deep-tactics", action="store_true", help="Ejecuta YOLO para estimar balón, equipos, posesión y patrones.")
        parser.add_argument("--annotated-mp4", action="store_true", help="Exporta además MP4 con explicación táctica quemada.")

    def handle(self, *args, **options):
        video_id = int(options["video_id"])
        video = RivalVideo.objects.select_related("team").filter(id=video_id).first()
        if not video or not getattr(video, "video", None):
            raise CommandError(f"Video #{video_id} no encontrado o sin archivo local.")
        try:
            video_path = video.video.path
        except Exception as exc:
            raise CommandError(f"No se pudo resolver ruta del video: {exc}") from exc
        if not video_path or not Path(video_path).exists():
            raise CommandError(f"No existe el archivo del video: {video_path}")
        team = video.team
        if not team:
            raise CommandError("El video no tiene team.")

        collection = str(options["collection"] or "IA MaxCuts")[:80]
        if options.get("replace"):
            for clip in list(VideoClip.objects.filter(team=team, video=video, collection=collection)):
                tags = clip.tags if isinstance(clip.tags, list) else []
                if "ai_maxcuts" in tags:
                    clip.delete()
            for event in list(VideoTimelineEvent.objects.filter(team=team, video=video, payload__ai_maxcuts=True)):
                event.delete()

        result = suggest_autocuts(
            video_path,
            profile=str(options["profile"] or "tactical"),
            max_moments=max(1, min(80, int(options["max_moments"] or 40))),
            min_gap_s=max(0.5, float(options["min_gap"] or 3.0)),
            pre_s=max(0.0, float(options["pre"] or 4.0)),
            post_s=max(0.0, float(options["post"] or 5.0)),
            max_seconds_scan=None,
            refine=True,
        )
        moments = result.get("moments") if isinstance(result, dict) else []
        if not isinstance(moments, list):
            moments = []

        deep_payload = None
        if options.get("deep_tactics"):
            deep_payload = self._build_deep_payload(video_path, result)
        calibration = _video_studio_ai_get_game_calibration(team, video)
        senior_knowledge = _video_studio_ai_active_knowledge(team)

        created = []
        allowed_kinds = {k for k, _ in VideoTimelineEvent.KIND_CHOICES}
        for idx, moment in enumerate(moments[: int(options["max_moments"] or 40)], start=1):
            try:
                start = max(0.0, float(moment.get("clip_in_s") or 0.0))
                end = max(start + 0.5, float(moment.get("clip_out_s") or start + 7.0))
                kind = str(moment.get("kind") or VideoTimelineEvent.KIND_TAG).strip().lower() or VideoTimelineEvent.KIND_TAG
                label = str(moment.get("label") or "Auto - Accion").strip()[:130]
                score = float(moment.get("score") or 0.0)
            except Exception:
                continue
            title = f"IA {idx:02d} - {label} - {start:.1f}-{end:.1f}s"
            clip = VideoClip.objects.create(
                team=team,
                owner_user=None,
                video=video,
                title=title[:180],
                collection=collection,
                in_ms=int(round(start * 1000)),
                out_ms=int(round(end * 1000)),
                tags=["ai_maxcuts", "autocut", kind, "review"],
                notes=f"Score AutoCut {score:.3f}. Revision IA pendiente.",
                overlay={"ai_maxcuts": True, "autocut": {"moment": moment, "rank": idx}},
                created_by="codex",
            )
            VideoTimelineEvent.objects.create(
                team=team,
                owner_user=None,
                video=video,
                time_ms=int(round(float(moment.get("time_s") or start) * 1000)),
                kind=kind if kind in allowed_kinds else VideoTimelineEvent.KIND_TAG,
                label=title[:160],
                color="#22d3ee",
                payload={"ai_maxcuts": True, "autocut": True, "score": score, "rank": idx, "moment": moment},
                created_by="codex",
            )
            deep_item = self._analyze_deep_clip(deep_payload, start=start, end=end, rank=idx, fallback_kind=kind, calibration=calibration)
            senior = self._build_senior_read(
                deep_item,
                start=start,
                end=end,
                fallback_kind=kind,
                knowledge=senior_knowledge,
            )
            if senior:
                deep_item["senior"] = senior
                if senior.get("action"):
                    deep_item["actions"] = self._merge_actions([senior["action"]], deep_item.get("actions") or [], include_old=True)
                if senior.get("explanation"):
                    deep_item["explanation"] = senior["explanation"]
            try:
                detected = _video_studio_ai_detect_actions_for_clip(team=team, video=video, clip=clip)
            except Exception as exc:
                detected = {"error": str(exc), "actions": []}
            actions = detected.get("actions") if isinstance(detected, dict) and isinstance(detected.get("actions"), list) else []
            if deep_item.get("actions"):
                detected["deep_tactics"] = deep_item
                detected["actions"] = self._merge_actions(deep_item.get("actions") or [], actions)
                actions = detected["actions"]
            top_action = actions[0] if actions else {}
            explanation = deep_item.get("explanation") or ""
            clip.overlay = {
                **(clip.overlay or {}),
                "ai_actions": detected,
                **self._build_clip_overlay(deep_item, start=start, end=end, title=title),
            }
            if top_action:
                action_key = str(top_action.get("key") or "").strip()
                if action_key:
                    tag = f"action:{action_key}"
                    if tag not in clip.tags:
                        clip.tags = (clip.tags or []) + [tag]
                senior_key = str((deep_item.get("senior") or {}).get("key") or "").strip()
                if senior_key:
                    senior_tag = f"senior:{senior_key}"
                    if senior_tag not in clip.tags:
                        clip.tags = (clip.tags or []) + [senior_tag]
                clip.notes = (
                    f"Score AutoCut {score:.3f}. Accion IA: "
                    f"{top_action.get('label') or action_key} ({float(top_action.get('confidence') or 0):.2f})."
                )
                if (deep_item.get("senior") or {}).get("coach_question"):
                    clip.notes = f"{clip.notes} Pregunta entrenador: {(deep_item.get('senior') or {}).get('coach_question')}"
            if explanation:
                clip.notes = f"{clip.notes} {explanation}".strip()
            clip.save(update_fields=["overlay", "tags", "notes", "updated_at"])
            created.append(
                {
                    "clip_id": int(clip.id),
                    "rank": idx,
                    "start_s": round(start, 3),
                    "end_s": round(end, 3),
                    "duration_s": round(end - start, 3),
                    "kind": kind,
                    "label": label,
                    "score": round(score, 4),
                    "actions": actions[:5],
                    "deep_tactics": deep_item,
                    "senior": deep_item.get("senior") or {},
                    "explanation": explanation,
                    "title": clip.title,
                }
            )

        out_dir = Path(str(options["out_dir"] or "")).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "video_id": int(video.id),
            "video_title": str(video.title),
            "duration_s": result.get("duration_s") if isinstance(result, dict) else None,
            "created_clips": len(created),
            "collection": collection,
            "generated_at": timezone.now().isoformat(),
            "clips": created,
        }
        summary_path = out_dir / "ia_maxcuts_resumen.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        exported = self._export_mp4(
            video_path,
            created,
            out_dir,
            int(options["export_mp4"] or 0),
            annotated=bool(options.get("annotated_mp4")),
        )
        (out_dir / "exports.txt").write_text("\n".join(exported), encoding="utf-8")
        self.stdout.write(
            json.dumps(
                {
                    "ok": True,
                    "clips_created": len(created),
                    "summary_path": str(summary_path),
                    "exports_dir": str(out_dir),
                    "mp4_exported": len(exported),
                    "top": created[:8],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    def _build_deep_payload(self, video_path: str, result: dict) -> dict:
        try:
            from football.video_ai_services import yolo_track_video  # noqa: WPS433
        except Exception as exc:
            return {"ok": False, "error": f"YOLO no disponible: {exc}", "frames": []}
        model_path = Path("data/video_ai/models/yolo11n.pt").resolve()
        duration = float((result or {}).get("duration_s") or 0.0)
        if duration <= 0:
            duration = float((result or {}).get("scan_limit_s") or 0.0) or 180.0
        try:
            payload = yolo_track_video(
                source=Path(video_path),
                model_path=model_path,
                start_s=0.0,
                end_s=duration,
                conf=0.18,
                imgsz=960,
                include_ball=True,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "frames": []}
        frames = payload.get("frames") if isinstance(payload, dict) and isinstance(payload.get("frames"), list) else []
        teams = self._infer_team_clusters(frames)
        return {"ok": True, "frames": frames, "teams": teams, "raw_meta": {"model": payload.get("model"), "frames": len(frames)}}

    def _infer_team_clusters(self, frames: list[dict]) -> dict:
        hues = []
        track_hues = {}
        for frame in frames:
            for det in frame.get("detections") or []:
                if int(det.get("class_id") or 0) != 0:
                    continue
                color = det.get("color") if isinstance(det.get("color"), dict) else {}
                tid = det.get("track_id")
                if tid is None:
                    continue
                h = color.get("h")
                s = color.get("s")
                if h is None or float(s or 0.0) < 25:
                    continue
                track_hues.setdefault(int(tid), []).append(float(h))
        for vals in track_hues.values():
            if vals:
                hues.append(sum(vals) / len(vals))
        if len(hues) < 2:
            return {"centers": [], "track_team": {}}
        c1 = min(hues)
        c2 = max(hues)
        for _ in range(10):
            g1 = [h for h in hues if self._hue_dist(h, c1) <= self._hue_dist(h, c2)]
            g2 = [h for h in hues if self._hue_dist(h, c2) < self._hue_dist(h, c1)]
            if g1:
                c1 = sum(g1) / len(g1)
            if g2:
                c2 = sum(g2) / len(g2)
        centers = [c1, c2]
        track_team = {}
        for tid, vals in track_hues.items():
            h = sum(vals) / len(vals)
            team_idx = 0 if self._hue_dist(h, centers[0]) <= self._hue_dist(h, centers[1]) else 1
            track_team[str(tid)] = f"team_{team_idx + 1}"
        return {"centers": [round(c, 2) for c in centers], "track_team": track_team}

    def _hue_dist(self, a: float, b: float) -> float:
        d = abs(float(a) - float(b))
        return min(d, 180.0 - d)

    def _analyze_deep_clip(self, payload: dict | None, *, start: float, end: float, rank: int, fallback_kind: str, calibration: dict | None = None) -> dict:
        if not payload or not payload.get("ok"):
            return {"available": False, "error": (payload or {}).get("error", ""), "actions": [], "explanation": ""}
        frames = [f for f in (payload.get("frames") or []) if float(f.get("t") or 0.0) >= start and float(f.get("t") or 0.0) <= end]
        if not frames:
            return {"available": False, "actions": [], "explanation": ""}
        track_team = ((payload.get("teams") or {}).get("track_team") or {})
        samples = []
        possessions = []
        ball_pts = []
        widths = []
        depths = []
        lane_samples = []
        pressure_vals = []
        unique_player_ids = set()
        for frame in frames:
            people = [d for d in (frame.get("detections") or []) if int(d.get("class_id") or 0) == 0 and float(d.get("conf") or 0.0) >= 0.18]
            balls = [d for d in (frame.get("detections") or []) if int(d.get("class_id") or 0) == 32 and float(d.get("conf") or 0.0) >= 0.10]
            for p in people:
                if p.get("track_id") is not None:
                    unique_player_ids.add(str(p.get("track_id")))
            if people:
                xs = [float(p.get("x_rel") or 0.0) for p in people]
                ys = [float(p.get("y_rel") or 0.0) for p in people]
                widths.append((max(xs) - min(xs), max(ys) - min(ys), len(people)))
                depths.append((min(xs), max(xs), sum(xs) / len(xs), len(people)))
                lane_counts = {
                    "carril_exterior_izquierdo": 0,
                    "carril_interior_izquierdo": 0,
                    "carril_central": 0,
                    "carril_interior_derecho": 0,
                    "carril_exterior_derecho": 0,
                }
                for y in ys:
                    if y < 0.18:
                        lane_counts["carril_exterior_izquierdo"] += 1
                    elif y < 0.36:
                        lane_counts["carril_interior_izquierdo"] += 1
                    elif y <= 0.64:
                        lane_counts["carril_central"] += 1
                    elif y <= 0.82:
                        lane_counts["carril_interior_derecho"] += 1
                    else:
                        lane_counts["carril_exterior_derecho"] += 1
                lane_samples.append(lane_counts)
            ball = max(balls, key=lambda d: float(d.get("conf") or 0.0), default=None)
            possessor = None
            if ball:
                bx = float(ball.get("x_rel") or 0.0)
                by = float(ball.get("y_rel") or 0.0)
                ball_pts.append({"t": float(frame.get("t") or 0.0), "x": bx, "y": by})
                candidates = []
                for p in people:
                    px = float(p.get("x_rel") or 0.0)
                    py = float(p.get("y_rel") or 0.0)
                    dist = math.hypot((px - bx) * 1.6, py - by)
                    candidates.append((dist, p))
                if candidates:
                    candidates.sort(key=lambda row: row[0])
                    if candidates[0][0] <= 0.18:
                        possessor = candidates[0][1]
            if possessor is not None:
                tid = possessor.get("track_id")
                team = track_team.get(str(tid), "unknown")
                possessions.append(team)
                px = float(possessor.get("x_rel") or 0.0)
                py = float(possessor.get("y_rel") or 0.0)
                opp = []
                for p in people:
                    if p is possessor:
                        continue
                    pt = track_team.get(str(p.get("track_id")), "unknown")
                    if team != "unknown" and pt == team:
                        continue
                    opp.append(math.hypot((float(p.get("x_rel") or 0.0) - px) * 1.6, float(p.get("y_rel") or 0.0) - py))
                if opp:
                    pressure_vals.append(min(opp))
            samples.append({"t": float(frame.get("t") or 0.0), "people": len(people), "ball": bool(ball), "possessor": bool(possessor)})

        ball_start = ball_pts[0] if ball_pts else {}
        ball_end = ball_pts[-1] if ball_pts else {}
        dx = float(ball_end.get("x", 0.0) or 0.0) - float(ball_start.get("x", 0.0) or 0.0)
        dy = float(ball_end.get("y", 0.0) or 0.0) - float(ball_start.get("y", 0.0) or 0.0)
        attack_progression = _video_studio_ai_attack_progression(dx, calibration or {})
        progression = abs(dx)
        lateral = abs(dy)
        last_third = bool(ball_pts and (float(ball_end.get("x") or 0.0) >= 0.67 or float(ball_end.get("x") or 0.0) <= 0.33))
        wide = bool(ball_pts and (float(ball_end.get("y") or 0.0) <= 0.27 or float(ball_end.get("y") or 0.0) >= 0.73))
        central = bool(ball_pts and 0.36 <= float(ball_end.get("y") or 0.0) <= 0.64)
        team_changes = sum(1 for a, b in zip(possessions, possessions[1:]) if a != b and a != "unknown" and b != "unknown")
        avg_pressure = sum(pressure_vals) / len(pressure_vals) if pressure_vals else None
        avg_people = sum(s["people"] for s in samples) / len(samples) if samples else 0.0
        avg_width = sum(w[0] for w in widths) / len(widths) if widths else 0.0
        avg_depth = sum((d[1] - d[0]) for d in depths) / len(depths) if depths else 0.0
        avg_line_x = sum(d[2] for d in depths) / len(depths) if depths else None
        lane_density = {}
        if lane_samples:
            lane_keys = list(lane_samples[0].keys())
            lane_density = {key: round(sum(sample.get(key, 0) for sample in lane_samples) / len(lane_samples), 3) for key in lane_keys}
        occupied_lane_avg = sum(1 for value in lane_density.values() if float(value or 0.0) >= 0.75) if lane_density else 0
        compactness = (avg_people / max(0.08, avg_width * avg_depth)) if avg_people and avg_width and avg_depth else 0.0
        ball_jumps = [
            math.hypot(float(b.get("x", 0.0)) - float(a.get("x", 0.0)), float(b.get("y", 0.0)) - float(a.get("y", 0.0)))
            for a, b in zip(ball_pts, ball_pts[1:])
        ]
        jump_sorted = sorted(ball_jumps)
        median_jump = jump_sorted[len(jump_sorted) // 2] if jump_sorted else 0.0
        frame_count = max(1, len(frames))
        ball_rate = len(ball_pts) / frame_count
        possession_rate = len(possessions) / frame_count
        # Si ByteTrack fragmenta mucho los IDs, no usamos cambios de equipo como "robo/transición".
        track_fragmentation = len(unique_player_ids) / max(1.0, avg_people)
        ball_reliable = len(ball_pts) >= 8 and ball_rate >= 0.14 and median_jump <= 0.22
        possession_reliable = possession_rate >= 0.28 and track_fragmentation <= 12.0
        field_calibrated = bool((calibration or {}).get("field_calibrated"))
        direction_known = bool((calibration or {}).get("attack_direction_known"))
        direction = str((calibration or {}).get("attack_direction") or "unknown")
        block_height_hint = ""
        field_height_hint = ""
        block_evidence_level = "unavailable"
        if avg_line_x is not None:
            if avg_line_x < 0.33:
                field_height_hint = "zona_baja"
            elif avg_line_x < 0.66:
                field_height_hint = "zona_media"
            else:
                field_height_hint = "zona_alta"
            attack_x = 1.0 - avg_line_x if direction == "rtl" else avg_line_x
            if attack_x < 0.33:
                block_height_hint = "bloque_bajo"
            elif attack_x < 0.66:
                block_height_hint = "bloque_medio"
            else:
                block_height_hint = "bloque_alto"
            block_evidence_level = "supported" if field_calibrated and direction_known and avg_people >= 8 else "hypothesis"
        actions = []
        reasons = []
        if str(fallback_kind) == "abp":
            actions.append({"key": "posible_reinicio", "label": "Posible reinicio / ABP", "confidence": 0.46, "reasons": ["autocut_reinicio", "requiere_revision"]})
            reasons.append("el patrón temporal sugiere reinicio, no confirma ABP")
        if ball_reliable and (progression >= 0.16 or lateral >= 0.22):
            # Sin dirección de ataque calibrada no afirmamos progresión ni cambio de orientación.
            label = "Desplazamiento del balón"
            key = "desplazamiento_balon"
            conf = min(0.58, 0.34 + max(progression, lateral) * 0.55)
            actions.append({"key": key, "label": label, "confidence": conf, "reasons": ["balon_detectado", "direccion_no_calibrada"]})
            reasons.append("movimiento del balón detectado sin dirección de ataque calibrada")
        elif not ball_reliable:
            reasons.append("balón no fiable para clasificar la acción")
        if field_calibrated and direction_known and ball_reliable and attack_progression >= 0.16:
            actions.append({"key": "progresion", "label": "Progresión", "confidence": min(0.78, 0.52 + attack_progression), "reasons": ["campo_calibrado", "direccion_ataque", "balon_avanza"]})
        if field_calibrated and direction_known and ball_reliable and wide and last_third:
            actions.append({"key": "centro_lateral", "label": "Centro / ataque exterior", "confidence": 0.62, "reasons": ["campo_calibrado", "banda", "ultimo_tercio"]})
        if field_calibrated and direction_known and ball_reliable and last_third and central:
            actions.append({"key": "finalizacion_probable", "label": "Finalización probable", "confidence": 0.58, "reasons": ["campo_calibrado", "zona_central_finalizacion"]})
        if team_changes and possession_reliable:
            actions.append({"key": "posible_cambio_posesion", "label": "Posible cambio de posesión", "confidence": min(0.56, 0.38 + team_changes * 0.04), "reasons": ["posesion_aproximada", "requiere_revision"]})
            reasons.append("posible cambio de posesión, no confirmado como transición")
        elif team_changes:
            reasons.append("cambios de equipo descartados por tracking inestable")
        if avg_pressure is not None and avg_pressure <= 0.075 and possession_reliable:
            actions.append({"key": "posible_presion", "label": "Posible presión cercana", "confidence": 0.50, "reasons": ["oponente_cerca_poseedor", "posesion_aproximada"]})
            reasons.append("oponente cercano al poseedor estimado")
        if avg_people >= 8 and avg_width >= 0.45 and not actions:
            actions.append({"key": "candidato_estructura", "label": "Candidato de estructura colectiva", "confidence": 0.40, "reasons": ["ocupacion_ancha", "sin_evento_confirmado"]})
            reasons.append("ocupación colectiva visible, acción no clasificada")
        if block_height_hint and avg_people >= 8:
            actions.append({"key": f"posible_{block_height_hint}" if block_evidence_level == "hypothesis" else block_height_hint, "label": block_height_hint.replace("_", " ").title(), "confidence": 0.42 if block_evidence_level == "supported" else 0.34, "reasons": ["altura_media_jugadores", block_evidence_level]})
        if not actions:
            actions.append({"key": "candidato_revisar", "label": "Candidato para revisar", "confidence": 0.30, "reasons": ["senales_insuficientes", "sin_afirmacion_tactica"]})
        actions.sort(key=lambda row: float(row.get("confidence") or 0.0), reverse=True)
        label = actions[0].get("label") or "Acción"
        explanation = f"{label}: " + (", ".join(reasons[:3]) if reasons else "candidato por actividad del juego")
        return {
            "available": True,
            "rank": rank,
            "actions": actions[:6],
            "explanation": explanation,
            "reliability": {
                "ball_reliable": bool(ball_reliable),
                "ball_rate": round(ball_rate, 4),
                "median_ball_jump": round(median_jump, 4),
                "possession_reliable": bool(possession_reliable),
                "possession_rate": round(possession_rate, 4),
                "track_fragmentation": round(track_fragmentation, 4),
                "field_calibrated": bool(field_calibrated),
                "direction_known": bool(direction_known),
                "calibration_confidence": round(float((calibration or {}).get("confidence") or 0.0), 4),
            },
            "ball": {"start": ball_start, "end": ball_end, "points": len(ball_pts), "progression": round(progression, 4), "attack_progression": round(attack_progression, 4), "lateral": round(lateral, 4)},
            "possession": {"samples": len(possessions), "team_changes": team_changes if possession_reliable else 0, "raw_team_changes": team_changes, "dominant": self._most_common(possessions)},
            "pressure": {"avg_nearest_opponent": round(avg_pressure, 4) if avg_pressure is not None else None},
            "shape": {
                "avg_players": round(avg_people, 2),
                "avg_width": round(avg_width, 4),
                "avg_depth": round(avg_depth, 4),
                "avg_line_x": round(avg_line_x, 4) if avg_line_x is not None else None,
                "lane_density": lane_density,
                "occupied_lane_avg": occupied_lane_avg,
                "compactness": round(compactness, 4),
                "field_height_hint": field_height_hint,
                "block_height_hint": block_height_hint,
                "block_evidence_level": block_evidence_level,
            },
            "teams": self._compact_team_payload(payload.get("teams") if isinstance(payload.get("teams"), dict) else {}),
        }

    def _build_senior_read(self, deep_item: dict, *, start: float, end: float, fallback_kind: str, knowledge: list[dict]) -> dict:
        if not deep_item or not deep_item.get("available"):
            return {}
        reliability = deep_item.get("reliability") if isinstance(deep_item.get("reliability"), dict) else {}
        ball = deep_item.get("ball") if isinstance(deep_item.get("ball"), dict) else {}
        shape = deep_item.get("shape") if isinstance(deep_item.get("shape"), dict) else {}
        pressure = deep_item.get("pressure") if isinstance(deep_item.get("pressure"), dict) else {}
        actions = deep_item.get("actions") if isinstance(deep_item.get("actions"), list) else []
        action_keys = {str(row.get("key") or "") for row in actions if isinstance(row, dict)}
        ball_reliable = bool(reliability.get("ball_reliable"))
        possession_reliable = bool(reliability.get("possession_reliable"))
        progression = float(ball.get("progression") or 0.0)
        lateral = float(ball.get("lateral") or 0.0)
        avg_players = float(shape.get("avg_players") or 0.0)
        avg_width = float(shape.get("avg_width") or 0.0)
        avg_depth = float(shape.get("avg_depth") or 0.0)
        occupied_lane_avg = int(shape.get("occupied_lane_avg") or 0)
        compactness = float(shape.get("compactness") or 0.0)
        block_height_hint = str(shape.get("block_height_hint") or "")
        block_evidence_level = str(shape.get("block_evidence_level") or "")
        avg_pressure = pressure.get("avg_nearest_opponent")
        abp_rule = self._abp_senior_rule(deep_item)
        rules = [
            {
                "key": "lectura_bloque",
                "concept": "coach_defensa_distancias_bloque",
                "title": "Bloque: altura y distancias",
                "score": 0.42 + min(0.14, avg_players / 80.0) + min(0.10, avg_depth * 0.35) + min(0.08, compactness / 220.0) + (0.06 if block_evidence_level == "supported" else 0.0),
                "when": avg_players >= 8 and bool(block_height_hint),
                "roles": ["linea defensiva", "linea media", "intervalos", "espacio a espalda"],
                "why": f"La IA estima {block_height_hint.replace('_', ' ')} desde la altura media del bloque; debe revisarse con líneas y distancias visibles.",
            },
            {
                "key": "ocupacion_5_carriles",
                "concept": "espacio_5_carriles",
                "title": "Ocupación de 5 carriles",
                "score": 0.40 + min(0.18, avg_width * 0.32) + min(0.10, avg_players / 90.0) + min(0.08, occupied_lane_avg / 30.0),
                "when": avg_players >= 8 and (avg_width >= 0.42 or occupied_lane_avg >= 3),
                "roles": ["carril exterior", "carril interior", "carril central", "lado débil"],
                "why": "La ocupación ancha permite revisar si exteriores, interiores y carril central están complementados o se pisan zonas.",
            },
            {
                "key": "salida_3_hombres",
                "concept": "coach_salida_hombre_libre",
                "title": "Salida: poseedor, apoyo y tercer hombre",
                "score": 0.42 + min(0.16, avg_players / 70.0) + min(0.14, avg_width / 5.0) + (0.08 if ball_reliable else 0.0),
                "when": avg_players >= 7 and avg_width >= 0.34 and fallback_kind != "abp",
                "roles": ["poseedor probable", "apoyo cercano", "tercer hombre / hombre libre", "primer rival que condiciona"],
                "why": "La IA busca si la estructura ofrece poseedor, apoyo y hombre libre; no marca a todos, sólo los participantes de la posible salida.",
            },
            {
                "key": "cambio_lado_debil",
                "concept": "coach_cambio_orientacion_lado_debil",
                "title": "Cambio al lado débil",
                "score": 0.44 + min(0.22, lateral * 0.65) + (0.10 if ball_reliable else 0.0),
                "when": ball_reliable and lateral >= 0.18,
                "roles": ["poseedor", "bloque que bascula", "receptor lado débil", "opción de continuidad"],
                "why": "El balón se desplaza lateralmente; la pregunta senior es si el cambio crea ventaja o sólo cambia la zona de juego.",
            },
            {
                "key": "superar_linea",
                "concept": "coach_progresion_superar_linea",
                "title": "Progresión: superar línea",
                "score": 0.45 + min(0.24, progression * 0.70) + (0.08 if ball_reliable else 0.0),
                "when": ball_reliable and progression >= 0.14,
                "roles": ["poseedor", "receptor potencial", "rival de la línea superada", "apoyo de seguridad"],
                "why": "Hay avance del balón; la lectura se centra en si la ventaja estaba en conducir, pasar o fijar antes de soltar.",
            },
            {
                "key": "presion_y_cobertura",
                "concept": "coach_defensa_saltar_o_temporizar",
                "title": "Presión: salto y cobertura",
                "score": 0.43 + (0.12 if possession_reliable else 0.0) + (0.12 if avg_pressure is not None and float(avg_pressure) <= 0.09 else 0.0),
                "when": avg_pressure is not None and float(avg_pressure) <= 0.11,
                "roles": ["poseedor presionado", "defensor que salta", "cobertura", "línea de pase que debe cerrarse"],
                "why": "Aparece presión cercana; el corte debe enseñar si el salto mejora la situación o rompe la estructura.",
            },
            {
                "key": "abp_roles_segunda_jugada",
                "concept": "coach_abp_roles_bloqueos",
                "title": abp_rule["title"],
                "score": 0.54,
                "when": str(fallback_kind) == "abp" or "posible_reinicio" in action_keys,
                "roles": abp_rule["roles"],
                "why": abp_rule["why"],
                "abp_type": abp_rule["type"],
                "capture_must_show": abp_rule["capture_must_show"],
            },
        ]
        candidates = [rule for rule in rules if rule["when"]]
        if not candidates:
            candidates = [
                {
                    "key": "estructura_entrenable",
                    "concept": "coach_corte_ventana_entrenador",
                    "title": "Estructura entrenable",
                    "score": 0.36 + min(0.12, avg_players / 90.0),
                    "roles": ["origen", "jugador que decide", "opción cercana", "consecuencia"],
                    "why": "No hay fiabilidad suficiente para afirmar una acción, pero sí una ventana que puede revisarse con criterio de entrenador.",
                }
            ]
        best = max(candidates, key=lambda row: float(row.get("score") or 0.0))
        entry = self._knowledge_by_concept(knowledge, str(best.get("concept") or ""))
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        coach_question = str(payload.get("coach_question") or self._default_coach_question(str(best["key"]))).strip()
        capture_must_show = best.get("capture_must_show") if isinstance(best.get("capture_must_show"), list) else []
        if not capture_must_show:
            capture_must_show = payload.get("capture_must_show") if isinstance(payload.get("capture_must_show"), list) else []
        if not capture_must_show:
            capture_must_show = ["origen", "accion principal", "consecuencia"]
        training_transfer = str(payload.get("training_transfer") or "").strip()
        title = str(entry.get("title") or best.get("title") or "Lectura senior").strip()
        score = max(0.20, min(0.86, float(best.get("score") or 0.0)))
        if not ball_reliable:
            score = min(score, 0.56)
        explanation = (
            f"{title}: {best.get('why')} "
            f"Pregunta: {coach_question} "
            f"Debe verse: {', '.join(str(x) for x in capture_must_show[:4])}."
        )
        return {
            "key": str(best["key"]),
            "title": title,
            "confidence": round(score, 4),
            "coach_question": coach_question,
            "capture_must_show": capture_must_show[:6],
            "training_transfer": training_transfer,
            "selected_roles": list(best.get("roles") or [])[:6],
            "window_reason": "Empieza antes del origen útil y termina tras la consecuencia inmediata.",
            "phase_model": self._senior_phase_model(str(best["key"])),
            "abp_type": str(best.get("abp_type") or ""),
            "source_concept": str(best.get("concept") or ""),
            "source_summary": str(entry.get("summary") or "")[:500],
            "explanation": explanation[:700],
            "action": {
                "key": f"senior_{best['key']}",
                "label": title,
                "confidence": round(score, 4),
                "reasons": ["lectura_senior", str(best.get("concept") or ""), "roles_selectivos"],
            },
            "clip_window": {"start_s": round(start, 3), "end_s": round(end, 3), "duration_s": round(end - start, 3)},
        }

    def _knowledge_by_concept(self, knowledge: list[dict], concept_key: str) -> dict:
        for item in knowledge or []:
            if str(item.get("concept_key") or "") == concept_key:
                return item
        return {}

    def _default_coach_question(self, key: str) -> str:
        defaults = {
            "salida_3_hombres": "¿Hay poseedor, apoyo y tercer hombre para superar la presión?",
            "cambio_lado_debil": "¿Cuándo aparece el lado débil y quién debe verlo?",
            "superar_linea": "¿La ventaja estaba en conducir, pasar o fijar?",
            "presion_y_cobertura": "¿La presión mejora la situación o rompe la estructura?",
            "abp_roles_segunda_jugada": "¿Cada jugador cumple su rol antes del golpeo y tras el rechace?",
        }
        return defaults.get(key, "¿Se entiende por qué ocurrió, no sólo qué ocurrió?")

    def _senior_phase_model(self, key: str) -> list[str]:
        if key == "abp_roles_segunda_jugada":
            return ["organización previa", "golpeo/reinicio", "primera disputa", "segunda jugada", "final de acción"]
        return ["origen", "acción principal", "consecuencia"]

    def _abp_senior_rule(self, deep_item: dict) -> dict:
        abp_type = self._infer_abp_type(deep_item)
        if abp_type == "falta_lateral":
            return {
                "type": abp_type,
                "title": "Falta lateral: línea, carga y segunda jugada",
                "roles": ["golpeador", "línea defensiva", "atacante que carga zona", "marcador directo", "jugador de segunda jugada"],
                "capture_must_show": ["organización previa", "golpeador", "línea defensiva", "zona de caída", "segunda jugada"],
                "why": "El patrón se parece a una falta lateral: el corte debe enseñar altura de la línea, carrera de atacantes, zona de caída y respuesta al rechace.",
            }
        if abp_type == "corner_probable":
            return {
                "type": abp_type,
                "title": "Córner: bloqueos, zona de caída y rechace",
                "roles": ["sacador", "bloqueador o pantalla", "rematador objetivo", "marcador directo", "jugador de segunda jugada"],
                "capture_must_show": ["organización previa", "bloqueos/carreras", "primer contacto", "rechace", "segunda jugada"],
                "why": "El patrón se parece a un córner: el corte debe mostrar rutina previa, carreras/bloqueos, primer contacto y segunda jugada.",
            }
        if abp_type == "saque_banda_largo":
            return {
                "type": abp_type,
                "title": "Saque de banda largo: carga y segunda jugada",
                "roles": ["sacador", "primer duelo", "pantalla/bloqueo", "zona de caída", "jugador de segunda jugada"],
                "capture_must_show": ["organización previa", "saque", "primer duelo", "rechace", "segunda jugada"],
                "why": "El patrón se parece a un saque de banda largo: el valor está en la carga, primer duelo y segunda jugada.",
            }
        return {
            "type": abp_type,
            "title": "ABP: roles y segunda jugada",
            "roles": ["sacador/golpeador", "bloqueador o marcador", "zona de caída", "jugador de segunda jugada"],
            "capture_must_show": ["organización previa", "golpeo/reinicio", "primera disputa", "segunda jugada", "final de acción"],
            "why": "El patrón sugiere reinicio; un corte útil debe mostrar organización previa, disputa y respuesta al rechace.",
        }

    def _infer_abp_type(self, deep_item: dict) -> str:
        ball = deep_item.get("ball") if isinstance(deep_item.get("ball"), dict) else {}
        start = ball.get("start") if isinstance(ball.get("start"), dict) else {}
        end = ball.get("end") if isinstance(ball.get("end"), dict) else {}
        pts = [p for p in [start, end] if isinstance(p, dict)]
        if not pts:
            return "reinicio_no_clasificado"
        x_vals = [float(p.get("x") or 0.0) for p in pts]
        y_vals = [float(p.get("y") or 0.0) for p in pts]
        near_endline = any(x <= 0.10 or x >= 0.90 for x in x_vals)
        near_touchline = any(y <= 0.12 or y >= 0.88 for y in y_vals)
        wide = any(y <= 0.24 or y >= 0.76 for y in y_vals)
        deep_wide = any(y <= 0.18 or y >= 0.82 for y in y_vals)
        if near_endline and near_touchline:
            return "corner_probable"
        if near_touchline and not near_endline:
            return "saque_banda_largo"
        if wide or deep_wide:
            return "falta_lateral"
        return "falta_frontal_o_reinicio_central"

    def _most_common(self, values: list[str]) -> str:
        counts = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return max(counts.items(), key=lambda row: row[1])[0] if counts else ""

    def _compact_team_payload(self, teams: dict) -> dict:
        track_team = teams.get("track_team") if isinstance(teams.get("track_team"), dict) else {}
        counts = {}
        for value in track_team.values():
            key = str(value or "unknown")
            counts[key] = counts.get(key, 0) + 1
        return {
            "centers": teams.get("centers") if isinstance(teams.get("centers"), list) else [],
            "track_count": len(track_team),
            "team_counts": counts,
            "note": "Asignacion aproximada por color; no se usa para afirmar transiciones si el tracking es inestable.",
        }

    def _merge_actions(self, deep_actions: list[dict], old_actions: list[dict], *, include_old: bool = False) -> list[dict]:
        out = []
        seen = set()
        source = list(deep_actions or []) + (list(old_actions or []) if include_old or not deep_actions else [])
        for row in source:
            key = str(row.get("key") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(row)
        out.sort(key=lambda row: float(row.get("confidence") or 0.0), reverse=True)
        return out[:8]

    def _build_clip_overlay(self, deep_item: dict, *, start: float, end: float, title: str) -> dict:
        explanation = str((deep_item or {}).get("explanation") or "").strip()
        senior = (deep_item or {}).get("senior") if isinstance((deep_item or {}).get("senior"), dict) else {}
        coach_question = str(senior.get("coach_question") or "").strip()
        roles = senior.get("selected_roles") if isinstance(senior.get("selected_roles"), list) else []
        ball = (deep_item or {}).get("ball") if isinstance((deep_item or {}).get("ball"), dict) else {}
        b0 = ball.get("start") if isinstance(ball.get("start"), dict) else {}
        b1 = ball.get("end") if isinstance(ball.get("end"), dict) else {}
        w, h = 1280, 720
        objects = []
        def data(kind):
            return {"uid": f"ai-{kind}-{int(start*1000)}", "kind": kind, "t_in_s": float(start), "t_out_s": float(end), "fade_in_ms": 150, "fade_out_ms": 180, "anim": "none"}
        objects.append({"type": "rect", "version": "5.3.0", "left": 42, "top": h - 142, "width": 830, "height": 96, "fill": "rgba(2,6,23,0.72)", "stroke": "rgba(34,211,238,0.75)", "strokeWidth": 2, "rx": 8, "ry": 8, "data": data("ai_explanation_box")})
        objects.append({"type": "textbox", "version": "5.3.0", "left": 66, "top": h - 126, "width": 790, "height": 36, "fill": "#f8fafc", "fontSize": 24, "fontWeight": "800", "fontFamily": "Arial", "text": (title[:70] or "Corte IA"), "data": data("ai_title")})
        overlay_text = explanation[:170] or "Candidato IA para revisar."
        if coach_question:
            overlay_text = f"{coach_question} Roles: {', '.join(str(x) for x in roles[:3])}"[:190]
        objects.append({"type": "textbox", "version": "5.3.0", "left": 66, "top": h - 88, "width": 790, "height": 52, "fill": "#cbd5e1", "fontSize": 20, "fontFamily": "Arial", "text": overlay_text, "data": data("ai_explanation")})
        if b0 and b1:
            x0 = float(b0.get("x") or 0.0) * w
            y0 = float(b0.get("y") or 0.0) * h
            x1 = float(b1.get("x") or 0.0) * w
            y1 = float(b1.get("y") or 0.0) * h
            if x0 or y0 or x1 or y1:
                objects.append({"type": "line", "version": "5.3.0", "x1": x0, "y1": y0, "x2": x1, "y2": y1, "left": min(x0, x1), "top": min(y0, y1), "stroke": "#22d3ee", "strokeWidth": 7, "strokeLineCap": "round", "data": data("movement_line")})
                objects.append({"type": "circle", "version": "5.3.0", "left": x1 - 18, "top": y1 - 18, "radius": 18, "fill": "rgba(34,211,238,0.20)", "stroke": "#22d3ee", "strokeWidth": 4, "data": data("ai_ball_target")})
        return {"version": "5.3.0", "objects": objects, "ai_overlay": True}

    def _escape_drawtext(self, value: str) -> str:
        text = str(value or "").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        return text.replace("\n", " ")[:180]

    def _export_mp4(self, video_path: str, created: list[dict], out_dir: Path, limit: int, *, annotated: bool = False) -> list[str]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg or limit <= 0:
            return []
        exported = []
        for item in created[: min(limit, len(created))]:
            prefix = "annotated_" if annotated else ""
            out_path = out_dir / f"{prefix}cut_{int(item['rank']):02d}_{float(item['start_s']):.1f}_{float(item['end_s']):.1f}.mp4"
            if annotated:
                explanation = self._escape_drawtext(item.get("explanation") or item.get("label") or "Corte IA")
                label = self._escape_drawtext((item.get("actions") or [{}])[0].get("label") if item.get("actions") else item.get("label"))
                vf = (
                    "drawbox=x=30:y=ih-145:w=iw-60:h=112:color=black@0.58:t=fill,"
                    "drawbox=x=30:y=ih-145:w=iw-60:h=112:color=0x22d3ee@0.85:t=3,"
                    f"drawtext=text='{label}':x=54:y=h-126:fontsize=26:fontcolor=white:box=0,"
                    f"drawtext=text='{explanation}':x=54:y=h-88:fontsize=20:fontcolor=0xcbd5e1:box=0"
                )
                cmd = [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{float(item['start_s']):.3f}",
                    "-t",
                    f"{float(item['duration_s']):.3f}",
                    "-i",
                    video_path,
                    "-vf",
                    vf,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    str(out_path),
                ]
                try:
                    subprocess.run(cmd, check=True, timeout=90)  # noqa: S603
                    exported.append(str(out_path))
                    continue
                except Exception:
                    pass
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{float(item['start_s']):.3f}",
                "-to",
                f"{float(item['end_s']):.3f}",
                "-i",
                video_path,
                "-c",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                str(out_path),
            ]
            try:
                subprocess.run(cmd, check=True, timeout=45)  # noqa: S603
                exported.append(str(out_path))
                continue
            except Exception:
                pass
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{float(item['start_s']):.3f}",
                "-t",
                f"{float(item['duration_s']):.3f}",
                "-i",
                video_path,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                str(out_path),
            ]
            try:
                subprocess.run(cmd, check=True, timeout=60)  # noqa: S603
                exported.append(str(out_path))
            except Exception:
                continue
        return exported
