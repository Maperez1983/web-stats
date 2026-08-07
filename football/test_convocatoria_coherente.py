"""La convocatoria no puede decir 18 y guardar 17.

El servidor tiene la ultima palabra sobre quien puede competir, y la usaba en silencio:
quitaba al lesionado de la lista y devolvia otro numero, mientras el contador de la
pantalla seguia contando por su cuenta.
"""
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import (
    Competition,
    ConvocationRecord,
    Group,
    Match,
    Player,
    PlayerInjuryRecord,
    Season,
    Team,
    Workspace,
    WorkspaceTeam,
)


class ConvocatoriaCoherenteTests(TestCase):
    def setUp(self):
        comp = Competition.objects.create(name="Liga CV", slug="liga-cv", region="Andalucia")
        self.temporada = Season.objects.create(competition=comp, name="2026/2027", is_current=True)
        grupo = Group.objects.create(season=self.temporada, name="G", slug="g-cv")
        self.team = Team.objects.create(name="Benagalbón CV", slug="ben-cv", group=grupo, is_primary=True)
        self.rival = Team.objects.create(name="Rival CV", slug="riv-cv", group=grupo)
        self.workspace = Workspace.objects.create(
            name="Benagalbón CV", slug="ben-cv-ws", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.match = Match.objects.create(
            season=self.temporada,
            home_team=self.team,
            away_team=self.rival,
            date=date.today() + timedelta(days=2),
            context=Match.CONTEXT_FRIENDLY,
        )
        self.jugadores = [
            Player.objects.create(team=self.team, name=f"Jugador {i}", number=i + 1) for i in range(5)
        ]
        self.lesionado = self.jugadores[-1]
        PlayerInjuryRecord.objects.create(
            player=self.lesionado,
            injury_date=date.today() - timedelta(days=3),
            injury_type="Rotura",
            is_active=True,
        )
        user = get_user_model().objects.create_user("entrenador_cv", password="x", is_superuser=True, is_staff=True)
        self.client.force_login(user)

    def _guardar(self, ids, **extra):
        cuerpo = {
            "players": [str(i) for i in ids],
            "match_info": {
                "opponent": self.rival.name,
                "date": self.match.date.strftime("%Y-%m-%d"),
                "context": Match.CONTEXT_FRIENDLY,
                **extra,
            },
        }
        return self.client.post(
            reverse("convocation-save"), data=json.dumps(cuerpo), content_type="application/json"
        )

    def test_al_guardar_dice_a_quien_ha_quitado_y_por_que(self):
        respuesta = self._guardar([p.id for p in self.jugadores])
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()

        self.assertEqual(datos["count"], 4, "el lesionado no entra en la lista")
        fuera = datos.get("removed") or []
        self.assertEqual(len(fuera), 1, "quitar a alguien en silencio es el bug")
        self.assertEqual(fuera[0]["name"], self.lesionado.name)
        self.assertEqual(fuera[0]["reason"], "lesion")
        self.assertIn("lesión", fuera[0]["reason_label"])

    def test_devuelve_la_lista_guardada_para_que_el_contador_no_mienta(self):
        datos = self._guardar([p.id for p in self.jugadores]).json()
        guardados = datos.get("player_ids")
        self.assertIsNotNone(guardados, "sin esto la pantalla sigue contando su propia seleccion")
        self.assertEqual(len(guardados), datos["count"])
        self.assertNotIn(self.lesionado.id, guardados)

    def test_guardar_dos_veces_no_deja_dos_convocatorias_del_mismo_partido(self):
        """El partido del 8 de agosto acabo con tres listas por pulsar Guardar tres veces."""
        self._guardar([p.id for p in self.jugadores[:3]])
        self._guardar([p.id for p in self.jugadores[:4]])

        registros = ConvocationRecord.objects.filter(team=self.team, match=self.match)
        self.assertEqual(registros.count(), 1)
        self.assertEqual(registros.first().players.count(), 4, "manda la ultima lista guardada")
        self.assertTrue(registros.first().is_current)

    def test_la_pantalla_no_trae_marcado_a_quien_ya_no_puede_competir(self):
        """Se guardo la lista y DESPUES llego la lesion: al abrir, no puede seguir marcado."""
        sano = ConvocationRecord.objects.create(team=self.team, match=self.match)
        sano.players.set(self.jugadores)

        respuesta = self.client.get(reverse("convocation"), {"match_id": self.match.id, "team": self.team.id})
        self.assertEqual(respuesta.status_code, 200)
        seleccionados = json.loads(respuesta.context["selected_player_ids_json"])
        self.assertNotIn(self.lesionado.id, seleccionados)
        self.assertEqual(len(seleccionados), 4)

        caidos = json.loads(respuesta.context["caidos_de_la_lista_json"])
        self.assertEqual(caidos, [self.lesionado.name], "y se dice, no se descuenta en silencio")
