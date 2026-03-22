from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from football.models import Match, MatchEvent, Team
from football.views import _event_signature


class Command(BaseCommand):
    help = 'Limpia duplicados de MatchEvent por partido de forma segura (ventana temporal corta).'

    def add_arguments(self, parser):
        parser.add_argument('--match-id', type=int, help='ID del partido a limpiar')
        parser.add_argument('--rival', type=str, help='Texto a buscar en nombre rival')
        parser.add_argument('--seconds', type=int, default=12, help='Ventana de duplicado en segundos (default: 12)')
        parser.add_argument(
            '--all-sources',
            action='store_true',
            help='Incluye también eventos importados (por defecto solo registro-acciones).',
        )
        parser.add_argument('--apply', action='store_true', help='Aplica borrado real (sin esto es dry-run)')

    def handle(self, *args, **options):
        seconds = max(1, int(options['seconds'] or 12))
        match = self._resolve_match(options)
        if not match:
            raise CommandError('No se encontró partido para limpiar')

        qs = MatchEvent.objects.filter(match=match)
        if not options['all_sources']:
            qs = qs.filter(source_file='registro-acciones')
        qs = qs.order_by('created_at', 'id')
        events = list(qs)
        if not events:
            self.stdout.write(self.style.WARNING(f'Partido {match.id}: sin eventos'))
            return

        by_signature = defaultdict(list)
        drop_ids = []
        window = timedelta(seconds=seconds)
        fallback_epoch = timezone.now()

        for event in events:
            signature = _event_signature(event)
            created_at = event.created_at or fallback_epoch
            previous_times = by_signature[signature]
            if any(abs(created_at - ts) <= window for ts in previous_times):
                drop_ids.append(event.id)
            else:
                previous_times.append(created_at)

        self.stdout.write(
            f'Partido {match.id} ({match}): total={len(events)} duplicados_detectados={len(drop_ids)} window={seconds}s'
        )
        if not drop_ids:
            return

        sample = list(
            MatchEvent.objects.filter(id__in=drop_ids).values_list(
                'id', 'created_at', 'minute', 'player_id', 'event_type', 'result', 'zone'
            )[:10]
        )
        self.stdout.write('Muestra duplicados (max 10):')
        for row in sample:
            self.stdout.write(f' - {row}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('Dry-run: no se borró nada. Usa --apply para aplicar.'))
            return

        deleted, _ = MatchEvent.objects.filter(id__in=drop_ids).delete()
        self.stdout.write(self.style.SUCCESS(f'Duplicados eliminados: {deleted}'))

    def _resolve_match(self, options):
        match_id = options.get('match_id')
        if match_id:
            return Match.objects.filter(id=match_id).first()

        rival = (options.get('rival') or '').strip()
        if rival:
            team = Team.objects.filter(is_primary=True).first()
            if not team:
                return None
            return (
                Match.objects.filter(home_team=team, away_team__name__icontains=rival)
                .order_by('-date', '-id')
                .first()
                or Match.objects.filter(away_team=team, home_team__name__icontains=rival)
                .order_by('-date', '-id')
                .first()
            )
        return None
