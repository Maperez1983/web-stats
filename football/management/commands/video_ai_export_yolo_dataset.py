from __future__ import annotations

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from football.models import VideoClip


def _safe_slug(value: str, fallback: str = "item") -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw[:80] or fallback


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


class Command(BaseCommand):
    help = "Exporta tracks corregidos del Video Studio a dataset YOLO local para entrenar detección/reidentificación."

    def add_arguments(self, parser):
        parser.add_argument("--clip-id", type=int, action="append", default=[], help="VideoClip.id a exportar. Repetible.")
        parser.add_argument("--video-id", type=int, default=0, help="Exporta clips de un RivalVideo.")
        parser.add_argument("--out", type=str, default="data/video_ai/yolo_mvp", help="Directorio dataset.")
        parser.add_argument("--class-name", type=str, default="player", help="Nombre de clase YOLO.")
        parser.add_argument("--every-n", type=int, default=5, help="Exporta 1 de cada N keyframes.")
        parser.add_argument("--max-frames", type=int, default=240, help="Máximo de imágenes exportadas.")
        parser.add_argument("--box-w", type=float, default=0.08, help="Ancho bbox relativo si el marker no lo trae.")
        parser.add_argument("--box-h", type=float, default=0.18, help="Alto bbox relativo si el marker no lo trae.")
        parser.add_argument(
            "--anchors-only",
            action="store_true",
            help="Exporta solo anclajes manuales de markers (mayor calidad, menos cantidad).",
        )

    def handle(self, *args, **options):
        try:
            import cv2  # noqa: WPS433
        except Exception as exc:
            raise CommandError(f"OpenCV no disponible: {exc}") from exc

        clip_ids = [int(x) for x in (options.get("clip_id") or []) if int(x or 0) > 0]
        video_id = int(options.get("video_id") or 0)
        if not clip_ids and not video_id:
            raise CommandError("Indica --clip-id o --video-id.")

        out_dir = Path(str(options.get("out") or "data/video_ai/yolo_mvp")).resolve()
        images_dir = out_dir / "images" / "train"
        labels_dir = out_dir / "labels" / "train"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)

        class_name = str(options.get("class_name") or "player").strip() or "player"
        every_n = max(1, int(options.get("every_n") or 5))
        max_frames = max(1, int(options.get("max_frames") or 240))
        default_box_w = max(0.02, min(0.40, float(options.get("box_w") or 0.08)))
        default_box_h = max(0.02, min(0.50, float(options.get("box_h") or 0.18)))
        anchors_only = bool(options.get("anchors_only"))

        qs = VideoClip.objects.select_related("video", "team").order_by("id")
        if clip_ids:
            qs = qs.filter(id__in=clip_ids)
        if video_id:
            qs = qs.filter(video_id=int(video_id))

        exported = 0
        skipped = 0
        manifest_rows = []

        for clip in qs.iterator(chunk_size=50):
            if exported >= max_frames:
                break
            overlay = clip.overlay if isinstance(getattr(clip, "overlay", None), dict) else {}
            tracking = overlay.get("tracking") if isinstance(overlay.get("tracking"), dict) else {}
            tracks = tracking.get("tracks") if isinstance(tracking.get("tracks"), dict) else {}
            if not tracks:
                skipped += 1
                continue

            markers = tracking.get("markers") if isinstance(tracking.get("markers"), list) else []
            marker_by_uid = {
                str(m.get("uid") or "").strip(): m
                for m in markers
                if isinstance(m, dict) and str(m.get("uid") or "").strip()
            }
            fallback_marker = next((m for m in markers if isinstance(m, dict)), {})

            video = getattr(clip, "video", None)
            video_file = getattr(video, "video", None)
            video_path = Path(str(getattr(video_file, "path", "") or ""))
            if not video_path.exists():
                skipped += 1
                continue

            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                skipped += 1
                continue
            try:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                if width <= 0 or height <= 0:
                    skipped += 1
                    continue

                export_items = []
                if anchors_only:
                    for marker in markers:
                        if not isinstance(marker, dict):
                            continue
                        uid = str(marker.get("uid") or "anchor").strip() or "anchor"
                        anchors = marker.get("anchors") if isinstance(marker.get("anchors"), list) else []
                        raw_points = [
                            {
                                "t": item.get("t"),
                                "x_rel": item.get("x_rel"),
                                "y_rel": item.get("y_rel"),
                            }
                            for item in anchors
                            if isinstance(item, dict)
                        ]
                        if raw_points:
                            export_items.append((uid, raw_points, marker))
                else:
                    for track_uid, raw_points in tracks.items():
                        marker = marker_by_uid.get(str(track_uid)) or fallback_marker or {}
                        export_items.append((track_uid, raw_points, marker))

                for track_uid, raw_points, marker in export_items:
                    if exported >= max_frames:
                        break
                    points = raw_points if isinstance(raw_points, list) else []
                    if not points:
                        continue
                    box_w = max(0.02, min(0.40, _as_float(marker.get("bw_rel"), default_box_w)))
                    box_h = max(0.02, min(0.50, _as_float(marker.get("bh_rel"), default_box_h)))
                    track_slug = _safe_slug(str(track_uid), "track")

                    for idx, point in enumerate(points):
                        if exported >= max_frames:
                            break
                        if idx % every_n:
                            continue
                        if not isinstance(point, dict):
                            continue
                        t = _as_float(point.get("t"), -1.0)
                        x_rel = max(0.0, min(1.0, _as_float(point.get("x_rel"), 0.0)))
                        y_rel = max(0.0, min(1.0, _as_float(point.get("y_rel"), 0.0)))
                        if t < 0:
                            continue

                        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                        ok, frame = cap.read()
                        if not ok or frame is None:
                            skipped += 1
                            continue

                        stem = f"clip{int(clip.id):06d}_{track_slug}_{int(round(t * 1000)):09d}"
                        image_path = images_dir / f"{stem}.jpg"
                        label_path = labels_dir / f"{stem}.txt"
                        cv2.imwrite(str(image_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                        label_path.write_text(
                            f"0 {x_rel:.6f} {y_rel:.6f} {box_w:.6f} {box_h:.6f}\n",
                            encoding="utf-8",
                        )
                        manifest_rows.append(
                            {
                                "image": str(image_path.relative_to(out_dir)),
                                "label": str(label_path.relative_to(out_dir)),
                                "clip_id": int(clip.id),
                                "video_id": int(getattr(clip, "video_id", 0) or 0),
                                "track_uid": str(track_uid),
                                "t": float(t),
                                "bbox": [x_rel, y_rel, box_w, box_h],
                                "source": str(tracking.get("source") or ""),
                                "meta": tracking.get("meta") if isinstance(tracking.get("meta"), dict) else {},
                            }
                        )
                        exported += 1
            finally:
                cap.release()

        (out_dir / "data.yaml").write_text(
            "\n".join(
                [
                    f"path: {out_dir}",
                    "train: images/train",
                    "val: images/train",
                    "names:",
                    f"  0: {class_name}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (out_dir / "manifest.json").write_text(json.dumps(manifest_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "README.md").write_text(
            "\n".join(
                [
                    "# Video AI YOLO MVP dataset",
                    "",
                    "Dataset generado desde correcciones del Video Studio.",
                    "",
                    "- `images/train/`: frames extraidos del video.",
                    "- `labels/train/`: etiquetas YOLO `class x_center y_center width height` normalizadas.",
                    "- `data.yaml`: configuracion para entrenamiento YOLO.",
                    "- `manifest.json`: trazabilidad clip/video/track/tiempo.",
                    "",
                    "Siguiente paso: revisar etiquetas visualmente antes de entrenar.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Video AI dataset exportado: images={exported} skipped={skipped} out={out_dir}"
            )
        )
