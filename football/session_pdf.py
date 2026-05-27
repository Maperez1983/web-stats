from .session_plan_fields import parse_session_plan_fields, serialize_session_plan_fields
from .session_import_services import extract_pdf_text as import_extract_pdf_text
from django.utils.module_loading import import_string


def _views_func(name):
    return import_string(f'football.views.{name}')


def session_plan_pdf(request, session_id):
    return _views_func('session_plan_pdf')(request, session_id=session_id)


def build_session_pdf_context(request, team, session, pdf_style='uefa'):
    return _views_func('_build_session_pdf_context')(request, team, session, pdf_style=pdf_style)


def extract_pdf_text(pdf_file, max_chars=12000):
    return import_extract_pdf_text(pdf_file, max_chars=max_chars)


def recreate_canvas_state_from_preview_image_bytes(raw_bytes, canvas_width=1054, canvas_height=684):
    return _views_func('_recreate_canvas_state_from_preview_image_bytes')(
        raw_bytes,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
