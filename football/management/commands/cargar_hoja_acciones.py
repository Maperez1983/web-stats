"""Carga en un partido la hoja de acciones que el entrenador apuntó a mano.

Está pensado para los partidos que ya se jugaron y sólo existen en papel: el once
inicial sale del sistema, los cambios se declaran en el fichero, y de ahí salen los
minutos de cada jugador. Las acciones se guardan igual que si se hubieran capturado
en vivo (misma fuente, misma taxonomía), así que el acta y las fichas las ven.

    python3 manage.py cargar_hoja_acciones data/input/hoja_mosca.json
    python3 manage.py cargar_hoja_acciones data/input/hoja_mosca.json --confirmar

Sin --confirmar no escribe nada: enseña lo que haría.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from football.models import Match, MatchEvent, Player, Team

FUENTE = "registro-acciones"
SISTEMA = "touch-field"


class Command(BaseCommand):
    help = "Carga una hoja de acciones de un partido ya jugado (once del sistema + cambios declarados)."

    def add_arguments(self, parser):
        parser.add_argument("fichero", help="JSON con el partido, los cambios y las acciones por jugador.")
        parser.add_argument("--confirmar", action="store_true", help="Escribe de verdad. Sin esto sólo enseña.")
        parser.add_argument("--rehacer", action="store_true", help="Borra antes lo que ya hubiera de esta carga.")

    def handle(self, *args, **opciones):
        with open(opciones["fichero"], "r", encoding="utf-8") as f:
            hoja = json.load(f)

        equipo = self._equipo(hoja)
        partido = self._partido(hoja, equipo)
        plantilla = self._plantilla(equipo, hoja)
        once = self._once(partido, equipo, plantilla, hoja)
        cambios = self._con_el_descanso(hoja, once)

        minutos, tramos = self._minutos(once, cambios, int(hoja.get("duracion") or 90))
        acciones = self._acciones(hoja, plantilla, minutos, tramos, int(hoja.get("duracion") or 90))

        self.stdout.write(f"Partido: {partido}")
        self.stdout.write(f"Once inicial ({len(once)}): " + ", ".join(sorted(j.name for j in once)))
        for cambio in cambios:
            self.stdout.write(f"  {cambio['minuto']}'  sale {cambio['sale']}  ·  entra {cambio['entra']}")
        self.stdout.write("")
        for nombre in sorted(minutos):
            self.stdout.write(f"  {nombre:<16} {minutos[nombre]:>3}'   {acciones['por_jugador'].get(nombre, 0):>3} acciones")
        sin_minutos = sorted(acciones["sin_minutos"])
        if sin_minutos:
            self.stdout.write(self.style.WARNING(
                "\nSin minutos (no salen en el once ni en los cambios): " + ", ".join(sin_minutos)
            ))
        self.stdout.write(f"\nEventos a crear: {len(acciones['eventos'])}")

        if not opciones["confirmar"]:
            self.stdout.write(self.style.WARNING("Ensayo. Vuelve con --confirmar para escribirlo."))
            return

        with transaction.atomic():
            if opciones["rehacer"]:
                borrados = MatchEvent.objects.filter(
                    match=partido, source_file=FUENTE, raw_data__hoja=hoja.get("id") or "hoja"
                ).delete()
                self.stdout.write(f"Borrados de una carga anterior: {borrados[0]}")
            MatchEvent.objects.bulk_create(acciones["eventos"])
        self.stdout.write(self.style.SUCCESS(f"Cargadas {len(acciones['eventos'])} acciones en {partido}."))

    # ------------------------------------------------------------------ piezas

    def _equipo(self, hoja):
        equipo = Team.objects.filter(slug=hoja["equipo"]).first() or Team.objects.filter(name=hoja["equipo"]).first()
        if not equipo:
            raise CommandError(f"No encuentro el equipo {hoja['equipo']!r}")
        return equipo

    def _partido(self, hoja, equipo):
        partido = Match.objects.filter(id=hoja.get("partido_id")).first() if hoja.get("partido_id") else None
        if not partido:
            raise CommandError("Dime el partido con 'partido_id'.")
        if equipo.id not in {partido.home_team_id, partido.away_team_id}:
            raise CommandError("Ese partido no es de ese equipo.")
        return partido

    def _plantilla(self, equipo, hoja):
        por_nombre = {}
        for jugador in Player.objects.filter(team=equipo):
            por_nombre[jugador.name.strip().lower()] = jugador
        alias = hoja.get("alias") or {}
        for mote, real in alias.items():
            jugador = por_nombre.get(str(real).strip().lower())
            if jugador:
                por_nombre[str(mote).strip().lower()] = jugador
        return por_nombre

    def _once(self, partido, equipo, plantilla, hoja):
        """El once inicial sale del sistema; el fichero sólo puede darlo si aún no está guardado."""
        from football.views import _stored_lineup_for_match

        guardado = _stored_lineup_for_match(equipo, partido) or {}
        ids = [str(fila.get("id")) for fila in (guardado.get("starters") or []) if fila.get("id")]
        if ids:
            por_id = {str(j.id): j for j in Player.objects.filter(id__in=ids)}
            return [por_id[i] for i in ids if i in por_id]
        nombres = hoja.get("once") or []
        if not nombres:
            raise CommandError("No hay once guardado para ese partido y el fichero tampoco lo trae.")
        once = []
        for nombre in nombres:
            jugador = plantilla.get(str(nombre).strip().lower())
            if not jugador:
                raise CommandError(f"No encuentro en la plantilla a {nombre!r}")
            once.append(jugador)
        return once

    def _con_el_descanso(self, hoja, once):
        """Completa la tanda del descanso.

        En un partido de base la mayoría de cambios se hacen todos juntos en el descanso y
        nadie apunta quién salió por quién: eso da igual, porque no cambia los minutos de
        nadie. Lo que sí se sabe es quién jugó una parte. Así que salen los del once que
        jugaron sólo 45', entran los que tienen acciones sin haber salido de inicio, y se
        emparejan por orden.
        """
        cambios = list(hoja.get("cambios") or [])
        descanso = hoja.get("descanso")
        minutos = hoja.get("minutos") or {}
        if not descanso or not minutos:
            return cambios

        nombres_once = {j.name for j in once}
        entran_despues = {c["entra"] for c in cambios}
        # Quien sale de inicio y luego "vuelve a entrar" tuvo que salir antes: sale en el descanso.
        salen = [
            n for n in nombres_once
            if n in entran_despues or (int(minutos.get(n, 0)) and int(minutos[n]) <= int(descanso))
        ]
        entran = [
            n for n in (hoja.get("acciones") or {})
            if n not in nombres_once and n not in entran_despues and int(minutos.get(n, 0)) >= int(descanso)
        ]
        salen.sort()
        entran.sort()
        for sale, entra in zip(salen, entran):
            cambios.append({"minuto": int(descanso), "sale": sale, "entra": entra, "supuesto": True})
        sobran = salen[len(entran):] + entran[len(salen):]
        if sobran:
            self.stdout.write(self.style.WARNING(
                "En el descanso no cuadran las entradas con las salidas: " + ", ".join(sobran)
            ))
        return cambios

    def _minutos(self, once, cambios, duracion):
        """Tramos de cada uno: entra cuando entra y sale cuando sale.

        Devuelve (minutos, tramos). Los tramos importan tanto como el total: una acción de
        quien entró en el 65 no puede quedar apuntada en el minuto 9.
        """
        dentro = {j.name: 0 for j in once}
        minutos = {}
        tramos = {}
        for cambio in sorted(cambios, key=lambda c: int(c["minuto"])):
            minuto = int(cambio["minuto"])
            sale, entra = cambio["sale"], cambio["entra"]
            if sale in dentro:
                desde = dentro.pop(sale)
                minutos[sale] = minutos.get(sale, 0) + (minuto - desde)
                tramos.setdefault(sale, []).append((desde, minuto))
            dentro[entra] = minuto
        for nombre, desde in dentro.items():
            minutos[nombre] = minutos.get(nombre, 0) + (duracion - desde)
            tramos.setdefault(nombre, []).append((desde, duracion))
        return minutos, tramos

    def _acciones(self, hoja, plantilla, minutos, tramos, duracion):
        """Reparte las acciones de cada jugador dentro de los minutos que estuvo en el campo."""
        eventos = []
        por_jugador = {}
        sin_minutos = set()
        for nombre, lineas in (hoja.get("acciones") or {}).items():
            jugador = plantilla.get(str(nombre).strip().lower())
            if not jugador:
                raise CommandError(f"No encuentro en la plantilla a {nombre!r}")
            jugados = minutos.get(nombre)
            if not jugados:
                sin_minutos.add(nombre)
            total = sum(int(linea.get("veces") or 1) for linea in lineas)
            por_jugador[nombre] = total
            i = 0
            for linea in lineas:
                for _ in range(int(linea.get("veces") or 1)):
                    i += 1
                    # Sin minuto exacto en la hoja, se reparten por el tiempo que jugó: no inventa
                    # un minuto falso, sólo coloca la acción dentro de su tramo real.
                    minuto = self._minuto_de(tramos.get(nombre), i, total, duracion)
                    eventos.append(MatchEvent(
                        match_id=hoja["partido_id"],
                        player=jugador,
                        minute=minuto,
                        period=1 if minuto < duracion / 2 else 2,
                        event_type=linea["accion"],
                        result=linea.get("resultado", ""),
                        zone=linea.get("zona", ""),
                        tercio="",
                        observation=linea.get("nota", ""),
                        source_file=FUENTE,
                        system=SISTEMA,
                        raw_data={"team_side": "for", "hoja": hoja.get("id") or "hoja"},
                    ))
        return {"eventos": eventos, "por_jugador": por_jugador, "sin_minutos": sin_minutos}

    def _minuto_de(self, tramos, i, total, duracion):
        """Reparte la acción i-ésima dentro del tiempo REAL que ese jugador estuvo en el campo."""
        if not tramos:
            tramos = [(0, duracion)]
        jugado = sum(hasta - desde for desde, hasta in tramos) or 1
        # posición proporcional dentro de todo lo que jugó, y de ahí al tramo que le toca
        avance = (jugado * i) / float(total + 1)
        for desde, hasta in tramos:
            dura = hasta - desde
            if avance <= dura:
                return int(desde + avance)
            avance -= dura
        return int(tramos[-1][1]) - 1
