from .library_repositories import (
    LIBRARY_MICROCYCLE_MARKER,
    LIBRARY_REPOSITORY_AI_TRAINER,
    LIBRARY_REPOSITORY_CHOICES,
    LIBRARY_REPOSITORY_INTERACTIVE,
    LIBRARY_REPOSITORY_TRADITIONAL,
    library_repository_for_task,
    normalize_library_repository,
)


def task_scope_for_item(task):
    from .views import _task_scope_for_item

    return _task_scope_for_item(task)


def task_preview_needs_refresh(task):
    from .views import _task_preview_needs_refresh

    return _task_preview_needs_refresh(task)


def task_analysis_needs_refresh(task):
    from .views import _task_analysis_needs_refresh

    return _task_analysis_needs_refresh(task)


def ensure_library_task_preview(task, force=False, prefer_render=False):
    from .views import _ensure_library_task_preview

    return _ensure_library_task_preview(task, force=force, prefer_render=prefer_render)


def maybe_render_task_preview_server_side(task, *, force=False):
    from .views import _maybe_render_task_preview_server_side

    return _maybe_render_task_preview_server_side(task, force=force)


def analyze_preview_image_bytes(raw_bytes):
    from .views import _analyze_preview_image_bytes

    return _analyze_preview_image_bytes(raw_bytes)


def cleanup_task_joined_text_fields(task):
    from .views import _cleanup_task_joined_text_fields

    return _cleanup_task_joined_text_fields(task)


def refresh_task_from_pdf_analysis(task):
    from .views import _refresh_task_from_pdf_analysis

    return _refresh_task_from_pdf_analysis(task)


def learn_task_blueprint_from_task(*, team, task, scope_key: str = '', actor_username: str = ''):
    from .views import _learn_task_blueprint_from_task

    return _learn_task_blueprint_from_task(
        team=team,
        task=task,
        scope_key=scope_key,
        actor_username=actor_username,
    )


def ensure_library_task_preview_legacy(task, force=False, prefer_render=False):
    return ensure_library_task_preview(task, force=force, prefer_render=prefer_render)
