import re
from datetime import datetime, time, timedelta

from django.db.models import Max
from django.utils.module_loading import import_string
from django.utils import timezone

from .library_repositories import (
    INBOX_MICROCYCLE_TITLE,
    INBOX_MICROCYCLE_WEEK_END,
    INBOX_MICROCYCLE_WEEK_START,
    LIBRARY_REPOSITORY_TRADITIONAL,
)
from .models import SessionTask, TrainingMicrocycle
from .session_plan_fields import serialize_session_plan_fields
from .task_library_services import ensure_library_task_preview


def _views_func(name):
    return import_string(f'football.views.{name}')


def apply_analysis_to_task(*args, **kwargs):
    return _views_func('_apply_analysis_to_task')(*args, **kwargs)


def extract_pdf_text(pdf_file, max_chars=12000):
    return _views_func('_extract_pdf_text')(pdf_file, max_chars=max_chars)


def extract_preview_images_from_pdf(*args, **kwargs):
    return _views_func('_extract_preview_images_from_pdf')(*args, **kwargs)


def extract_tasks_from_pdf_text(*args, **kwargs):
    return _views_func('_extract_tasks_from_pdf_text')(*args, **kwargs)


def get_or_create_inbox_microcycle(*args, **kwargs):
    team = args[0] if args else kwargs.get('team')
    if not team:
        return None
    try:
        obj = TrainingMicrocycle.objects.filter(team=team, week_start=INBOX_MICROCYCLE_WEEK_START).first()
        if obj:
            changed = False
            if getattr(obj, 'week_end', None) != INBOX_MICROCYCLE_WEEK_END:
                obj.week_end = INBOX_MICROCYCLE_WEEK_END
                changed = True
            if str(getattr(obj, 'title', '') or '').strip() != INBOX_MICROCYCLE_TITLE:
                obj.title = INBOX_MICROCYCLE_TITLE
                changed = True
            if changed:
                try:
                    obj.save(update_fields=['title', 'week_end', 'updated_at'])
                except Exception:
                    obj.save()
            return obj
        return TrainingMicrocycle.objects.create(
            team=team,
            title=INBOX_MICROCYCLE_TITLE,
            objective='',
            week_start=INBOX_MICROCYCLE_WEEK_START,
            week_end=INBOX_MICROCYCLE_WEEK_END,
            status=TrainingMicrocycle.STATUS_DRAFT,
            notes='(Sistema) Bandeja de sesiones sueltas.',
        )
    except Exception:
        return None


def week_bounds_for_date(value):
    if not value:
        return None, None
    try:
        weekday = int(value.weekday())
    except Exception:
        return None, None
    week_start = value - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_or_create_week_microcycle(*args, **kwargs):
    team = args[0] if args else kwargs.get('team')
    session_date = args[1] if len(args) > 1 else kwargs.get('session_date')
    title_hint = kwargs.get('title_hint', '')
    if not team or not session_date:
        return None
    week_start, week_end = week_bounds_for_date(session_date)
    if not week_start or not week_end:
        return None
    try:
        existing = TrainingMicrocycle.objects.filter(team=team, week_start=week_start).first()
        if existing:
            return existing
        return TrainingMicrocycle.objects.create(
            team=team,
            title=str(title_hint or 'Microciclo semanal').strip()[:140] or 'Microciclo semanal',
            objective='',
            week_start=week_start,
            week_end=week_end,
            status=TrainingMicrocycle.STATUS_DRAFT,
            notes='(Sistema) Microciclo creado automáticamente desde sesión importada.',
        )
    except Exception:
        return None


def learn_task_blueprint_from_pdf_import(*args, **kwargs):
    return _views_func('_learn_task_blueprint_from_pdf_import')(*args, **kwargs)


def next_session_task_order(*args, **kwargs):
    session = args[0] if args else kwargs.get('session')
    return (SessionTask.objects.filter(session=session, deleted_at__isnull=True).aggregate(Max('order')).get('order__max') or 0) + 1


def parse_pdf_session_header_fields(*args, **kwargs):
    extracted_text = args[0] if args else kwargs.get('extracted_text')
    text = str(extracted_text or '')
    if not text.strip():
        return {}
    cleaned = re.sub(r'\s+', ' ', text.replace('\n', ' ')).strip()
    out = {}
    try:
        m = re.search(r'(?i)\bfecha\s*:\s*(\d{2}/\d{2}/\d{4})\b', cleaned)
        if m:
            out['date'] = datetime.strptime(m.group(1), '%d/%m/%Y').date()
    except Exception:
        pass
    try:
        m = re.search(r'(?i)\bhora\s*:\s*(\d{1,2})\s*[:h]\s*(\d{2})\b', cleaned)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                out['time'] = time(hh, mm)
    except Exception:
        pass
    for out_key, label in (('microcycle_number', 'micro'), ('mesocycle_number', 'meso')):
        try:
            m = re.search(rf'(?i)\b{label}[\s\-]*ciclo\s*:\s*(?:n[º°o]\s*)?0*(\d{{1,3}})\b', cleaned)
            if m:
                out[out_key] = int(m.group(1))
        except Exception:
            pass
    try:
        m = re.search(r'(?i)\bmd\s*:\s*([+\-]?\s*\d{1,2})\s*(?:n[º°o]\s*)?0*(\d{1,4})?\b', cleaned)
        if m:
            out['md'] = int(m.group(1).replace(' ', ''))
            if m.group(2):
                out['session_number'] = int(m.group(2))
    except Exception:
        pass
    try:
        m = re.search(r'(?i)\b(?:sesion|sesión)\s*(?:n[º°o]\s*)?0*(\d{1,4})\b', cleaned)
        if m:
            out['session_number'] = int(m.group(1))
    except Exception:
        pass
    return out


def suggest_blocks_for_session_pdf_segments(*args, **kwargs):
    return _views_func('_suggest_blocks_for_session_pdf_segments')(*args, **kwargs)


def suggest_session_plan_fields_from_pdf_text(*args, **kwargs):
    return _views_func('_suggest_session_plan_fields_from_pdf_text')(*args, **kwargs)


def get_or_create_library_session_with_repository(*args, **kwargs):
    return _views_func('_get_or_create_library_session_with_repository')(*args, **kwargs)


def import_library_tasks_from_pdf_advanced(*args, **kwargs):
    return _views_func('_import_library_tasks_from_pdf_advanced')(*args, **kwargs)
