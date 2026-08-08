"""Arregla las tarjetas de biblioteca que no enseñan lo que deberían. Dos averías distintas.

La tarjeta pinta, por este orden: PORTADA, miniatura, PDF, dibujo.

1) PORTADAS PELADAS. Hay portadas que son sólo hierba: ni líneas, ni conos, ni fichas. Como la
   portada gana, esas tareas enseñan un rectángulo verde aunque debajo tengan su dibujo
   perfecto. A esas se les quita la portada y la tarjeta pasa a enseñar el dibujo. Si no hay
   nada debajo NO se tocan: un campo verde es feo, pero es mejor que un hueco gris, y esa tarea
   lo que necesita es que le regeneren la portada.

2) MINIATURAS QUE APUNTAN A UN FICHERO QUE NO EXISTE. Y varias apuntan al fichero de OTRA
   tarea: la 266 al de la 226, la 267 al de la 158. Son copias que heredaron la ruta del
   original. Se les borra la ruta rota; el endpoint de imagen reconstruye la miniatura desde
   el lienzo, que es justo lo que hace cuando no encuentra ninguna guardada.

    python3 manage.py arreglar_tarjetas_biblioteca                # sólo propone
    python3 manage.py arreglar_tarjetas_biblioteca --apply
    python3 manage.py arreglar_tarjetas_biblioteca --team 3 --apply
"""
import re

from django.core.management.base import BaseCommand

from football.library_repositories import is_library_session
from football.management.commands.revisar_miniaturas import datos_de_url, es_cesped_pelado
from football.models import SessionTask

CLAVE_META = "cover_image_embedded_v1"


def portada_de(tarea):
    """Los bytes de la portada, esté en su columna o -las viejas- dentro del JSON."""
    crudo = datos_de_url(getattr(tarea, "cover_data_b64", ""))
    if crudo:
        return crudo
    return datos_de_url(tarea.cover_embedded_url())


def tiene_algo_debajo(tarea):
    light = getattr(tarea, "task_layout_light", None)
    if isinstance(light, dict) and light.get("has_canvas"):
        return "dibujo"
    if getattr(tarea, "task_preview_image", None):
        return "miniatura"
    if getattr(tarea, "task_pdf", None):
        return "PDF"
    return ""


class Command(BaseCommand):
    help = "Quita las portadas que son campo pelado cuando debajo hay dibujo. No borra tareas."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe (por defecto sólo propone).")
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")
        parser.add_argument("--limite", type=int, default=0, help="Mirar sólo las N primeras.")

    def handle(self, *args, **options):
        aplicar = bool(options.get("apply"))
        equipo = int(options.get("team") or 0)
        limite = int(options.get("limite") or 0)

        qs = (
            SessionTask.objects.select_related("session__microcycle__team")
            .filter(deleted_at__isnull=True, cover_present=True)
        )
        if equipo:
            qs = qs.filter(session__microcycle__team_id=equipo)

        # --- 2) rutas de miniatura que no existen (se recorre aparte: otro filtro) ---
        rutas_rotas = []
        qs_mini = SessionTask.objects.select_related("session__microcycle__team").filter(
            deleted_at__isnull=True
        ).exclude(task_preview_image="")
        if equipo:
            qs_mini = qs_mini.filter(session__microcycle__team_id=equipo)
        for tarea in qs_mini.iterator():
            if not is_library_session(getattr(tarea, "session", None)):
                continue
            campo = tarea.task_preview_image
            try:
                campo.open("rb")
                try:
                    if not (campo.read(64) or b""):
                        rutas_rotas.append((tarea, "vacía"))
                finally:
                    try:
                        campo.close()
                    except Exception:
                        pass
            except Exception:
                rutas_rotas.append((tarea, "no existe"))

        se_quitan = []
        peladas_sin_nada = []
        buenas = 0
        miradas = 0
        for tarea in qs.iterator():
            if not is_library_session(getattr(tarea, "session", None)):
                continue
            if limite and miradas >= limite:
                break
            crudo = portada_de(tarea)
            if not crudo:
                continue
            miradas += 1
            if not es_cesped_pelado(crudo):
                buenas += 1
                continue
            debajo = tiene_algo_debajo(tarea)
            if debajo:
                se_quitan.append((tarea, debajo))
            else:
                peladas_sin_nada.append(tarea)

        self.stdout.write(self.style.SUCCESS(f"\nPortadas miradas: {miradas}"))
        self.stdout.write(f"  {buenas:>5}  enseñan algo (se quedan)")
        self.stdout.write(f"  {len(se_quitan):>5}  peladas CON dibujo debajo  <-- se les quita la portada")
        self.stdout.write(f"  {len(peladas_sin_nada):>5}  peladas y sin nada debajo (no se tocan: habría que regenerarlas)")

        for tarea, debajo in se_quitan[:30]:
            self.stdout.write(f'  {tarea.id:>6}  pasa a enseñar su {debajo:9s}  {str(tarea.title or "")[:48]}')
        if len(se_quitan) > 30:
            self.stdout.write(f"  … y {len(se_quitan) - 30} más")

        if peladas_sin_nada:
            self.stdout.write("\n  ids de las que se quedarían con la portada verde (para regenerar):")
            self.stdout.write("  " + ", ".join(str(t.id) for t in peladas_sin_nada[:60]))

        if rutas_rotas:
            self.stdout.write(self.style.SUCCESS(
                f"\nMiniaturas que apuntan a un fichero que no está: {len(rutas_rotas)}"
            ))
            self.stdout.write("  (se les borra la ruta; la imagen se reconstruye desde el lienzo)")
            for tarea, motivo in rutas_rotas[:20]:
                ruta = str(getattr(tarea.task_preview_image, "name", "") or "")
                # Sólo es "de otra tarea" si el nombre lleva un id DISTINTO. El primer esquema de
                # nombres era `task-preview-<hash>` y no llevaba id ninguno: decir de esos que son
                # de otra tarea es acusar a los datos de algo que no ha pasado.
                otro = re.search(r"task-(\d+)-", ruta)
                pista = ""
                if otro and int(otro.group(1)) != int(tarea.id):
                    pista = f"  <-- es la miniatura de la tarea {otro.group(1)}"
                elif not otro:
                    pista = "  (nombre antiguo, sin id)"
                self.stdout.write(f"  {tarea.id:>6}  {motivo:9s}  {ruta}{pista}")

        if not aplicar:
            self.stdout.write(self.style.WARNING("\nPropuesta: nada escrito. Repite con --apply."))
            return

        for tarea, _ in rutas_rotas:
            SessionTask.objects.filter(id=tarea.id).update(task_preview_image="")
        if rutas_rotas:
            self.stdout.write(self.style.SUCCESS(f"Rutas rotas limpiadas: {len(rutas_rotas)}"))

        escritas = 0
        for tarea, _ in se_quitan:
            cambios = {"cover_present": False, "cover_data_b64": ""}
            # La portada vieja puede estar DENTRO del JSON: si se deja ahí, la tarjeta la sigue
            # dando por buena y no habríamos arreglado nada.
            layout = tarea.tactical_layout if isinstance(tarea.tactical_layout, dict) else None
            meta = layout.get("meta") if isinstance(layout, dict) and isinstance(layout.get("meta"), dict) else None
            if meta and CLAVE_META in meta:
                nuevo_meta = {k: v for k, v in meta.items() if k != CLAVE_META}
                cambios["tactical_layout"] = {**layout, "meta": nuevo_meta}
            light = tarea.task_layout_light if isinstance(tarea.task_layout_light, dict) else None
            meta_light = light.get("meta") if isinstance(light, dict) and isinstance(light.get("meta"), dict) else None
            if meta_light and CLAVE_META in meta_light:
                cambios["task_layout_light"] = {
                    **light, "meta": {k: v for k, v in meta_light.items() if k != CLAVE_META}
                }
            # update() y no save(): save() vuelve a derivar task_family del JSON y las tareas
            # catalogadas a mano llevan el tipo en la columna, no en el JSON.
            SessionTask.objects.filter(id=tarea.id).update(**cambios)
            escritas += 1

        self.stdout.write(self.style.SUCCESS(f"\nAplicado: {escritas} tarjetas pasan a enseñar su dibujo."))
