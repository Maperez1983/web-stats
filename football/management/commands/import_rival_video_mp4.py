from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.core.files.base import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from football.models import AnalystVideoFolder, RivalVideo, Team


def _run_out(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    return str(p.stdout or "")


def _ffprobe_video_codec(path: str) -> str:
    out = _run_out(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=nw=1:nk=1",
            path,
        ]
    ).strip()
    return out


def _ffprobe_duration_seconds(path: str) -> float:
    out = _run_out(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            path,
        ]
    ).strip()
    try:
        return float(out)
    except Exception:
        return 0.0


def _transcode_to_h264_aac(
    *,
    input_path: str,
    output_path: str,
    height: int = 720,
    fps: int = 30,
    crf: int = 23,
    preset: str = "veryfast",
    audio_bitrate: str = "128k",
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise CommandError("FFmpeg no está disponible en este entorno.")
    in_path = str(input_path)
    out_path = str(output_path)

    vf = []
    if height and int(height) > 0:
        vf.append(f"scale=-2:{int(height)}")
    if fps and int(fps) > 0:
        vf.append(f"fps={int(fps)}")
    vf_arg = ",".join(vf) if vf else None

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        in_path,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        str(preset or "veryfast"),
        "-crf",
        str(int(crf)),
        "-c:a",
        "aac",
        "-b:a",
        str(audio_bitrate or "128k"),
        "-movflags",
        "+faststart",
    ]
    if vf_arg:
        cmd.extend(["-vf", vf_arg])
    cmd.append(out_path)
    subprocess.check_call(cmd)  # noqa: S603


class Command(BaseCommand):
    help = "Importa un vídeo local al repositorio de Análisis (RivalVideo) y lo deja listo para Video Studio."

    def add_arguments(self, parser):
        parser.add_argument("mp4_path", help="Ruta al vídeo (MP4/MKV/WEBM...).")
        parser.add_argument("--team-id", type=int, default=0, help="Team.id destino (si no, usa el equipo primario).")
        parser.add_argument("--rival-team-id", type=int, default=0, help="Team.id del rival (opcional).")
        parser.add_argument("--title", default="", help="Título del vídeo (si vacío, usa el nombre del archivo).")
        parser.add_argument("--folder", default="", help="Nombre de carpeta (AnalystVideoFolder).")
        parser.add_argument(
            "--source",
            default=RivalVideo.SOURCE_MANUAL,
            choices=[c[0] for c in RivalVideo.SOURCE_CHOICES],
            help="Fuente (manual/rfaf/preferente/universo/youtube).",
        )
        parser.add_argument("--notes", default="", help="Notas iniciales.")
        parser.add_argument("--created-by", default="import_cmd", help="created_by (texto).")
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada; solo valida y muestra metadata.")
        parser.add_argument(
            "--transcode",
            default="auto",
            choices=["auto", "on", "off"],
            help="Transcodificar a H.264/AAC para compatibilidad (auto=si no es h264).",
        )
        parser.add_argument("--height", type=int, default=720, help="Alto objetivo al transcodificar (0 = mantener).")
        parser.add_argument("--fps", type=int, default=30, help="FPS objetivo al transcodificar (0 = mantener).")
        parser.add_argument("--crf", type=int, default=23, help="CRF para libx264 (más bajo = más calidad).")
        parser.add_argument("--preset", default="veryfast", help="Preset libx264 (ultrafast..veryslow).")
        parser.add_argument("--autocut", action="store_true", help="Lanza AutoCut tras importar (best-effort).")

    def handle(self, *args, **options):
        src_path = Path(str(options["mp4_path"])).expanduser().resolve()
        if not src_path.exists():
            raise CommandError(f"No existe: {src_path}")
        if src_path.is_dir():
            raise CommandError(f"Es un directorio: {src_path}")

        team_id = int(options.get("team_id") or 0)
        rival_team_id = int(options.get("rival_team_id") or 0)
        title = str(options.get("title") or "").strip()
        folder_name = str(options.get("folder") or "").strip()
        source = str(options.get("source") or RivalVideo.SOURCE_MANUAL).strip()
        notes = str(options.get("notes") or "").strip()
        created_by = str(options.get("created_by") or "import_cmd").strip()[:80]
        dry_run = bool(options.get("dry_run"))
        transcode_mode = str(options.get("transcode") or "auto").strip().lower()
        height = int(options.get("height") or 0)
        fps = int(options.get("fps") or 0)
        crf = int(options.get("crf") or 23)
        preset = str(options.get("preset") or "veryfast").strip()
        do_autocut = bool(options.get("autocut"))

        team = (
            Team.objects.filter(id=team_id).first()
            if team_id
            else Team.objects.filter(is_primary=True).order_by("id").first()
        )
        if not team:
            raise CommandError("No se encontró equipo destino. Usa --team-id.")
        rival_team = Team.objects.filter(id=rival_team_id).first() if rival_team_id else None

        resolved_title = (title or src_path.stem).strip()[:180] or "Vídeo rival"
        vcodec = _ffprobe_video_codec(str(src_path))
        duration = _ffprobe_duration_seconds(str(src_path))

        wants_transcode = False
        if transcode_mode == "on":
            wants_transcode = True
        elif transcode_mode == "off":
            wants_transcode = False
        else:
            wants_transcode = bool(vcodec and vcodec.lower() != "h264")

        info = {
            "src": str(src_path),
            "title": resolved_title,
            "team_id": int(team.id),
            "rival_team_id": int(rival_team.id) if rival_team else 0,
            "folder": folder_name,
            "source": source,
            "vcodec": vcodec or "",
            "duration_s": float(duration or 0.0),
            "transcode": wants_transcode,
            "transcode_params": {"height": height, "fps": fps, "crf": crf, "preset": preset},
            "autocut": do_autocut,
        }
        self.stdout.write(json.dumps(info, ensure_ascii=False, indent=2))

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: no se guardará nada."))
            return

        folder = None
        if folder_name:
            folder, _created = AnalystVideoFolder.objects.get_or_create(
                team=team,
                rival_team=rival_team,
                name=folder_name[:140],
                defaults={"created_by": created_by},
            )

        tmp_out_path = None
        final_path = src_path
        try:
            if wants_transcode:
                tmp_out = tempfile.NamedTemporaryFile(prefix="2j-import-video-", suffix=".mp4", delete=False)
                tmp_out_path = Path(tmp_out.name)
                tmp_out.close()
                self.stdout.write(self.style.WARNING("Transcodificando a H.264/AAC (puede tardar)..."))
                _transcode_to_h264_aac(
                    input_path=str(src_path),
                    output_path=str(tmp_out_path),
                    height=height,
                    fps=fps,
                    crf=crf,
                    preset=preset,
                )
                final_path = tmp_out_path

            with transaction.atomic():
                entry = RivalVideo.objects.create(
                    team=team,
                    rival_team=rival_team,
                    folder=folder,
                    title=resolved_title,
                    source=source if source in {c[0] for c in RivalVideo.SOURCE_CHOICES} else RivalVideo.SOURCE_MANUAL,
                    notes=notes[:4000],
                )
                with open(final_path, "rb") as fh:
                    upload = File(fh, name=f"{src_path.stem}.mp4")
                    entry.video.save(upload.name, upload, save=True)

                if do_autocut:
                    try:
                        from football.views import _video_studio_schedule_autocut_after_upload  # noqa: WPS433

                        _video_studio_schedule_autocut_after_upload(
                            video_id=int(entry.id),
                            team_id=int(team.id),
                            owner_user_id=None,
                            created_by=created_by,
                        )
                    except Exception:
                        self.stdout.write(self.style.WARNING("AutoCut no se pudo lanzar (se ignora)."))

            self.stdout.write(self.style.SUCCESS(f"OK importado RivalVideo.id={entry.id}"))
        finally:
            if tmp_out_path is not None:
                try:
                    tmp_out_path.unlink(missing_ok=True)
                except Exception:
                    pass

