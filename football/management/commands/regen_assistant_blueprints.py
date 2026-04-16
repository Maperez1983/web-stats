from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.utils import OperationalError

from football.models import AssistantKnowledgeDocument, TaskBlueprint, Team


class Command(BaseCommand):
    help = "Regenera TaskBlueprints a partir de los documentos OCR/PDF ya importados (AssistantKnowledgeDocument)."

    def add_arguments(self, parser):
        parser.add_argument("--team-slug", dest="team_slug", help="Slug del equipo (Team.slug).")
        parser.add_argument("--team-id", dest="team_id", type=int, help="ID del equipo (Team.id).")
        parser.add_argument(
            "--purge",
            dest="purge",
            action="store_true",
            default=False,
            help="Borra blueprints previos generados desde los docs antes de recrearlos.",
        )
        parser.add_argument(
            "--max-docs",
            dest="max_docs",
            type=int,
            default=250,
            help="Máximo de documentos a procesar.",
        )
        parser.add_argument(
            "--reextract",
            dest="reextract",
            action="store_true",
            default=False,
            help="Vuelve a extraer texto desde el fichero original antes de generar blueprints (útil si mejora el OCR).",
        )

    def handle(self, *args, **options):
        team = self._resolve_team(options)
        purge = bool(options.get("purge"))
        max_docs = int(options.get("max_docs") or 0) or 250
        reextract = bool(options.get("reextract"))

        try:
            from football import views as football_views  # noqa: WPS433
        except Exception as exc:
            raise CommandError(f"No se pudo importar football.views: {exc}") from exc

        try:
            docs = list(
                AssistantKnowledgeDocument.objects.filter(team=team, is_active=True).order_by("-created_at", "-id")[:max_docs]
            )
        except OperationalError as exc:
            raise CommandError(
                "La tabla de AssistantKnowledgeDocument no existe en la BD. Ejecuta `python manage.py migrate`."
            ) from exc

        if not docs:
            raise CommandError("No hay documentos activos para este equipo.")

        created = 0
        updated = 0
        deleted = 0
        errors = 0

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Equipo: {team.name} (slug={team.slug}, id={team.id}) · docs={len(docs)} · purge={purge} · reextract={reextract}"
            )
        )

        for idx, doc in enumerate(docs, start=1):
            self.stdout.write(f"[{idx}/{len(docs)}] doc#{doc.id} {doc.title}")
            try:
                with transaction.atomic():
                    if purge:
                        qs = TaskBlueprint.objects.filter(team=team, payload__meta__source_doc_id=int(doc.id))
                        qs = qs.filter(created_by__startswith="assistant_docs")
                        deleted += int(qs.count() or 0)
                        qs.delete()
                    if reextract:
                        try:
                            raw = b""
                            if getattr(doc, "file", None):
                                try:
                                    doc.file.open("rb")
                                except Exception:
                                    pass
                                try:
                                    raw = doc.file.read() or b""
                                except Exception:
                                    raw = b""
                                try:
                                    doc.file.close()
                                except Exception:
                                    pass
                        except Exception:
                            raw = b""
                        if raw:
                            title = str(getattr(doc, "title", "") or "")
                            mime = str(getattr(doc, "mime_type", "") or "")
                            lower = title.lower()
                            is_pdf = lower.endswith(".pdf") or mime == "application/pdf"
                            is_image = mime.startswith("image/") or lower.endswith((".png", ".jpg", ".jpeg", ".webp"))
                            extracted_text = ""
                            try:
                                if is_pdf:
                                    extracted_text = football_views._extract_pdf_text_via_pdftotext(raw)  # type: ignore[attr-defined]
                                elif is_image:
                                    extracted_text = football_views._extract_image_text_via_tesseract(raw)  # type: ignore[attr-defined]
                                else:
                                    extracted_text = raw.decode("utf-8", errors="ignore")
                            except Exception:
                                extracted_text = ""
                            min_len = 120 if is_pdf else (40 if is_image else 30)
                            if extracted_text and len(extracted_text.strip()) >= min_len:
                                doc.extracted_text = extracted_text[:500_000]
                                doc.extracted_at = football_views.timezone.now()  # type: ignore[attr-defined]
                                doc.save(update_fields=["extracted_text", "extracted_at"])
                    res = football_views._assistant_create_blueprints_from_document(team, doc)  # type: ignore[attr-defined]
                    created += int(res.get("created", 0) or 0)
                    updated += int(res.get("updated", 0) or 0)
            except Exception:
                errors += 1
                continue

        self.stdout.write(self.style.SUCCESS(f"OK · created={created} updated={updated} deleted={deleted} errors={errors}"))

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
