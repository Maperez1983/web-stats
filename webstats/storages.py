"""Almacenamiento de medios con URL estable.

El bucket es privado y las fotos son de menores, así que las URLs van FIRMADAS y eso no
se toca. El problema no era la firma: era que se generaba una firma nueva en cada render,
así que la URL de la misma foto cambiaba en cada carga de página y el navegador no podía
reutilizar ni un byte. Medido en producción: 9,5 MB de avatares y escudos volvían a
bajarse enteros en CADA visita a la portada del entrenador.

La firma dura 12 h (`AWS_QUERYSTRING_EXPIRE`). Aquí se guarda la URL ya firmada durante
una ventana más corta que esa validez, de modo que todos los renders de esa ventana
devuelven exactamente la misma URL y el navegador puede cachearla. Ni el bucket deja de
ser privado ni la firma deja de caducar.
"""
import hashlib
import logging

from django.core.cache import cache
from storages.backends.s3 import S3Storage

logger = logging.getLogger(__name__)


class MediaConUrlEstable(S3Storage):
    # La mitad de la validez de la firma: la URL más "vieja" que puede recibir alguien
    # todavía le sirve otras 6 horas.
    VENTANA_SEGUNDOS = 6 * 60 * 60

    def url(self, name, parameters=None, expire=None, http_method=None):
        # Sólo se reutiliza la URL SIMPLE de lectura. Cualquier petición con parámetros
        # propios (rangos, descargas forzadas, otro método) se firma aparte, como siempre.
        if parameters or expire or http_method or not getattr(self, "querystring_auth", True):
            return super().url(name, parameters=parameters, expire=expire, http_method=http_method)

        clave = "media-url:" + hashlib.sha1(str(name).encode("utf-8", "ignore")).hexdigest()
        try:
            guardada = cache.get(clave)
        except Exception:
            guardada = None
        if guardada:
            return guardada

        firmada = super().url(name)
        try:
            cache.set(clave, firmada, self.VENTANA_SEGUNDOS)
        except Exception:
            logger.debug("No se pudo guardar la URL de medios en caché", exc_info=True)
        return firmada
