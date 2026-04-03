import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from football.models import Team, TeamRosterSnapshot
from football.services import fetch_preferente_team_roster, find_preferente_team_url


def _unique_team_slug(base_name: str) -> str:
    base_slug = slugify(str(base_name or '').strip()) or 'rival'
    slug = base_slug
    suffix = 2
    while Team.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{suffix}'
        suffix += 1
    return slug


class Command(BaseCommand):
    help = (
        'Sincroniza y cachea la plantilla de rivales para preparar fichas técnicas de partido.\n'
        '- provider=universo_rfaf: usa Universo RFAF (requiere storage_state vigente).\n'
        '- provider=lapreferente: usa LaPreferente (puede sufrir 403 puntuales).\n'
        'Guarda los resultados en TeamRosterSnapshot para consumo desde el análisis/partido.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            default=os.getenv('RIVAL_ROSTER_PROVIDER', TeamRosterSnapshot.PROVIDER_UNIVERSO),
            choices=[TeamRosterSnapshot.PROVIDER_UNIVERSO, TeamRosterSnapshot.PROVIDER_PREFERENTE],
            help='Fuente principal para descargar plantillas.',
        )
        parser.add_argument(
            '--group-id',
            default=os.getenv('RIVAL_ROSTER_GROUP_ID', '').strip(),
            help='ID del grupo en Universo RFAF (solo si provider=universo_rfaf).',
        )
        parser.add_argument('--force', action='store_true', help='Fuerza refresco incluso si la caché es reciente.')
        parser.add_argument(
            '--max-age-days',
            type=int,
            default=int(os.getenv('RIVAL_ROSTER_CACHE_DAYS', '14') or '14'),
            help='Edad máxima (días) para considerar válida la caché.',
        )
        parser.add_argument('--limit', type=int, default=0, help='Limita nº de equipos procesados (0=sin límite).')

    def handle(self, *args, **options):
        provider = str(options.get('provider') or '').strip()
        group_id = str(options.get('group_id') or '').strip()
        force = bool(options.get('force'))
        limit = int(options.get('limit') or 0)
        max_age_days = max(1, int(options.get('max_age_days') or 14))
        threshold = timezone.now() - timedelta(days=max_age_days)

        primary_team = Team.objects.filter(is_primary=True).select_related('group').first()
        group = primary_team.group if primary_team else None

        processed = 0
        refreshed = 0
        skipped = 0
        failed = 0

        if provider == TeamRosterSnapshot.PROVIDER_UNIVERSO:
            if not group_id:
                group_id = str(getattr(group, 'external_id', '') or '').strip()
            if not group_id:
                raise CommandError(
                    'Falta group-id para Universo RFAF. Pasa --group-id o configura Group.external_id.'
                )

            # Import tardío para evitar cargar `football.views` en cada comando.
            from football.views import _fetch_universo_live_classification, fetch_universo_team_roster

            payload = _fetch_universo_live_classification(group_id)
            rows = payload.get('clasificacion') if isinstance(payload, dict) else None
            if not isinstance(rows, list) or not rows:
                raise CommandError(
                    'No se pudo obtener la clasificación desde Universo RFAF. '
                    'Comprueba que el storage_state/token esté vigente.'
                )

            for row in rows:
                if limit and processed >= limit:
                    break
                if not isinstance(row, dict):
                    continue
                team_code = str(row.get('codequipo') or row.get('cod_equipo') or '').strip()
                team_name = str(row.get('nombre') or row.get('team') or '').strip()
                if not team_code.isdigit() or not team_name:
                    continue
                processed += 1

                team = Team.objects.filter(external_id=team_code).first()
                if not team:
                    team = Team.objects.filter(name__iexact=team_name).first()
                if not team:
                    team = Team.objects.create(
                        name=team_name,
                        slug=_unique_team_slug(team_name),
                        short_name=team_name[:60],
                        group=group,
                        external_id=team_code,
                    )
                else:
                    changed_fields = []
                    if team.external_id != team_code:
                        team.external_id = team_code
                        changed_fields.append('external_id')
                    if group and not team.group_id:
                        team.group = group
                        changed_fields.append('group')
                    if changed_fields:
                        team.save(update_fields=changed_fields)

                snapshot = TeamRosterSnapshot.objects.filter(team=team, provider=provider).first()
                if snapshot and not force and snapshot.updated_at and snapshot.updated_at >= threshold and snapshot.roster_payload:
                    skipped += 1
                    continue

                try:
                    roster = fetch_universo_team_roster(team_code)
                    TeamRosterSnapshot.objects.update_or_create(
                        team=team,
                        provider=provider,
                        defaults={
                            'roster_payload': roster,
                            'source_url': f'https://www.universorfaf.es/team/{team_code}',
                            'error': '',
                        },
                    )
                    refreshed += 1
                except Exception as exc:
                    failed += 1
                    TeamRosterSnapshot.objects.update_or_create(
                        team=team,
                        provider=provider,
                        defaults={
                            'roster_payload': [],
                            'source_url': f'https://www.universorfaf.es/team/{team_code}',
                            'error': str(exc)[:240],
                        },
                    )
        else:
            if not group:
                raise CommandError('No hay equipo principal con grupo asignado para iterar rivales.')
            rivals = list(Team.objects.filter(group=group).order_by('name', 'id'))
            for team in rivals:
                if limit and processed >= limit:
                    break
                if not team or not team.name:
                    continue
                processed += 1
                url = (team.preferente_url or '').strip()
                if not url:
                    try:
                        url = find_preferente_team_url(team.name)
                    except Exception:
                        url = ''
                    if url:
                        team.preferente_url = url
                        team.save(update_fields=['preferente_url'])
                snapshot = TeamRosterSnapshot.objects.filter(team=team, provider=provider).first()
                if snapshot and not force and snapshot.updated_at and snapshot.updated_at >= threshold and snapshot.roster_payload:
                    skipped += 1
                    continue
                if not url:
                    failed += 1
                    continue
                try:
                    roster = fetch_preferente_team_roster(url)
                    TeamRosterSnapshot.objects.update_or_create(
                        team=team,
                        provider=provider,
                        defaults={'roster_payload': roster, 'source_url': url, 'error': ''},
                    )
                    refreshed += 1
                except Exception as exc:
                    failed += 1
                    TeamRosterSnapshot.objects.update_or_create(
                        team=team,
                        provider=provider,
                        defaults={'roster_payload': [], 'source_url': url, 'error': str(exc)[:240]},
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Rivales procesados: {processed} · refrescados: {refreshed} · omitidos: {skipped} · fallidos: {failed}'
            )
        )

