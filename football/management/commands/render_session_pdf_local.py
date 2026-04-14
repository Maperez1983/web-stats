from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from football.models import TrainingSession
from football.views import session_plan_pdf


class Command(BaseCommand):
    help = "Renderiza un PDF de sesión (club/uefa) en local y lo guarda en /tmp o en un path."

    def add_arguments(self, parser):
        parser.add_argument("--session-id", type=int, required=True)
        parser.add_argument("--style", choices=["club", "uefa"], default="club")
        parser.add_argument("--out", type=str, default="")
        parser.add_argument("--user", type=str, default="admin", help="Username para construir el request.")

    def handle(self, *args, **options):
        session_id = int(options["session_id"])
        style = str(options["style"] or "club").strip().lower()
        out_raw = str(options["out"] or "").strip()
        username = str(options["user"] or "admin").strip() or "admin"

        session = (
            TrainingSession.objects
            .select_related("microcycle__team")
            .filter(id=session_id)
            .first()
        )
        if not session:
            raise CommandError("Sesión no encontrada.")

        User = get_user_model()
        user = User.objects.filter(username=username).first() or User.objects.order_by("id").first()
        if not user:
            raise CommandError("No hay usuarios en DB para ejecutar el render.")

        # Evita DisallowedHost en RequestFactory + build_absolute_uri.
        try:
            hosts = list(getattr(settings, "ALLOWED_HOSTS", []) or [])
            if "testserver" not in hosts:
                hosts.append("testserver")
            settings.ALLOWED_HOSTS = hosts
        except Exception:
            pass

        rf = RequestFactory()
        request = rf.get(f"/_local/session/{session_id}/pdf?style={style}&force_pdf=1")
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request.user = user

        # Render con la vista real (incluye guardrails/branding/preview).
        response = session_plan_pdf(request, session_id=session_id)
        content_type = str(getattr(response, "get", lambda *_: "")("Content-Type") or "")
        body = getattr(response, "content", b"") or b""
        if "application/pdf" not in content_type:
            raise CommandError(f"No devolvió PDF (Content-Type={content_type}). ¿WeasyPrint disponible? bytes={len(body)}")

        if out_raw:
            out_path = Path(out_raw).expanduser()
        else:
            out_path = Path("/tmp") / f"session-{session_id}-{style}.pdf"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(body)
        self.stdout.write(self.style.SUCCESS(f"OK: {out_path} ({len(body)} bytes)"))

