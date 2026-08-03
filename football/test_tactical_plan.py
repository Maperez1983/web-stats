import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from football.models import (
    Player,
    TacticalPlan,
    Team,
    TeamRosterSnapshot,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class PlanteamientoTests(TestCase):
    """Táctica · Planteamiento: el once del equipo, guardado y reutilizable."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="Benagalbón", slug="bena", is_primary=True)
        self.ws = Workspace.objects.create(name="Club", slug="club", kind=Workspace.KIND_CLUB)
        WorkspaceMembership.objects.create(workspace=self.ws, user=self.user, role="owner")
        WorkspaceTeam.objects.create(workspace=self.ws, team=self.team, is_default=True)
        self.p1 = Player.objects.create(team=self.team, name="Uno", number=1, is_active=True)
        self.p2 = Player.objects.create(team=self.team, name="Dos", number=2, is_active=True)
        self.rival = Team.objects.create(name="C.D. Rival", slug="rival")
        TeamRosterSnapshot.objects.create(
            team=self.rival,
            provider="lapreferente",
            roster_payload=[
                {"name": f"Rival {i}", "number": i, "position": "MC", "photo_url": f"https://ej/{i}.png"}
                for i in range(1, 15)
            ],
        )
        self.client = Client()
        self.client.force_login(self.user)
        s = self.client.session
        s["active_workspace_id"] = self.ws.id
        s["active_team_by_workspace"] = {str(self.ws.id): self.team.id}
        s.save()

    def _guardar(self, **extra):
        payload = {"name": "1-4-3-3 base", "formation": "1-4-3-3",
                   "lineup": {"starters": [{"id": self.p1.id, "x_pct": 7, "y_pct": 50}]}}
        payload.update(extra)
        return self.client.post(reverse("tactics-plan-save"), data=json.dumps(payload),
                                content_type="application/json", secure=True)

    def test_la_pantalla_usa_el_cesped_de_siempre(self):
        r = self.client.get(reverse("tactics-plan"), secure=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("coach_home_pitch_surface", html, "el campo tiene que ser el mismo de toda la app")
        self.assertIn("C.D. Rival", html, "los rivales con plantilla volcada deben poder elegirse")

    def test_guardar_y_recuperar_un_planteamiento(self):
        r = self._guardar(rival_team_id=self.rival.id,
                          rival_lineup={"starters": [{"code": "r1", "name": "Rival 1", "number": "1"}]})
        self.assertEqual(r.status_code, 200)
        plan = r.json()["plan"]
        self.assertEqual(len(plan["lineup"]["starters"]), 1)
        self.assertEqual(len(plan["rival_lineup"]["starters"]), 1)
        self.assertEqual(plan["lineup"]["_meta"]["orientation"], "lr",
                         "misma orientación que el prepartido, o no se podrá volcar")

    def test_el_mismo_nombre_no_duplica(self):
        self._guardar()
        self._guardar()
        self.assertEqual(TacticalPlan.objects.filter(team=self.team).count(), 1)

    def test_no_se_cuela_un_jugador_de_otro_equipo(self):
        otro = Team.objects.create(name="Otro", slug="otro")
        intruso = Player.objects.create(team=otro, name="Intruso", is_active=True)
        r = self._guardar(lineup={"starters": [{"id": intruso.id, "x_pct": 50, "y_pct": 50}]})
        self.assertEqual(r.json()["plan"]["lineup"]["starters"], [])

    def test_el_once_no_pasa_de_once(self):
        jugadores = [Player.objects.create(team=self.team, name=f"J{i}", number=i, is_active=True) for i in range(3, 20)]
        filas = [{"id": p.id, "x_pct": 50, "y_pct": 50} for p in jugadores]
        r = self._guardar(lineup={"starters": filas})
        self.assertEqual(len(r.json()["plan"]["lineup"]["starters"]), 11)

    def test_plantilla_del_rival_y_borrado(self):
        r = self.client.get(reverse("tactics-plan-rival") + f"?rival={self.rival.id}", secure=True)
        self.assertEqual(len(r.json()["players"]), 14)
        plan_id = self._guardar().json()["plan"]["id"]
        r = self.client.post(reverse("tactics-plan-delete"), data=json.dumps({"id": plan_id}),
                             content_type="application/json", secure=True)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(TacticalPlan.objects.filter(team=self.team).count(), 0)


class AplicarPlanteamientoTests(PlanteamientoTests):
    """El puente: un planteamiento vuelca sobre el prepartido de un partido."""

    def _partido(self):
        import datetime

        from football.models import Competition, Match, Season

        comp = Competition.objects.create(name="Amistosos")
        temporada = Season.objects.create(
            competition=comp, name="2026/2027",
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2027, 6, 30),
        )
        return Match.objects.create(
            season=temporada, home_team=self.team, away_team=self.rival,
            date=datetime.date(2026, 8, 20), context="friendly",
        )

    def test_aplicar_deja_el_once_en_el_partido(self):
        from football.models import MatchLineup, RivalConvocationRecord

        plan = self._guardar(
            rival_team_id=self.rival.id,
            rival_lineup={"starters": [{"code": "r1", "name": "Rival 1", "number": "1", "x_pct": 93, "y_pct": 50}]},
        ).json()["plan"]
        partido = self._partido()

        r = self.client.post(
            reverse("tactics-plan-apply"),
            data=json.dumps({"plan_id": plan["id"], "match_id": partido.id}),
            content_type="application/json", secure=True,
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["ok"])

        guardado = MatchLineup.objects.get(team=self.team, match=partido)
        titulares = guardado.lineup_data["starters"]
        self.assertEqual(len(titulares), 1)
        self.assertEqual(titulares[0]["x_pct"], 7, "la posición del planteamiento tiene que llegar tal cual")
        self.assertEqual(guardado.lineup_data["_meta"]["orientation"], "lr")
        self.assertEqual(guardado.lineup_data["_meta"]["source"], "tactics-plan-apply")

        rival = RivalConvocationRecord.objects.get(team=self.team, match=partido)
        self.assertEqual(len(rival.lineup_data["starters"]), 1)

    def test_el_titular_que_no_estaba_convocado_se_convoca(self):
        plan = self._guardar().json()["plan"]
        partido = self._partido()
        r = self.client.post(
            reverse("tactics-plan-apply"),
            data=json.dumps({"plan_id": plan["id"], "match_id": partido.id}),
            content_type="application/json", secure=True,
        )
        # p1 no estaba en ninguna convocatoria: si no se añade, el once se guardaría vacío.
        self.assertEqual(r.json()["starters"], 1)

    def test_no_se_aplica_a_un_partido_de_otro_equipo(self):
        import datetime

        from football.models import Competition, Match, Season

        otro = Team.objects.create(name="Otro club", slug="otro-club")
        comp = Competition.objects.create(name="Liga")
        temporada = Season.objects.create(
            competition=comp, name="26/27",
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2027, 6, 30),
        )
        ajeno = Match.objects.create(season=temporada, home_team=otro, away_team=self.rival,
                                     date=datetime.date(2026, 9, 1))
        plan = self._guardar().json()["plan"]
        r = self.client.post(
            reverse("tactics-plan-apply"),
            data=json.dumps({"plan_id": plan["id"], "match_id": ajeno.id}),
            content_type="application/json", secure=True,
        )
        self.assertEqual(r.status_code, 404)


class ImagenPlanteamientoTests(PlanteamientoTests):
    """La página que se fotografía para la charla."""

    def test_el_campo_solo_lleva_los_dos_onces(self):
        plan = self._guardar(
            rival_team_id=self.rival.id,
            rival_lineup={"starters": [{"code": "r1", "name": "Rival 1", "number": "9", "x_pct": 93, "y_pct": 50}]},
        ).json()["plan"]
        r = self.client.get(reverse("tactics-plan-board", args=[plan["id"]]), secure=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("coach_home_pitch_surface", html)
        self.assertIn("Rival 1", html)
        self.assertIn("Uno", html, "nuestro titular tiene que salir")
        # Es una página para fotografiar: nada de menús ni paneles.
        self.assertNotIn("dragon_nav", html)
        self.assertNotIn("tp-panel", html)

    def test_no_se_puede_ver_el_campo_de_otro_equipo(self):
        otro = Team.objects.create(name="Otro club", slug="otro-club")
        ajeno = TacticalPlan.objects.create(team=otro, name="suyo")
        r = self.client.get(reverse("tactics-plan-board", args=[ajeno.id]), secure=True)
        self.assertEqual(r.status_code, 302, "debe rebotar, no enseñar el planteamiento de otro")
