from .library_repositories import INBOX_MICROCYCLE_WEEK_START, LIBRARY_REPOSITORY_TRADITIONAL
from .session_plan_fields import serialize_session_plan_fields
from .task_library_services import ensure_library_task_preview


def apply_analysis_to_task(*args, **kwargs):
    from .views import _apply_analysis_to_task

    return _apply_analysis_to_task(*args, **kwargs)


def extract_pdf_text(pdf_file, max_chars=12000):
    from .views import _extract_pdf_text

    return _extract_pdf_text(pdf_file, max_chars=max_chars)


def extract_preview_images_from_pdf(*args, **kwargs):
    from .views import _extract_preview_images_from_pdf

    return _extract_preview_images_from_pdf(*args, **kwargs)


def extract_tasks_from_pdf_text(*args, **kwargs):
    from .views import _extract_tasks_from_pdf_text

    return _extract_tasks_from_pdf_text(*args, **kwargs)


def get_or_create_inbox_microcycle(*args, **kwargs):
    from .views import _get_or_create_inbox_microcycle

    return _get_or_create_inbox_microcycle(*args, **kwargs)


def get_or_create_week_microcycle(*args, **kwargs):
    from .views import _get_or_create_week_microcycle

    return _get_or_create_week_microcycle(*args, **kwargs)


def learn_task_blueprint_from_pdf_import(*args, **kwargs):
    from .views import _learn_task_blueprint_from_pdf_import

    return _learn_task_blueprint_from_pdf_import(*args, **kwargs)


def next_session_task_order(*args, **kwargs):
    from .views import _next_session_task_order

    return _next_session_task_order(*args, **kwargs)


def parse_pdf_session_header_fields(*args, **kwargs):
    from .views import _parse_pdf_session_header_fields

    return _parse_pdf_session_header_fields(*args, **kwargs)


def suggest_blocks_for_session_pdf_segments(*args, **kwargs):
    from .views import _suggest_blocks_for_session_pdf_segments

    return _suggest_blocks_for_session_pdf_segments(*args, **kwargs)


def suggest_session_plan_fields_from_pdf_text(*args, **kwargs):
    from .views import _suggest_session_plan_fields_from_pdf_text

    return _suggest_session_plan_fields_from_pdf_text(*args, **kwargs)


def get_or_create_library_session_with_repository(*args, **kwargs):
    from .views import _get_or_create_library_session_with_repository

    return _get_or_create_library_session_with_repository(*args, **kwargs)


def import_library_tasks_from_pdf_advanced(*args, **kwargs):
    from .views import _import_library_tasks_from_pdf_advanced

    return _import_library_tasks_from_pdf_advanced(*args, **kwargs)
