"""Los medios privados se sirven por una dirección NUESTRA, estable y cacheable.

Medido en producción: 9,5 MB de avatares y escudos se volvían a bajar enteros en cada
visita, porque el bucket firmaba cada URL de nuevo y la dirección de la misma foto cambiaba
a cada carga.
"""
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.urls import reverse

from football import media_estable


class _Fichero:
    def __init__(self, name):
        self.name = name

    @property
    def url(self):
        return f"https://bucket.s3.amazonaws.com/{self.name}?X-Amz-Signature=cambiante"


class DireccionEstableTests(TestCase):
    def test_la_direccion_no_cambia_entre_llamadas(self):
        """Es todo el objetivo: la misma foto, la misma dirección."""
        fichero = _Fichero("media/player-avatars/player-13_RgG3ty1.png")
        self.assertEqual(media_estable.url_estable(fichero), media_estable.url_estable(fichero))

    def test_al_reemplazar_la_foto_cambia_la_direccion(self):
        """El bucket guarda cada versión con otro nombre, así que se puede cachear un año
        sin miedo a servir una foto vieja."""
        vieja = media_estable.url_estable(_Fichero("media/player-avatars/player-13_AAA.png"))
        nueva = media_estable.url_estable(_Fichero("media/player-avatars/player-13_BBB.png"))
        self.assertNotEqual(vieja, nueva)

    def test_sin_fichero_no_hay_direccion(self):
        self.assertEqual(media_estable.url_estable(_Fichero("")), "")
        self.assertEqual(media_estable.url_estable(None), "")

    def test_un_token_manipulado_no_vale(self):
        token = media_estable.token_de("media/foto.png")
        self.assertEqual(media_estable.nombre_de(token), "media/foto.png")
        self.assertEqual(media_estable.nombre_de(token[:-3] + "xxx"), "")
        self.assertEqual(media_estable.nombre_de("cualquier-cosa"), "")

    def test_un_token_firmado_no_puede_salirse_del_almacen(self):
        """Aunque alguien consiguiera firmar, no puede pedir ficheros del servidor."""
        for malo in ("/etc/passwd", "../../secreto.txt", "media/../../etc/hosts"):
            token = signing.dumps({"n": malo}, salt=media_estable.SAL, compress=True)
            self.assertEqual(media_estable.nombre_de(token), "", malo)


class VistaDeMediosTests(TestCase):
    def setUp(self):
        self.url = reverse("media-file", args=[media_estable.token_de("media/no-existe.png")])

    def test_sin_sesion_no_se_sirve(self):
        """Son fotos del club: la dirección es estable, no pública."""
        respuesta = self.client.get(self.url)
        self.assertIn(respuesta.status_code, (302, 403))

    def test_un_token_invalido_da_404(self):
        get_user_model().objects.create_user("mirona", password="x")
        self.client.login(username="mirona", password="x")
        respuesta = self.client.get(reverse("media-file", args=["esto-no-es-un-token"]))
        self.assertEqual(respuesta.status_code, 404)
