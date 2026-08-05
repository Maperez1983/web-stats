from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import (
    AppUserRole,
    Competition,
    Group,
    Player,
    PlayerInjuryRecord,
    Season,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    TrainingSessionAttendance,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class PlayerInjuryDetailViewTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(name='CompInjury', slug='comp-injury')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='GrupoInjury', slug='grupo-injury')
        self.team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-injury',
            short_name='Benagalbón',
            group=self.group,
            is_primary=True,
        )
        self.user = get_user_model().objects.create_user(
            username='injury-manager',
            email='injury-manager@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='Injury Workspace',
            slug='injury-workspace',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.player = Player.objects.create(
            team=self.team,
            name='Jugador Lesión',
            full_name='Jugador Lesión',
            is_active=True,
        )
        self.record = PlayerInjuryRecord.objects.create(
            player=self.player,
            injury='Sobrecarga',
            injury_type='Muscular',
            injury_zone='Isquios',
            injury_side='izquierdo',
            injury_date=date(2026, 7, 1),
            notes='Carga alta',
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session['active_team_by_workspace'] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_save_record_marks_recovered_and_creates_milestone(self):
        self.player.injury = self.record.injury
        self.player.injury_type = self.record.injury_type
        self.player.injury_zone = self.record.injury_zone
        self.player.injury_side = self.record.injury_side
        self.player.injury_date = self.record.injury_date
        self.player.save()
        response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={
                'action': 'save-record',
                'injury': 'Sobrecarga',
                'injury_type': 'Muscular',
                'injury_zone': 'Isquios',
                'injury_side': 'izquierdo',
                'injury_date': '2026-07-01',
                'return_date': '',
                'estimated_return_date': '',
                'blocks_training': '1',
                'is_recovered': '1',
                'training_status': 'rehab',
                'notes': 'Evolución favorable',
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 302)

        self.record.refresh_from_db()
        self.assertTrue(self.record.is_recovered)
        self.assertFalse(self.record.is_active)
        self.assertTrue(self.record.blocks_training)
        self.assertIsNotNone(self.record.return_date)
        self.player.refresh_from_db()
        self.assertEqual(self.player.injury, '')
        self.assertEqual(self.player.injury_type, '')
        self.assertEqual(self.player.injury_zone, '')
        self.assertEqual(self.player.injury_side, '')
        self.assertIsNone(self.player.injury_date)

        milestone_response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={
                'action': 'add-milestone',
                'milestone_title': 'Prueba diagnóstica',
                'milestone_date': '2026-07-04',
                'milestone_notes': 'Control ecográfico',
                'milestone_done': '1',
            },
            secure=True,
        )
        self.assertEqual(milestone_response.status_code, 302)
        self.assertEqual(self.record.milestones.count(), 1)

    def test_reopen_record_clears_actual_return_and_restores_player_injury(self):
        self.record.is_recovered = True
        self.record.return_date = date(2026, 7, 31)
        self.record.save()
        self.player.injury = ""
        self.player.injury_type = ""
        self.player.injury_zone = ""
        self.player.injury_side = ""
        self.player.injury_date = None
        self.player.save()

        response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={'action': 'reopen-record'},
            secure=True,
        )

        self.assertRedirects(
            response,
            reverse('player-injury-detail', args=[self.player.id, self.record.id]) + '?saved=reopened',
            fetch_redirect_response=False,
        )
        self.record.refresh_from_db()
        self.player.refresh_from_db()
        self.assertFalse(self.record.is_recovered)
        self.assertTrue(self.record.is_active)
        self.assertIsNone(self.record.return_date)
        self.assertEqual(self.player.injury, "Sobrecarga")
        self.assertEqual(self.player.injury_date, date(2026, 7, 1))

    def test_saving_active_status_clears_previous_actual_return(self):
        self.record.is_recovered = True
        self.record.return_date = date(2026, 7, 31)
        self.record.save()

        response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={
                'action': 'save-record',
                'injury': 'Sobrecarga',
                'injury_type': 'Muscular',
                'injury_zone': 'Isquios',
                'injury_side': 'izquierdo',
                'injury_date': '2026-07-01',
                'estimated_return_date': '2026-08-11',
                'return_date': '2026-07-31',
                'injury_status': 'active',
                'blocks_training': '1',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.record.refresh_from_db()
        self.assertFalse(self.record.is_recovered)
        self.assertTrue(self.record.is_active)
        self.assertIsNone(self.record.return_date)
        self.assertEqual(self.record.estimated_return_date, date(2026, 8, 11))

    def test_recovering_one_record_keeps_future_injury_mark_when_another_is_active(self):
        today = date.today()
        PlayerInjuryRecord.objects.create(
            player=self.player,
            injury='Segunda lesión activa',
            injury_date=today,
            is_active=True,
        )
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            week_start=today,
            week_end=today + timedelta(days=7),
        )
        session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=today + timedelta(days=1),
        )
        mark = TrainingSessionAttendance.objects.create(
            session=session,
            player=self.player,
            status=TrainingSessionAttendance.STATUS_INJURED,
        )

        response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={
                'action': 'save-record',
                'injury': self.record.injury,
                'injury_date': self.record.injury_date.isoformat(),
                'injury_status': 'recovered',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TrainingSessionAttendance.objects.filter(id=mark.id).exists())

    def test_closed_record_shows_reopen_action_and_explicit_status(self):
        self.record.is_recovered = True
        self.record.return_date = date(2026, 7, 31)
        self.record.save()

        response = self.client.get(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reabrir lesión')
        self.assertContains(response, 'name="injury_status"')
        self.assertContains(response, 'value="active"')
        self.assertContains(response, 'value="recovered"')


class PartesAbiertosSimultaneosTests(TestCase):
    """Varios partes abiertos a la vez: el caso que dejaba a un jugador lesionado para siempre.

    Cerrar el parte que tienes delante no le devuelve a "disponible" si le quedan otros sin alta,
    y desde la pantalla no había forma de enterarse.
    """

    # Mismo escenario que la clase de arriba (club, workspace, jugador y un parte abierto); se
    # reutiliza tal cual en vez de heredar, que volvería a ejecutar sus tests con otro nombre.
    setUp = PlayerInjuryDetailViewTests.setUp

    def _segundo_parte(self, **extra):
        datos = dict(
            player=self.player,
            injury='Lesión antigua',
            injury_date=date(2026, 6, 1),
            is_active=True,
        )
        datos.update(extra)
        return PlayerInjuryRecord.objects.create(**datos)

    def test_la_ficha_avisa_de_los_otros_partes_sin_alta(self):
        otro = self._segundo_parte()

        response = self.client.get(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'parte más sin alta')
        self.assertContains(response, 'Lesión antigua')
        self.assertContains(response, reverse('player-injury-detail', args=[self.player.id, otro.id]))
        self.assertContains(response, 'Cerrar el otro parte')

    def test_sin_otros_partes_no_hay_aviso(self):
        response = self.client.get(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'sin alta')

    def test_cerrar_los_restantes_les_pone_fecha_de_alta(self):
        otro = self._segundo_parte()
        tercero = self._segundo_parte(injury='Otra más', injury_date=date(2026, 5, 1))

        response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={'action': 'close-others'},
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        for cerrado in (otro, tercero):
            cerrado.refresh_from_db()
            self.assertTrue(cerrado.is_recovered)
            self.assertFalse(cerrado.is_active)
            # Sin fecha de alta el parte queda "recuperado" pero sin cerrar de verdad.
            self.assertIsNotNone(cerrado.return_date)
        # El parte que estabas mirando NO se toca: cerrarlo es otra acción.
        self.record.refresh_from_db()
        self.assertTrue(self.record.is_active)

    def test_la_ficha_del_jugador_cuenta_los_partes_sin_alta(self):
        self._segundo_parte()

        response = self.client.get(
            reverse('player-detail', args=[self.player.id]) + '?tab=injuries',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Partes sin alta')
        self.assertContains(response, 'Tiene 2 partes abiertos a la vez')

    def test_el_formulario_de_alta_avisa_antes_de_abrir_otra(self):
        response = self.client.get(
            reverse('player-form', args=[self.player.id, 'lesion']),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ya tiene 1 parte sin alta')
        self.assertContains(response, reverse('player-injury-detail', args=[self.player.id, self.record.id]))
