from __future__ import annotations

import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from football.models import (
    ImportedSessionDocument,
    SessionTask,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class Command(BaseCommand):
    help = "Smoke test del sistema (flujo crítico) usando Django test client."

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=None, help="Team.id a usar en requests.")
        parser.add_argument("--username", type=str, default="smoke_admin")
        parser.add_argument("--password", type=str, default="smoke_admin_123")
        parser.add_argument(
            "--pdf-path",
            type=str,
            default="media/session-tasks-pdf/SESION_121__MARTES.pdf",
            help="PDF local para probar importación.",
        )

    def handle(self, *args, **options):
        username = str(options.get("username") or "smoke_admin").strip()
        password = str(options.get("password") or "smoke_admin_123").strip()
        team_id = options.get("team_id")
        pdf_path = str(options.get("pdf_path") or "").strip()

        # Informa si el entorno no está en modo "fallback monoclub"; en smoke usamos usuario plataforma.
        if not os.getenv("ALLOW_SINGLE_CLUB_FALLBACK"):
            self.stdout.write(self.style.WARNING("Nota: ALLOW_SINGLE_CLUB_FALLBACK no está activo. Smoke usa superuser."))

        team = Team.objects.filter(id=int(team_id)).first() if team_id else Team.objects.filter(is_primary=True).first()
        if not team:
            team = Team.objects.order_by("id").first()
        if not team:
            raise SystemExit("No hay equipos en BD (Team).")

        # Usuario plataforma para evitar restricciones de workspace/club.
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.create_superuser(username=username, email="", password=password)
        else:
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save(update_fields=["is_staff", "is_superuser", "password"])

        # Asegura contexto de workspace club + acceso al equipo para que todas las vistas/API resuelvan team.
        # primary_team es OneToOne: si ya existe un workspace para ese team, lo reutilizamos.
        workspace = Workspace.objects.filter(primary_team=team).first()
        if not workspace:
            ws_slug = f"smoke-ws-{int(team.id)}"
            workspace, _ = Workspace.objects.get_or_create(
                slug=ws_slug,
                defaults={
                    "name": f"SMOKE · {team.display_name}",
                    "kind": Workspace.KIND_CLUB,
                    "primary_team": None,
                    "owner_user": user,
                    "is_active": True,
                },
            )
        # Asegura tipo club y activo (sin tocar el primary_team si ya está ocupado).
        try:
            updates = {}
            if workspace.kind != Workspace.KIND_CLUB:
                updates["kind"] = Workspace.KIND_CLUB
            if not workspace.is_active:
                updates["is_active"] = True
            if updates:
                for k, v in updates.items():
                    setattr(workspace, k, v)
                workspace.save(update_fields=list(updates.keys()))
        except Exception:
            pass
        WorkspaceTeam.objects.get_or_create(workspace=workspace, team=team, defaults={"is_default": True})
        WorkspaceTeamAccess.objects.get_or_create(
            workspace=workspace,
            team=team,
            user=user,
            defaults={"is_default": True},
        )

        # Evita DisallowedHost (por defecto Django test client usa "testserver").
        c = Client(HTTP_HOST="localhost")
        if not c.login(username=username, password=password):
            raise SystemExit("No se pudo hacer login en smoke user.")

        failures: list[str] = []

        def _ok(label: str, cond: bool, detail: str = ""):
            if cond:
                self.stdout.write(self.style.SUCCESS(f"OK  {label}"))
            else:
                msg = f"FAIL {label}"
                if detail:
                    msg += f" · {detail}"
                failures.append(msg)
                self.stdout.write(self.style.ERROR(msg))

        # 1) Dashboard
        dash_url = reverse("dashboard-home")
        resp = c.get(dash_url, {"team": int(team.id), "workspace": int(workspace.id)})
        _ok("GET dashboard", resp.status_code == 200, f"status={resp.status_code}")

        # 2) Página sesiones/planning (render principal)
        sessions_url = reverse("sessions")
        resp = c.get(sessions_url, {"team": int(team.id), "workspace": int(workspace.id), "tab": "create"})
        _ok("GET sesiones", resp.status_code == 200, f"status={resp.status_code}")

        # 3) Importar tarea PDF (library_upload_pdf raw) y verificar que se crea.
        pdf_file = None
        pdf_bytes = b""
        try:
            pdf_bytes = Path(pdf_path).read_bytes()
        except Exception:
            pdf_bytes = b""
        if not pdf_bytes:
            self.stdout.write(self.style.WARNING(f"No se encontró PDF en {pdf_path}. Se omite importación PDF."))
        else:
            pdf_file = SimpleUploadedFile("smoke_task.pdf", pdf_bytes, content_type="application/pdf")
            before = SessionTask.objects.count()
            post_data = {
                    "planner_action": "library_upload_pdf",
                    "planner_tab": "import",
                    "team": int(team.id),
                    "workspace": int(workspace.id),
                    "pdf_import_mode": "raw",
                    "pdf_task_title": "SMOKE PDF",
                    "pdf_task_objective": "",
                    "pdf_task_block": SessionTask.BLOCK_MAIN_1,
                    "pdf_task_minutes": "15",
                    "library_task_pdf": pdf_file,
                }
            resp = c.post(sessions_url, data=post_data)
            _ok("POST importar tarea PDF", resp.status_code in (200, 302), f"status={resp.status_code}")
            after = SessionTask.objects.count()
            _ok("tarea PDF creada", after >= before + 1, f"before={before} after={after}")

        # 4) Enviar a papelera una tarea de biblioteca (si existe).
        lib_task = (
            SessionTask.objects
            .select_related("session__microcycle")
            .filter(session__microcycle__team=team, deleted_at__isnull=True)
            .order_by("-id")
            .first()
        )
        if lib_task:
            resp = c.post(
                sessions_url,
                data={
                    "planner_action": "delete_library_task",
                    "planner_tab": "library",
                    "team": int(team.id),
                    "workspace": int(workspace.id),
                    "library_repo": "traditional",
                    "task_id": int(lib_task.id),
                },
            )
            _ok("POST papelera tarea", resp.status_code in (200, 302), f"status={resp.status_code}")
            lib_task.refresh_from_db()
            _ok("tarea marcada deleted_at", bool(lib_task.deleted_at), "deleted_at vacío")

        # 5) PDF viewer page básico (no ejecuta iframe, solo HTML).
        viewer_url = reverse("pdf-viewer")
        resp = c.get(viewer_url, {"u": "/coach/sesiones/"})
        _ok("GET pdf viewer (guardrails)", resp.status_code in (200, 400), f"status={resp.status_code}")

        # 6) Endpoint de blueprints (recomendador).
        bp_url = reverse("task-assistant-blueprints-api")
        resp = c.get(bp_url, {"team": int(team.id), "workspace": int(workspace.id)})
        _ok("GET blueprints api", resp.status_code == 200, f"status={resp.status_code}")

        # 7) Crea microciclo/sesión mínima (flujo base).
        try:
            # Evita colisión unique (week_start).
            week_start = TrainingMicrocycle.objects.filter(team=team).order_by("-week_start").values_list("week_start", flat=True).first()
            if week_start:
                # a la siguiente semana
                new_start = week_start.replace(day=min(28, week_start.day))  # safe
            else:
                from datetime import date, timedelta
                new_start = date.today()
            # Simple: usa get_or_create por week_start
            mc, _ = TrainingMicrocycle.objects.get_or_create(
                team=team,
                week_start=new_start,
                defaults={"week_end": new_start, "title": "SMOKE MC"},
            )
            sess, _ = TrainingSession.objects.get_or_create(
                microcycle=mc,
                session_date=new_start,
                defaults={"focus": "SMOKE SES", "duration_minutes": 90},
            )
            _ok("crear microciclo/sesión", bool(mc and sess), "")
        except Exception as exc:
            _ok("crear microciclo/sesión", False, str(exc))

        if failures:
            raise SystemExit("\n".join(failures))
