"""¿Estas tareas tienen dibujo de verdad, o el lienzo también está vacío? No escribe nada.

Al quitarles la portada pelada, la tarjeta pasó a pedir la miniatura... y sigue saliendo verde.
O sea que el problema está más abajo. Hay tres sitios donde puede estar la imagen y hay que
mirarlos por separado, porque el arreglo de cada caso es distinto:

  - el LIENZO (los objetos guardados). Si tiene fichas y conos, el dibujo existe y sólo hay que
    volver a renderizarlo.
  - la miniatura EMBEBIDA (`preview_data_b64`), que es lo que sirve el endpoint cuando no hay
    fichero. Si está pelada, es la que dejó vacía la regeneración masiva de la otra vez.
  - el fichero de miniatura.

    python3 manage.py revisar_dibujo --ids 628,612,609,599
    python3 manage.py revisar_dibujo --team 3 --limite 40
"""
from django.core.management.base import BaseCommand

from football.library_repositories import is_library_session
from football.management.commands.revisar_miniaturas import datos_de_url, es_cesped_pelado
from football.models import SessionTask


def cuenta_objetos(tarea):
    """Cuántas cosas hay dibujadas en el lienzo (fichas, conos, flechas)."""
    layout = tarea.tactical_layout if isinstance(tarea.tactical_layout, dict) else {}
    meta = layout.get("meta") if isinstance(layout.get("meta"), dict) else {}
    graphic = meta.get("graphic_editor") if isinstance(meta.get("graphic_editor"), dict) else {}
    estado = graphic.get("canvas_state") if isinstance(graphic.get("canvas_state"), dict) else {}
    objetos = estado.get("objects") if isinstance(estado.get("objects"), list) else []
    sueltos = layout.get("tokens") if isinstance(layout.get("tokens"), list) else []
    return len(objetos), len(sueltos)


class Command(BaseCommand):
    help = "Dice si una tarea tiene dibujo de verdad y qué imagen guardada tiene. No escribe nada."

    def add_arguments(self, parser):
        parser.add_argument("--ids", default="", help="Lista de ids separados por coma.")
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")
        parser.add_argument("--limite", type=int, default=25, help="Cuántas mirar si no das ids.")

    def handle(self, *args, **options):
        ids = [int(x) for x in str(options.get("ids") or "").replace(" ", "").split(",") if x.isdigit()]
        equipo = int(options.get("team") or 0)
        limite = max(1, int(options.get("limite") or 25))

        qs = SessionTask.objects.select_related("session__microcycle__team").filter(deleted_at__isnull=True)
        if ids:
            qs = qs.filter(id__in=ids)
        else:
            if equipo:
                qs = qs.filter(session__microcycle__team_id=equipo)
            qs = qs.filter(cover_present=False)

        self.stdout.write("")
        self.stdout.write(f'{"id":>6}  {"objetos":>7}  {"embebida":>18}  {"fichero":>10}  título')
        self.stdout.write("  " + "-" * 76)

        resumen = {"con_dibujo": 0, "sin_dibujo": 0, "embebida_pelada": 0, "sin_imagen": 0}
        mirados = 0
        for tarea in qs.iterator():
            if not is_library_session(getattr(tarea, "session", None)):
                continue
            if not ids and mirados >= limite:
                break
            mirados += 1

            objetos, tokens = cuenta_objetos(tarea)
            if objetos or tokens:
                resumen["con_dibujo"] += 1
            else:
                resumen["sin_dibujo"] += 1

            crudo = datos_de_url(getattr(tarea, "preview_data_b64", "") or tarea.preview_embedded_url())
            if not crudo:
                estado_embebida = "no tiene"
                resumen["sin_imagen"] += 1
            elif es_cesped_pelado(crudo):
                estado_embebida = "PELADA"
                resumen["embebida_pelada"] += 1
            else:
                estado_embebida = f"ok ({len(crudo)//1024} KB)"

            fichero = "sí" if getattr(tarea, "task_preview_image", None) else "no"
            self.stdout.write(
                f'{tarea.id:>6}  {objetos:>3}+{tokens:<3}  {estado_embebida:>18}  {fichero:>10}  '
                f'{str(tarea.title or "")[:34]}'
            )

        self.stdout.write("")
        self.stdout.write(f'  {resumen["con_dibujo"]:>5}  tienen objetos en el lienzo (el dibujo EXISTE)')
        self.stdout.write(f'  {resumen["sin_dibujo"]:>5}  el lienzo está vacío de verdad')
        self.stdout.write(f'  {resumen["embebida_pelada"]:>5}  su miniatura embebida es campo pelado')
        self.stdout.write(f'  {resumen["sin_imagen"]:>5}  no tienen miniatura embebida')
        self.stdout.write("\nEste comando no ha escrito nada.")
