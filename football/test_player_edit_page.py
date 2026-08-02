"""
El mantenimiento de la ficha sale a su propia pantalla.

La ficha tenía 198 campos de formulario; 62 de ellos eran este bloque, metido como plegable
dentro de la pestaña Datos personales. Una pantalla de consulta no es un formulario. Ahora
`/player/N/editar/` aloja el formulario, con el MISMO markup (partial compartido) y enviando
al mismo sitio de siempre: no se ha duplicado ni una línea de guardado.
"""

from django.contrib.auth import get_user_model
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from football.models import (
    AppUserRole,
    Competition,
    ConvocationRecord,
    Group,
    Match,
    Player,
    PlayerInjuryRecord,
    PlayerStatistic,
    Season,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    TrainingSessionAttendance,
    Workspace,
    WorkspaceTeam,
)


class PlayerEditPageTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", number=21, is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        self.workspace.owner_user = self.staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(self.staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_the_edit_page_renders(self):
        response = self.client.get(reverse("player-edit", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar ficha")

    def test_the_ficha_links_it_and_no_longer_carries_the_form(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, reverse("player-edit", args=[self.player.id]))
        # El formulario de perfil ya no vive en la ficha.
        self.assertNotContains(response, 'value="profile"')

    def test_saving_still_works_from_the_new_page(self):
        # El POST sigue yendo a la ficha, que es donde está el guardado de siempre.
        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "profile", "skin_grade": "5", "hair_color": "#1a1a1a"},
            HTTP_HOST="localhost",
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.skin_grade, 5)

    def test_recovery_cannot_precede_injury(self):
        response = self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {
                "form_action": "injuries",
                "injury": "Esguince",
                "injury_date": "2026-08-10",
                "injury_return_date": "2026-08-01",
            },
            HTTP_HOST="localhost",
        )
        self.assertRedirects(response, reverse("player-detail", args=[self.player.id]) + "?tab=salud")
        self.assertFalse(PlayerInjuryRecord.objects.filter(player=self.player).exists())

    def test_a_player_cannot_open_it(self):
        user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = user
        self.player.save(update_fields=["user"])
        client = Client()
        client.force_login(user)
        response = client.get(reverse("player-edit", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("player-home"))


class PlayerEvaluationNewPageTests(TestCase):
    """La nueva valoración —67 campos— sale también de la pestaña de consulta."""

    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        staff = get_user_model().objects.create_superuser("mister2", "m2@example.com", "x")
        self.workspace.owner_user = staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_the_page_renders(self):
        response = self.client.get(
            reverse("player-evaluation-new", args=[self.player.id]), HTTP_HOST="localhost"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evaluación del cuerpo técnico")
        self.assertContains(response, "Juego de espaldas")
        self.assertContains(response, "Pases en largo")
        self.assertContains(response, "Presión")
        self.assertContains(response, "Cobertura")

    def test_the_ficha_links_it_and_no_longer_carries_the_form(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, reverse("player-evaluation-new", args=[self.player.id]))
        self.assertNotContains(response, 'value="evaluation"')

    def test_saving_still_works(self):
        from football.models import PlayerEvaluation

        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "evaluation", "evaluation_type": "monthly", "status": "draft",
             "technical_rating": "6"},
            HTTP_HOST="localhost",
        )
        self.assertTrue(PlayerEvaluation.objects.filter(player=self.player).exists())


class PlayerDashboardAgendaTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior-dashboard", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.staff = get_user_model().objects.create_superuser("mister-dashboard", "md@example.com", "x")
        self.workspace.owner_user = self.staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(self.staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()
        today = timezone.localdate()
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title="Semana",
            week_start=today - timedelta(days=today.weekday()),
            week_end=today - timedelta(days=today.weekday()) + timedelta(days=6),
        )

    def test_only_closed_sessions_count_attendance(self):
        today = timezone.localdate()
        planned = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=today,
            focus="Presión alta",
            status=TrainingSession.STATUS_PLANNED,
        )
        closed = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=today - timedelta(days=1),
            focus="Finalización",
            status=TrainingSession.STATUS_DONE,
        )
        TrainingSessionAttendance.objects.create(
            session=planned, player=self.player, status=TrainingSessionAttendance.STATUS_PRESENT
        )
        TrainingSessionAttendance.objects.create(
            session=closed, player=self.player, status=TrainingSessionAttendance.STATUS_ABSENT
        )

        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")

        self.assertEqual(response.context["attendance_session_total"], 1)
        self.assertEqual(response.context["attendance_marked_total"], 1)
        self.assertEqual(response.context["attendance_completed_total"], 0)
        planned_row = next(row for row in response.context["player_agenda_rows"] if row["id"] == planned.id)
        self.assertEqual(planned_row["status_label"], "")

    def test_ficha_has_dashboard_personal_data_and_month_agenda(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, 'data-pane="resumen"')
        self.assertContains(response, 'data-pane="personal"')
        self.assertContains(response, 'data-pane="agenda"')
        self.assertContains(response, "Entrenamientos y partidos")

        html = response.content.decode("utf-8")
        personal = html.split('data-pane="personal"', 1)[1].split('data-pane="agenda"', 1)[0]
        self.assertNotIn("Próximas sesiones", personal)
        self.assertNotIn("Asistencia (temporada)", personal)

    def test_open_match_does_not_count_as_played_in_player_detail(self):
        competition = Competition.objects.create(name="Liga ficha", slug="liga-ficha-dashboard")
        season = Season.objects.create(competition=competition, name="2026/2027")
        group = Group.objects.create(season=season, name="Grupo ficha", slug="grupo-ficha-dashboard")
        self.team.group = group
        self.team.save(update_fields=["group"])
        rival = Team.objects.create(name="Rival", slug="rival-ficha-dashboard", group=group)
        today = timezone.localdate()

        for offset, is_closed in ((-1, True), (3, False)):
            match = Match.objects.create(
                season=season,
                group=group,
                date=today + timedelta(days=offset),
                home_team=self.team,
                away_team=rival,
                is_closed=is_closed,
                stats_source=Match.STATS_SOURCE_MANUAL,
            )
            convocation = ConvocationRecord.objects.create(team=self.team, match=match, is_current=not is_closed)
            convocation.players.add(self.player)
            PlayerStatistic.objects.create(
                player=self.player,
                season=season,
                match=match,
                context="manual-match",
                name="manual_minutes",
                value=45,
            )

        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["pj"], 1)
        self.assertEqual(response.context["dashboard_performance"]["matches"], 1)

    def test_closed_internal_match_counts_for_every_roster_player(self):
        competition = Competition.objects.create(name="Liga interna", slug="liga-interna-dashboard")
        season = Season.objects.create(competition=competition, name="2026/2027")
        group = Group.objects.create(season=season, name="Grupo interno", slug="grupo-interno-dashboard")
        self.team.group = group
        self.team.save(update_fields=["group"])
        teammate = Player.objects.create(team=self.team, name="Compañero sin registro", is_active=True)
        Match.objects.create(
            season=season,
            group=group,
            date=timezone.localdate() - timedelta(days=1),
            home_team=self.team,
            away_team=self.team,
            is_closed=True,
            context=Match.CONTEXT_FRIENDLY,
            round="Partido interno",
        )

        response = self.client.get(reverse("player-detail", args=[teammate.id]), HTTP_HOST="localhost")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["pj"], 1)
        self.assertEqual(response.context["stats"]["minutes"], 0)


class PlayerFormPageTests(TestCase):
    """
    Una sola pantalla aloja los formularios de mantenimiento que salieron de la ficha.

    El ajuste manual de estadísticas NO salió: precarga con las estadísticas agregadas que la
    ficha calcula, y ese cálculo no se duplica. Además pertenece a la pestaña que ajusta.
    """

    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        staff = get_user_model().objects.create_superuser("mister3", "m3@example.com", "x")
        self.workspace.owner_user = staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_each_form_has_its_page(self):
        for key, titulo in [("fisico", "registro físico"), ("lesion", "lesión"), ("comunicacion", "comunicación")]:
            response = self.client.get(reverse("player-form", args=[self.player.id, key]), HTTP_HOST="localhost")
            self.assertEqual(response.status_code, 200, key)
            self.assertContains(response, titulo)

    def test_an_invented_key_is_404(self):
        response = self.client.get(reverse("player-form", args=[self.player.id, "inventado"]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 404)

    def test_the_ficha_links_them_and_dropped_the_forms(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        for key in ("fisico", "lesion", "comunicacion"):
            self.assertContains(response, reverse("player-form", args=[self.player.id, key]))
        for accion in ('value="physical"', 'value="injuries"', 'value="communication"'):
            self.assertNotContains(response, accion)
        # El ajuste manual se queda en su pestaña.
        self.assertContains(response, 'value="manual_stats"')

    def test_saving_an_injury_still_works(self):
        from football.models import PlayerInjuryRecord

        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "injuries", "injury": "Sobrecarga", "injury_date": "2026-07-01",
             "injury_record_mode": "new"},
            HTTP_HOST="localhost",
        )
        self.assertTrue(PlayerInjuryRecord.objects.filter(player=self.player).exists())
    Season,
