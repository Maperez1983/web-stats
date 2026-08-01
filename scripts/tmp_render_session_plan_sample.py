from pathlib import Path

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory

from football.models import TrainingSession
from football.session_pdf import build_session_pdf_context


def build_request(path: str):
    factory = RequestFactory()
    request = factory.get(path, secure=False, HTTP_HOST="127.0.0.1:8000")
    user = get_user_model().objects.filter(is_superuser=True).order_by("id").first()
    if user is None:
        user = get_user_model().objects.order_by("id").first()
    request.user = user
    return request


def render_session(session_id: int, style: str, out_name: str):
    session = (
        TrainingSession.objects.select_related("microcycle__team")
        .prefetch_related("tasks")
        .filter(id=session_id)
        .first()
    )
    if not session:
        raise SystemExit(f"Session {session_id} not found")
    request = build_request(f"/coach/sesiones/sesion/{session.id}/pdf/?style={style}")
    context = build_session_pdf_context(request, session.microcycle.team, session, pdf_style=style)
    html = render_to_string("football/session_plan_pdf.html", context)
    out_path = Path("tmp") / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(out_path)


def main():
    candidates = list(TrainingSession.objects.select_related("microcycle__team").prefetch_related("tasks").order_by("-id")[:150])
    session = None
    best_score = -1
    for item in candidates:
        task_count = item.tasks.filter(deleted_at__isnull=True).count()
        content_len = len(str(item.content or "").strip())
        score = content_len + (task_count * 500)
        if score > best_score:
            best_score = score
            session = item
    if not session:
        raise SystemExit("No sessions found")
    render_session(session.id, "club", "session_plan_club_sample.html")
    render_session(session.id, "uefa", "session_plan_uefa_sample.html")


if __name__ == "__main__":
    main()
