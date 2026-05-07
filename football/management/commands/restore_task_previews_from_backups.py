import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from football.models import SessionTask, TaskStudioTask

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None


def _md5(raw: bytes) -> str:
    return hashlib.md5(raw or b"", usedforsecurity=False).hexdigest()


def _build_default_fallback_hashes() -> set[str]:
    """
    Hashes del payload que se guarda cuando no hay preview y se usa el placeholder (campo vacío).
    Importante: replica el re-encode (thumbnail + quality) de `_default_task_preview_payload`.
    """
    candidates = [
        Path(settings.BASE_DIR) / "static" / "football" / "campo-futbol-fallback.jpg",
        Path(settings.BASE_DIR) / "static" / "football" / "campo-futbol.jpg",
    ]
    src = next((p for p in candidates if p.exists() and p.is_file()), None)
    if not src:
        return set()
    raw = src.read_bytes()
    hashes = {_md5(raw)}
    if Image is None:
        return hashes
    try:
        import io

        with Image.open(io.BytesIO(raw)) as img:
            normalized = img.convert("RGB")
            normalized.thumbnail((1200, 850))
            out = io.BytesIO()
            normalized.save(out, format="JPEG", quality=74, optimize=True)
            hashes.add(_md5(out.getvalue()))
    except Exception:
        pass
    return hashes


def _looks_like_image(raw: bytes) -> bool:
    if not raw:
        return False
    # Quick header checks.
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if raw.startswith(b"\xff\xd8\xff"):
        return True
    if raw[:4] == b"RIFF" and b"WEBP" in raw[:16]:
        return True
    if Image is None:
        return True
    try:
        import io

        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        return True
    except Exception:
        return False


def _looks_like_pitch_only_preview(raw: bytes) -> bool:
    """
    Detecta previews "solo césped" (sin overlay) aunque no coincidan exactamente con el JPG placeholder.

    Heurística conservadora: casi todo verde/blanco y muy poco "otro" color.
    """
    if Image is None or not raw:
        return False
    try:
        import io

        with Image.open(io.BytesIO(raw)) as img:
            rgb = img.convert("RGB")
            sample = rgb.copy()
            sample.thumbnail((128, 128))
            pixels = list(sample.getdata())
            total = max(1, len(pixels))
            greenish = 0
            whitish = 0
            darkish = 0
            other = 0
            for r, g, b in pixels:
                if g > 70 and g > (r + 14) and g > (b + 10):
                    greenish += 1
                elif r > 232 and g > 232 and b > 232:
                    whitish += 1
                elif r < 30 and g < 30 and b < 30:
                    darkish += 1
                else:
                    other += 1
            green_ratio = greenish / total
            white_ratio = whitish / total
            dark_ratio = darkish / total
            other_ratio = other / total
            return (
                green_ratio >= 0.70
                and other_ratio <= 0.06
                and white_ratio <= 0.38
                and dark_ratio <= 0.55
            )
    except Exception:
        return False


def _load_backup_candidates(kind: str, task_id: int) -> list[dict]:
    prefix = f"backups/tasks/{kind}/{task_id}"
    try:
        _dirs, files = default_storage.listdir(prefix)
    except Exception:
        return []
    files = [f for f in files if str(f).endswith(".json")]
    # Más reciente primero (el nombre incluye timestamp).
    files = sorted(files, reverse=True)
    out: list[dict] = []
    for name in files:
        path = f"{prefix}/{name}".strip("/")
        try:
            with default_storage.open(path, "rb") as handle:
                payload = json.loads(handle.read().decode("utf-8"))
            if isinstance(payload, dict):
                out.append(payload)
        except Exception:
            continue
    return out


def _extract_preview_names_from_backup_payload(payload: dict) -> list[str]:
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    preview = str(task.get("task_preview_image") or "").strip()
    if preview:
        return [preview]
    # Fallback: algunos snapshots guardan `meta.original_version.task_preview_image`.
    layout = task.get("tactical_layout") if isinstance(task.get("tactical_layout"), dict) else {}
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    original = meta.get("original_version") if isinstance(meta.get("original_version"), dict) else {}
    preview2 = str(original.get("task_preview_image") or "").strip()
    return [preview2] if preview2 else []


def _extract_preview_name_from_original_version(obj) -> str:
    try:
        layout = obj.tactical_layout if isinstance(getattr(obj, "tactical_layout", None), dict) else {}
        meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
        original = meta.get("original_version") if isinstance(meta.get("original_version"), dict) else {}
        return str(original.get("task_preview_image") or "").strip()
    except Exception:
        return ""


class Command(BaseCommand):
    help = (
        "Restaura previews de tareas desde backups JSON (default_storage/backups/tasks/*) "
        "cuando la preview actual coincide con el placeholder (campo vacío)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--only", choices=["all", "sessions", "task_studio"], default="all")
        parser.add_argument("--task-id", type=int, default=0, help="Procesa solo este ID (según --only).")
        parser.add_argument("--dry-run", action="store_true", help="No guarda cambios, solo informa.")
        parser.add_argument("--limit", type=int, default=0, help="Límite de tareas a procesar (0 = sin límite).")
        parser.add_argument(
            "--also-pitch-only",
            action="store_true",
            help="Trata como placeholder previews que parecen 'solo césped' aunque no coincidan por hash.",
        )

    def handle(self, *args, **options):
        only = str(options.get("only") or "all").strip()
        task_id = int(options.get("task_id") or 0)
        dry_run = bool(options.get("dry_run"))
        limit = int(options.get("limit") or 0)
        also_pitch_only = bool(options.get("also_pitch_only"))

        fallback_hashes = _build_default_fallback_hashes()
        if not fallback_hashes:
            self.stdout.write(self.style.WARNING("No se pudo calcular el hash del placeholder (campo vacío)."))

        def iter_targets():
            if only in {"all", "sessions"}:
                qs = SessionTask.objects.order_by("id")
                if task_id:
                    qs = qs.filter(id=task_id)
                for obj in qs:
                    yield "session_task", obj
            if only in {"all", "task_studio"}:
                qs = TaskStudioTask.objects.order_by("id")
                if task_id:
                    qs = qs.filter(id=task_id)
                for obj in qs:
                    yield "task_studio_task", obj

        restored = 0
        scanned = 0
        skipped = 0
        for kind, obj in iter_targets():
            scanned += 1
            if limit and scanned > limit:
                break

            current_name = str(getattr(getattr(obj, "task_preview_image", None), "name", "") or "").strip()
            if not current_name:
                skipped += 1
                continue

            try:
                with default_storage.open(current_name, "rb") as handle:
                    current_raw = handle.read()
            except Exception:
                current_raw = b""

            current_hash = _md5(current_raw) if current_raw else ""
            is_placeholder = bool(fallback_hashes and current_hash in fallback_hashes)
            # También tratamos como "placeholder" previews inválidas (incluye el sentinel de tests).
            if not is_placeholder:
                if not _looks_like_image(current_raw):
                    is_placeholder = True
                if current_raw == b"preview-image":
                    is_placeholder = True
                if also_pitch_only and _looks_like_pitch_only_preview(current_raw):
                    is_placeholder = True

            if not is_placeholder:
                skipped += 1
                continue

            # 1) Si existe `meta.original_version.task_preview_image`, priorízalo.
            candidate_names: list[str] = []
            ov = _extract_preview_name_from_original_version(obj)
            if ov:
                candidate_names.append(ov)

            # 2) Backups JSON (más recientes primero).
            for payload in _load_backup_candidates(kind, int(getattr(obj, "id", 0) or 0)):
                candidate_names.extend(_extract_preview_names_from_backup_payload(payload))

            # Normaliza y elimina duplicados manteniendo orden.
            seen = set()
            normalized_candidates: list[str] = []
            for name in candidate_names:
                name = str(name or "").strip()
                if not name or name == current_name or name in seen:
                    continue
                seen.add(name)
                normalized_candidates.append(name)

            chosen = ""
            for name in normalized_candidates:
                try:
                    if not default_storage.exists(name):
                        continue
                    with default_storage.open(name, "rb") as handle:
                        raw = handle.read()
                    if not raw or raw == b"preview-image":
                        continue
                    if fallback_hashes and _md5(raw) in fallback_hashes:
                        continue
                    if not _looks_like_image(raw):
                        continue
                    chosen = name
                    break
                except Exception:
                    continue

            if not chosen:
                continue

            self.stdout.write(f"- #{obj.id} {kind}: {current_name}  ->  {chosen}")
            if dry_run:
                continue

            try:
                obj.task_preview_image = chosen
                obj.save(update_fields=["task_preview_image"])
                restored += 1
            except Exception as exc:  # pragma: no cover
                self.stdout.write(self.style.WARNING(f"  ! No se pudo restaurar #{obj.id}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Restore previews: restored={restored} scanned={scanned} skipped={skipped} dry_run={dry_run}"
            )
        )
