from __future__ import annotations

import base64
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from football.models import AppUserRole, Team, Workspace, WorkspaceMembership, WorkspaceTeam, WorkspaceTeamAccess


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = PROJECT_ROOT / "football" / "static" / "football" / "images" / "pitch3d"
DEFAULT_STADIUM_MODEL = PROJECT_ROOT / "football" / "static" / "football" / "models" / "pitch3d" / "stadium_malaga_rosaleda.glb"


def _wait_for_server(base_url: str, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url.rstrip('/')}/login/", timeout=2) as response:
                if int(getattr(response, "status", 0) or 0) < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.35)
    raise CommandError(f"No se pudo arrancar el servidor local en {base_url}: {last_error!r}")


def _ensure_render_user(username: str, team_id: int = 0):
    User = get_user_model()
    user = User.objects.filter(username=username, is_active=True).first()
    if not user:
        user = User.objects.create_user(username=username, email=f"{username}@example.com", password="stadium-render")
    AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_COACH})

    team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.first()
    if not team:
        raise CommandError("No hay ningún Team en la base de datos para abrir la pizarra.")

    workspace = (
        Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True, primary_team=team).first()
        or Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True).first()
    )
    if not workspace:
        workspace = Workspace.objects.create(
            name=f"Club {team.name}",
            slug=f"club-{team.id}",
            kind=Workspace.KIND_CLUB,
            primary_team=team,
            owner_user=user,
            enabled_modules={},
            subscription_status="trial",
            is_active=True,
        )
    if workspace.primary_team_id is None:
        workspace.primary_team = team
        workspace.save(update_fields=["primary_team"])

    WorkspaceTeam.objects.get_or_create(workspace=workspace, team=team, defaults={"is_default": True})
    WorkspaceMembership.objects.get_or_create(workspace=workspace, user=user, defaults={"role": WorkspaceMembership.ROLE_ADMIN})
    WorkspaceTeamAccess.objects.get_or_create(workspace=workspace, team=team, user=user, defaults={"is_default": True})
    return user, team, workspace


def _make_session_cookie(user, team, workspace) -> tuple[str, str]:
    client = Client()
    client.force_login(user)
    try:
        session = client.session
        session["active_workspace_id"] = int(workspace.id)
        session["active_team_id"] = int(team.id)
        session.save()
    except Exception:
        pass
    cookie_name = str(getattr(settings, "SESSION_COOKIE_NAME", "sessionid") or "sessionid")
    cookie = client.cookies.get(cookie_name)
    if not cookie or not getattr(cookie, "value", ""):
        raise CommandError("No se pudo crear la cookie de sesión para Playwright.")
    return cookie_name, str(cookie.value)


def _outputs_are_fresh(stadium_model: Path, output_paths: list[Path]) -> bool:
    if not stadium_model.exists():
        return False
    if not output_paths or any(not p.exists() for p in output_paths):
        return False
    model_mtime = stadium_model.stat().st_mtime
    return all(p.stat().st_mtime >= model_mtime for p in output_paths)


class Command(BaseCommand):
    help = "Renderiza las vistas cenitales del estadio 3D y actualiza los PNG usados por la pizarra 2D."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="", help="URL de una app ya arrancada. Si se omite, arranca runserver local.")
        parser.add_argument("--host", default="127.0.0.1", help="Host local para runserver.")
        parser.add_argument("--port", type=int, default=8013, help="Puerto local para runserver.")
        parser.add_argument("--username", default="stadium.render", help="Usuario técnico para abrir la pizarra.")
        parser.add_argument("--team-id", type=int, default=0, help="Team.id opcional.")
        parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Directorio donde guardar los PNG.")
        parser.add_argument("--stadium-model", default=str(DEFAULT_STADIUM_MODEL), help="GLB usado para decidir si los PNG están obsoletos.")
        parser.add_argument("--css-width", type=int, default=4096, help="Ancho CSS forzado del canvas 3D antes de exportar.")
        parser.add_argument("--css-height", type=int, default=2298, help="Alto CSS forzado del canvas 3D antes de exportar.")
        parser.add_argument("--force", action="store_true", help="Regenera aunque los PNG sean más nuevos que el GLB.")
        parser.add_argument("--downloads-copy", default="", help="Directorio opcional donde copiar también una versión de revisión.")
        parser.add_argument("--keep-server", action="store_true", help="No para el runserver arrancado por el comando.")

    def handle(self, *args, **options):
        out_dir = Path(str(options["out_dir"])).expanduser().resolve()
        stadium_model = Path(str(options["stadium_model"])).expanduser().resolve()
        out_h = out_dir / "stadium_rosaleda_top_h.png"
        out_v = out_dir / "stadium_rosaleda_top_v.png"
        force = bool(options["force"])

        if not force and _outputs_are_fresh(stadium_model, [out_h, out_v]):
            self.stdout.write(self.style.SUCCESS("Las vistas cenitales ya están actualizadas. Usa --force para regenerar."))
            return

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise CommandError(f"Playwright no está disponible en este entorno: {exc!r}") from exc

        user, team, workspace = _ensure_render_user(str(options["username"] or "stadium.render"), int(options["team_id"] or 0))
        cookie_name, cookie_value = _make_session_cookie(user, team, workspace)

        base_url = str(options.get("base_url") or "").strip().rstrip("/")
        proc = None
        if not base_url:
            host = str(options["host"] or "127.0.0.1").strip()
            port = int(options["port"] or 8013)
            base_url = f"http://{host}:{port}"
            env = os.environ.copy()
            env.setdefault("DEBUG", "true")
            env.setdefault("SECRET_KEY", "dev")
            env.setdefault("ALLOW_SQLITE_IN_PROD", "true")
            env.setdefault("ALLOW_SINGLE_CLUB_FALLBACK", "true")
            cmd = [sys.executable, str(PROJECT_ROOT / "manage.py"), "runserver", f"{host}:{port}", "--noreload"]
            proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            _wait_for_server(base_url)
        cookie_domain = urlparse(base_url).hostname or str(options.get("host") or "127.0.0.1")

        css_width = max(1600, int(options["css_width"] or 4096))
        css_height = max(900, int(options["css_height"] or 2298))
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--use-angle=metal", "--no-sandbox"])
                ctx = browser.new_context(
                    viewport={"width": min(css_width, 2560), "height": min(css_height, 1440)},
                    device_scale_factor=1,
                    ignore_https_errors=True,
                )
                ctx.add_cookies(
                    [
                        {
                            "name": cookie_name,
                            "value": cookie_value,
                            "domain": cookie_domain,
                            "path": "/",
                            "httpOnly": True,
                            "sameSite": "Lax",
                        }
                    ]
                )
                page = ctx.new_page()
                page.set_default_timeout(120000)
                page.set_default_navigation_timeout(120000)
                page.goto(f"{base_url}/coach/sesiones/tareas/nueva/?reset=1&cleardraft=1&device=desktop", wait_until="domcontentloaded")
                page.wait_for_selector("#task-builder-form")
                page.wait_for_function(
                    "() => document.querySelector('#task-builder-form')?.dataset?.webstatsTpadReady === '1'",
                    timeout=120000,
                )
                page.locator("#pitch-3d-open").click()
                page.wait_for_selector("#task-pitch-3d-canvas", state="visible")
                page.wait_for_function("() => window.__WEBSTATS_PITCH3D_SCENE && window.__WEBSTATS_PITCH3D_CAMERA", timeout=120000)
                page.evaluate(
                    """({ width, height }) => {
                        const modal = document.querySelector('#task-pitch-3d-modal');
                        const card = modal?.querySelector('.sim-3d-card');
                        const head = modal?.querySelector('.sim-3d-head');
                        const foot = modal?.querySelector('.sim-3d-foot');
                        const body = modal?.querySelector('.sim-3d-body');
                        if (modal) {
                          modal.style.placeItems = 'start';
                          modal.style.padding = '0';
                          modal.style.overflow = 'visible';
                        }
                        if (card) {
                          card.style.width = `${width}px`;
                          card.style.height = `${height}px`;
                          card.style.maxWidth = 'none';
                          card.style.maxHeight = 'none';
                          card.style.borderRadius = '0';
                        }
                        if (head) head.style.display = 'none';
                        if (foot) foot.style.display = 'none';
                        if (body) {
                          body.style.width = `${width}px`;
                          body.style.height = `${height}px`;
                        }
                        window.dispatchEvent(new Event('resize'));
                    }""",
                    {"width": css_width, "height": css_height},
                )
                page.wait_for_timeout(5000)

                results = []
                for camera, target in (("top_h", out_h), ("top_v", out_v)):
                    page.evaluate(
                        """(camera) => {
                            const select = document.querySelector('#task-pitch-3d-camera');
                            if (select) {
                              select.value = camera;
                              select.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }""",
                        camera,
                    )
                    page.wait_for_timeout(2200)
                    data = page.evaluate(
                        """() => {
                            const canvas = document.querySelector('#task-pitch-3d-canvas');
                            return {
                              dataUrl: canvas ? canvas.toDataURL('image/png') : '',
                              width: canvas?.width || 0,
                              height: canvas?.height || 0
                            };
                        }"""
                    )
                    data_url = str(data.get("dataUrl") or "")
                    if not data_url.startswith("data:image/png;base64,"):
                        raise CommandError(f"No se pudo extraer PNG del canvas para {camera}.")
                    target.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
                    results.append((target, int(data.get("width") or 0), int(data.get("height") or 0)))

                browser.close()
        finally:
            if proc is not None and not bool(options["keep_server"]):
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        downloads_copy = str(options.get("downloads_copy") or "").strip()
        if downloads_copy:
            review_dir = Path(downloads_copy).expanduser().resolve()
            review_dir.mkdir(parents=True, exist_ok=True)
            for target, _w, _h in results:
                (review_dir / target.name).write_bytes(target.read_bytes())

        for target, width, height in results:
            size_mb = target.stat().st_size / (1024 * 1024)
            self.stdout.write(self.style.SUCCESS(f"Render actualizado: {target} ({width}x{height}, {size_mb:.1f} MB)"))
