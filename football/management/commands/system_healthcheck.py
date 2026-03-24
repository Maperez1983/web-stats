from django.core.management.base import BaseCommand

from football.healthchecks import run_system_healthcheck


class Command(BaseCommand):
    help = 'Ejecuta una verificación rápida del sistema: BD, rutas y dependencias opcionales.'

    def handle(self, *args, **options):
        report = run_system_healthcheck()

        db = report['database']
        self.stdout.write(
            f"database: {'OK' if db['ok'] else 'ERROR'} · {db['detail']}"
        )

        for label, item in report['paths'].items():
            self.stdout.write(
                f"{label}: {'OK' if item['ok'] else 'WARN'} · {item['detail']}"
            )

        for label, item in report['dependencies'].items():
            level = 'OK' if item['ok'] else 'WARN'
            self.stdout.write(f"{label}: {level} · {item['detail']}")

        if report['ok']:
            self.stdout.write(self.style.SUCCESS('Healthcheck general OK'))
        else:
            self.stdout.write(self.style.WARNING('Healthcheck con advertencias'))
