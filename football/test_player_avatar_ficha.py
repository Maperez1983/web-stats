import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from football.models import Player, Team


class PlayerAvatarFichaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juan", is_active=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_profile_form_saves_skin_grade_and_hair(self):
        url = reverse("player-detail", args=[self.player.id])
        self.client.post(
            url,
            {"form_action": "profile", "skin_grade": "5", "hair_color": "#1a1a1a"},
            HTTP_HOST="localhost",
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.skin_grade, 5)
        self.assertEqual(self.player.hair_color, "#1a1a1a")

    def test_profile_form_rejects_bad_values(self):
        url = reverse("player-detail", args=[self.player.id])
        self.client.post(
            url,
            {"form_action": "profile", "skin_grade": "9", "hair_color": "rojo"},
            HTTP_HOST="localhost",
        )
        self.player.refresh_from_db()
        self.assertIsNone(self.player.skin_grade)
        self.assertEqual(self.player.hair_color, "")

    def test_preview_query_overrides_change_output(self):
        base = reverse("player-avatar-recolored", args=[self.player.id])
        plain = self.client.get(base, HTTP_HOST="localhost").content
        tinted = self.client.get(base + "?g=6&h=%231a1a1a", HTTP_HOST="localhost").content
        self.assertNotEqual(plain, tinted)

    def test_lineup_card_exposes_avatar_url_when_personalized(self):
        from football.views import _safe_initial_eleven_player_card

        # Sin personalización: sin avatar_url (usa kit genérico por rol en el campo).
        self.assertEqual(_safe_initial_eleven_player_card(self.player)["avatar_url"], "")
        # Con grado de piel: la tarjeta expone la URL del avatar recoloreado.
        self.player.skin_grade = 3
        self.player.save()
        card = _safe_initial_eleven_player_card(self.player)
        self.assertEqual(card["avatar_url"], reverse("player-avatar-recolored", args=[self.player.id]))

    def test_resolver_priority(self):
        from django.core.files.base import ContentFile
        from football.views import resolve_player_avatar_url

        # 1) nada -> ''
        self.assertEqual(resolve_player_avatar_url(self.player), "")
        # 2) grado de piel -> avatar recoloreado (sintético)
        self.player.skin_grade = 4
        self.player.save()
        self.assertEqual(resolve_player_avatar_url(self.player), reverse("player-avatar-recolored", args=[self.player.id]))
        # 3) avatar generado (face-swap) -> tiene prioridad sobre el sintético.
        # El avatar ya no se sirve por la URL firmada del bucket -que cambiaba en cada
        # render- sino por una direccion nuestra y estable (/media/f/<token>/), asi que se
        # comprueba a que fichero apunta, que es lo que este test siempre quiso decir.
        from football import media_estable

        self.player.avatar_generated.save("gen.png", ContentFile(b"\x89PNG\r\n\x1a\n"), save=True)
        url = resolve_player_avatar_url(self.player)
        self.assertTrue(url.startswith("/media/f/"), url)
        token = url.split("/media/f/")[1].rstrip("/")
        self.assertIn("player-avatars/", media_estable.nombre_de(token))

    def test_editor_catalog_exposes_display(self):
        from django.test import RequestFactory
        from football.views import _build_tactical_player_catalog

        req = RequestFactory().get("/")
        req.user = self.user
        # jugador con grado de piel -> display.mode = 'avatar'
        self.player.skin_grade = 2
        self.player.save()
        catalog = _build_tactical_player_catalog(req, self.team)
        entry = next((c for c in catalog if c.get("id") == self.player.id), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["display"]["mode"], "avatar")
        self.assertIn("display", entry)

    def test_avatar_pending_flag(self):
        from football.views import player_avatar_pending
        from football.management.commands.generate_player_avatars import _inputs_key

        # Sin características ni foto -> no hay nada pendiente.
        self.assertFalse(player_avatar_pending(self.player))
        # Con característica y sin avatar generado -> pendiente. Hace falta saber su edad: sin
        # fecha de nacimiento ni categoría del equipo no hay cuerpo que ponerle, y entonces no es
        # trabajo pendiente sino un dato que falta.
        self.player.birth_date = datetime.date(2000, 5, 9)
        self.player.skin_grade = 3
        self.player.save()
        self.assertTrue(player_avatar_pending(self.player))
        # Tras "generar" (clave al día) -> ya no pendiente.
        self.player.avatar_source_key = _inputs_key(self.player)
        self.player.save()
        self.assertFalse(player_avatar_pending(self.player))
        # Si cambia una característica -> vuelve a pendiente.
        self.player.hairstyle = "rizado"
        self.player.save()
        self.assertTrue(player_avatar_pending(self.player))

    def test_goalkeeper_gets_goalkeeper_figure(self):
        from football.views import resolve_player_avatar_url
        gk = Player.objects.create(team=self.team, name="Portero", position="Portero", is_active=True, skin_grade=3)
        url = resolve_player_avatar_url(gk)
        # Un portero NO recibe la figura de CAMPO recoloreada, pero tampoco se queda sin nada:
        # la biblioteca tiene figura de portero y antes no la usaba nadie, así que en la pizarra
        # acababa con el muñeco genérico.
        self.assertNotIn("player-avatar-recolored", url)
        self.assertNotEqual(url, "")
        self.assertIn("gk_", url)

    def test_profile_form_saves_hairstyle(self):
        url = reverse("player-detail", args=[self.player.id])
        self.client.post(url, {"form_action": "profile", "hairstyle": "rizado"}, HTTP_HOST="localhost")
        self.player.refresh_from_db()
        self.assertEqual(self.player.hairstyle, "rizado")
        # valor inválido -> vacío
        self.client.post(url, {"form_action": "profile", "hairstyle": "mohicano"}, HTTP_HOST="localhost")
        self.player.refresh_from_db()
        self.assertEqual(self.player.hairstyle, "")


class AvatarGenericoPorEdadTests(TestCase):
    """
    Un jugador sin datos tiene que salir igualmente, y con el cuerpo de su edad.

    Antes se quedaba sin avatar y el llamante caía en un PNG de adulto para todo el mundo: en la
    pizarra de un benjamín salían veinte hombres hechos y derechos.
    """

    def setUp(self):
        self.benjamines = Team.objects.create(name="Benagalbón Benjamín A", slug="benj-a", category="Benjamín")
        self.senior = Team.objects.create(name="Benagalbón", slug="senior", category="Senior")

    def test_cuerpo_por_categoria_cuando_falta_la_fecha(self):
        from football.management.commands.generate_player_avatars import figura_para

        nino = Player.objects.create(team=self.benjamines, name="Nino", is_active=True)
        figura = figura_para(nino)
        self.assertIsNotNone(figura, "un benjamín sin fecha debe coger el cuerpo de su categoría")
        self.assertTrue(figura["clave"].startswith("peque"), figura)

    def test_la_fecha_manda_sobre_la_categoria(self):
        from football.management.commands.generate_player_avatars import figura_para

        # Un cadete apuntado por error en el equipo de benjamines: manda SU fecha.
        mayor = Player.objects.create(
            team=self.benjamines, name="Mayor", is_active=True, birth_date=datetime.date(2011, 1, 1)
        )
        self.assertEqual(figura_para(mayor)["clave"][:3], "ado")

    def test_el_resolver_da_figura_generica_al_nino_y_nada_al_adulto(self):
        from football.views import resolve_player_avatar_url

        nino = Player.objects.create(team=self.benjamines, name="Nino2", is_active=True)
        url = resolve_player_avatar_url(nino)
        self.assertIn("nino_peque", url, "el niño sin datos debe recibir un cuerpo de niño")
        # El adulto se queda como estaba: '' y el llamante pone su PNG de siempre.
        adulto = Player.objects.create(team=self.senior, name="Adulto", is_active=True)
        self.assertEqual(resolve_player_avatar_url(adulto), "")

    def test_variantes_repartidas_pero_estables(self):
        from football.management.commands.generate_player_avatars import figura_para

        ninos = [Player.objects.create(team=self.benjamines, name=f"N{i}", is_active=True) for i in range(6)]
        claves = [figura_para(p)["clave"] for p in ninos]
        self.assertGreater(len(set(claves)), 1, "seis niños no pueden salir todos con el mismo cuerpo")
        # Y el reparto no cambia entre llamadas: nadie cambia de cuerpo al regenerar.
        self.assertEqual(claves, [figura_para(p)["clave"] for p in ninos])


class PizarraPlantillaNinosTests(TestCase):
    """En el campo de Inicio, un benjamín 'a prueba' no puede salir con chándal de adulto."""

    def test_el_nino_a_prueba_lleva_chandal_pero_el_suyo(self):
        from football.views import _build_coach_pitch_board_players

        equipo = Team.objects.create(name="Benagalbón Benjamín A", slug="bj-a", category="Benjamín")
        nino = Player.objects.create(team=equipo, name="Nino", position="MC", is_active=True)
        grupos = _build_coach_pitch_board_players(equipo, [nino], {}, set())
        ficha = grupos[0] if isinstance(grupos, list) else [c for g in grupos.values() for c in g][0]
        self.assertEqual(ficha["state"], "trial", "sigue siendo a prueba: el estado manda")
        self.assertIn("chandal_peque.png", ficha["avatar"], "chándal, sí, pero el de su edad")

    def test_el_adulto_a_prueba_conserva_su_chandal(self):
        from football.views import _build_coach_pitch_board_players

        equipo = Team.objects.create(name="Benagalbón", slug="sr", category="Senior")
        adulto = Player.objects.create(team=equipo, name="Adulto", position="MC", is_active=True)
        grupos = _build_coach_pitch_board_players(equipo, [adulto], {}, set())
        ficha = grupos[0] if isinstance(grupos, list) else [c for g in grupos.values() for c in g][0]
        self.assertEqual(ficha["avatar_url"], "")
        self.assertIn("chandal_black.png", ficha["avatar"])


class EdadImposibleTests(TestCase):
    """Hay fichas reales con el año '0017' en vez de '2017'. Un dato así no puede decidir nada."""

    def test_una_edad_imposible_se_trata_como_desconocida(self):
        from football.management.commands.generate_player_avatars import edad_de, figura_para

        equipo = Team.objects.create(name="Benagalbón Benjamín A", slug="bj-err", category="Benjamín")
        marc = Player.objects.create(
            team=equipo, name="Marc", is_active=True, birth_date=datetime.date(17, 1, 1)
        )
        self.assertIsNone(edad_de(marc), "2009 años no es una edad")
        # Y entonces manda la categoría del equipo: cuerpo de niño, no de adulto.
        self.assertTrue(figura_para(marc)["clave"].startswith("peque"))
