"""¿De dónde salen las tareas que la biblioteca llama "Interactivas"?

El entrenador no ha creado ninguna tarea interactiva y le salen por cientos. Este comando NO
toca nada: sólo dice quién las metió ahí, contando por el `source` que cada tarea lleva en su
metadata y enseñando una muestra de títulos.

Sospecha principal: guardar una jugada desde Táctica (api/tactical-playbook/tasks/save/) archiva
la jugada en la biblioteca con repository="interactive" y source="tactics-playbook". O sea que
serían sus jugadas de la pizarra, guardadas bajo un nombre que él nunca eligió.

    python3 manage.py revisar_interactivas
    python3 manage.py revisar_interactivas --team 3
"""
from django.core.management.base import BaseCommand

from football.library_repositories import (
    LIBRARY_REPOSITORY_CHOICES,
    LIBRARY_REPOSITORY_INTERACTIVE,
    is_library_session,
    library_repository_for_session,
    normalize_library_repository,
)
from football.models import SessionTask


def repo_de(tarea):
    """Igual que en el listado: copia ligera primero y, si no dice nada, la sesión."""
    light = getattr(tarea, "task_layout_light", None)
    meta = light.get("meta") if isinstance(light, dict) and isinstance(light.get("meta"), dict) else {}
    repo = normalize_library_repository(
        meta.get("repository") or meta.get("library_repo") or meta.get("library_repository"),
        fallback="",
    )
    if repo in LIBRARY_REPOSITORY_CHOICES:
        return repo, "metadata de la tarea"
    return library_repository_for_session(getattr(tarea, "session", None)), "la sesión que la aloja"


class Command(BaseCommand):
    help = 'Explica de dónde salen las tareas que la biblioteca llama "Interactivas". No escribe nada.'

    def add_arguments(self, parser):
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")
        parser.add_argument("--muestra", type=int, default=12, help="Cuántos títulos enseñar.")

    def handle(self, *args, **options):
        equipo = int(options.get("team") or 0)
        muestra = int(options.get("muestra") or 12)

        qs = (
            SessionTask.objects.select_related("session__microcycle__team")
            .filter(deleted_at__isnull=True)
            .defer("tactical_layout", "preview_data_b64", "cover_data_b64")
        )
        if equipo:
            qs = qs.filter(session__microcycle__team_id=equipo)

        por_origen = {}
        por_equipo = {}
        por_via = {}
        ejemplos = []
        total = 0
        for tarea in qs.iterator():
            if not is_library_session(getattr(tarea, "session", None)):
                continue
            repo, via = repo_de(tarea)
            if repo != LIBRARY_REPOSITORY_INTERACTIVE:
                continue
            total += 1
            light = getattr(tarea, "task_layout_light", None)
            meta = light.get("meta") if isinstance(light, dict) and isinstance(light.get("meta"), dict) else {}
            origen = str(meta.get("source") or "").strip() or "(sin source)"
            por_origen[origen] = por_origen.get(origen, 0) + 1
            por_via[via] = por_via.get(via, 0) + 1
            eq = getattr(getattr(getattr(tarea, "session", None), "microcycle", None), "team", None)
            nombre_eq = str(getattr(eq, "name", "") or getattr(eq, "display_name", "") or f"equipo {getattr(eq, 'id', '?')}")
            por_equipo[nombre_eq] = por_equipo.get(nombre_eq, 0) + 1
            if len(ejemplos) < muestra:
                ejemplos.append((tarea.id, origen, str(tarea.title or "")[:56], nombre_eq))

        self.stdout.write(self.style.SUCCESS(f"\nTareas que salen como INTERACTIVAS: {total}"))

        self.stdout.write("\n=== quién las marcó así ===")
        for via, n in sorted(por_via.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"  {n:>5}  {via}")

        self.stdout.write("\n=== de dónde vienen (meta.source) ===")
        for origen, n in sorted(por_origen.items(), key=lambda kv: -kv[1]):
            pista = ""
            if origen == "tactics-playbook":
                pista = "  <-- jugadas guardadas desde Táctica"
            elif origen == "(sin source)":
                pista = "  <-- no lo dicen; lo marca la sesión de biblioteca interactiva"
            self.stdout.write(f"  {n:>5}  {origen}{pista}")

        self.stdout.write("\n=== por equipo ===")
        for eq, n in sorted(por_equipo.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"  {n:>5}  {eq}")

        if ejemplos:
            self.stdout.write("\n=== muestra ===")
            for tid, origen, titulo, eq in ejemplos:
                self.stdout.write(f"  {tid:>6}  [{origen}]  {titulo}  ({eq})")

        self.stdout.write("\nEste comando no ha escrito nada.")
