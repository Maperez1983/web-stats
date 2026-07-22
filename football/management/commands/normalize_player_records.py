from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from football.models import Player, ScoutingTarget
from football.normalization import normalize_player_record, normalize_scouting_target_record


class Command(BaseCommand):
    help = 'Normaliza nombres y posiciones de jugadores y jugadores ojeados existentes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra los cambios sin guardarlos en base de datos.',
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        player_changes = 0
        scouting_changes = 0
        conflicts = 0

        self.stdout.write(self.style.NOTICE('Normalizando jugadores...'))
        for player in Player.objects.select_related('team').order_by('team_id', 'id').iterator():
            before = {
                'name': player.name,
                'full_name': player.full_name,
                'nickname': player.nickname,
                'origin_team': player.origin_team,
                'preferred_position': player.preferred_position,
                'previous_season_position': player.previous_season_position,
                'position': player.position,
            }
            changed_fields = normalize_player_record(player)
            if not changed_fields:
                continue
            after = {field: getattr(player, field) for field in before}
            player_changes += 1
            self.stdout.write(
                f'Jugador #{player.id}: ' + ', '.join(
                    f'{field}="{before[field]}" -> "{after[field]}"' for field in changed_fields
                )
            )
            if dry_run:
                continue
            try:
                with transaction.atomic():
                    player.save(update_fields=changed_fields)
            except IntegrityError:
                conflicts += 1
                self.stderr.write(
                    self.style.WARNING(
                        f'Conflicto al normalizar Player #{player.id} "{before["name"]}" '
                        f'en equipo {getattr(player.team, "id", None)}. Se deja sin guardar.'
                    )
                )

        self.stdout.write(self.style.NOTICE('Normalizando ojeados...'))
        for target in ScoutingTarget.objects.select_related('workspace', 'player').order_by('workspace_id', 'id').iterator():
            before = {
                'subject_name': target.subject_name,
                'subject_team_name': target.subject_team_name,
                'position': target.position,
            }
            changed_fields = normalize_scouting_target_record(target)
            if not changed_fields:
                continue
            after = {field: getattr(target, field) for field in before}
            scouting_changes += 1
            self.stdout.write(
                f'Ojeado #{target.id}: ' + ', '.join(
                    f'{field}="{before[field]}" -> "{after[field]}"' for field in changed_fields
                )
            )
            if dry_run:
                continue
            try:
                with transaction.atomic():
                    target.save(update_fields=changed_fields)
            except IntegrityError:
                conflicts += 1
                self.stderr.write(
                    self.style.WARNING(
                        f'Conflicto al normalizar ScoutingTarget #{target.id} '
                        f'"{before["subject_name"]}". Se deja sin guardar.'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Listo. Jugadores tocados: {player_changes}. Ojeados tocados: {scouting_changes}. '
                f'Conflictos: {conflicts}.'
            )
        )
