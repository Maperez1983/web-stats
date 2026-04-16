import mimetypes
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone

from football.models import AssistantKnowledgeDocument, Team


class Command(BaseCommand):
    help = "Importa documentos (PDF/TXT/MD/PNG/JPG/WEBP) como base de conocimiento del Asistente de tareas para un equipo."

    def add_arguments(self, parser):
        parser.add_argument("--team-slug", dest="team_slug", help="Slug del equipo (Team.slug).")
        parser.add_argument("--team-id", dest="team_id", type=int, help="ID del equipo (Team.id).")
        parser.add_argument(
            "--path",
            dest="path",
            required=True,
            help="Ruta a un fichero o carpeta (se importan PDFs/TXT/MD e imágenes PNG/JPG/WEBP).",
        )
        parser.add_argument(
            "--recursive",
            dest="recursive",
            action="store_true",
            default=False,
            help="Si --path es carpeta, busca también en subcarpetas.",
        )
        parser.add_argument(
            "--max-files",
            dest="max_files",
            type=int,
            default=200,
            help="Máximo de ficheros a procesar (evita importaciones accidentales enormes).",
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=False,
            help="Simula sin escribir en la BD ni guardar ficheros.",
        )
        parser.add_argument(
            "--skip-blueprints",
            dest="skip_blueprints",
            action="store_true",
            default=False,
            help="No genera TaskBlueprints a partir del texto extraído.",
        )
        parser.add_argument(
            "--skip-extract",
            dest="skip_extract",
            action="store_true",
            default=False,
            help="No extrae texto (solo guarda el documento).",
        )

    def handle(self, *args, **options):
        team = self._resolve_team(options)
        root = Path(str(options.get("path") or "")).expanduser()
        if not root.exists():
            raise CommandError(f"No existe la ruta: {root}")

        recursive = bool(options.get("recursive"))
        max_files = int(options.get("max_files") or 0) or 200
        dry_run = bool(options.get("dry_run"))
        skip_blueprints = bool(options.get("skip_blueprints"))
        skip_extract = bool(options.get("skip_extract"))

        allowed = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}
        paths = []
        if root.is_file():
            paths = [root]
        else:
            iterator = root.rglob("*") if recursive else root.glob("*")
            for p in iterator:
                if not p.is_file():
                    continue
                if p.suffix.lower() not in allowed:
                    continue
                paths.append(p)

        paths = sorted(paths)[:max_files]
        if not paths:
            raise CommandError("No se encontraron ficheros soportados (.pdf/.txt/.md/.png/.jpg/.jpeg/.webp) en la ruta indicada.")

        # Importamos utilidades desde `views` para reutilizar exactamente la misma lógica de extracción y blueprints.
        try:
            from football import views as football_views  # noqa: WPS433
        except Exception as exc:
            raise CommandError(f"No se pudo importar football.views: {exc}") from exc

        extracted = 0
        saved = 0
        skipped = 0
        errors = 0
        bp_created = 0
        bp_updated = 0

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Equipo: {team.name} (slug={team.slug}, id={team.id}) · ficheros={len(paths)} · dry_run={dry_run}"
            )
        )

        for idx, path in enumerate(paths, start=1):
            title = path.name[:220] or "Documento"
            self.stdout.write(f"[{idx}/{len(paths)}] {title}")

            try:
                raw = path.read_bytes()
            except Exception:
                errors += 1
                continue
            if not raw:
                errors += 1
                continue

            sha = AssistantKnowledgeDocument.sha256_for_bytes(raw)
            try:
                if AssistantKnowledgeDocument.objects.filter(team=team, sha256=sha).exists():
                    skipped += 1
                    continue
            except OperationalError as exc:
                raise CommandError(
                    "La tabla de AssistantKnowledgeDocument no existe en la BD. Ejecuta `python manage.py migrate`."
                ) from exc

            mime = mimetypes.guess_type(title)[0] or ""
            if path.suffix.lower() == ".pdf":
                mime = mime or "application/pdf"
            elif path.suffix.lower() == ".md":
                mime = mime or "text/markdown"
            elif path.suffix.lower() == ".txt":
                mime = mime or "text/plain"

            extracted_text = ""
            suffix = path.suffix.lower()
            is_pdf = suffix == ".pdf"
            is_image = suffix in {".png", ".jpg", ".jpeg", ".webp"}
            if not skip_extract:
                try:
                    if is_pdf:
                        extracted_text = football_views._extract_pdf_text_via_pdftotext(raw)  # type: ignore[attr-defined]
                    elif is_image:
                        extracted_text = football_views._extract_image_text_via_tesseract(raw)  # type: ignore[attr-defined]
                    else:
                        extracted_text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    extracted_text = ""

            if dry_run:
                saved += 1
                min_len = 120 if is_pdf else (40 if is_image else 30)
                extracted += 1 if (extracted_text and len(extracted_text.strip()) >= min_len) else 0
                continue

            with transaction.atomic():
                doc = AssistantKnowledgeDocument(team=team, title=title, sha256=sha, mime_type=mime)
                doc.file.save(Path(title).name, ContentFile(raw), save=False)
                min_len = 120 if is_pdf else (40 if is_image else 30)
                if extracted_text and len(extracted_text.strip()) >= min_len:
                    doc.extracted_text = extracted_text[:500_000]
                    doc.extracted_at = timezone.now()
                    extracted += 1
                doc.save()
                saved += 1

                if not skip_blueprints:
                    try:
                        res = football_views._assistant_create_blueprints_from_document(team, doc)  # type: ignore[attr-defined]
                        bp_created += int(res.get("created", 0) or 0)
                        bp_updated += int(res.get("updated", 0) or 0)
                    except Exception:
                        pass

        self.stdout.write(
            self.style.SUCCESS(
                f"OK · saved={saved} skipped={skipped} extracted={extracted} blueprints(created={bp_created}, updated={bp_updated}) errors={errors}"
            )
        )

    def _resolve_team(self, options):
        team_id = options.get("team_id")
        team_slug = str(options.get("team_slug") or "").strip()
        if not team_id and not team_slug:
            raise CommandError("Indica --team-id o --team-slug.")
        if team_id:
            team = Team.objects.filter(id=int(team_id)).first()
        else:
            team = Team.objects.filter(slug=team_slug).first()
        if not team:
            raise CommandError("No se encontró el equipo indicado.")
        return team
