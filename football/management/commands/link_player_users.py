from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from football.models import AppUserRole, MatchEvent, Player, Team


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
            "--auto",
            action="append",
            default=[],
            help="Intenta enlazar automáticamente un username (puede repetirse).",
        )
        parser.add_argument(
            "--link",
            action="append",
            default=[],
            help="Formato: username=player_id (puede repetirse).",
        )
        parser.add_argument(
            "--find",
            default="",
            help="Busca jugadores por texto (muestra ids + pistas).",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Lista todos los jugadores del equipo principal con id/usuario/acciones/lesión.",
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
        auto_users: list[str] = [str(v or "").strip() for v in (options.get("auto") or []) if str(v or "").strip()]
        find_query = str(options.get("find") or "").strip()
        do_list = bool(options.get("list"))

        primary_team = Team.objects.filter(is_primary=True).first()
        if not primary_team:
            self.stdout.write(self.style.ERROR("No hay equipo principal configurado."))
            return

        User = get_user_model()

        def actions_count(player: Player) -> int:
            try:
                return MatchEvent.objects.filter(player=player).count()
            except Exception:
                return 0

        def injury_label(player: Player) -> str:
            text = str(getattr(player, "injury", "") or "").strip()
            if text:
                return text
            try:
                record = player.injury_records.filter(is_active=True).order_by("-injury_date", "-id").first()
                if record:
                    return str(record.injury or "").strip() or "Lesión activa"
            except Exception:
                pass
            return ""

        def print_player_row(player: Player):
            linked_user = getattr(getattr(player, "user", None), "username", "") or ""
            full_name = str(getattr(player, "full_name", "") or "").strip()
            inj = injury_label(player)
            acts = actions_count(player)
            parts = [f"id={player.id}", f"nombre={player.name}"]
            if full_name and full_name != player.name:
                parts.append(f"full={full_name}")
            if linked_user:
                parts.append(f"user={linked_user}")
            if inj:
                parts.append(f"lesión={inj}")
            parts.append(f"acciones={acts}")
            self.stdout.write(" · ".join(parts))

        if do_list:
            players = list(Player.objects.filter(team=primary_team).order_by("name", "id"))
            for p in players:
                print_player_row(p)

        if find_query:
            q = slugify(find_query).replace("-", " ").strip()
            tokens = [t for t in re.split(r"\s+", q) if t]
            players = list(Player.objects.filter(team=primary_team).order_by("name", "id"))
            matches = []
            for p in players:
                hay = " ".join([slugify(p.name or ""), slugify(getattr(p, "full_name", "") or ""), slugify(getattr(p, "nickname", "") or "")])
                if any(tok in hay for tok in tokens):
                    matches.append(p)
            if not matches:
                self.stdout.write(self.style.WARNING("Sin resultados para --find."))
            else:
                for p in matches[:50]:
                    print_player_row(p)

        def auto_link(username: str):
            user = User.objects.filter(username__iexact=username).first()
            if not user:
                self.stdout.write(self.style.ERROR(f"Usuario no encontrado: {username}"))
                return
            AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_PLAYER})

            raw = re.sub(r"[\.\_\-]+", " ", str(username or "").strip())
            slug = slugify(raw).replace("-", " ").strip()
            tokens = [t for t in re.split(r"\s+", slug) if t and t not in {"jugador", "player"}]
            # evitar token "angel" porque es nombre común y provoca ambigüedad
            tokens = [t for t in tokens if t not in {"angel"}]

            players = list(Player.objects.filter(team=primary_team).order_by("name", "id"))
            scored = []
            for p in players:
                hay = " ".join([slugify(p.name or ""), slugify(getattr(p, "full_name", "") or ""), slugify(getattr(p, "nickname", "") or "")])
                score = sum(1 for t in tokens if t and t in hay)
                if score:
                    scored.append((score, p))
            scored.sort(key=lambda item: (-item[0], item[1].id))
            if not scored:
                self.stdout.write(self.style.ERROR(f"[auto] No encuentro jugador candidato para {username}. Usa --find o --link."))
                return
            best_score = scored[0][0]
            best = [p for s, p in scored if s == best_score]
            if len(best) != 1:
                self.stdout.write(self.style.ERROR(f"[auto] Ambiguo para {username}. Candidatos:"))
                for p in best[:10]:
                    print_player_row(p)
                self.stdout.write(self.style.ERROR("Usa --link username=player_id para fijarlo."))
                return
            player = best[0]
            spec = f"{username}={player.id}"
            _apply_link_spec(spec)

        def _apply_link_spec(spec: str):
            raw = str(spec or "").strip()
            if not raw or "=" not in raw:
                self.stdout.write(self.style.ERROR(f"--link inválido: {spec!r} (usa username=player_id)"))
                return
            username, player_id_raw = raw.split("=", 1)
            username = (username or "").strip()
            player_id_raw = (player_id_raw or "").strip()
            try:
                player_id = int(player_id_raw)
            except Exception:
                self.stdout.write(self.style.ERROR(f"--link inválido: {spec!r} (player_id debe ser numérico)"))
                return

            user = User.objects.filter(username__iexact=username).first()
            if not user:
                self.stdout.write(self.style.ERROR(f"Usuario no encontrado: {username}"))
                return

            AppUserRole.objects.update_or_create(user=user, defaults={"role": AppUserRole.ROLE_PLAYER})

            player = Player.objects.filter(id=player_id, team=primary_team).first()
            if not player:
                self.stdout.write(self.style.ERROR(f"Jugador no encontrado en el equipo principal: id={player_id}"))
                return

            existing_player_for_user = Player.objects.filter(team=primary_team, user=user).exclude(id=player.id).first()
            if existing_player_for_user and not force:
                self.stdout.write(
                    self.style.ERROR(
                        f"{username} ya está enlazado a Player id={existing_player_for_user.id} ({existing_player_for_user.name}). Usa --force para re-enlazar."
                    )
                )
                return

            existing_user_for_player = (
                Player.objects.filter(team=primary_team, id=player.id)
                .exclude(user__isnull=True)
                .exclude(user=user)
                .first()
            )
            if existing_user_for_player and not force:
                other_user = getattr(existing_user_for_player, "user", None)
                other_username = other_user.get_username() if other_user else "otro usuario"
                self.stdout.write(
                    self.style.ERROR(
                        f"Player id={player.id} ({player.name}) ya está enlazado a {other_username}. Usa --force para re-enlazar."
                    )
                )
                return

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

        for username in auto_users:
            auto_link(username)

        for spec in link_specs:
            _apply_link_spec(spec)

        if not (do_list or find_query or auto_users or link_specs):
            self.stdout.write(self.style.WARNING("Nada que hacer. Usa --list, --find, --auto o --link."))
