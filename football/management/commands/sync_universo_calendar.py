"""Sincroniza el calendario/resultados de Universo RFAF hacia objetos Match locales.

DRY-RUN por defecto (no escribe nada). Añade --write para aplicar de verdad.

Ejemplos:
    python manage.py sync_universo_calendar --team 12
    python manage.py sync_universo_calendar --team "Benagalbon" --write
"""

from django.core.management.base import BaseCommand, CommandError

from football.calendar_sync_services import sync_team_calendar_from_universo
from football.models import Team


class Command(BaseCommand):
    help = "Sincroniza partidos/resultados desde Universo RFAF hacia Match (dry-run por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("--team", required=True, help="ID o nombre del equipo principal.")
        parser.add_argument("--write", action="store_true", help="Aplica los cambios (por defecto es dry-run).")
        parser.add_argument("--max-rounds", type=int, default=40, help="Máximo de jornadas a recorrer.")

    def _resolve_team(self, raw):
        raw = str(raw or "").strip()
        if raw.isdigit():
            team = Team.objects.filter(id=int(raw)).first()
            if team:
                return team
        team = Team.objects.filter(name__iexact=raw).first() or Team.objects.filter(name__icontains=raw).first()
        return team

    def handle(self, *args, **options):
        team = self._resolve_team(options["team"])
        if not team:
            raise CommandError(f"Equipo no encontrado: {options['team']!r}")
        write = bool(options["write"])
        summary = sync_team_calendar_from_universo(team, write=write, max_rounds=int(options["max_rounds"]))

        mode = "APLICADO" if write else "DRY-RUN (sin escribir)"
        self.stdout.write(self.style.MIGRATE_HEADING(f"Sync calendario Universo · {team.name} · {mode}"))
        if summary["errors"]:
            for err in summary["errors"]:
                self.stdout.write(self.style.ERROR(f"  ⚠ {err}"))
            if not summary["rows"]:
                return
        for row in summary["rows"]:
            tag = {"created": "＋", "updated": "↻", "skipped": "·"}.get(row["action"], "?")
            loc = "L" if row["home"] else "V"
            score = f" {row['score']}" if row["score"] else ""
            self.stdout.write(
                f"  {tag} {row['date']} [{loc}] vs {row['opponent']}{score}  ({row['detail']})"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Resumen: {summary['created']} nuevos · {summary['updated']} actualizados · {summary['skipped']} sin cambios"
            )
        )
        if not write and (summary["created"] or summary["updated"]):
            self.stdout.write(self.style.WARNING("Nada escrito (dry-run). Repite con --write para aplicar."))
