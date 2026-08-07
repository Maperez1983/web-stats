"""Pone TIPO DE ENTRENO a las tareas de biblioteca que no lo tienen.

Las 179 del PPT de Aitor se catalogaron leyendo diapositiva a diapositiva y estan al 100%. Las
otras dos bibliotecas no: quedan tareas sin `task_family`, y esas NO salen en ninguna carpeta —
solo entrando por "Todos los tipos".

Se clasifica por el TEXTO de la tarea (titulo, objetivo, consignas, reglas). No por la geometria
del dibujo: en este proyecto eso ya fallo 12 de 14 veces. Y lo que no esta claro se deja sin tipo:
mejor una tarea en "Todos los tipos" que una tarea mal archivada.

Uso:
    python3 manage.py catalogar_tareas_sin_tipo                 # solo propone
    python3 manage.py catalogar_tareas_sin_tipo --apply
    python3 manage.py catalogar_tareas_sin_tipo --team 1 --apply
"""
import re
import unicodedata

from django.core.management.base import BaseCommand

from football.library_repositories import is_library_session
from football.models import SessionTask

# Orden IMPORTANTE: se comprueba de arriba abajo y gana la primera. Lo mas especifico primero,
# porque "partido condicionado" contiene "partido" y "rueda de pases" contiene "pases".
REGLAS = [
    ("finalizacion", [
        "finalizacion", "finalizar", "remate", "definicion", "tiro a puerta", "disparo",
        "abp", "balon parado", "corner", "saque de esquina", "falta directa", "penalti", "estrategia",
    ]),
    ("transicion", [
        "transicion", "contraataque", "contra ataque", "repliegue", "tras perdida",
        "tras recuperacion", "robo y ataque", "basculacion",
    ]),
    ("circuito", [
        "rueda de pases", "rueda", "circuito", "oleada", "estaciones", "pasar y seguir",
        "secuencia de pases",
    ]),
    ("rondo", [
        "rondo", "posesion", "conservacion", "mantenimiento del balon", "6x2", "5x2", "4x2", "6 x 2",
    ]),
    ("posicion", [
        "juego de posicion", "salida de balon", "progresion", "superioridad", "amplitud",
        "entre lineas", "tercer hombre", "circulacion",
    ]),
    ("partido", [
        "partido", "amistoso", "juego real", "11 vs 11", "11vs11", "situacion real", "partidillo",
    ]),
    ("estructural", [
        "fisico", "preparacion fisica", "resistencia", "fuerza", "velocidad", "coordinacion",
        "activacion", "calentamiento", "estiramiento", "prevencion", "movilidad", "core",
    ]),
]


def sin_tildes(texto):
    t = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def texto_de(tarea):
    trozos = [
        getattr(tarea, "title", ""),
        getattr(tarea, "objective", ""),
        getattr(tarea, "coaching_points", ""),
        getattr(tarea, "confrontation_rules", ""),
    ]
    layout = tarea.tactical_layout if isinstance(tarea.tactical_layout, dict) else {}
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    analysis = meta.get("analysis") if isinstance(meta.get("analysis"), dict) else {}
    hoja = analysis.get("task_sheet") if isinstance(analysis.get("task_sheet"), dict) else {}
    for clave in ("description", "coaching", "rules", "organization"):
        trozos.append(hoja.get(clave) or "")
    return sin_tildes(" ".join(str(x) for x in trozos))


def clasificar(tarea):
    """Devuelve (familia, palabra, competidoras).

    Si encajan DOS familias ("Rueda de pases con finalizacion", "Circuito de fuerza") no se elige
    en silencio por el orden de las reglas: se marca como dudosa para que la decida una persona.
    Archivar mal es peor que no archivar.
    """
    texto = texto_de(tarea)
    if not texto.strip():
        return None, "", []
    encajes = []
    for familia, palabras in REGLAS:
        for palabra in palabras:
            # \b para que "core" no encaje dentro de "recorrido"
            if re.search(r"\b" + re.escape(palabra), texto):
                encajes.append((familia, palabra))
                break
    if not encajes:
        return None, "", []
    if len(encajes) == 1:
        return encajes[0][0], encajes[0][1], []
    return None, "", encajes


class Command(BaseCommand):
    help = "Pone tipo de entreno a las tareas de biblioteca que no lo tienen (por su texto)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe (por defecto solo propone).")
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")

    def handle(self, *args, **options):
        aplicar = bool(options.get("apply"))
        solo_equipo = int(options.get("team") or 0)

        qs = SessionTask.objects.select_related("session__microcycle").filter(
            deleted_at__isnull=True
        ).exclude(task_family__gt="")
        if solo_equipo:
            qs = qs.filter(session__microcycle__team_id=solo_equipo)

        propuestas = {}
        sin_clasificar = []
        dudosas = []
        for tarea in qs.iterator():
            if not is_library_session(getattr(tarea, "session", None)):
                continue
            familia, palabra, encajes = clasificar(tarea)
            if familia:
                propuestas.setdefault(familia, []).append((tarea, palabra))
            elif encajes:
                dudosas.append((tarea, encajes))
            else:
                sin_clasificar.append(tarea)

        total = sum(len(v) for v in propuestas.values())
        for familia, filas in sorted(propuestas.items(), key=lambda kv: -len(kv[1])):
            self.stdout.write(self.style.SUCCESS(f"\n=== {familia} · {len(filas)} tareas ==="))
            for tarea, palabra in filas[:200]:
                self.stdout.write(f'  {tarea.id:>5}  «{palabra}»  {str(tarea.title or "")[:58]}')

        if dudosas:
            self.stdout.write(self.style.WARNING(f"\n=== DUDOSAS · {len(dudosas)} (encajan en varios tipos) ==="))
            self.stdout.write("  (no las toco: dime tu cual es y las pongo)")
            for tarea, encajes in dudosas[:200]:
                cuales = " / ".join(f"{f}«{p}»" for f, p in encajes)
                self.stdout.write(f'  {tarea.id:>5}  {str(tarea.title or "")[:44]:44s} -> {cuales}')

        if sin_clasificar:
            self.stdout.write(self.style.WARNING(f"\n=== SIN CLASIFICAR · {len(sin_clasificar)} ==="))
            self.stdout.write("  (se quedan sin tipo a proposito: mejor eso que archivarlas mal)")
            for tarea in sin_clasificar[:200]:
                self.stdout.write(f'  {tarea.id:>5}  {str(tarea.title or "")[:64]}')

        self.stdout.write("")
        self.stdout.write(f"se catalogarian : {total}")
        self.stdout.write(f"dudosas         : {len(dudosas)}")
        self.stdout.write(f"se quedan fuera : {len(sin_clasificar)}")

        if not aplicar:
            self.stdout.write(self.style.WARNING("Propuesta: nada escrito. Repite con --apply."))
            return

        escritas = 0
        for familia, filas in propuestas.items():
            ids = [t.id for t, _ in filas]
            # update() y no save(): save() DERIVA task_family del JSON y borraria lo que ponemos.
            escritas += SessionTask.objects.filter(id__in=ids).update(task_family=familia)
        self.stdout.write(self.style.SUCCESS(f"Aplicado: {escritas} tareas catalogadas."))
