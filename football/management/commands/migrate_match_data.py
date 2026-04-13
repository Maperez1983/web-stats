from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from football.models import (
    ConvocationRecord,
    Match,
    MatchEvent,
    MatchReport,
    PlayerCommunication,
    PlayerStatistic,
    RivalConvocationRecord,
    Team,
)
from football.views import _invalidate_team_dashboard_caches


class Command(BaseCommand):
    help = (
        'Migra datos (eventos/convocatoria/stats) desde un Match incorrecto a otro Match '
        'para corregir un registro de acciones guardado en el partido equivocado.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--team-id', type=int, help='ID del equipo (Team.id) para acotar la migración')
        parser.add_argument('--team-slug', type=str, help='Slug del equipo (Team.slug) para acotar la migración')
        parser.add_argument('--from-match-id', type=int, required=True, help='ID del partido origen (incorrecto)')
        parser.add_argument('--to-match-id', type=int, required=True, help='ID del partido destino (correcto)')
        parser.add_argument(
            '--set-from-date',
            type=str,
            help='Opcional: fija la fecha del partido origen (YYYY-MM-DD), útil si quedó duplicada.',
        )
        parser.add_argument(
            '--set-from-round',
            type=str,
            help='Opcional: fija la jornada/ronda del partido origen (solo si procede).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplica cambios reales (sin esto es dry-run).',
        )
        parser.add_argument(
            '--allow-merge',
            action='store_true',
            help='Permite migrar aunque el partido destino ya tenga eventos (no recomendado).',
        )

    def handle(self, *args, **options):
        team = self._resolve_team(options)
        from_match = Match.objects.filter(id=int(options['from_match_id'])).select_related('home_team', 'away_team').first()
        to_match = Match.objects.filter(id=int(options['to_match_id'])).select_related('home_team', 'away_team').first()
        if not from_match or not to_match:
            raise CommandError('No se encontró from_match o to_match. Revisa los IDs.')
        if from_match.id == to_match.id:
            raise CommandError('from_match_id y to_match_id no pueden ser el mismo.')

        if team:
            self._assert_team_in_match(team, from_match, label='from_match')
            self._assert_team_in_match(team, to_match, label='to_match')

        move_filter = Q()
        if team:
            move_filter = Q(player__team=team) | Q(player__isnull=True)

        from_events_qs = MatchEvent.objects.filter(match=from_match)
        if team:
            from_events_qs = from_events_qs.filter(move_filter)
        from_player_stats_qs = PlayerStatistic.objects.filter(match=from_match)
        from_comms_qs = PlayerCommunication.objects.filter(match=from_match)
        from_reports_qs = MatchReport.objects.filter(match=from_match)
        from_convocations_qs = ConvocationRecord.objects.filter(match=from_match)
        from_rival_conv_qs = RivalConvocationRecord.objects.filter(match=from_match)

        if team:
            from_player_stats_qs = from_player_stats_qs.filter(player__team=team)
            from_comms_qs = from_comms_qs.filter(player__team=team)
            from_convocations_qs = from_convocations_qs.filter(team=team)
            from_rival_conv_qs = from_rival_conv_qs.filter(team=team)

        to_events_count = MatchEvent.objects.filter(match=to_match).count()
        if team:
            to_events_count = MatchEvent.objects.filter(match=to_match).filter(move_filter).count()

        summary = {
            'team': getattr(team, 'slug', None) or getattr(team, 'id', None) or '(no team filter)',
            'from_match': self._match_label(from_match),
            'to_match': self._match_label(to_match),
            'from': {
                'events': from_events_qs.count(),
                'player_stats': from_player_stats_qs.count(),
                'communications': from_comms_qs.count(),
                'reports': from_reports_qs.count(),
                'convocations': from_convocations_qs.count(),
                'rival_convocations': from_rival_conv_qs.count(),
            },
            'to_existing': {
                'events': to_events_count,
            },
        }
        self.stdout.write('Resumen migración:')
        for key, value in summary.items():
            self.stdout.write(f'- {key}: {value}')

        if not options.get('apply'):
            self.stdout.write(self.style.WARNING('Dry-run: no se aplicó nada. Usa --apply para ejecutar.'))
            return
        from_counts = summary.get('from') if isinstance(summary, dict) else {}
        from_total = 0
        if isinstance(from_counts, dict):
            try:
                from_total = sum(int(from_counts.get(key) or 0) for key in from_counts.keys())
            except Exception:
                from_total = 0
        only_updates_from_match = bool((options.get('set_from_date') or '').strip() or (options.get('set_from_round') or '').strip()) and from_total <= 0
        if to_events_count and not options.get('allow_merge') and not only_updates_from_match:
            raise CommandError(
                'El partido destino ya tiene eventos. Por seguridad, abortamos la migración. '
                'Si estás seguro de querer combinar, repite con --allow-merge.'
            )

        with transaction.atomic():
            updated_events = from_events_qs.update(match=to_match)
            updated_stats = from_player_stats_qs.update(match=to_match)
            updated_comms = from_comms_qs.update(match=to_match)
            updated_reports = from_reports_qs.update(match=to_match)

            updated_convocations = 0
            for record in from_convocations_qs.select_related('match').order_by('-created_at', '-id'):
                record.match = to_match
                self._sync_convocation_fields_from_match(record, team=team, match=to_match)
                record.save(update_fields=['match', 'round', 'match_date', 'match_time', 'location', 'opponent_name'])
                updated_convocations += 1

            updated_rival_convocations = 0
            for record in from_rival_conv_qs.select_related('match').order_by('-updated_at', '-id'):
                existing = None
                try:
                    if team:
                        existing = RivalConvocationRecord.objects.filter(team=team, match=to_match).first()
                except Exception:
                    existing = None
                if existing:
                    # Merge suave: si el destino está vacío, completa con el origen.
                    changed = False
                    if not existing.convocation_data and record.convocation_data:
                        existing.convocation_data = record.convocation_data
                        changed = True
                    if not existing.lineup_data and record.lineup_data:
                        existing.lineup_data = record.lineup_data
                        changed = True
                    if changed:
                        existing.save(update_fields=['convocation_data', 'lineup_data', 'updated_at'])
                    record.delete()
                else:
                    record.match = to_match
                    record.save(update_fields=['match'])
                updated_rival_convocations += 1

            from_match_update_fields = []
            raw_date = (options.get('set_from_date') or '').strip()
            if raw_date:
                try:
                    parsed = datetime.strptime(raw_date, '%Y-%m-%d').date()
                    if from_match.date != parsed:
                        from_match.date = parsed
                        from_match_update_fields.append('date')
                except Exception:
                    raise CommandError('--set-from-date debe ser YYYY-MM-DD')
            raw_round = (options.get('set_from_round') or '').strip()
            if raw_round:
                if from_match.round != raw_round:
                    from_match.round = raw_round
                    from_match_update_fields.append('round')
            if from_match_update_fields:
                from_match.save(update_fields=from_match_update_fields)

            if team:
                _invalidate_team_dashboard_caches(team)

        self.stdout.write(
            self.style.SUCCESS(
                'Migración aplicada: '
                f'events={updated_events} stats={updated_stats} comms={updated_comms} '
                f'reports={updated_reports} convocations={updated_convocations} rival_convocations={updated_rival_convocations}'
            )
        )

    def _resolve_team(self, options):
        team_id = options.get('team_id')
        team_slug = (options.get('team_slug') or '').strip()
        if team_id:
            return Team.objects.filter(id=int(team_id)).first()
        if team_slug:
            return Team.objects.filter(slug=team_slug).first()
        return None

    def _assert_team_in_match(self, team, match, *, label):
        if not team or not match:
            return
        if int(match.home_team_id or 0) == int(team.id) or int(match.away_team_id or 0) == int(team.id):
            return
        raise CommandError(
            f'{label}: el partido {match.id} no está vinculado a team={team.slug} (home/away). '
            'Pasa el team correcto o omite --team-* para migración global (no recomendado).'
        )

    def _match_label(self, match):
        if not match:
            return ''
        opponent = None
        if match.home_team_id and match.away_team_id:
            opponent = f'{match.home_team} vs {match.away_team}'
        date_label = match.date.isoformat() if match.date else 'sin-fecha'
        return f'id={match.id} {opponent or ""} {date_label} {match.round or ""}'.strip()

    def _sync_convocation_fields_from_match(self, record, *, team=None, match=None):
        if not record or not match:
            return
        record.round = match.round or record.round
        record.match_date = match.date or record.match_date
        try:
            record.match_time = match.kickoff_time or record.match_time
        except Exception:
            pass
        record.location = match.location or record.location
        if team and (match.home_team_id or match.away_team_id):
            opponent = match.away_team if match.home_team_id == team.id else match.home_team
            if opponent:
                record.opponent_name = opponent.display_name or opponent.name or record.opponent_name
        return
