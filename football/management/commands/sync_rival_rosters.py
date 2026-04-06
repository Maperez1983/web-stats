import json
import os
import time
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from football.models import Team, TeamRosterSnapshot, TeamStanding, Group, Season, Competition
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
            '--home-team-id',
            type=int,
            default=int(os.getenv('RIVAL_ROSTER_HOME_TEAM_ID', '0') or '0'),
            help='ID del equipo propio (categoría) cuyo grupo se usa como contexto.',
        )
        parser.add_argument(
            '--include-primary',
            action='store_true',
            help='Incluye el equipo principal en la sincronización (por defecto se omite).',
        )
        parser.add_argument(
            '--update-standings',
            action='store_true',
            help='Actualiza TeamStanding con la clasificación descargada (recomendado).',
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
        update_standings = bool(options.get('update_standings'))
        home_team_id = int(options.get('home_team_id') or 0)
        dump_file = str(options.get('dump_file') or '').strip()
        load_file = str(options.get('load_file') or '').strip()

        primary_team = None
        if home_team_id:
            primary_team = Team.objects.filter(id=home_team_id).select_related('group', 'group__season', 'group__season__competition').first()
        if not primary_team:
            primary_team = Team.objects.filter(is_primary=True).select_related('group', 'group__season', 'group__season__competition').first()
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
            if primary_team and int(team_obj.id) == int(primary_team.id):
                return True
            return bool(getattr(team_obj, 'is_primary', False))

        def _ensure_group_season():
            # Para poder guardar TeamStanding, necesitamos season+competition.
            nonlocal group
            if not group:
                return None, None, None
            season = getattr(group, 'season', None)
            competition = getattr(season, 'competition', None) if season else None
            if season and competition:
                return competition, season, group
            # Backfill mínimo: crea competition/season dummy si faltan.
            competition, _ = Competition.objects.get_or_create(
                name='Liga (sin nombre)',
                region='',
                defaults={'slug': slugify('liga-sin-nombre') or 'liga'},
            )
            season_name = f'{timezone.localdate().year}/{timezone.localdate().year + 1}' if timezone.localdate().month >= 7 else f'{timezone.localdate().year - 1}/{timezone.localdate().year}'
            season, _ = Season.objects.get_or_create(
                competition=competition,
                name=season_name,
                defaults={'is_current': True},
            )
            group.season = season
            group.save(update_fields=['season'])
            return competition, season, group

        def _update_group_external_id(value):
            if not group or not value:
                return
            if str(getattr(group, 'external_id', '') or '').strip() == str(value).strip():
                return
            # Solo actualizamos si está vacío (o si parece ser otro id de Universo).
            existing = str(getattr(group, 'external_id', '') or '').strip()
            if not existing:
                group.external_id = str(value).strip()
                group.save(update_fields=['external_id'])

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
            _update_group_external_id(group_id)

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
            if update_standings:
                competition, season, group_for_standings = _ensure_group_season()
                if season and group_for_standings:
                    updated_team_ids = set()
                    def _safe_int(value, default=0):
                        try:
                            return int(str(value).strip())
                        except Exception:
                            return default
                    for idx, row in enumerate(rows, start=1):
                        if not isinstance(row, dict):
                            continue
                        team_code = str(row.get('codequipo') or row.get('cod_equipo') or '').strip()
                        team_name = str(row.get('nombre') or row.get('team') or '').strip()
                        if not team_name:
                            continue
                        team = None
                        if team_code:
                            team = Team.objects.filter(external_id=team_code).first()
                        if not team and primary_team:
                            # Si el nombre coincide con nuestro equipo, reutilizamos la instancia.
                            if str(primary_team.name or '').strip().lower() == team_name.strip().lower():
                                team = primary_team
                        if not team:
                            team = Team.objects.filter(group=group_for_standings, name__iexact=team_name).first()
                        if not team:
                            team = Team.objects.create(
                                name=team_name,
                                slug=_unique_team_slug(team_name),
                                short_name=team_name[:60],
                                group=group_for_standings,
                                external_id=team_code or '',
                            )
                        changed_fields = []
                        if team_code and str(getattr(team, 'external_id', '') or '').strip() != team_code:
                            team.external_id = team_code
                            changed_fields.append('external_id')
                        if getattr(team, 'group_id', None) != getattr(group_for_standings, 'id', None):
                            team.group = group_for_standings
                            changed_fields.append('group')
                        if team_name and team.name != team_name:
                            team.name = team_name
                            changed_fields.append('name')
                        if changed_fields:
                            team.save(update_fields=changed_fields)
                        updated_team_ids.add(int(team.id))
                        gf = _safe_int(row.get('goles_a_favor') or row.get('goals_for') or row.get('gf'), default=0)
                        ga = _safe_int(row.get('goles_en_contra') or row.get('goals_against') or row.get('gc'), default=0)
                        gd_raw = row.get('diferencia_goles') or row.get('goal_difference') or row.get('dg')
                        gd = _safe_int(gd_raw, default=(gf - ga))
                        TeamStanding.objects.update_or_create(
                            season=season,
                            group=group_for_standings,
                            team=team,
                            defaults={
                                'position': _safe_int(row.get('posicion') or row.get('position'), default=idx),
                                'played': _safe_int(row.get('jugados') or row.get('played') or row.get('pj'), default=0),
                                'wins': _safe_int(row.get('ganados') or row.get('wins') or row.get('pg'), default=0),
                                'draws': _safe_int(row.get('empatados') or row.get('draws') or row.get('pe'), default=0),
                                'losses': _safe_int(row.get('perdidos') or row.get('losses') or row.get('pp'), default=0),
                                'goals_for': gf,
                                'goals_against': ga,
                                'goal_difference': gd,
                                'points': _safe_int(row.get('puntos') or row.get('points') or row.get('pt') or row.get('pts'), default=0),
                                'last_updated': timezone.now(),
                            },
                        )
                    if updated_team_ids:
                        TeamStanding.objects.filter(group=group_for_standings).exclude(team_id__in=updated_team_ids).delete()

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
