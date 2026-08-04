"""El registro del partido convertido en clips del vídeo."""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from football.models import (
    Competition,
    Match,
    MatchEvent,
    Player,
    RivalVideo,
    Season,
    Team,
    VideoClip,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)
from football.video_from_actions import clips_desde_el_registro, momento_de_video, titulo_de


class ClipsDesdeElRegistroTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("va", "va@example.com", "x")
        self.team = Team.objects.create(name="Benagalbón", slug="bena-va", is_primary=True)
        self.rival = Team.objects.create(name="Rival", slug="rival-va")
        self.ws = Workspace.objects.create(name="Club", slug="club-va", kind=Workspace.KIND_CLUB)
        WorkspaceMembership.objects.create(workspace=self.ws, user=self.user, role="owner")
        WorkspaceTeam.objects.create(workspace=self.ws, team=self.team, is_default=True)
        self.p = Player.objects.create(team=self.team, name="Nico Ruiz", number=9, is_active=True)

        comp = Competition.objects.create(name="Liga", slug="liga-va")
        temporada = Season.objects.create(competition=comp, name="2026/2027")
        self.match = Match.objects.create(home_team=self.team, away_team=self.rival,
                                          date=date(2026, 8, 9), season=temporada)
        # Un vídeo que empieza 30 s antes del saque y con la 2ª parte en el minuto 50 del vídeo.
        self.video = RivalVideo.objects.create(team=self.team, title="Jornada 1", match=self.match,
                                               kickoff_ms=30000, second_half_ms=3000000)
        self.client = Client()
        self.client.force_login(self.user)
        s = self.client.session
        s["active_workspace_id"] = self.ws.id
        s["active_team_by_workspace"] = {str(self.ws.id): self.team.id}
        s.save()

    def _evento(self, **extra):
        datos = {"match": self.match, "player": self.p, "minute": 10, "event_type": "Gol",
                 "result": "Acierto", "zone": "Área", "source_file": "test"}
        datos.update(extra)
        return MatchEvent.objects.create(**datos)

    # --- dónde cae cada acción ---

    def test_el_minuto_se_traduce_al_segundo_del_video(self):
        ev = self._evento(minute=10)
        self.assertEqual(momento_de_video(ev, kickoff_ms=30000, second_half_ms=0), 30000 + 600000)

    def test_la_segunda_parte_no_arrastra_el_descanso(self):
        ev = self._evento(minute=50, period=2)
        # Minuto 50 = 5' de la segunda parte, que en el vídeo empieza en 50'00".
        self.assertEqual(
            momento_de_video(ev, kickoff_ms=30000, second_half_ms=3000000), 3000000 + 300000
        )

    def test_sin_segunda_parte_marcada_se_usa_el_reloj_corrido(self):
        ev = self._evento(minute=50, period=2)
        self.assertEqual(momento_de_video(ev, kickoff_ms=0, second_half_ms=0), 3000000)

    def test_una_accion_sin_minuto_no_inventa_un_momento(self):
        ev = self._evento(minute=None)
        self.assertIsNone(momento_de_video(ev, kickoff_ms=0, second_half_ms=0))

    def test_el_titulo_dice_minuto_accion_y_jugador(self):
        self.assertEqual(titulo_de(self._evento(minute=10)), "10' · Gol · Nico")

    # --- la generación ---

    def test_genera_un_clip_por_accion(self):
        self._evento(minute=10)
        self._evento(minute=20, event_type="Pérdida")
        creados, saltados, sin_minuto = clips_desde_el_registro(self.video)
        self.assertEqual((creados, saltados, sin_minuto), (2, 0, 0))
        clip = VideoClip.objects.order_by("in_ms").first()
        self.assertEqual(clip.in_ms, 30000 + 600000 - 12000)
        self.assertEqual(clip.collection, "Registro del partido")
        self.assertIn("Gol", clip.tags)

    def test_volver_a_pulsar_no_duplica(self):
        self._evento(minute=10)
        clips_desde_el_registro(self.video)
        creados, saltados, _ = clips_desde_el_registro(self.video)
        self.assertEqual((creados, saltados), (0, 1))
        self.assertEqual(VideoClip.objects.count(), 1)

    def test_las_acciones_sin_minuto_se_cuentan_aparte(self):
        self._evento(minute=None)
        creados, _saltados, sin_minuto = clips_desde_el_registro(self.video)
        self.assertEqual((creados, sin_minuto), (0, 1))

    def test_no_se_cortan_clips_fuera_del_video(self):
        self._evento(minute=80)
        creados, saltados, _ = clips_desde_el_registro(self.video, duracion_ms=60000)
        self.assertEqual((creados, saltados), (0, 1), "un corte que empieza tras el final es ruido")

    # --- el endpoint ---

    def test_el_endpoint_ata_el_video_y_genera(self):
        self._evento(minute=10)
        otro = RivalVideo.objects.create(team=self.team, title="Suelto")
        r = self.client.post(
            reverse("analysis-video-clips-from-actions", args=[otro.id]),
            data=json.dumps({"match_id": self.match.id, "kickoff_s": 30, "second_half_s": 3000}),
            content_type="application/json", secure=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["created"], 1)
        otro.refresh_from_db()
        self.assertEqual(otro.match_id, self.match.id)
        self.assertEqual(otro.kickoff_ms, 30000)

    def test_sin_partido_atado_no_genera_y_lo_dice(self):
        suelto = RivalVideo.objects.create(team=self.team, title="Suelto")
        r = self.client.post(reverse("analysis-video-clips-from-actions", args=[suelto.id]),
                             data=json.dumps({}), content_type="application/json", secure=True)
        self.assertEqual(r.status_code, 400)
        self.assertIn("partido", r.json()["error"])

    def test_no_se_ata_a_un_partido_de_otro_equipo(self):
        ajeno_comp = Competition.objects.create(name="Otra", slug="otra-va")
        ajena = Season.objects.create(competition=ajeno_comp, name="26/27")
        otro_equipo = Team.objects.create(name="Ajeno", slug="ajeno-va")
        partido_ajeno = Match.objects.create(home_team=otro_equipo, away_team=self.rival,
                                             date=date(2026, 8, 9), season=ajena)
        r = self.client.post(
            reverse("analysis-video-clips-from-actions", args=[self.video.id]),
            data=json.dumps({"match_id": partido_ajeno.id}),
            content_type="application/json", secure=True,
        )
        self.assertEqual(r.status_code, 404)
