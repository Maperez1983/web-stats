from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from football.models import AppUserRole, Player, Team


class Command(BaseCommand):
    help = (
        "Enlaza usuarios (rol jugador) con su ficha Player de forma explícita.\n"
        "Uso típico para reparar casos donde dos logins apuntan a la misma ficha.\n\n"
        "Ejemplos:\n"
        "  python manage.py link_player_users --link angel.ayala=6 --apply\n"
        "  python manage.py link_player_users --link angel.sanchez=25 --apply\n"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--link",
            action="append",
            default=[],
            help="Formato: username=player_id (puede repetirse).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica cambios. Sin esto, solo muestra lo que haría (dry-run).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite re-enlazar aunque el usuario o el jugador ya estén enlazados.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        apply = bool(options.get("apply"))
        force = bool(options.get("force"))
        link_specs: list[str] = list(options.get("link") or [])

        primary_team = Team.objects.filter(is_primary=True).first()
        if not primary_team:
            self.stdout.write(self.style.ERROR("No hay equipo principal configurado."))
            return

        User = get_user_model()

        if not link_specs:
            self.stdout.write(self.style.WARNING("No se han indicado --link. Nada que hacer."))
            return

        for spec in link_specs:
            raw = str(spec or "").strip()
            if not raw or "=" not in raw:
                self.stdout.write(self.style.ERROR(f"--link inválido: {spec!r} (usa username=player_id)"))
                continue
            username, player_id_raw = raw.split("=", 1)
            username = (username or "").strip()
            player_id_raw = (player_id_raw or "").strip()
            try:
                player_id = int(player_id_raw)
            except Exception:
                self.stdout.write(self.style.ERROR(f"--link inválido: {spec!r} (player_id debe ser numérico)"))
                continue

            user = User.objects.filter(username__iexact=username).first()
            if not user:
                self.stdout.write(self.style.ERROR(f"Usuario no encontrado: {username}"))
                continue

            AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_PLAYER})

            player = Player.objects.filter(id=player_id, team=primary_team).first()
            if not player:
                self.stdout.write(self.style.ERROR(f"Jugador no encontrado en el equipo principal: id={player_id}"))
                continue

            existing_player_for_user = Player.objects.filter(team=primary_team, user=user).exclude(id=player.id).first()
            if existing_player_for_user and not force:
                self.stdout.write(
                    self.style.ERROR(
                        f"{username} ya está enlazado a Player id={existing_player_for_user.id} ({existing_player_for_user.name}). Usa --force para re-enlazar."
                    )
                )
                continue

            existing_user_for_player = Player.objects.filter(team=primary_team, id=player.id).exclude(user__isnull=True).exclude(user=user).first()
            if existing_user_for_player and not force:
                other_user = getattr(existing_user_for_player, "user", None)
                other_username = other_user.get_username() if other_user else "otro usuario"
                self.stdout.write(
                    self.style.ERROR(
                        f"Player id={player.id} ({player.name}) ya está enlazado a {other_username}. Usa --force para re-enlazar."
                    )
                )
                continue

            action = "ENLAZAR"
            if player.user_id and player.user_id != user.id:
                action = "REENLAZAR"
            msg = f"{action}: {username} -> Player id={player.id} ({player.name})"
            if apply:
                if force:
                    Player.objects.filter(team=primary_team, user=user).exclude(id=player.id).update(user=None)
                player.user = user
                player.save(update_fields=["user"])
                self.stdout.write(self.style.SUCCESS(msg))
            else:
                self.stdout.write(self.style.WARNING(f"[dry-run] {msg}"))

