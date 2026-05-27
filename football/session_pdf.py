from .session_plan_fields import parse_session_plan_fields, serialize_session_plan_fields


def session_plan_pdf(request, session_id):
    from .views import session_plan_pdf as view_session_plan_pdf

    return view_session_plan_pdf(request, session_id=session_id)


def build_session_pdf_context(request, team, session, pdf_style='uefa'):
    from .views import _build_session_pdf_context

    return _build_session_pdf_context(request, team, session, pdf_style=pdf_style)


def extract_pdf_text(pdf_file, max_chars=12000):
    from .views import _extract_pdf_text

    return _extract_pdf_text(pdf_file, max_chars=max_chars)


def recreate_canvas_state_from_preview_image_bytes(raw_bytes, canvas_width=1054, canvas_height=684):
    from .views import _recreate_canvas_state_from_preview_image_bytes

    return _recreate_canvas_state_from_preview_image_bytes(
        raw_bytes,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
