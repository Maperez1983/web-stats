from django.core.management.base import BaseCommand

from football.models import Team
from football.stats_audit import run_stats_audit


class Command(BaseCommand):
    help = 'Audita coherencia entre registros de acciones, tarjetas, goles, mapas y estadísticas mostradas.'

    def handle(self, *args, **options):
        primary_team = Team.objects.filter(is_primary=True).first()
        report = run_stats_audit(primary_team)

        for key, value in report['summary'].items():
            self.stdout.write(f'{key}: {value}')

        duplicate_matches = report['details'].get('duplicate_matches') or []
        if duplicate_matches:
            self.stdout.write('duplicate_matches:')
            for item in duplicate_matches:
                self.stdout.write(f"  - signature={item['signature']} match_ids={item['match_ids']}")

        if report['issues']:
            self.stdout.write(self.style.WARNING('Issues detectados:'))
            for issue in report['issues']:
                self.stdout.write(f'  - {issue}')
        else:
            self.stdout.write(self.style.SUCCESS('Auditoría de estadísticas OK'))

        notes = report.get('notes') or []
        if notes:
            self.stdout.write('Notas:')
            for note in notes:
                self.stdout.write(f'  - {note}')
