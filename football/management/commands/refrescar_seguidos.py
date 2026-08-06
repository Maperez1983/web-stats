"""Actualiza los datos de los equipos que el club sigue esta temporada.

Por qué existe: el agente semanal recorre la CLASIFICACIÓN de tu competición, así que un rival
de amistoso -que es justo lo que se acaba siguiendo- nunca se refrescaba. Sus números se
quedaban como el día que se importaron.

Fuentes, en cascada:
  - laPreferente: trae partidos, minutos, goles y tarjetas, pero SOLO responde desde una IP
    residencial, así que ese lado lo cubre el agente del Mac.
  - Universo RFAF: responde desde el servidor y trae partidos, titularidades, goles y tarjetas
    (no minutos). Es lo que usa este comando.

Se distinguen por el código: los de laPreferente empiezan por E (E1879), los de Universo son
numéricos (2749448).
"""

from django.core.management.base import BaseCommand

from football.models import RivalPlayer, SeasonWatch, Team
from football.universo_client import fetch_universo_team_stats


class Command(BaseCommand):
    help = 'Refresca desde Universo RFAF los equipos en seguimiento (y los de los jugadores seguidos).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Enseña qué haría y no guarda nada.')
        parser.add_argument('--equipo', default='', help='Refresca solo este id de equipo.')

    def _equipos_a_refrescar(self, solo_id=''):
        """Los equipos seguidos MÁS los equipos de los jugadores rivales seguidos.

        Si sigues a un jugador, lo que quieres ver actualizado son sus números, y esos vienen
        con la plantilla de su equipo: no tiene sentido pedirte que sigas también al equipo.
        """
        watches = SeasonWatch.objects.filter(is_active=True).select_related('team', 'rival_player__team')
        ids = set()
        for w in watches:
            if w.team_id:
                ids.add(int(w.team_id))
            elif w.rival_player_id and getattr(w.rival_player, 'team_id', None):
                ids.add(int(w.rival_player.team_id))
        if solo_id:
            try:
                ids = {int(solo_id)} & ids or {int(solo_id)}
            except (TypeError, ValueError):
                pass
        return list(Team.objects.filter(id__in=ids).order_by('name'))

    def handle(self, *args, **options):
        seco = bool(options['dry_run'])
        equipos = self._equipos_a_refrescar(options.get('equipo') or '')
        if not equipos:
            self.stdout.write('No hay nada en seguimiento.')
            return

        total_act = total_nuevos = 0
        for team in equipos:
            code = str(getattr(team, 'external_id', '') or '').strip()
            if not code:
                self.stdout.write(f'  · {team.display_name[:34]:34} sin código: no se puede refrescar')
                continue
            if code.upper().startswith('E'):
                self.stdout.write(f'  · {team.display_name[:34]:34} es de laPreferente: lo cubre el agente del Mac')
                continue
            try:
                filas = fetch_universo_team_stats(code)
            except Exception as exc:
                self.stdout.write(f'  · {team.display_name[:34]:34} error: {type(exc).__name__}')
                continue
            if not filas:
                self.stdout.write(f'  · {team.display_name[:34]:34} Universo no devolvió plantilla')
                continue

            act = nuevos = 0
            for fila in filas:
                if seco:
                    continue
                # Se casa por licencia si la hay, y si no por nombre: la licencia es estable,
                # el nombre puede venir escrito de otra forma.
                jugador = None
                if fila['source_player_id']:
                    jugador = RivalPlayer.objects.filter(
                        team=team, source_player_id=fila['source_player_id']
                    ).first()
                if jugador is None:
                    jugador = RivalPlayer.objects.filter(team=team, full_name__iexact=fila['full_name']).first()
                campos = {
                    'matches_played': fila['matches_played'],
                    'goals': fila['goals'],
                    'yellow_cards': fila['yellow_cards'],
                    'red_cards': fila['red_cards'],
                    'is_active': True,
                }
                if jugador is None:
                    RivalPlayer.objects.create(
                        team=team,
                        full_name=fila['full_name'],
                        source=RivalPlayer.SOURCE_UNIVERSO,
                        source_player_id=fila['source_player_id'],
                        number=fila['number'],
                        photo_url=fila['photo_url'][:300],
                        **campos,
                    )
                    nuevos += 1
                else:
                    for k, v in campos.items():
                        setattr(jugador, k, v)
                    if fila['number'] and not jugador.number:
                        jugador.number = fila['number']
                    if fila['photo_url'] and not jugador.photo_url:
                        jugador.photo_url = fila['photo_url'][:300]
                    jugador.save()
                    act += 1
            total_act += act
            total_nuevos += nuevos
            self.stdout.write(
                f'  · {team.display_name[:34]:34} {len(filas):3} jugadores'
                + ('  (prueba: no se ha guardado)' if seco else f'  {act} actualizados, {nuevos} nuevos')
            )

        self.stdout.write(f'\nEquipos: {len(equipos)} · actualizados {total_act} · nuevos {total_nuevos}')
