from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.text import slugify

from football.models import Player, Team
from football.views import save_player_license


def _which(cmd: str) -> bool:
    return bool(shutil.which(cmd))


def _run_capture(args: list[str]) -> str:
    try:
        out = subprocess.check_output(args, stderr=subprocess.STDOUT)
        return out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as exc:
        raw = (exc.output or b"").decode("utf-8", errors="replace")
        raise CommandError(f"Error ejecutando: {' '.join(args)}\n{raw}") from exc


_FIELD_RE = {
    "nombre": re.compile(r"^Nombre:\s*(?P<val>.+?)\s*$", re.MULTILINE | re.IGNORECASE),
    "apellido1": re.compile(r"^Apellido\s*1:\s*(?P<val>.+?)\s*$", re.MULTILINE | re.IGNORECASE),
    "apellido2": re.compile(r"^Apellido\s*2:\s*(?P<val>.+?)\s*$", re.MULTILINE | re.IGNORECASE),
    "licencia": re.compile(r"^Código\s+de\s+Licencia:\s*(?P<val>.+?)\s*(Hasta:|$)", re.MULTILINE | re.IGNORECASE),
    "categoria": re.compile(r"^Categoría:\s*(?P<val>.+?)\s*$", re.MULTILINE | re.IGNORECASE),
    "club": re.compile(r"^Club:\s*(?P<val>.+?)\s*$", re.MULTILINE | re.IGNORECASE),
}


def _extract_fields(text: str) -> dict:
    payload: dict[str, str] = {}
    for key, regex in _FIELD_RE.items():
        match = regex.search(text or "")
        if match:
            payload[key] = str(match.group("val") or "").strip()
    return payload


def _normalize_person_key(nombre: str, apellido1: str, apellido2: str) -> str:
    return slugify(" ".join([nombre or "", apellido1 or "", apellido2 or ""]).strip())


def _player_keys(player: Player) -> set[str]:
    keys: set[str] = set()
    if not player:
        return keys
    for raw in [getattr(player, "full_name", ""), getattr(player, "name", "")]:
        raw = str(raw or "").strip()
        if raw:
            keys.add(slugify(raw))
    return {key for key in keys if key}


def _score_match(candidate_key: str, player_keys: set[str]) -> float:
    if not candidate_key or not player_keys:
        return 0.0
    best = 0.0
    for pk in player_keys:
        if not pk:
            continue
        if pk == candidate_key:
            return 1.0
        best = max(best, SequenceMatcher(a=candidate_key, b=pk).ratio())
    return best


@dataclass(frozen=True)
class PageMatch:
    page_index: int
    person_key: str
    nombre: str
    apellido1: str
    apellido2: str
    licencia_code: str
    categoria: str
    club: str
    best_player_id: int | None
    best_player_name: str
    best_score: float


class Command(BaseCommand):
    help = "Importa licencias federativas desde un PDF multi‑página y las asigna a jugadores por nombre."

    def add_arguments(self, parser):
        parser.add_argument("--pdf", type=str, required=True, help="Ruta al PDF con licencias (una por página).")
        parser.add_argument("--team-id", type=int, default=0, help="ID del equipo (recomendado).")
        parser.add_argument("--team-slug", type=str, default="", help="Slug del equipo (alternativa a --team-id).")
        parser.add_argument("--min-score", type=float, default=0.82, help="Umbral mínimo de matching (0-1).")
        parser.add_argument("--apply", action="store_true", help="Aplica cambios y guarda licencias en MEDIA.")
        parser.add_argument("--dry-run", action="store_true", help="Solo muestra el mapeo propuesto (por defecto).")
        parser.add_argument("--out-json", type=str, default="", help="Escribe un resumen JSON en esta ruta.")
        parser.add_argument("--limit", type=int, default=0, help="Procesa solo las primeras N páginas (0=all).")

    def handle(self, *args, **opts):
        pdf_path = Path(str(opts["pdf"])).expanduser()
        if not pdf_path.exists() or not pdf_path.is_file():
            raise CommandError(f"PDF no encontrado: {pdf_path}")

        team_id = int(opts.get("team_id") or 0)
        team_slug = str(opts.get("team_slug") or "").strip()
        if not team_id and not team_slug:
            raise CommandError("Indica el equipo con --team-id o --team-slug para evitar asignaciones erróneas.")

        team = None
        if team_id:
            team = Team.objects.filter(id=team_id).first()
        if not team and team_slug:
            team = Team.objects.filter(slug=team_slug).first()
        if not team:
            raise CommandError("Equipo no encontrado.")

        players = list(Player.objects.filter(team=team).order_by("name", "id"))
        if not players:
            raise CommandError("El equipo no tiene jugadores.")

        min_score = float(opts.get("min_score") or 0.82)
        apply_changes = bool(opts.get("apply"))
        dry_run = bool(opts.get("dry_run")) or (not apply_changes)
        limit_pages = int(opts.get("limit") or 0)

        if not _which("pdfseparate") or not _which("pdftotext"):
            raise CommandError("Faltan binarios `pdfseparate`/`pdftotext` (poppler-utils).")

        player_index: list[tuple[Player, set[str]]] = [(p, _player_keys(p)) for p in players]

        matches: list[PageMatch] = []
        errors: list[str] = []
        assigned = 0
        skipped = 0

        with tempfile.TemporaryDirectory(prefix="licenses-pdf-") as tmpdir:
            tmpdir_path = Path(tmpdir)
            pattern = tmpdir_path / "page-%d.pdf"
            _run_capture(["pdfseparate", str(pdf_path), str(pattern)])

            pages = sorted(tmpdir_path.glob("page-*.pdf"))
            if limit_pages > 0:
                pages = pages[: max(0, limit_pages)]

            for idx, page_file in enumerate(pages, start=1):
                try:
                    text = _run_capture(["pdftotext", "-f", "1", "-l", "1", str(page_file), "-"])
                except CommandError as exc:
                    errors.append(f"page {idx}: pdftotext error: {exc}")
                    continue

                fields = _extract_fields(text)
                nombre = fields.get("nombre", "")
                apellido1 = fields.get("apellido1", "")
                apellido2 = fields.get("apellido2", "")
                person_key = _normalize_person_key(nombre, apellido1, apellido2)
                licencia_code = fields.get("licencia", "")
                categoria = fields.get("categoria", "")
                club = fields.get("club", "")

                best_player = None
                best_score = 0.0
                for player_obj, keys in player_index:
                    score = _score_match(person_key, keys)
                    if score > best_score:
                        best_score = score
                        best_player = player_obj

                match = PageMatch(
                    page_index=idx,
                    person_key=person_key,
                    nombre=nombre,
                    apellido1=apellido1,
                    apellido2=apellido2,
                    licencia_code=licencia_code,
                    categoria=categoria,
                    club=club,
                    best_player_id=int(best_player.id) if best_player else None,
                    best_player_name=str(best_player.name if best_player else ""),
                    best_score=float(best_score),
                )
                matches.append(match)

                if not best_player or best_score < min_score:
                    skipped += 1
                    continue

                if dry_run:
                    continue

                try:
                    pdf_bytes = page_file.read_bytes()
                    upload = SimpleUploadedFile(
                        name=f"licencia-page-{idx}.pdf",
                        content=pdf_bytes,
                        content_type="application/pdf",
                    )
                    save_player_license(best_player, upload)
                    assigned += 1
                except Exception as exc:
                    errors.append(f"page {idx}: no se pudo guardar licencia para player_id={best_player.id}: {exc}")

        # Summary
        report = {
            "ok": True,
            "pdf": str(pdf_path),
            "team": {"id": int(team.id), "slug": team.slug, "name": team.display_name},
            "dry_run": bool(dry_run),
            "min_score": min_score,
            "pages_total": len(matches),
            "assigned": assigned,
            "skipped": skipped,
            "errors": errors,
            "matches": [
                {
                    "page": m.page_index,
                    "nombre": m.nombre,
                    "apellido1": m.apellido1,
                    "apellido2": m.apellido2,
                    "licencia_code": m.licencia_code,
                    "categoria": m.categoria,
                    "club": m.club,
                    "best_player_id": m.best_player_id,
                    "best_player_name": m.best_player_name,
                    "best_score": round(m.best_score, 3),
                }
                for m in matches
            ],
        }

        if opts.get("out_json"):
            out_path = Path(str(opts["out_json"])).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        # Console output (compact)
        self.stdout.write(self.style.SUCCESS(f"Licencias PDF procesadas: pages={len(matches)} team={team.slug} dry_run={dry_run}"))
        self.stdout.write(f"- assigned={assigned} skipped={skipped} errors={len(errors)} min_score={min_score}")
        if dry_run:
            self.stdout.write("Ejemplos de mapeo (top 12):")
            for m in matches[:12]:
                self.stdout.write(f"  - p{m.page_index:03d} {m.nombre} {m.apellido1} {m.apellido2} -> {m.best_player_name} ({m.best_score:.2f})")
        if errors:
            self.stdout.write(self.style.WARNING("Errores (primeros 8):"))
            for item in errors[:8]:
                self.stdout.write(f"  - {item}")
