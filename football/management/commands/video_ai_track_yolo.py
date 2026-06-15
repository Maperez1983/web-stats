from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from football.models import RivalVideo
from football.video_ai_services import write_track_json, yolo_track_video


class Command(BaseCommand):
    help = "Ejecuta YOLO+ByteTrack sobre un vídeo/rango y guarda detecciones con IDs en JSON."

    def add_arguments(self, parser):
        parser.add_argument("--video-id", type=int, default=0, help="RivalVideo.id origen.")
        parser.add_argument("--source", type=str, default="", help="Ruta de vídeo si no se usa --video-id.")
        parser.add_argument("--start", type=float, default=0.0, help="Segundo inicial.")
        parser.add_argument("--end", type=float, default=0.0, help="Segundo final. 0 = vídeo completo.")
        parser.add_argument("--model", type=str, default="data/video_ai/models/yolo11n.pt", help="Pesos YOLO.")
        parser.add_argument("--out", type=str, default="", help="JSON salida.")
        parser.add_argument("--conf", type=float, default=0.25, help="Confianza mínima.")
        parser.add_argument("--imgsz", type=int, default=960, help="Tamaño de inferencia.")
        parser.add_argument("--tracker", type=str, default="bytetrack.yaml", help="Tracker Ultralytics.")
        parser.add_argument("--save-video", action="store_true", help="Guarda vídeo anotado de Ultralytics.")
        parser.add_argument("--no-ball", action="store_true", help="No intenta detectar balón.")

    def handle(self, *args, **options):
        video_id = int(options.get("video_id") or 0)
        source_arg = str(options.get("source") or "").strip()
        start_s = max(0.0, float(options.get("start") or 0.0))
        end_s = max(0.0, float(options.get("end") or 0.0))
        model_path = Path(str(options.get("model") or "data/video_ai/models/yolo11n.pt")).resolve()
        conf = max(0.01, min(0.95, float(options.get("conf") or 0.25)))
        imgsz = max(320, min(1920, int(options.get("imgsz") or 960)))
        tracker = str(options.get("tracker") or "bytetrack.yaml").strip() or "bytetrack.yaml"
        include_ball = not bool(options.get("no_ball"))

        if not model_path.exists():
            raise CommandError(f"No existe el modelo: {model_path}")

        if video_id:
            video = RivalVideo.objects.filter(id=int(video_id)).first()
            if not video or not getattr(video, "video", None):
                raise CommandError(f"RivalVideo no encontrado o sin archivo: {video_id}")
            source = Path(str(video.video.path))
        elif source_arg:
            source = Path(source_arg).expanduser().resolve()
        else:
            raise CommandError("Indica --video-id o --source.")

        if not source.exists():
            raise CommandError(f"No existe el vídeo: {source}")

        out_path = Path(str(options.get("out") or "").strip() or "data/video_ai/runs/yolo_track.json").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            payload = yolo_track_video(
                source=source,
                model_path=model_path,
                start_s=start_s,
                end_s=end_s,
                conf=conf,
                imgsz=imgsz,
                tracker=tracker,
                include_ball=include_ball,
            )
            payload["video_id"] = int(video_id or 0)
            write_track_json(payload, out_path)
            unique_ids = sorted(
                {
                    int(det["track_id"])
                    for row in payload.get("frames", [])
                    for det in row.get("detections", [])
                    if det.get("track_id") is not None and int(det.get("class_id") or 0) == 0
                }
            )
            balls = sum(
                1
                for row in payload.get("frames", [])
                for det in row.get("detections", [])
                if int(det.get("class_id") or 0) == 32
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"YOLO track OK frames={len(payload.get('frames', []))} ids={len(unique_ids)} ball_dets={balls} out={out_path}"
                )
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
