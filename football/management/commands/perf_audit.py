from __future__ import annotations

import time
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from football.models import Team, Workspace, WorkspaceMembership, WorkspaceTeam, WorkspaceTeamAccess


@dataclass(frozen=True)
class AuditResult:
    url: str
    status: int
    total_ms: int
    db_ms: int
    queries: int


def _sum_db_ms(captured_queries: list[dict]) -> int:
    total = 0.0
    for q in captured_queries or []:
        try:
            total += float(q.get("time") or 0.0)
        except Exception:
            continue
    return int(round(total * 1000.0))


def _normalize_sql_for_grouping(sql: str) -> str:
    import re

    sql = str(sql or "").strip()
    if not sql:
        return ""
    sql = sql.replace("\n", " ")
    sql = re.sub(r"'[^']*'", "'?'", sql)
    sql = re.sub(r"\\b\\d+\\b", "?", sql)
    sql = re.sub(r"\\s+", " ", sql).strip()
    return sql


def _top_repeated_queries(captured_queries: list[dict], limit: int) -> list[dict]:
    counts: dict[str, int] = {}
    sample_sql: dict[str, str] = {}
    for q in captured_queries or []:
        raw_sql = str(q.get("sql") or "").strip()
        key = _normalize_sql_for_grouping(raw_sql)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
        sample_sql.setdefault(key, raw_sql)
    rows = [{"count": c, "sql": sample_sql.get(k) or k} for k, c in counts.items()]
    rows.sort(key=lambda r: int(r.get("count") or 0), reverse=True)
    return rows[: max(0, int(limit or 0))]


def _top_queries(captured_queries: list[dict], limit: int) -> list[dict]:
    rows = []
    for q in captured_queries or []:
        try:
            t = float(q.get("time") or 0.0)
        except Exception:
            t = 0.0
        rows.append({"time": t, "sql": str(q.get("sql") or "").strip()})
    rows.sort(key=lambda r: r["time"], reverse=True)
    return rows[: max(0, int(limit or 0))]


class Command(BaseCommand):
    help = "Auditoría rápida de rendimiento: mide tiempo total + nº queries por endpoint."

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=0, help="Team.id (si 0, usa el primario o el primero).")
        parser.add_argument("--host", type=str, default="localhost", help="Host para evitar DisallowedHost.")
        parser.add_argument("--repeat", type=int, default=2, help="Repite cada URL N veces (1=cold; 2=cold+warm).")
        parser.add_argument("--only", type=str, default="", help="Filtro substring de URL.")
        parser.add_argument("--username", type=str, default="perf_audit_admin", help="Usuario superuser temporal.")
        parser.add_argument("--password", type=str, default="perf_audit_admin_123", help="Password para el usuario.")
        parser.add_argument("--sql", action="store_true", help="Imprime SQL del endpoint más lento.")
        parser.add_argument("--sql-limit", type=int, default=10, help="Top N SQL por tiempo (cuando --sql).")
        parser.add_argument("--sql-top-repeated", type=int, default=8, help="Top N patrones repetidos (cuando --sql).")

    def handle(self, *args, **options):
        host = str(options.get("host") or "localhost").strip() or "localhost"
        repeat = max(1, int(options.get("repeat") or 1))
        only = str(options.get("only") or "").strip().lower()
        username = str(options.get("username") or "perf_audit_admin").strip()
        password = str(options.get("password") or "perf_audit_admin_123").strip()
        want_sql = bool(options.get("sql"))
        sql_limit = max(1, int(options.get("sql_limit") or 10))
        sql_top_repeated = max(0, int(options.get("sql_top_repeated") or 0))

        team_id = int(options.get("team_id") or 0)
        team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.filter(is_primary=True).first()
        if not team:
            team = Team.objects.order_by("id").first()
        if not team:
            raise SystemExit("No hay Team en la base de datos.")

        User = get_user_model()
        user = User.objects.filter(username=username, is_active=True).first()
        if not user:
            user = User.objects.create_superuser(username=username, email="", password=password)
        else:
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save(update_fields=["is_staff", "is_superuser", "password"])

        workspace = (
            Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True, primary_team=team).first()
            or Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True).first()
        )
        if not workspace:
            workspace = Workspace.objects.create(
                name=f"PerfAudit · {team.name}",
                slug=f"perf-audit-{team.id}",
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
        WorkspaceMembership.objects.get_or_create(
            workspace=workspace,
            user=user,
            defaults={"role": WorkspaceMembership.ROLE_ADMIN},
        )
        WorkspaceTeamAccess.objects.get_or_create(workspace=workspace, team=team, user=user, defaults={"is_default": True})

        c = Client()
        c.force_login(user)
        try:
            sess = c.session
            sess["active_workspace_id"] = int(workspace.id)
            sess["active_team_id"] = int(team.id)
            sess.save()
        except Exception:
            pass

        urls = [
            f"/?team={int(team.id)}",
            f"/coach/?team={int(team.id)}",
            f"/players/?team={int(team.id)}",
            f"/coach/sesiones/?team={int(team.id)}",
            f"/coach/analisis/?team={int(team.id)}",
        ]
        try:
            urls.append(reverse("dashboard-home") + f"?team={int(team.id)}")
        except Exception:
            pass
        try:
            from football.models import Player

            player = Player.objects.filter(team=team).order_by("id").first()
            if player:
                urls.append(f"/player/{int(player.id)}/?team={int(team.id)}")
        except Exception:
            pass

        if only:
            urls = [u for u in urls if only in u.lower()]
        if not urls:
            raise SystemExit("No hay URLs a auditar (filtro --only demasiado restrictivo).")

        self.stdout.write("== PERF AUDIT ==")
        self.stdout.write(f"Team: {team.id} · {team.display_name}")
        self.stdout.write(f"Workspace: {workspace.id} · {workspace.slug}")
        self.stdout.write(f"Repeat: {repeat}")
        if only:
            self.stdout.write(f"Filter: {only}")

        results: list[AuditResult] = []
        captured_by_result: dict[AuditResult, list[dict]] = {}
        by_url: dict[str, list[AuditResult]] = {}

        def fetch(url: str) -> AuditResult:
            with CaptureQueriesContext(connection) as ctx:
                t0 = time.perf_counter()
                resp = c.get(url, HTTP_HOST=host, follow=False)
                total_ms = int(round((time.perf_counter() - t0) * 1000.0))
            r = AuditResult(
                url=url,
                status=int(resp.status_code or 0),
                total_ms=total_ms,
                db_ms=_sum_db_ms(ctx.captured_queries),
                queries=len(ctx.captured_queries),
            )
            if want_sql:
                captured_by_result[r] = list(ctx.captured_queries)
            return r

        for url in urls:
            for i in range(repeat):
                r = fetch(url)
                results.append(r)
                by_url.setdefault(r.url, []).append(r)
                pass_label = "cold" if i == 0 else f"warm{i}"
                self.stdout.write(
                    f"{pass_label:>6} · {r.total_ms:>5} ms · {r.queries:>4} q · db {r.db_ms:>5} ms · {r.status} · {r.url}"
                )

        self.stdout.write("\n== SUMMARY (best warm) ==")
        per_url_best: list[AuditResult] = []
        for url, rs in by_url.items():
            warm = rs[1:] if len(rs) > 1 else rs
            best = sorted(warm, key=lambda x: (x.total_ms, x.queries))[0]
            per_url_best.append(best)
            self.stdout.write(f"{best.total_ms:>5} ms · {best.queries:>4} q · db {best.db_ms:>5} ms · {best.status} · {url}")

        if want_sql and per_url_best:
            target = sorted(per_url_best, key=lambda x: (x.total_ms, x.queries), reverse=True)[0]
            captured = captured_by_result.get(target) or []
            self.stdout.write(f"\n== TOP SQL ({sql_limit}) · {target.total_ms} ms · {target.url} ==")
            top = _top_queries(captured, sql_limit)
            for idx, q in enumerate(top, start=1):
                sql = (q.get("sql") or "").replace("\n", " ").strip()
                if len(sql) > 240:
                    sql = sql[:240] + "…"
                ms = int(round(float(q.get("time") or 0) * 1000.0))
                self.stdout.write(f"{idx:>2}. {ms:>4} ms · {sql}")
            if sql_top_repeated:
                reps = _top_repeated_queries(captured, sql_top_repeated)
                self.stdout.write(f"\n== TOP REPEATED SQL ({sql_top_repeated}) · {target.url} ==")
                for idx, row in enumerate(reps, start=1):
                    sql = str(row.get("sql") or "").replace("\n", " ").strip()
                    if len(sql) > 240:
                        sql = sql[:240] + "…"
                    self.stdout.write(f"{idx:>2}. x{int(row.get('count') or 0):<3} · {sql}")
