from datetime import date

from django.db.models import Q


INBOX_MICROCYCLE_WEEK_START = date(2000, 1, 1)
INBOX_MICROCYCLE_WEEK_END = date(2099, 12, 31)
INBOX_MICROCYCLE_TITLE = 'Sesiones sueltas (sin microciclo)'

LIBRARY_MICROCYCLE_MARKER = '[2J_LIBRARY_MICROCYCLE]'
TRASH_MICROCYCLE_WEEK_START = date(1970, 1, 1)
TRASH_MICROCYCLE_WEEK_END = date(1970, 1, 7)
TRASH_MICROCYCLE_TITLE = 'Papelera (sistema)'
TRASH_MICROCYCLE_MARKER = '[2J_TRASH_MICROCYCLE]'
TRASH_SESSION_REASON_PREFIX = '[2J_TRASH_SESSION]'

LIBRARY_REPOSITORY_TRADITIONAL = 'traditional'
LIBRARY_REPOSITORY_INTERACTIVE = 'interactive'
LIBRARY_REPOSITORY_AI_TRAINER = 'ai_trainer'
LIBRARY_REPOSITORY_CHOICES = {
    LIBRARY_REPOSITORY_TRADITIONAL,
    LIBRARY_REPOSITORY_INTERACTIVE,
    LIBRARY_REPOSITORY_AI_TRAINER,
}


def normalize_library_repository(value, *, fallback=LIBRARY_REPOSITORY_TRADITIONAL):
    raw = str(value or '').strip().lower()
    if raw in {'tradicional', 'tradicionales', 'pdf'}:
        return LIBRARY_REPOSITORY_TRADITIONAL
    if raw in {'interactiva', 'interactivas'}:
        return LIBRARY_REPOSITORY_INTERACTIVE
    if raw in {'ia', 'ai', 'iatrainer', 'ia-trainer', 'ia_trainer'}:
        return LIBRARY_REPOSITORY_AI_TRAINER
    if raw in LIBRARY_REPOSITORY_CHOICES:
        return raw
    return fallback


def is_library_microcycle(microcycle):
    if not microcycle:
        return False
    try:
        notes = str(getattr(microcycle, 'notes', '') or '')
        if LIBRARY_MICROCYCLE_MARKER in notes:
            return True
        if 'microciclo tecnico generado automaticamente para biblioteca' in notes.lower():
            return True
        objective = str(getattr(microcycle, 'objective', '') or '')
        if objective.strip().lower() == 'repositorio de tareas en pdf':
            return True
        title = str(getattr(microcycle, 'title', '') or '')
        if title.strip().lower().startswith('biblioteca '):
            return True
        return False
    except Exception:
        return False


def is_library_session(session):
    if not session:
        return False
    try:
        return is_library_microcycle(getattr(session, 'microcycle', None))
    except Exception:
        return False


def exclude_library_sessions_qs(qs):
    try:
        return qs.exclude(
            Q(microcycle__notes__icontains=LIBRARY_MICROCYCLE_MARKER)
            | Q(microcycle__notes__icontains='microciclo tecnico generado automaticamente para biblioteca')
            | Q(microcycle__objective__iexact='Repositorio de tareas en pdf')
            | Q(microcycle__title__istartswith='Biblioteca ')
            | Q(microcycle__week_start=TRASH_MICROCYCLE_WEEK_START)
            | Q(microcycle__notes__icontains=TRASH_MICROCYCLE_MARKER)
            | Q(microcycle__title__istartswith='Papelera')
        )
    except Exception:
        return qs


def library_repository_for_session(session):
    if not session:
        return LIBRARY_REPOSITORY_TRADITIONAL
    focus = str(getattr(session, 'focus', '') or '').strip().lower()
    if 'biblioteca interactiva' in focus:
        return LIBRARY_REPOSITORY_INTERACTIVE
    if 'biblioteca ia' in focus or 'biblioteca ai' in focus:
        return LIBRARY_REPOSITORY_AI_TRAINER
    return LIBRARY_REPOSITORY_TRADITIONAL


def library_repository_for_task(task):
    if not task:
        return LIBRARY_REPOSITORY_TRADITIONAL
    try:
        layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        raw_repo = meta.get('repository') or meta.get('library_repo') or meta.get('library_repository')
        repo = normalize_library_repository(raw_repo, fallback='')
        if repo in LIBRARY_REPOSITORY_CHOICES:
            return repo
    except Exception:
        pass
    return library_repository_for_session(getattr(task, 'session', None))
