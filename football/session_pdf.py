from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.utils.text import slugify

from .models import TrainingSession
from .session_plan_fields import parse_session_plan_fields, serialize_session_plan_fields
from .session_import_services import extract_pdf_text as import_extract_pdf_text
from .session_canvas_recreate import recreate_canvas_state_from_preview_image_bytes
from .view_delegates import call_view


SESSION_PDF_DELEGATED_VIEW_NAMES = (
    '_build_session_pdf_context',
)


def session_plan_pdf(request, session_id):
    from .views import (
        _build_pdf_response_or_html_fallback,
        _build_session_pdf_context,
        _can_access_sessions_workspace,
        _forbid_if_workspace_module_disabled,
    )

    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    forbidden = _forbid_if_workspace_module_disabled(request, 'sessions', label='sesiones')
    if forbidden:
        return forbidden
    session = (
        TrainingSession.objects
        .select_related('microcycle__team')
        .prefetch_related('tasks')
        .filter(id=session_id)
        .first()
    )
    if not session:
        raise Http404('Sesión no encontrada')

    pdf_style = (request.GET.get('style') or 'uefa').strip().lower()
    if pdf_style not in {'uefa', 'club', 'hybrid'}:
        pdf_style = 'uefa'
    force_pdf = str(request.GET.get('force_pdf') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    inline = str(request.GET.get('inline') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    context = _build_session_pdf_context(request, session.microcycle.team, session, pdf_style=pdf_style)
    html = render_to_string('football/session_plan_pdf.html', context)
    filename = slugify(f'sesion-{session.session_date}-{session.focus}') or f'sesion-{session.id}'
    return _build_pdf_response_or_html_fallback(request, html, filename, inline=inline, force_pdf=force_pdf)


def build_session_pdf_context(request, team, session, pdf_style='uefa'):
    return call_view('_build_session_pdf_context', request, team, session, pdf_style=pdf_style)


def extract_pdf_text(pdf_file, max_chars=12000):
    return import_extract_pdf_text(pdf_file, max_chars=max_chars)
