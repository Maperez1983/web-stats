"""Manda a su temporada de verdad las sesiones anteriores al arranque de la pretemporada.

La temporada 2026/2027 se dio de alta empezando el 1 de julio, pero la pretemporada del club
arrancó el 21 de julio. Las sesiones con fecha anterior son de la temporada pasada y estaban
apareciendo mezcladas con las de esta.

La sesión se manda a la temporada del workspace **que contiene su fecha**; si ninguna la contiene,
a la última que termina antes del corte. Nunca se inventa una temporada ni se mueve hacia delante:
si la que toca es la que ya tiene, se deja en paz.

Se saltan las sesiones de BIBLIOTECA y de PAPELERA (`exclude_library_sessions_qs`): la biblioteca
cuelga de un microciclo centinela con fecha del año 2000, y moverlo de temporada rompería el
repositorio de tareas. No se usa "es del año 2000" como regla: se usa el filtro del propio proyecto.

Las tareas de la sesión llevan su propia `club_season` heredada, así que viajan con ella.

Uso:
    python3 manage.py sanear_sesiones_por_temporada                      # solo informa
    python3 manage.py sanear_sesiones_por_temporada --apply
    python3 manage.py sanear_sesiones_por_temporada --corte 2026-07-21 --apply
"""
from datetime import date, datetime

from django.core.management.base import BaseCommand

from football.library_repositories import exclude_library_sessions_qs
from football.models import SessionTask, TrainingSession, Workspace, WorkspaceSeason, WorkspaceTeam

CORTE_POR_DEFECTO = date(2026, 7, 21)


class Command(BaseCommand):
    help = "Manda a su temporada las sesiones anteriores al arranque de la pretemporada."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Escribe (por defecto solo informa).")
        parser.add_argument("--corte", default="", help="Fecha de arranque, AAAA-MM-DD. Por defecto 2026-07-21.")
        parser.add_argument("--team", type=int, default=0, help="Limitar a un equipo.")

    def handle(self, *args, **options):
        aplicar = bool(options.get("apply"))
        solo_equipo = int(options.get("team") or 0)
        corte_raw = str(options.get("corte") or "").strip()
        if corte_raw:
            try:
                corte = datetime.strptime(corte_raw, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.ERROR("--corte debe ser AAAA-MM-DD."))
                return
        else:
            corte = CORTE_POR_DEFECTO

        self.stdout.write(f"Corte: sesiones anteriores a {corte.isoformat()}")
        self.stdout.write("")

        # El workspace de una sesión se resuelve por su EQUIPO, no por su club_season: justamente
        # la club_season es lo que puede estar mal.
        equipo_a_workspace = {}
        for link in WorkspaceTeam.objects.select_related("workspace", "team"):
            equipo_a_workspace.setdefault(link.team_id, link.workspace)
        # Un equipo puede colgar del club sólo como `primary_team`, sin fila en WorkspaceTeam.
        # Sin esto sus sesiones se quedaban sin temporada destino y no se saneaba ninguna.
        for workspace in Workspace.objects.exclude(primary_team__isnull=True).select_related("primary_team"):
            equipo_a_workspace.setdefault(workspace.primary_team_id, workspace)

        temporadas_por_workspace = {}
        for temporada in WorkspaceSeason.objects.all().order_by("workspace_id", "start_date"):
            temporadas_por_workspace.setdefault(temporada.workspace_id, []).append(temporada)

        def contiene(t, fecha):
            return t.start_date <= fecha <= (t.end_date or date(9999, 12, 31))

        def temporada_que_toca(workspace, fecha):
            """La temporada de verdad de una sesión anterior al corte.

            Normalmente es la que contiene su fecha. Pero la temporada nueva se dio de alta
            empezando el 1 de julio y la pretemporada arrancó el 21: una sesión del 10 de julio
            "cae dentro" de la nueva y sin embargo es de la vieja. Por eso, si la temporada que
            contiene la fecha es la MISMA que contiene el corte, se manda a la anterior. Una
            sesión de hace dos años no se toca: su temporada ya es la correcta.
            """
            temporadas = temporadas_por_workspace.get(getattr(workspace, "id", None)) or []
            if not temporadas:
                return None
            # Anterior a la PRIMERA temporada del club no hay "temporada anterior" a la que
            # mandarla: eso no es una sesión de entrenamiento, es un centinela del sistema (la
            # biblioteca cuelga de una con fecha del año 2000). Se deja en paz. Esto es lo que de
            # verdad protege, porque no depende de cómo esté nombrada.
            if fecha < temporadas[0].start_date:
                return None
            del_corte = next((t for t in temporadas if contiene(t, corte)), None)
            contenedora = next((t for t in temporadas if contiene(t, fecha)), None)
            if contenedora and (del_corte is None or contenedora.id != del_corte.id):
                return contenedora
            referencia = del_corte or contenedora
            anteriores = [t for t in temporadas if t.start_date < (referencia.start_date if referencia else corte)]
            return anteriores[-1] if anteriores else None

        qs = TrainingSession.objects.select_related("microcycle__team", "club_season").filter(
            session_date__lt=corte
        )
        if solo_equipo:
            qs = qs.filter(microcycle__team_id=solo_equipo)
        qs = exclude_library_sessions_qs(qs)
        # `exclude_library_sessions_qs` sólo mira el MICROCICLO, y en producción hay sesiones de
        # biblioteca cuyo microciclo no lleva la marca: lo único que las delata es su propio
        # `focus` ("Biblioteca de Aitor"). Sin esto, la simulación proponía mover la biblioteca
        # del Senior. Se excluyen también aquí.
        qs = qs.exclude(focus__istartswith="Biblioteca").exclude(focus__istartswith="Papelera")

        movidas = 0
        sin_temporada = 0
        ya_correctas = 0
        tareas_movidas = 0

        for sesion in qs.order_by("session_date", "id"):
            equipo = getattr(getattr(sesion, "microcycle", None), "team", None)
            workspace = equipo_a_workspace.get(getattr(equipo, "id", None))
            destino = temporada_que_toca(workspace, sesion.session_date)
            actual = sesion.club_season
            nombre_equipo = str(getattr(equipo, "name", "?"))

            if destino is None:
                sin_temporada += 1
                self.stdout.write(
                    f"  ? {sesion.session_date} · {nombre_equipo} · sesión {sesion.id}: "
                    "no hay temporada que la acoja, se deja como está"
                )
                continue
            if actual and actual.id == destino.id:
                ya_correctas += 1
                continue

            movidas += 1
            etiqueta_actual = getattr(actual, "label", None) or "(sin temporada)"
            self.stdout.write(
                f"  → {sesion.session_date} · {nombre_equipo} · sesión {sesion.id}: "
                f"{etiqueta_actual} → {destino.label}"
            )
            if not aplicar:
                continue

            sesion.club_season = destino
            sesion.save(update_fields=["club_season"])
            tareas_movidas += SessionTask.objects.filter(session=sesion).update(club_season=destino)

        self.stdout.write("")
        self.stdout.write(f"sesiones a mover      : {movidas}")
        self.stdout.write(f"ya estaban bien       : {ya_correctas}")
        self.stdout.write(f"sin temporada destino : {sin_temporada}")
        if aplicar:
            self.stdout.write(f"tareas arrastradas    : {tareas_movidas}")
            self.stdout.write(self.style.SUCCESS("Aplicado."))
        else:
            self.stdout.write(self.style.WARNING("Simulación: nada escrito. Repite con --apply."))
