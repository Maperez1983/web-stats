"""La URL de una foto no puede cambiar en cada render.

Medido en producción: 9,5 MB de avatares y escudos se volvían a bajar ENTEROS en cada
visita a la portada del entrenador, porque el bucket firma cada URL con la hora actual y
el navegador veía una dirección distinta cada vez.
"""
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from webstats.storages import MediaConUrlEstable


class _S3Falso:
    """Imita al backend real: cada llamada devuelve una firma distinta, como boto3."""

    def __init__(self):
        self.llamadas = 0

    def url(self, name, parameters=None, expire=None, http_method=None):
        self.llamadas += 1
        return f"https://bucket.s3.amazonaws.com/{name}?X-Amz-Signature=firma{self.llamadas}"


class UrlDeMediosEstableTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.falso = _S3Falso()
        self.almacen = MediaConUrlEstable.__new__(MediaConUrlEstable)
        self.almacen.querystring_auth = True
        self._parche = mock.patch.object(
            MediaConUrlEstable,
            "url",
            autospec=True,
            side_effect=lambda self_, name, **kw: MediaConUrlEstable.url(self_, name, **kw),
        )

    def _con_backend_falso(self):
        return mock.patch(
            "webstats.storages.S3Storage.url",
            autospec=True,
            side_effect=lambda self_, name, parameters=None, expire=None, http_method=None: self.falso.url(
                name, parameters, expire, http_method
            ),
        )

    def test_dos_renders_seguidos_dan_la_misma_url(self):
        with self._con_backend_falso():
            una = self.almacen.url("media/player-13.png")
            otra = self.almacen.url("media/player-13.png")
        self.assertEqual(una, otra)
        self.assertEqual(self.falso.llamadas, 1, "la segunda vez no se vuelve a firmar")

    def test_cada_foto_tiene_la_suya(self):
        with self._con_backend_falso():
            una = self.almacen.url("media/player-13.png")
            otra = self.almacen.url("media/player-99.png")
        self.assertNotEqual(una, otra)

    def test_la_url_sigue_firmada(self):
        """El bucket es privado y las fotos son de menores: la firma no se quita."""
        with self._con_backend_falso():
            url = self.almacen.url("media/player-13.png")
        self.assertIn("X-Amz-Signature", url)

    def test_una_peticion_con_parametros_propios_se_firma_aparte(self):
        """Rangos de vídeo o descargas forzadas no pueden compartir URL cacheada."""
        with self._con_backend_falso():
            self.almacen.url("media/video.mp4")
            self.almacen.url("media/video.mp4", parameters={"ResponseContentDisposition": "attachment"})
        self.assertEqual(self.falso.llamadas, 2)

    def test_si_el_bucket_es_publico_no_se_toca_nada(self):
        self.almacen.querystring_auth = False
        with self._con_backend_falso():
            self.almacen.url("media/player-13.png")
            self.almacen.url("media/player-13.png")
        self.assertEqual(self.falso.llamadas, 2, "sin firma no hay nada que estabilizar")

    def test_si_la_cache_falla_la_foto_sigue_saliendo(self):
        with self._con_backend_falso(), mock.patch(
            "webstats.storages.cache.get", side_effect=RuntimeError("cache caída")
        ), mock.patch("webstats.storages.cache.set", side_effect=RuntimeError("cache caída")):
            url = self.almacen.url("media/player-13.png")
        self.assertIn("X-Amz-Signature", url)
