from __future__ import annotations

import json
import textwrap
from pathlib import Path

import cv2
from django.core.management.base import BaseCommand, CommandError

from football.models import RivalVideo, VideoClip


class Command(BaseCommand):
    help = "Exporta cortes IA con caja de explicacion quemada usando OpenCV."

    def add_arguments(self, parser):
        parser.add_argument("--video-id", type=int, required=True)
        parser.add_argument("--collection", type=str, default="IA MaxCuts")
        parser.add_argument("--out-dir", type=str, default="/Volumes/Mac Satecchi/Mac/Downloads/IA_MaxCuts_video_7_deep/annotated_cv")

    def handle(self, *args, **options):
        video = RivalVideo.objects.filter(id=int(options["video_id"])).first()
        if not video or not getattr(video, "video", None):
            raise CommandError("Video no encontrado o sin archivo.")
        source = video.video.path
        if not source or not Path(source).exists():
            raise CommandError(f"No existe el archivo: {source}")
        clips = list(VideoClip.objects.filter(video=video, collection=str(options["collection"] or "IA MaxCuts")).order_by("in_ms"))
        if not clips:
            raise CommandError("No hay cortes para exportar.")
        out_dir = Path(str(options["out_dir"])).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(source)
        if not cap or not cap.isOpened():
            raise CommandError("No se pudo abrir el video con OpenCV.")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        exported = []
        try:
            for clip in clips:
                start = float(getattr(clip, "in_ms", 0) or 0) / 1000.0
                end = float(getattr(clip, "out_ms", 0) or 0) / 1000.0
                if end <= start:
                    continue
                label, explanation = self._clip_text(clip)
                out_path = out_dir / f"annotated_cv_{int(clip.id)}_{start:.1f}_{end:.1f}.mp4"
                writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
                if not writer or not writer.isOpened():
                    continue
                cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000.0)
                while True:
                    pos_s = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
                    if pos_s > end:
                        break
                    ok, frame = cap.read()
                    if not ok:
                        break
                    frame = self._draw_panel(frame, label=label, explanation=explanation)
                    writer.write(frame)
                writer.release()
                if out_path.exists() and out_path.stat().st_size > 1000:
                    exported.append(str(out_path))
        finally:
            try:
                cap.release()
            except Exception:
                pass
        (out_dir / "exports.txt").write_text("\n".join(exported), encoding="utf-8")
        self.stdout.write(json.dumps({"exported": len(exported), "out_dir": str(out_dir), "files": exported}, ensure_ascii=False, indent=2))

    def _clip_text(self, clip: VideoClip) -> tuple[str, str]:
        overlay = clip.overlay if isinstance(getattr(clip, "overlay", None), dict) else {}
        ai = overlay.get("ai_actions") if isinstance(overlay.get("ai_actions"), dict) else {}
        deep = ai.get("deep_tactics") if isinstance(ai.get("deep_tactics"), dict) else {}
        actions = ai.get("actions") if isinstance(ai.get("actions"), list) else []
        top = actions[0] if actions and isinstance(actions[0], dict) else {}
        label = str(top.get("label") or top.get("key") or "Corte IA").strip()[:60]
        explanation = str(deep.get("explanation") or getattr(clip, "notes", "") or label).strip()
        return label, explanation[:210]

    def _draw_panel(self, frame, *, label: str, explanation: str):
        height, width = frame.shape[:2]
        y0 = max(20, height - 155)
        y1 = max(y0 + 90, height - 34)
        overlay = frame.copy()
        cv2.rectangle(overlay, (28, y0), (width - 28, y1), (23, 6, 2), -1)
        frame = cv2.addWeighted(overlay, 0.68, frame, 0.32, 0)
        cv2.rectangle(frame, (28, y0), (width - 28, y1), (238, 211, 34), 3)
        cv2.putText(frame, str(label)[:52], (54, y0 + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.92, (255, 255, 255), 2, cv2.LINE_AA)
        for idx, line in enumerate(textwrap.wrap(str(explanation), width=86)[:2]):
            cv2.putText(frame, line, (54, y0 + 76 + idx * 28), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (240, 232, 226), 2, cv2.LINE_AA)
        return frame
