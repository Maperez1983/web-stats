import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from football.models import RivalVideo, Team, VideoAiInsight, VideoClip, VideoTimelineEvent


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def _run_out(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    return str(p.stdout or "")


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


def _ocr_scorebar_image(img_path: str) -> str:
    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-:._ "
    text = _run_out(
        [
            "tesseract",
            img_path,
            "stdout",
            "-l",
            "eng",
            "--psm",
            "6",
            "-c",
            f"tessedit_char_whitelist={whitelist}",
        ]
    )
    return " ".join(str(text or "").split())


def _extract_scorebar_frame(*, video_path: str, at_seconds: float, out_path: str) -> None:
    # Crop tuned for typical broadcast overlays (top bar).
    # Marbella/Baeza (y similares): marcador en esquina superior izquierda.
    vf = "crop=800:160:0:0,scale=1280:-1"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(max(0.0, float(at_seconds))),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-vf",
            vf,
            out_path,
        ]
    )


def _guess_scoreboard_start_seconds(video_path: str) -> float:
    """
    Heurística: busca el primer minuto donde el OCR detecta un patrón tipo 'MAR 0-0 BAE 00:00'.
    """
    pattern = re.compile(r"\b[A-Z_]{2,6}\s+\d{1,2}\s*[-:]\s*\d{1,2}\s+[A-Z_]{2,6}\b", re.IGNORECASE)
    with tempfile.TemporaryDirectory(prefix="2j_score_start_") as tmp:
        for t in range(0, 1800, 60):
            out = str(Path(tmp) / f"probe_{t}.png")
            try:
                _extract_scorebar_frame(video_path=video_path, at_seconds=float(t), out_path=out)
                text = _ocr_scorebar_image(out)
                if pattern.search(text):
                    return max(0.0, float(t) - 30.0)
            except Exception:
                continue
    return 0.0


def _input_hash_for_file(path: str) -> str:
    p = Path(path)
    try:
        st = p.stat()
        raw = f"{p.name}|{st.st_size}|{int(st.st_mtime)}"
    except Exception:
        raw = p.name
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ScoreSample:
    video_t: float
    a: Optional[str] = None
    b: Optional[str] = None
    ascore: Optional[int] = None
    bscore: Optional[int] = None
    mm: Optional[int] = None
    ss: Optional[int] = None
    raw: str = ""


def _parse_score_text(text: str) -> ScoreSample:
    # Tolerant format: MAR_ 0-0 BAE 04:25 (OCR can add underscores/dots).
    line_re = re.compile(
        r"(?P<a>[A-Z_]{2,6})\s+(?P<ascore>\d{1,2})\s*[-:]\s*(?P<bscore>\d{1,2})\s+(?P<b>[A-Z_]{2,6}).*?(?P<mm>\d{1,2})\s*[:.]\s*(?P<ss>\d{2})",
        re.IGNORECASE,
    )
    m = line_re.search(text or "")
    if not m:
        return ScoreSample(video_t=0.0, raw=text or "")
    try:
        return ScoreSample(
            video_t=0.0,
            a=str(m.group("a") or "").replace("_", "").upper(),
            b=str(m.group("b") or "").replace("_", "").upper(),
            ascore=int(m.group("ascore")),
            bscore=int(m.group("bscore")),
            mm=int(m.group("mm")),
            ss=int(m.group("ss")),
            raw=text or "",
        )
    except Exception:
        return ScoreSample(video_t=0.0, raw=text or "")


def _extract_score_samples(*, video_path: str, start: float, interval: float, max_seconds: float = 0.0) -> list[ScoreSample]:
    """
    Extrae samples OCR del marcador cada `interval` segundos, empezando en `start`.
    """
    duration = _ffprobe_duration_seconds(video_path) or 0.0
    if duration <= 0:
        raise CommandError("No se pudo obtener la duración del vídeo con ffprobe.")
    end = float(duration)
    if max_seconds and max_seconds > 0:
        end = min(end, float(start) + float(max_seconds))

    samples: list[ScoreSample] = []
    with tempfile.TemporaryDirectory(prefix="2j_score_ocr_") as tmp:
        idx = 0
        t = float(start)
        while t < end:
            idx += 1
            img = str(Path(tmp) / f"score_{idx:06d}.png")
            try:
                _extract_scorebar_frame(video_path=video_path, at_seconds=t, out_path=img)
                txt = _ocr_scorebar_image(img)
            except Exception:
                txt = ""
            s = _parse_score_text(txt)
            s.video_t = float(t)
            samples.append(s)
            t += float(interval)
    return samples


def _stable_goal_events(samples: list[ScoreSample]) -> list[dict]:
    """
    Devuelve eventos de gol estables (filtra glitches OCR).

    Criterio:
    - cambio de marcador válido = +1 en uno de los dos equipos
    - exige 2 samples seguidos con el nuevo marcador antes de aceptarlo
    - aplica smoothing por mayoría en ventana de 3 (más reactivo con OCR intermitente)
    """
    parsed = [
        s
        for s in samples
        if s.ascore is not None and s.bscore is not None and s.mm is not None and s.ss is not None
    ]
    if not parsed:
        return []

    window: list[tuple[int, int]] = []
    smoothed: list[tuple[ScoreSample, tuple[int, int]]] = []
    for s in parsed:
        window.append((int(s.ascore or 0), int(s.bscore or 0)))
        window = window[-3:]
        best = Counter(window).most_common(1)[0][0]
        smoothed.append((s, best))

    stable_events: list[dict] = []
    cur_score = smoothed[0][1]
    pending: Optional[tuple[tuple[int, int], int, ScoreSample]] = None  # (score, run_len, sample)

    for s, score in smoothed[1:]:
        if score == cur_score:
            pending = None
            continue
        if pending and pending[0] == score:
            pending = (score, pending[1] + 1, s)
        else:
            pending = (score, 1, s)

        if pending[1] >= 2:
            prev = cur_score
            cur = pending[0]
            da = cur[0] - prev[0]
            db = cur[1] - prev[1]
            if da >= 0 and db >= 0 and (da + db) == 1:
                stable_events.append(
                    {
                        "video_t": float(pending[2].video_t),
                        "match_clock": f"{int(pending[2].mm or 0):02d}:{int(pending[2].ss or 0):02d}",
                        "score_prev": [int(prev[0]), int(prev[1])],
                        "score_new": [int(cur[0]), int(cur[1])],
                        "teams": {"a": pending[2].a or "", "b": pending[2].b or ""},
                        "raw": str(pending[2].raw or ""),
                    }
                )
            cur_score = cur
            pending = None

    return stable_events


class Command(BaseCommand):
    help = "Genera eventos/clips a partir del marcador (OCR) en un MP4 y los guarda en el sistema."

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, required=True)
        parser.add_argument("--video-id", type=int, default=0, help="Si existe RivalVideo, lo usa y no crea uno nuevo.")
        parser.add_argument("--video-path", type=str, default="", help="Ruta a MP4 local para crear RivalVideo y analizar.")
        parser.add_argument("--title", type=str, default="")
        parser.add_argument("--rival-team-id", type=int, default=0)
        parser.add_argument("--start", type=float, default=-1.0, help="Segundo donde empieza el marcador (auto si -1).")
        parser.add_argument("--interval", type=float, default=15.0, help="OCR cada N segundos.")
        parser.add_argument("--max-seconds", type=float, default=0.0, help="Limita análisis a N segundos (0=todo).")
        parser.add_argument("--create-clips", action="store_true", help="Crea clips IN/OUT alrededor de cada gol detectado.")
        parser.add_argument("--clip-pre", type=float, default=30.0, help="Segundos antes del gol para IN.")
        parser.add_argument("--clip-post", type=float, default=20.0, help="Segundos después del gol para OUT.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        team_id = int(opts["team_id"])
        video_id = int(opts.get("video_id") or 0)
        video_path = str(opts.get("video_path") or "").strip()
        title = str(opts.get("title") or "").strip()
        rival_team_id = int(opts.get("rival_team_id") or 0)
        start = float(opts.get("start") if opts.get("start") is not None else -1.0)
        interval = float(opts.get("interval") or 15.0)
        max_seconds = float(opts.get("max_seconds") or 0.0)
        create_clips = bool(opts.get("create_clips"))
        clip_pre = float(opts.get("clip_pre") or 30.0)
        clip_post = float(opts.get("clip_post") or 20.0)
        dry_run = bool(opts.get("dry_run"))

        team = Team.objects.filter(id=team_id).first()
        if not team:
            raise CommandError(f"No existe Team id={team_id}")
        rival_team = Team.objects.filter(id=rival_team_id).first() if rival_team_id else None

        video: Optional[RivalVideo] = None
        if video_id:
            video = RivalVideo.objects.filter(id=video_id).first()
            if not video:
                raise CommandError(f"No existe RivalVideo id={video_id}")
            if not video.video:
                raise CommandError("El RivalVideo no tiene archivo asociado (campo video vacío).")
            video_path = str(video.video.path)
            if not title:
                title = str(video.title or "").strip()
        else:
            if not video_path:
                raise CommandError("Debes pasar --video-id o --video-path.")
            if not Path(video_path).exists():
                raise CommandError(f"No existe el archivo: {video_path}")
            if not title:
                title = Path(video_path).stem[:180]

        if start < 0:
            self.stdout.write("Detectando inicio de marcador (auto)…")
            start = _guess_scoreboard_start_seconds(video_path)
        start = max(0.0, start)

        self.stdout.write(f"Analizando OCR: start={start:.1f}s interval={interval:.1f}s…")
        samples = _extract_score_samples(video_path=video_path, start=start, interval=interval, max_seconds=max_seconds)
        events = _stable_goal_events(samples)

        parsed_count = sum(1 for s in samples if s.ascore is not None)
        self.stdout.write(f"samples={len(samples)} parsed={parsed_count} goals_detected={len(events)}")
        for ev in events[:12]:
            self.stdout.write(
                f"- t={ev['video_t']:.0f}s match={ev['match_clock']} score {ev['score_prev'][0]}-{ev['score_prev'][1]} -> {ev['score_new'][0]}-{ev['score_new'][1]}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se guardó nada."))
            return

        # Crea RivalVideo si no existía.
        if not video:
            self.stdout.write("Creando RivalVideo…")
            video = RivalVideo(
                team=team,
                rival_team=rival_team,
                title=title[:180],
                source=RivalVideo.SOURCE_MANUAL,
                notes="Importado desde MP4 local (OCR).",
            )
            with open(video_path, "rb") as f:
                video.video.save(Path(video_path).name, File(f), save=False)
            video.save()

        input_hash = _input_hash_for_file(video_path)
        insight_payload = {
            "provider": "heuristic",
            "kind": "scoreboard_ocr_v1",
            "start_seconds": start,
            "interval_seconds": interval,
            "events": events,
            "generated_at": timezone.now().isoformat(),
        }
        VideoAiInsight.objects.update_or_create(
            team=team,
            video=video,
            input_hash=input_hash,
            defaults={
                "status": VideoAiInsight.STATUS_OK,
                "provider": "heuristic",
                "model": "scoreboard_ocr_v1",
                "payload": insight_payload,
                "error": "",
                "created_by": "seed_video_ocr",
            },
        )

        created_events = 0
        created_clips = 0
        for ev in events:
            t_ms = int(max(0.0, float(ev.get("video_t") or 0.0)) * 1000.0)
            label = f"Gol {ev['score_new'][0]}-{ev['score_new'][1]}"

            # Idempotencia simple: evita duplicados si se re-ejecuta.
            exists = VideoTimelineEvent.objects.filter(video=video, team=team, kind=VideoTimelineEvent.KIND_GOAL, time_ms=t_ms).exists()
            if not exists:
                VideoTimelineEvent.objects.create(
                    team=team,
                    video=video,
                    time_ms=t_ms,
                    kind=VideoTimelineEvent.KIND_GOAL,
                    label=label[:160],
                    color="#f59e0b",
                    payload={
                        "match_clock": ev.get("match_clock") or "",
                        "score_prev": ev.get("score_prev") or [],
                        "score_new": ev.get("score_new") or [],
                        "teams": ev.get("teams") or {},
                    },
                    created_by="seed_video_ocr",
                )
                created_events += 1

            if create_clips:
                in_ms = max(0, int(t_ms - (clip_pre * 1000.0)))
                out_ms = max(in_ms + 5000, int(t_ms + (clip_post * 1000.0)))
                clip_exists = VideoClip.objects.filter(video=video, team=team, in_ms=in_ms, out_ms=out_ms, collection="Goles").exists()
                if not clip_exists:
                    VideoClip.objects.create(
                        team=team,
                        video=video,
                        title=label[:180],
                        collection="Goles",
                        in_ms=int(in_ms),
                        out_ms=int(out_ms),
                        tags=["goal"],
                        notes=f"Auto desde OCR · {ev.get('match_clock') or ''}",
                        created_by="seed_video_ocr",
                    )
                    created_clips += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"OK: RivalVideo #{video.id} · timeline_events +{created_events} · clips +{created_clips}"
            )
        )
