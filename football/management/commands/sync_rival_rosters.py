import json
import os
import time
from datetime import timedelta
from pathlib import Path

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
        '- provider=universo_rfaf: usa Universo RFAF (requiere token; `RFAF_ACCESS_TOKEN` recomendado).\n'
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
        parser.add_argument(
            '--include-primary',
            action='store_true',
            help='Incluye el equipo principal en la sincronización (por defecto se omite).',
        )
        parser.add_argument('--force', action='store_true', help='Fuerza refresco incluso si la caché es reciente.')
        parser.add_argument(
            '--max-age-days',
            type=int,
            default=int(os.getenv('RIVAL_ROSTER_CACHE_DAYS', '14') or '14'),
            help='Edad máxima (días) para considerar válida la caché.',
        )
        parser.add_argument('--limit', type=int, default=0, help='Limita nº de equipos procesados (0=sin límite).')
        parser.add_argument(
            '--dump-file',
            default='',
            help='Guarda un JSON con las plantillas descargadas (útil para ejecutar en local y cargar luego en servidor).',
        )
        parser.add_argument(
            '--load-file',
            default='',
            help='Carga plantillas desde un JSON (sin hacer peticiones externas) y las guarda en BD.',
        )

    def handle(self, *args, **options):
        provider = str(options.get('provider') or '').strip()
        group_id = str(options.get('group_id') or '').strip()
        force = bool(options.get('force'))
        limit = int(options.get('limit') or 0)
        max_age_days = max(1, int(options.get('max_age_days') or 14))
        threshold = timezone.now() - timedelta(days=max_age_days)
        include_primary = bool(options.get('include_primary'))
        dump_file = str(options.get('dump_file') or '').strip()
        load_file = str(options.get('load_file') or '').strip()

        primary_team = Team.objects.filter(is_primary=True).select_related('group').first()
        group = primary_team.group if primary_team else None

        processed = 0
        refreshed = 0
        skipped = 0
        failed = 0

        dump_payload = None
        if dump_file:
            dump_payload = {
                'provider': provider,
                'group_id': group_id,
                'generated_at': timezone.now().isoformat(),
                'teams': [],
            }

        def _should_skip_team(team_obj: Team) -> bool:
            if include_primary:
                return False
            if not team_obj:
                return True
            return bool(getattr(team_obj, 'is_primary', False))

        def _write_dump():
            if not dump_payload or not dump_file:
                return
            path = Path(dump_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(dump_payload, ensure_ascii=False, indent=2), encoding='utf-8')

        if load_file:
            path = Path(load_file)
            if not path.exists():
                raise CommandError(f'No existe el fichero: {load_file}')
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except Exception as exc:
                raise CommandError(f'No se pudo leer JSON: {exc}') from exc
            teams = payload.get('teams') if isinstance(payload, dict) else None
            if not isinstance(teams, list) or not teams:
                raise CommandError('JSON inválido: falta `teams` o está vacío.')
            if not provider:
                provider = str(payload.get('provider') or '').strip()
            if provider not in {TeamRosterSnapshot.PROVIDER_UNIVERSO, TeamRosterSnapshot.PROVIDER_PREFERENTE}:
                raise CommandError(f'Provider inválido en JSON: {provider!r}')
            for entry in teams:
                if limit and processed >= limit:
                    break
                if not isinstance(entry, dict):
                    continue
                team_code = str(entry.get('team_code') or entry.get('external_id') or entry.get('code') or '').strip()
                team_name = str(entry.get('team_name') or entry.get('name') or '').strip()
                roster = entry.get('roster')
                if not team_name or not isinstance(roster, list):
                    continue
                processed += 1

                team = None
                if team_code:
                    team = Team.objects.filter(external_id=team_code).first()
                if not team:
                    team = Team.objects.filter(name__iexact=team_name).first()
                if not team:
                    team = Team.objects.create(
                        name=team_name,
                        slug=_unique_team_slug(team_name),
                        short_name=team_name[:60],
                        group=group,
                        external_id=team_code or '',
                    )
                else:
                    changed_fields = []
                    if team_code and team.external_id != team_code:
                        team.external_id = team_code
                        changed_fields.append('external_id')
                    if group and not team.group_id:
                        team.group = group
                        changed_fields.append('group')
                    if changed_fields:
                        team.save(update_fields=changed_fields)
                if _should_skip_team(team):
                    skipped += 1
                    continue
                TeamRosterSnapshot.objects.update_or_create(
                    team=team,
                    provider=provider,
                    defaults={
                        'roster_payload': roster,
                        'source_url': str(entry.get('source_url') or entry.get('url') or '').strip(),
                        'error': str(entry.get('error') or '').strip()[:240],
                    },
                )
                refreshed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'(LOAD) Rivales procesados: {processed} · guardados: {refreshed} · omitidos: {skipped} · fallidos: {failed}'
                )
            )
            return

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
                    'Comprueba que `RFAF_USER`/`RFAF_PASS` sean correctos o define `RFAF_ACCESS_TOKEN`. '
                    'Puedes ejecutar: `python manage.py universo_rfaf_diagnostics --group-id <id>`'
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

                if _should_skip_team(team):
                    skipped += 1
                    continue

                snapshot = TeamRosterSnapshot.objects.filter(team=team, provider=provider).first()
                if snapshot and not force and snapshot.updated_at and snapshot.updated_at >= threshold and snapshot.roster_payload:
                    skipped += 1
                    continue

                try:
                    roster = None
                    last_exc = None
                    for attempt in range(3):
                        try:
                            roster = fetch_universo_team_roster(team_code)
                            last_exc = None
                            break
                        except Exception as exc:
                            last_exc = exc
                            time.sleep(1.3 * (attempt + 1))
                    if roster is None and last_exc:
                        raise last_exc
                    TeamRosterSnapshot.objects.update_or_create(
                        team=team,
                        provider=provider,
                        defaults={
                            'roster_payload': roster,
                            'source_url': f'https://www.universorfaf.es/team/{team_code}',
                            'error': '',
                        },
                    )
                    if dump_payload is not None:
                        dump_payload['teams'].append(
                            {
                                'team_code': team_code,
                                'team_name': team.name,
                                'source_url': f'https://www.universorfaf.es/team/{team_code}',
                                'roster': roster,
                                'error': '',
                            }
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
                    if dump_payload is not None:
                        dump_payload['teams'].append(
                            {
                                'team_code': team_code,
                                'team_name': team.name,
                                'source_url': f'https://www.universorfaf.es/team/{team_code}',
                                'roster': [],
                                'error': str(exc)[:240],
                            }
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
                if _should_skip_team(team):
                    skipped += 1
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
                    if dump_payload is not None:
                        dump_payload['teams'].append(
                            {
                                'team_code': str(team.external_id or '').strip(),
                                'team_name': team.name,
                                'source_url': url,
                                'roster': [],
                                'error': 'No se pudo resolver URL de LaPreferente.',
                            }
                        )
                    continue
                try:
                    roster = fetch_preferente_team_roster(url)
                    TeamRosterSnapshot.objects.update_or_create(
                        team=team,
                        provider=provider,
                        defaults={'roster_payload': roster, 'source_url': url, 'error': ''},
                    )
                    if dump_payload is not None:
                        dump_payload['teams'].append(
                            {
                                'team_code': str(team.external_id or '').strip(),
                                'team_name': team.name,
                                'source_url': url,
                                'roster': roster,
                                'error': '',
                            }
                        )
                    refreshed += 1
                except Exception as exc:
                    failed += 1
                    TeamRosterSnapshot.objects.update_or_create(
                        team=team,
                        provider=provider,
                        defaults={'roster_payload': [], 'source_url': url, 'error': str(exc)[:240]},
                    )
                    if dump_payload is not None:
                        dump_payload['teams'].append(
                            {
                                'team_code': str(team.external_id or '').strip(),
                                'team_name': team.name,
                                'source_url': url,
                                'roster': [],
                                'error': str(exc)[:240],
                            }
                        )

        _write_dump()
        self.stdout.write(
            self.style.SUCCESS(
                f'Rivales procesados: {processed} · refrescados: {refreshed} · omitidos: {skipped} · fallidos: {failed}'
            )
        )
