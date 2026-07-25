from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import (
    ScoutingTarget,
    ScoutingTargetSeasonStat,
    Team,
    Workspace,
    WorkspaceMembership,
)
from football.preferente_player_services import parse_preferente_player

ADAM = (
    "DAM\n"
    "Adam Mastari el Moussaoui\n"
    "CLUB AL QUE PERTENECE: Jugador Sin Equipo\n"
    "POSICIÓN: Delantero\n"
    "POSICIÓN ESPECÍFICA: Extremo Derecho\n"
    "LUGAR DE NACIMIENTO: Málaga (Málaga)\n"
    "FECHA DE NACIMIENTO: 01/01/2006\n"
    "EDAD: 20 Años\n"
    "EQUIPO DE PROCEDENCIA: San Fernando C.D.\n"
    "OTRAS OBSERVACIONES:\n"
    "Trayectoria como Jugador\n"
    "2024/2025\n"
    "18 Años\t\t14º\t\n"
    "San Fernando C.D. Juvenil\n\n"
    "División de Honor Grupo 4\n\n"
    "Extremo Derecho\t9\t9\t5\t384\t0\t1\t0\t2\t2\t5\n"
    "2021/2022\n"
    "15 Años\t\t10º\t\n"
    "C.D. 26 de Febrero Cadete\n\n"
    "División de Honor Andaluza\n\n"
    "Extremo Derecho\t27\t27\t22\t0\t15\t1\t0\t10\t5\t12\n"
)


class PreferentePlayerParserTests(TestCase):
    def test_parses_header_and_seasons(self):
        r = parse_preferente_player(ADAM)
        self.assertEqual(r["name"], "Adam Mastari el Moussaoui")
        self.assertEqual(r["current_team"], "Jugador Sin Equipo")
        self.assertEqual(r["specific_position"], "Extremo Derecho")
        self.assertEqual(r["birth_date"], "2006-01-01")
        self.assertEqual(r["origin_team"], "San Fernando C.D.")
        self.assertEqual(len(r["seasons"]), 2)
        cadete = next(s for s in r["seasons"] if s["season"] == "2021/2022")
        self.assertEqual(cadete["team"], "C.D. 26 de Febrero Cadete")
        self.assertEqual(cadete["goals"], 15)
        self.assertEqual(cadete["matches_completed"], 27)
        self.assertEqual(cadete["matches_starter"], 22)

    def test_empty_text(self):
        r = parse_preferente_player("")
        self.assertEqual(r["name"], "")
        self.assertEqual(r["seasons"], [])


class ImportPreferentePlayerViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="Bena", slug="bena", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="Bena", slug="bena", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def test_import_creates_target_and_season_stats(self):
        resp = self.client.post(
            "/direccion/",
            {"action": "import_preferente", "preferente_text": ADAM},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 302)
        target = ScoutingTarget.objects.get(workspace=self.workspace, subject_name="Adam Mastari El Moussaoui")
        self.assertEqual(str(target.birth_date), "2006-01-01")
        self.assertEqual(target.subject_team_name, "Sin Equipo (Ex San Fernando C. D.)")
        self.assertEqual(ScoutingTargetSeasonStat.objects.filter(target=target).count(), 2)
        cadete = ScoutingTargetSeasonStat.objects.get(target=target, season="2021/2022")
        self.assertEqual(cadete.goals, 15)
        self.assertEqual(cadete.matches_completed, 27)

    def test_reimport_replaces_season_stats(self):
        for _ in range(2):
            self.client.post(
                "/direccion/",
                {"action": "import_preferente", "preferente_text": ADAM},
                HTTP_HOST="localhost",
            )
        self.assertEqual(ScoutingTarget.objects.filter(subject_name="Adam Mastari El Moussaoui").count(), 1)
        target = ScoutingTarget.objects.get(subject_name="Adam Mastari El Moussaoui")
        self.assertEqual(ScoutingTargetSeasonStat.objects.filter(target=target).count(), 2)

    def test_empty_paste_shows_error(self):
        resp = self.client.post(
            "/direccion/",
            {"action": "import_preferente", "preferente_text": "   "},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ScoutingTarget.objects.count(), 0)
