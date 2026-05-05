from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client

from football.models import AppUserRole, Team, Workspace, WorkspaceMembership, WorkspaceTeam, WorkspaceTeamAccess


def _is_internal_href(href: str) -> bool:
    if not href:
        return False
    href = str(href).strip()
    if not href:
        return False
    if href.startswith("#"):
        return False
    if href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:"):
        return False
    if href.startswith("http://") or href.startswith("https://"):
        try:
            parsed = urlparse(href)
        except Exception:
            return False
        # Permitimos mismo host o relativo; para el smoke local solo seguimos paths relativos.
        return bool(parsed.path and parsed.path.startswith("/"))
    return href.startswith("/")


def _normalize_href(href: str) -> str:
    href = str(href or "").strip()
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        try:
            parsed = urlparse(href)
            return parsed.path + (f"?{parsed.query}" if parsed.query else "")
        except Exception:
            return ""
    return href


@dataclass
class LinkCheck:
    url: str
    status: int
    location: str = ""
    note: str = ""


class Command(BaseCommand):
    help = "UI smoke: recorre enlaces internos y detecta 404/500 o redirecciones sospechosas."

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=0, help="Team.id a usar (si 0, el primero).")
        parser.add_argument("--host", type=str, default="localhost", help="Host para evitar DisallowedHost.")
        parser.add_argument("--max-pages", type=int, default=140, help="Máximo de URLs a visitar.")
        parser.add_argument("--max-links-per-page", type=int, default=120, help="Máximo enlaces extraídos por página.")
        parser.add_argument("--print-ok", action="store_true", help="Imprime también OKs.")
        parser.add_argument("--as-superuser", action="store_true", help="Ejecuta como superuser (por defecto crea/usa un coach).")

    def handle(self, *args, **options):
        User = get_user_model()
        as_superuser = bool(options.get("as_superuser"))
        if as_superuser:
            user = User.objects.filter(is_superuser=True, is_active=True).first()
            if not user:
                raise SystemExit("No hay superuser activo para el smoke test.")
        else:
            user = User.objects.filter(username="smoke.coach", is_active=True).first()
            if not user:
                user = User.objects.create_user(username="smoke.coach", email="smoke.coach@example.com", password="smoke1234")
            AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_COACH})

        team_id = int(options["team_id"] or 0)
        team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.first()
        if not team:
            raise SystemExit("No hay Team en la base de datos.")

        # Garantiza workspace club para que las rutas que lo requieren no devuelvan 404.
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

        host = str(options["host"] or "localhost").strip() or "localhost"
        max_pages = max(10, int(options["max_pages"] or 140))
        max_links_per_page = max(20, int(options["max_links_per_page"] or 120))
        print_ok = bool(options["print_ok"])

        c = Client()
        c.force_login(user)
        try:
            sess = c.session
            sess["active_workspace_id"] = int(workspace.id)
            sess["active_team_id"] = int(team.id)
            sess.save()
        except Exception:
            pass

        seed_urls = [
            f"/?team={team.id}",
            f"/coach/?team={team.id}",
            f"/coach/sesiones/?team={team.id}",
            f"/coach/sesiones/?tab=library&team={team.id}",
            f"/coach/sesiones/?tab=sessions&team={team.id}",
            f"/coach/agenda/?team={team.id}",
            f"/convocatoria/?team={team.id}",
            f"/registro-acciones/?team={team.id}",
            f"/players/?team={team.id}",
            f"/coach/analisis/?team={team.id}",
            f"/coach/staff/?team={team.id}",
        ]

        visited: set[str] = set()
        queue: list[str] = []
        for u in seed_urls:
            if u not in visited:
                queue.append(u)

        bad: list[LinkCheck] = []
        oks = 0
        redirects_to_login = 0
        redirects_to_onboarding = 0

        def fetch(url: str):
            return c.get(url, HTTP_HOST=host, follow=False)

        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            resp = fetch(url)
            status = int(resp.status_code or 0)
            location = str(resp.get("Location") or "")

            if status in {301, 302, 303, 307, 308}:
                loc_path = _normalize_href(location)
                if re.search(r"/login/?($|\\?)", loc_path):
                    redirects_to_login += 1
                    bad.append(LinkCheck(url=url, status=status, location=location, note="REDIRECT_LOGIN"))
                    continue
                if loc_path.startswith("/onboarding/"):
                    redirects_to_onboarding += 1
                    bad.append(LinkCheck(url=url, status=status, location=location, note="REDIRECT_ONBOARDING"))
                    continue
                # Redirección “normal”: la seguimos (si es interna).
                if loc_path and loc_path.startswith("/") and loc_path not in visited:
                    queue.append(loc_path)
                if print_ok:
                    self.stdout.write(f"OK {status} {url} -> {location}")
                else:
                    oks += 1
                continue

            if status >= 400:
                bad.append(LinkCheck(url=url, status=status, location=location, note="HTTP_ERROR"))
                continue

            # OK HTML: extraer enlaces internos.
            try:
                ctype = str(resp.get("Content-Type") or "")
            except Exception:
                ctype = ""
            if "text/html" not in ctype:
                if print_ok:
                    self.stdout.write(f"OK {status} {url} (non-html)")
                else:
                    oks += 1
                continue

            try:
                html = resp.content.decode("utf-8", "ignore")
            except Exception:
                html = ""
            soup = BeautifulSoup(html, "html.parser")
            hrefs = []
            for a in soup.select("a[href]"):
                hrefs.append(a.get("href"))
                if len(hrefs) >= max_links_per_page:
                    break
            for raw in hrefs:
                href = _normalize_href(raw)
                if not _is_internal_href(href):
                    continue
                # Evita rutas que suelen romper por depender de IDs no presentes.
                if "/admin/" in href:
                    continue
                if href.startswith("/static/") or href.startswith("/media/"):
                    continue
                if href not in visited and href not in queue:
                    queue.append(href)

            if print_ok:
                self.stdout.write(f"OK {status} {url} (links {len(hrefs)})")
            else:
                oks += 1

        self.stdout.write("")
        self.stdout.write(f"Visited: {len(visited)} pages · OK: {oks} · Bad: {len(bad)}")
        self.stdout.write(f"Redirects to /login: {redirects_to_login} · to /onboarding: {redirects_to_onboarding}")
        if bad:
            self.stdout.write("")
            self.stdout.write("BAD:")
            for item in bad[:80]:
                self.stdout.write(f"- {item.status} {item.url} -> {item.location} [{item.note}]")
            if len(bad) > 80:
                self.stdout.write(f"... {len(bad) - 80} más")
            raise SystemExit(2)
