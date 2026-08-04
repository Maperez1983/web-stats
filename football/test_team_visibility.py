from django.contrib.auth.models import User
from django.test import TestCase

from .models import Team, Workspace, WorkspaceMembership, WorkspaceTeam
from .team_visibility import excluir_equipos_ajenos, ids_de_equipos_ajenos


class EquiposDeOtroClubTests(TestCase):
    """Team es una tabla global: los equipos internos de otro cliente no se enseñan."""

    def setUp(self):
        self.duenio = User.objects.create_user(username="duenio-vis", password="x")
        self.otro = User.objects.create_user(username="otro-vis", password="x")
        self.club = Workspace.objects.create(
            name="Mi club", slug="mi-club-vis", kind=Workspace.KIND_CLUB, owner_user=self.duenio
        )
        self.club_rival = Workspace.objects.create(
            name="Club de otro cliente", slug="otro-club-vis", kind=Workspace.KIND_CLUB,
            owner_user=self.otro
        )
        self.mi_senior = Team.objects.create(name="Mi Senior", slug="mi-senior-vis")
        self.mi_cadete = Team.objects.create(name="Mi Cadete", slug="mi-cadete-vis")
        self.suyo = Team.objects.create(name="Cadete del otro cliente", slug="suyo-vis")
        self.federativo = Team.objects.create(name="CD Rival Federativo", slug="federativo-vis")
        WorkspaceTeam.objects.create(workspace=self.club, team=self.mi_senior)
        WorkspaceTeam.objects.create(workspace=self.club, team=self.mi_cadete)
        WorkspaceTeam.objects.create(workspace=self.club_rival, team=self.suyo)

    def test_el_equipo_de_otro_cliente_queda_fuera(self):
        self.assertEqual(ids_de_equipos_ajenos(self.mi_senior), {self.suyo.id})

    def test_los_mios_y_los_federativos_se_ven(self):
        visibles = excluir_equipos_ajenos(Team.objects.all(), self.mi_senior)

        self.assertIn(self.federativo, visibles)
        self.assertIn(self.mi_cadete, visibles)
        self.assertNotIn(self.suyo, visibles)

    def test_un_equipo_sin_club_no_esconde_nada(self):
        """Sin saber de quién es el que pregunta, no se oculta: mejor de más que romper."""
        self.assertEqual(ids_de_equipos_ajenos(self.federativo), set())

    def test_tambien_vale_pasando_el_espacio_de_trabajo(self):
        self.assertEqual(ids_de_equipos_ajenos(workspace=self.club), {self.suyo.id})


class SelectorDeRivalTests(TestCase):
    """El alta de partido no puede ofrecer las categorías internas de otro cliente."""

    def setUp(self):
        self.duenio = User.objects.create_user(username="duenio-sel", password="x")
        self.otro = User.objects.create_user(username="otro-sel", password="x")
        self.club = Workspace.objects.create(
            name="Club selector", slug="club-selector", kind=Workspace.KIND_CLUB, owner_user=self.duenio
        )
        self.ajeno = Workspace.objects.create(
            name="Otro cliente", slug="otro-cliente-sel", kind=Workspace.KIND_CLUB, owner_user=self.otro
        )
        self.mio = Team.objects.create(name="Mi Senior sel", slug="mi-senior-sel")
        self.suyo = Team.objects.create(name="Su Cadete sel", slug="su-cadete-sel")
        self.federativo = Team.objects.create(name="CD Federativo sel", slug="federativo-sel")
        WorkspaceTeam.objects.create(workspace=self.club, team=self.mio)
        WorkspaceTeam.objects.create(workspace=self.ajeno, team=self.suyo)

    def test_ofrece_los_federativos_pero_no_los_de_otro_cliente(self):
        from .views import build_match_rival_picker_options

        nombres = {str(o.get("name") or "") for o in build_match_rival_picker_options(self.mio)}

        self.assertIn("CD Federativo sel", nombres)
        self.assertNotIn("Su Cadete sel", nombres)


class ClasificacionPorCategoriaTests(TestCase):
    """Un club se llama igual en todas sus categorías: la tabla del cadete no es la del senior."""

    def setUp(self):
        self.cadete_propio = Team.objects.create(
            name="Mi Cadete cls", slug="mi-cadete-cls", category="CADETE"
        )
        self.rincon_senior = Team.objects.create(
            name="C.D. Rincón", slug="rincon-senior-cls", category="SENIOR"
        )
        self.rincon_cadete = Team.objects.create(
            name="C.D. Rincón", slug="rincon-cadete-cls", category="CADETE"
        )
        self.sin_categoria = Team.objects.create(name="CD Sin Categoría", slug="sin-cat-cls")

    def test_no_cuela_el_senior_en_la_tabla_del_cadete(self):
        from .team_visibility import misma_categoria

        visibles = misma_categoria(Team.objects.all(), self.cadete_propio)

        self.assertIn(self.rincon_cadete, visibles)
        self.assertNotIn(self.rincon_senior, visibles)

    def test_los_que_aun_no_tienen_categoria_siguen_entrando(self):
        """Son mayoría de los importados: excluirlos rompería emparejados que hoy funcionan."""
        from .team_visibility import misma_categoria

        self.assertIn(self.sin_categoria, misma_categoria(Team.objects.all(), self.cadete_propio))

    def test_si_el_equipo_no_tiene_categoria_no_se_filtra_nada(self):
        from .team_visibility import misma_categoria

        visibles = misma_categoria(Team.objects.all(), self.sin_categoria)

        self.assertIn(self.rincon_senior, visibles)
        self.assertIn(self.rincon_cadete, visibles)


class CategoriaArchivadaTests(TestCase):
    """"Este año no lo usamos" no es "bórralo": el histórico se queda."""

    def setUp(self):
        self.duenio = User.objects.create_user(username="duenio-arch", password="x")
        self.club = Workspace.objects.create(
            name="Club archivo", slug="club-archivo", kind=Workspace.KIND_CLUB, owner_user=self.duenio
        )
        self.senior = Team.objects.create(name="Senior arch", slug="senior-arch")
        self.alevin = Team.objects.create(name="Alevín arch", slug="alevin-arch")
        WorkspaceTeam.objects.create(workspace=self.club, team=self.senior, is_default=True)
        self.enlace_alevin = WorkspaceTeam.objects.create(workspace=self.club, team=self.alevin)

    def test_la_categoria_archivada_sale_de_los_selectores(self):
        from .workspace_context import workspace_team_links

        self.enlace_alevin.is_active = False
        self.enlace_alevin.save(update_fields=["is_active"])

        equipos = [enlace.team for enlace in workspace_team_links(self.club)]
        self.assertIn(self.senior, equipos)
        self.assertNotIn(self.alevin, equipos)

    def test_archivar_no_borra_nada(self):
        self.enlace_alevin.is_active = False
        self.enlace_alevin.save(update_fields=["is_active"])

        self.assertTrue(Team.objects.filter(id=self.alevin.id).exists())
        self.assertTrue(WorkspaceTeam.objects.filter(id=self.enlace_alevin.id).exists())

    def test_por_defecto_todas_estan_activas(self):
        from .workspace_context import workspace_team_links

        equipos = [enlace.team for enlace in workspace_team_links(self.club)]
        self.assertIn(self.alevin, equipos)


class ElSelectorNoSePuedeQuedarVacioTests(TestCase):
    """
    Un filtro nuevo no puede dejar al club sin categorías: sin ellas desaparece el selector
    y no hay forma de cambiar de equipo. Pasó al añadir `is_active`.
    """

    def setUp(self):
        self.duenio = User.objects.create_user(username="duenio-selector", password="x")
        self.club = Workspace.objects.create(
            name="Club selector vacio", slug="club-selector-vacio",
            kind=Workspace.KIND_CLUB, owner_user=self.duenio,
        )
        self.senior = Team.objects.create(name="Senior sel2", slug="senior-sel2")
        self.cadete = Team.objects.create(name="Cadete sel2", slug="cadete-sel2")
        WorkspaceTeam.objects.create(workspace=self.club, team=self.senior, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.club, team=self.cadete)

    def test_si_el_filtro_falla_se_devuelven_todas(self):
        from unittest.mock import patch

        from django.db.models import QuerySet

        from .workspace_context import workspace_team_links

        original = QuerySet.filter

        def _filter_que_falla(self, *args, **kwargs):
            if "is_active" in kwargs:
                raise Exception("la columna no existe en esta base de datos")
            return original(self, *args, **kwargs)

        with patch.object(QuerySet, "filter", _filter_que_falla):
            enlaces = workspace_team_links(self.club)

        self.assertEqual(len(enlaces), 2, "El club se quedó sin categorías al fallar el filtro")

    def test_en_condiciones_normales_filtra(self):
        from .workspace_context import workspace_team_links

        enlace = WorkspaceTeam.objects.get(workspace=self.club, team=self.cadete)
        enlace.is_active = False
        enlace.save(update_fields=["is_active"])

        equipos = [e.team for e in workspace_team_links(self.club)]
        self.assertEqual(equipos, [self.senior])


class AlEntrarElClubQueTocaTests(TestCase):
    """
    Con varios espacios de trabajo, entrar sin nada elegido metía al usuario en el PRIMERO
    POR ORDEN ALFABÉTICO. Al dueño de "Benagalbón" le tocaba "2J Football Intelligence
    (Demo)": Miembros y Configuración en 403 y su propio Staff en "club no configurado".
    """

    def setUp(self):
        from django.test import RequestFactory

        self.factory = RequestFactory()
        self.duenio = User.objects.create_user(username="duenio-entrada", password="x")
        # El de demo se llama con un "2" delante: gana por orden alfabético.
        self.demo = Workspace.objects.create(
            name="2J Football Intelligence (Demo)", slug="demo-entrada",
            kind=Workspace.KIND_CLUB, owner_user=User.objects.create_user(username="otro-entrada", password="x"),
        )
        self.suyo = Workspace.objects.create(
            name="Benagalbón", slug="suyo-entrada", kind=Workspace.KIND_CLUB, owner_user=self.duenio
        )
        WorkspaceMembership.objects.create(
            workspace=self.demo, user=self.duenio, role=WorkspaceMembership.ROLE_VIEWER
        )
        WorkspaceMembership.objects.create(
            workspace=self.suyo, user=self.duenio, role=WorkspaceMembership.ROLE_OWNER
        )

    def _peticion(self):
        from django.contrib.sessions.backends.db import SessionStore

        peticion = self.factory.get("/coach/")
        peticion.user = self.duenio
        peticion.session = SessionStore()
        return peticion

    def test_entra_en_el_club_que_administra_no_en_el_primero_alfabetico(self):
        from .workspace_context import get_active_workspace

        elegido = get_active_workspace(self._peticion())

        self.assertEqual(elegido, self.suyo, "Le ha metido en un club que no es el suyo")

    def test_si_no_es_dueño_de_ninguno_entra_donde_sea_miembro(self):
        from .workspace_context import get_active_workspace

        invitado = User.objects.create_user(username="invitado-entrada", password="x")
        WorkspaceMembership.objects.create(
            workspace=self.demo, user=invitado, role=WorkspaceMembership.ROLE_MEMBER
        )
        peticion = self._peticion()
        peticion.user = invitado

        self.assertEqual(get_active_workspace(peticion), self.demo)
