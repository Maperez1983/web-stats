from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from football.models import AppUserRole, Player, Team


def _build_base_username(name):
    value = slugify(name or '').replace('-', '.')
    value = value.strip('.')
    return value or 'jugador'


class Command(BaseCommand):
    help = 'Crea usuarios para jugadores del equipo principal y asigna rol jugador.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default='Jugador2026!',
            help='Contrasena temporal para usuarios nuevos (por defecto: Jugador2026!).',
        )
        parser.add_argument(
            '--force-reset-password',
            action='store_true',
            help='Reinicia la contrasena de usuarios existentes al valor indicado en --password.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = str(options.get('password') or 'Jugador2026!').strip()
        force_reset = bool(options.get('force_reset_password'))

        primary_team = Team.objects.filter(is_primary=True).first()
        if not primary_team:
            self.stdout.write(self.style.ERROR('No hay equipo principal configurado.'))
            return

        players = list(Player.objects.filter(team=primary_team).order_by('name'))
        if not players:
            self.stdout.write(self.style.WARNING('No hay jugadores para crear usuarios.'))
            return

        created = 0
        updated = 0
        for player in players:
            full_name = (player.full_name or player.name or '').strip()
            if not full_name:
                continue
            base_username = _build_base_username(full_name)
            username = base_username
            suffix = 2
            while User.objects.filter(username=username).exclude(first_name=player.name).exists():
                existing_for_player = User.objects.filter(first_name=player.name, last_name='').first()
                if existing_for_player:
                    username = existing_for_player.username
                    break
                username = f'{base_username}{suffix}'
                suffix += 1

            user = User.objects.filter(username=username).first()
            if not user:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=player.name or '',
                    last_name='',
                    is_active=True,
                )
                created += 1
            elif force_reset:
                user.set_password(password)
                user.is_active = True
                user.save(update_fields=['password', 'is_active'])
                updated += 1

            AppUserRole.objects.update_or_create(
                user=user,
                defaults={'role': AppUserRole.ROLE_PLAYER},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Usuarios jugador sincronizados. Creados: {created}. Actualizados: {updated}.'
            )
        )
