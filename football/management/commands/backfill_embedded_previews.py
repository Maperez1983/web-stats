import io
from typing import Iterable, Tuple

from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage

from football.models import SessionTask, TaskStudioTask

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None


def _build_embedded_preview_data_url(raw_bytes: bytes, *, max_w: int = 1100, max_h: int = 1100) -> str:
    """
    Compact, DB-embeddable JPEG data URL built from PNG/JPEG/WEBP bytes.

    Motivation: some hosts (Render/free or multi-instance) can lose ImageField-backed files.
    Storing a compact copy in `tactical_layout.meta.preview_data_embedded_v1` makes cards/PDF stable.
    """
    if Image is None or not raw_bytes:
        return ""
    try:
        import base64

        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb = img.convert("RGB")
            rgb.thumbnail((max(320, int(max_w)), max(180, int(max_h))))
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=82, optimize=True, progressive=True)
            payload = base64.b64encode(out.getvalue()).decode("ascii")
            return "data:image/jpeg;base64," + payload
    except Exception:
        return ""


def _iter_targets(only: str, task_id: int) -> Iterable[Tuple[str, object]]:
    if only in {"all", "sessions"}:
        qs = SessionTask.objects.order_by("id")
        if task_id:
            qs = qs.filter(id=task_id)
        for obj in qs.iterator():
            yield "session_task", obj
    if only in {"all", "task_studio"}:
        qs = TaskStudioTask.objects.order_by("id")
        if task_id:
            qs = qs.filter(id=task_id)
        for obj in qs.iterator():
            yield "task_studio_task", obj


class Command(BaseCommand):
    help = (
        "Genera `tactical_layout.meta.preview_data_embedded_v1` a partir de `task_preview_image` "
        "para que las previews sean estables aunque el filesystem del host sea efímero."
    )

    def add_arguments(self, parser):
        parser.add_argument("--only", choices=["all", "sessions", "task_studio"], default="all")
        parser.add_argument("--task-id", type=int, default=0, help="Procesa solo este ID (según --only).")
        parser.add_argument("--dry-run", action="store_true", help="No guarda cambios, solo informa.")
        parser.add_argument("--limit", type=int, default=0, help="Límite de items a procesar (0 = sin límite).")
        parser.add_argument("--force", action="store_true", help="Sobrescribe el embedded aunque ya exista.")

    def handle(self, *args, **options):
        only = str(options.get("only") or "all").strip()
        task_id = int(options.get("task_id") or 0)
        dry_run = bool(options.get("dry_run"))
        limit = int(options.get("limit") or 0)
        force = bool(options.get("force"))

        scanned = 0
        updated = 0
        skipped = 0
        missing = 0

        for kind, obj in _iter_targets(only, task_id):
            scanned += 1
            if limit and scanned > limit:
                break

            try:
                layout = getattr(obj, "tactical_layout", None)
                layout = layout if isinstance(layout, dict) else {}
                meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
                embedded = str(meta.get("preview_data_embedded_v1") or "").strip()
                if embedded and not force:
                    skipped += 1
                    continue
            except Exception:
                skipped += 1
                continue

            field = getattr(obj, "task_preview_image", None)
            current_name = str(getattr(field, "name", "") or "").strip()
            if not current_name:
                missing += 1
                continue

            try:
                with default_storage.open(current_name, "rb") as handle:
                    raw = handle.read() or b""
            except Exception:
                missing += 1
                continue

            embedded_url = _build_embedded_preview_data_url(raw, max_w=1100, max_h=1100)
            if not embedded_url:
                skipped += 1
                continue

            self.stdout.write(f"- #{getattr(obj, 'id', '?')} {kind}: embed <= {current_name}")
            if dry_run:
                continue

            try:
                layout = getattr(obj, "tactical_layout", None)
                layout = layout if isinstance(layout, dict) else {}
                layout = dict(layout)
                meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
                meta = dict(meta) if isinstance(meta, dict) else {}
                meta["preview_data_embedded_v1"] = embedded_url
                layout["meta"] = meta
                setattr(obj, "tactical_layout", layout)
                obj.save(update_fields=["tactical_layout"])
                updated += 1
            except Exception:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill embedded previews: updated={updated} scanned={scanned} skipped={skipped} missing={missing} dry_run={dry_run}"
            )
        )

