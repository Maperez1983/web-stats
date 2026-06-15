from __future__ import annotations

import json
import math
import shutil
import subprocess
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Exporta cortes IA con señalamiento táctico senior y protagonistas selectivos."

    def add_arguments(self, parser):
        parser.add_argument("--summary", type=str, required=True)
        parser.add_argument("--source-dir", type=str, required=True)
        parser.add_argument("--out-dir", type=str, required=True)
        parser.add_argument("--limit", type=int, default=8)
        parser.add_argument("--model", type=str, default="data/video_ai/models/yolo11n.pt")
        parser.add_argument("--conf", type=float, default=0.18)
        parser.add_argument("--imgsz", type=int, default=960)

    def handle(self, *args, **options):
        summary_path = Path(str(options["summary"])).expanduser()
        source_dir = Path(str(options["source_dir"])).expanduser()
        out_dir = Path(str(options["out_dir"])).expanduser()
        model_path = Path(str(options["model"])).expanduser()
        if not summary_path.exists():
            raise CommandError(f"No existe summary: {summary_path}")
        if not source_dir.exists():
            raise CommandError(f"No existe source-dir: {source_dir}")
        if not model_path.exists():
            raise CommandError(f"No existe modelo YOLO: {model_path}")
        try:
            from ultralytics import YOLO  # noqa: WPS433
            import cv2  # noqa: WPS433
        except Exception as exc:
            raise CommandError(f"No están disponibles ultralytics/cv2: {exc}") from exc

        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        clips = payload.get("clips") if isinstance(payload.get("clips"), list) else []
        out_dir.mkdir(parents=True, exist_ok=True)
        model = YOLO(str(model_path))
        exported = []
        reports = []
        for item in clips[: max(0, int(options["limit"] or 0))]:
            rank = int(item.get("rank") or 0)
            src = self._find_source_clip(source_dir, rank)
            if not src:
                reports.append({"rank": rank, "error": "source_clip_not_found"})
                continue
            senior = item.get("senior") if isinstance(item.get("senior"), dict) else {}
            out_path = out_dir / f"senior_selectivo_{rank:02d}_{float(item.get('start_s') or 0):.1f}_{float(item.get('end_s') or 0):.1f}.mp4"
            report = self._render_clip(
                cv2=cv2,
                model=model,
                src=src,
                out_path=out_path,
                senior=senior,
                conf=float(options["conf"] or 0.18),
                imgsz=int(options["imgsz"] or 960),
            )
            report["rank"] = rank
            report["src"] = str(src)
            report["out"] = str(out_path)
            reports.append(report)
            if out_path.exists():
                exported.append(str(out_path))
        (out_dir / "senior_export_report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "exports.txt").write_text("\n".join(exported), encoding="utf-8")
        self.stdout.write(json.dumps({"ok": True, "exported": len(exported), "out_dir": str(out_dir), "files": exported}, ensure_ascii=False, indent=2))

    def _find_source_clip(self, source_dir: Path, rank: int) -> Path | None:
        candidates = sorted(source_dir.glob(f"cut_{rank:02d}_*.mp4")) + sorted(source_dir.glob(f"annotated_cut_{rank:02d}_*.mp4"))
        return candidates[0] if candidates else None

    def _render_clip(self, *, cv2, model, src: Path, out_path: Path, senior: dict, conf: float, imgsz: int) -> dict:
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            return {"error": "cannot_open_source"}
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        cap.release()

        frames = []
        stats = {}
        for idx, result in enumerate(
            model.track(
                source=str(src),
                classes=[0, 32],
                conf=max(0.01, min(0.95, conf)),
                imgsz=max(320, min(1920, imgsz)),
                tracker="bytetrack.yaml",
                persist=True,
                stream=True,
                save=False,
                verbose=False,
            )
        ):
            boxes = result.boxes
            frame = getattr(result, "orig_img", None)
            detections = []
            ball = None
            if boxes is not None and len(boxes):
                xyxy = boxes.xyxy.cpu().numpy().tolist()
                confs = boxes.conf.cpu().numpy().tolist() if boxes.conf is not None else []
                ids = boxes.id.cpu().numpy().tolist() if boxes.id is not None else [None] * len(xyxy)
                clss = boxes.cls.cpu().numpy().tolist() if boxes.cls is not None else [0] * len(xyxy)
                for det_idx, box in enumerate(xyxy):
                    class_id = int(clss[det_idx]) if det_idx < len(clss) else 0
                    det = {
                        "track_id": int(ids[det_idx]) if ids[det_idx] is not None else None,
                        "class_id": class_id,
                        "conf": float(confs[det_idx]) if det_idx < len(confs) else 0.0,
                        "box": [float(x) for x in box],
                    }
                    if class_id == 32 and (ball is None or det["conf"] > ball["conf"]):
                        ball = det
                    elif class_id == 0 and det["track_id"] is not None:
                        detections.append(det)
            ball_center = self._center(ball["box"]) if ball else None
            for det in detections:
                tid = int(det["track_id"])
                cx, cy = self._center(det["box"])
                row = stats.setdefault(tid, {"count": 0, "near_ball": [], "centers": [], "area": []})
                row["count"] += 1
                row["centers"].append((cx, cy))
                row["area"].append(max(1.0, (det["box"][2] - det["box"][0]) * (det["box"][3] - det["box"][1])))
                if ball_center:
                    row["near_ball"].append(math.hypot((cx - ball_center[0]) / max(1, width), (cy - ball_center[1]) / max(1, height)))
            frames.append({"idx": idx, "image": frame, "people": detections, "ball": ball})

        selected = self._select_tracks(stats, senior)
        role_names = senior.get("selected_roles") if isinstance(senior.get("selected_roles"), list) else []
        role_by_track = {tid: self._ascii(role_names[pos] if pos < len(role_names) else f"protagonista {pos + 1}") for pos, tid in enumerate(selected)}
        tmp_video = out_path.with_suffix(".video.mp4")
        writer = cv2.VideoWriter(str(tmp_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            return {"error": "cannot_open_writer"}
        for frame in frames:
            img = frame["image"]
            if img is None:
                continue
            self._draw_header(cv2, img, senior)
            for det in frame["people"]:
                tid = int(det["track_id"])
                if tid not in selected:
                    continue
                self._draw_player(cv2, img, det["box"], role_by_track.get(tid, "protagonista"), selected.index(tid))
            if frame["ball"]:
                self._draw_ball(cv2, img, frame["ball"]["box"])
            writer.write(img)
        writer.release()
        self._mux_audio(src, tmp_video, out_path)
        try:
            tmp_video.unlink(missing_ok=True)
        except Exception:
            pass
        return {"selected_tracks": selected, "roles": role_by_track, "senior_key": senior.get("key") or ""}

    def _select_tracks(self, stats: dict, senior: dict) -> list[int]:
        rows = []
        key = str(senior.get("key") or "")
        for tid, row in stats.items():
            count = int(row.get("count") or 0)
            centers = row.get("centers") or []
            movement = 0.0
            if len(centers) >= 2:
                movement = math.hypot(centers[-1][0] - centers[0][0], centers[-1][1] - centers[0][1])
            near = row.get("near_ball") or []
            near_score = 1.0 / (0.05 + (sum(near) / len(near))) if near else 0.0
            area = sum(row.get("area") or [0.0]) / max(1, len(row.get("area") or []))
            score = count * 0.50 + near_score * 3.0 + movement * 0.025 + math.sqrt(max(0.0, area)) * 0.04
            if key.startswith("abp"):
                score = count * 0.75 + math.sqrt(max(0.0, area)) * 0.08 + near_score * 1.2
            rows.append((score, int(tid)))
        rows.sort(reverse=True)
        max_tracks = 4 if str(senior.get("key") or "").startswith("abp") else 3
        return [tid for _, tid in rows[:max_tracks]]

    def _draw_header(self, cv2, img, senior: dict) -> None:
        h, w = img.shape[:2]
        title = self._ascii(str(senior.get("title") or "Lectura senior"))[:52]
        question = self._ascii(str(senior.get("coach_question") or "Que debe corregir el entrenador?"))[:86]
        roles = senior.get("selected_roles") if isinstance(senior.get("selected_roles"), list) else []
        roles_text = self._ascii(" / ".join(str(x) for x in roles[:4]))[:96]
        cv2.rectangle(img, (24, 22), (min(w - 24, 1120), 126), (5, 12, 24), -1)
        cv2.rectangle(img, (24, 22), (min(w - 24, 1120), 126), (34, 211, 238), 2)
        cv2.putText(img, title, (46, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.86, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, question, (46, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (210, 220, 235), 1, cv2.LINE_AA)
        cv2.putText(img, roles_text, (46, 114), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (147, 197, 253), 1, cv2.LINE_AA)

    def _draw_player(self, cv2, img, box: list[float], label: str, idx: int) -> None:
        colors = [(20, 184, 166), (59, 130, 246), (245, 158, 11), (244, 63, 94)]
        color = colors[idx % len(colors)]
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        cv2.rectangle(img, (x0, y0), (x1, y1), color, 3)
        tag = f"{idx + 1}. {label}"[:34]
        tw = max(140, len(tag) * 10)
        y = max(18, y0 - 10)
        cv2.rectangle(img, (x0, y - 24), (min(x0 + tw, img.shape[1] - 4), y + 4), color, -1)
        cv2.putText(img, tag, (x0 + 6, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (2, 6, 23), 2, cv2.LINE_AA)

    def _draw_ball(self, cv2, img, box: list[float]) -> None:
        cx, cy = self._center(box)
        cv2.circle(img, (int(cx), int(cy)), 18, (34, 211, 238), 3)
        cv2.putText(img, "balon", (int(cx) + 18, int(cy) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (34, 211, 238), 2, cv2.LINE_AA)

    def _mux_audio(self, src: Path, video_only: Path, out_path: Path) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            shutil.copyfile(video_only, out_path)
            return
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_only),
            "-i",
            str(src),
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
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
            "-shortest",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=180)  # noqa: S603
        except Exception:
            shutil.copyfile(video_only, out_path)

    def _center(self, box: list[float]) -> tuple[float, float]:
        return ((float(box[0]) + float(box[2])) * 0.5, (float(box[1]) + float(box[3])) * 0.5)

    def _ascii(self, value: str) -> str:
        return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
