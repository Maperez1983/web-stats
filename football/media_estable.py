"""Direcciones ESTABLES para los medios privados (avatares, escudos, recursos de jugador).

El problema, medido en producción: 9,5 MB de avatares y escudos se volvían a bajar enteros
en cada visita. No porque pesen —que también—, sino porque el bucket es privado y cada
render firmaba la URL de nuevo: la dirección de la misma foto cambiaba a cada carga y el
navegador no podía reutilizar ni un byte.

Aquí la dirección la ponemos nosotros y no caduca: `/media/f/<token>/`, donde el token
lleva firmado el nombre del fichero en el almacén. Como el bucket guarda cada versión con
un nombre distinto (`AWS_S3_FILE_OVERWRITE = False` → `player-13_RgG3ty1.png`), al
reemplazar una foto cambia el nombre, cambia el token y cambia la dirección: se puede
cachear un año sin miedo a servir una foto vieja.

Sigue siendo privado: la vista exige sesión iniciada, igual que la página que muestra la
imagen. Lo que se gana es que la dirección no cambia entre visitas.

Es el mismo patrón que el proyecto ya usa para las fotos de jugador (`player-photo-file`);
lo único distinto es que aquí sí se puede cachear largo, porque el nombre versiona.
"""
import logging

from django.core import signing
from django.urls import reverse

logger = logging.getLogger(__name__)

SAL = "medios-estables"


# OJO: `signing.dumps` firma CON MARCA DE TIEMPO, asi que el token cambiaba cada segundo y
# la direccion volvia a ser distinta en cada render -justo lo que veniamos a arreglar-.
# `Signer` no lleva tiempo: mismo nombre, mismo token, siempre.
_firmante = signing.Signer(salt=SAL)


def token_de(nombre_en_almacen):
    return _firmante.sign_object({"n": str(nombre_en_almacen)}, compress=True)


def nombre_de(token):
    """Devuelve el nombre del fichero, o '' si el token no es nuestro o viene manipulado."""
    try:
        datos = _firmante.unsign_object(str(token))
    except signing.BadSignature:
        return ""
    except Exception:
        return ""
    nombre = str((datos or {}).get("n") or "").strip()
    # Un token válido nunca sale del almacén: sin esto, uno firmado con un nombre relativo
    # podría pedir cualquier cosa del disco del servidor.
    if not nombre or nombre.startswith("/") or ".." in nombre:
        return ""
    return nombre


def url_estable(fichero):
    """`/media/f/<token>/` para un FieldFile. Cadena vacía si no hay fichero."""
    nombre = str(getattr(fichero, "name", "") or "").strip()
    if not nombre:
        return ""
    try:
        return reverse("media-file", args=[token_de(nombre)])
    except Exception:
        logger.debug("No se pudo construir la URL estable del medio", exc_info=True)
        try:
            return fichero.url
        except Exception:
            return ""
