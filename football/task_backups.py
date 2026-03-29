import json
import uuid
from dataclasses import dataclass
from typing import Optional

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone


@dataclass(frozen=True)
class BackupResult:
    path: str
    created_at: str


def _safe_task_title(task) -> str:
    title = str(getattr(task, 'title', '') or '').strip()
    return title[:160] if title else ''


def _task_backup_payload(task, *, kind: str, reason: str, actor_username: str = '') -> dict:
    # Payload minimal pero suficiente para reconstruir la tarea.
    return {
        'kind': kind,
        'reason': reason,
        'captured_at': timezone.localtime().isoformat(),
        'actor': actor_username,
        'task': {
            'id': int(getattr(task, 'id', 0) or 0),
            'title': _safe_task_title(task),
            'block': str(getattr(task, 'block', '') or ''),
            'duration_minutes': int(getattr(task, 'duration_minutes', 0) or 0),
            'objective': str(getattr(task, 'objective', '') or ''),
            'coaching_points': str(getattr(task, 'coaching_points', '') or ''),
            'confrontation_rules': str(getattr(task, 'confrontation_rules', '') or ''),
            'notes': str(getattr(task, 'notes', '') or ''),
            'status': str(getattr(task, 'status', '') or ''),
            'order': int(getattr(task, 'order', 0) or 0),
            'deleted_at': (timezone.localtime(getattr(task, 'deleted_at')) if getattr(task, 'deleted_at', None) else None).isoformat()
            if getattr(task, 'deleted_at', None)
            else None,
            'workspace_id': int(getattr(task, 'workspace_id', 0) or 0) if hasattr(task, 'workspace_id') else None,
            'owner_id': int(getattr(task, 'owner_id', 0) or 0) if hasattr(task, 'owner_id') else None,
            'session_id': int(getattr(task, 'session_id', 0) or 0) if hasattr(task, 'session_id') else None,
            'tactical_layout': getattr(task, 'tactical_layout', None),
            'task_pdf': str(getattr(getattr(task, 'task_pdf', None), 'name', '') or ''),
            'task_preview_image': str(getattr(getattr(task, 'task_preview_image', None), 'name', '') or ''),
            'updated_at': timezone.localtime(getattr(task, 'updated_at')).isoformat() if getattr(task, 'updated_at', None) else None,
            'created_at': timezone.localtime(getattr(task, 'created_at')).isoformat() if getattr(task, 'created_at', None) else None,
        },
    }


def _prune_backups(prefix: str, *, keep_last: int = 40) -> None:
    try:
        dirs, files = default_storage.listdir(prefix)
    except Exception:
        return
    if not files or len(files) <= keep_last:
        return
    # Ordena por nombre (contiene timestamp), borra los más antiguos.
    files_sorted = sorted([f for f in files if f.endswith('.json')])
    to_delete = files_sorted[: max(0, len(files_sorted) - keep_last)]
    for name in to_delete:
        try:
            default_storage.delete(f'{prefix}/{name}'.strip('/'))
        except Exception:
            pass


def write_task_backup(task, *, kind: str, reason: str = 'save', actor_username: str = '', keep_last: int = 40) -> Optional[BackupResult]:
    """
    Guarda una copia de seguridad (JSON) en el storage por defecto.

    - No requiere migraciones.
    - Funciona en local (media/) y en S3 si está configurado.
    """
    if not task or not getattr(task, 'id', None):
        return None
    safe_kind = str(kind or '').strip() or 'task'
    task_id = int(getattr(task, 'id', 0) or 0)
    if task_id <= 0:
        return None
    ts = timezone.localtime().strftime('%Y%m%dT%H%M%S')
    suffix = uuid.uuid4().hex[:8]
    prefix = f'backups/tasks/{safe_kind}/{task_id}'
    filename = f'{ts}_{reason}_{suffix}.json'
    path = f'{prefix}/{filename}'
    payload = _task_backup_payload(task, kind=safe_kind, reason=reason, actor_username=str(actor_username or '').strip())
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    try:
        default_storage.save(path, ContentFile(raw))
    except Exception:
        return None
    _prune_backups(prefix, keep_last=keep_last)
    return BackupResult(path=path, created_at=payload['captured_at'])
