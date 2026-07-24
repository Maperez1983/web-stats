import io
import logging
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, storages

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None


logger = logging.getLogger(__name__)

# Tope de tamaño por documento subido (licencia/foto). Evita cargar en RAM ficheros enormes
# (save_player_license hace uploaded.read() completo) — protección frente a DoS por memoria.
MAX_PLAYER_DOCUMENT_BYTES = 15 * 1024 * 1024  # 15 MB


def player_license_storage_candidates(player):
    if not player:
        return []
    base_name = f'player-licenses/player-{player.id}'
    return [
        f'{base_name}.pdf',
        f'{base_name}.jpg',
        f'{base_name}.jpeg',
        f'{base_name}.png',
        f'{base_name}.webp',
    ]


def save_player_license(player, uploaded_license):
    """
    Guarda una licencia federativa del jugador (PDF o imagen).
    """
    if not player or not uploaded_license:
        return ''
    upload_size = int(getattr(uploaded_license, 'size', 0) or 0)
    if upload_size > MAX_PLAYER_DOCUMENT_BYTES:
        raise ValueError('La licencia supera el tamaño máximo permitido (15 MB).')
    try:
        storage = storages['default']
        if isinstance(storage, FileSystemStorage):
            storage = FileSystemStorage(location=getattr(settings, 'MEDIA_ROOT', None), base_url=getattr(settings, 'MEDIA_URL', '/media/'))

        raw_name = str(getattr(uploaded_license, 'name', '') or '')
        extension = Path(raw_name).suffix.lower()
        content_type = str(getattr(uploaded_license, 'content_type', '') or '').lower()
        is_pdf = extension == '.pdf' or content_type == 'application/pdf'

        if hasattr(uploaded_license, 'seek'):
            uploaded_license.seek(0)
        raw_bytes = uploaded_license.read()
        if not raw_bytes:
            return ''
        # No fiarse solo de la extensión/content-type (los controla el cliente): si dice ser
        # PDF, validamos la firma real (%PDF en la cabecera). Las imágenes se validan luego con PIL.
        if is_pdf and b'%PDF' not in raw_bytes[:1024]:
            raise ValueError('El archivo de licencia no es un PDF válido.')

        target_ext = '.pdf' if is_pdf else (extension if extension in {'.jpg', '.jpeg', '.png', '.webp'} else '.jpg')
        if is_pdf:
            content = ContentFile(raw_bytes)
            target_ext = '.pdf'
        else:
            if Image is None:
                if target_ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
                    return ''
                content = ContentFile(raw_bytes)
            else:
                try:
                    with Image.open(io.BytesIO(raw_bytes)) as img:
                        if ImageOps is not None:
                            try:
                                img = ImageOps.exif_transpose(img)
                            except Exception:
                                logger.debug('No se pudo aplicar EXIF transpose a la licencia del jugador %s', getattr(player, 'id', None), exc_info=True)
                        if img.mode in ('RGBA', 'LA', 'P'):
                            converted = img.convert('RGBA')
                            background = Image.new('RGBA', converted.size, (255, 255, 255, 255))
                            background.alpha_composite(converted)
                            normalized = background.convert('RGB')
                        else:
                            normalized = img.convert('RGB')
                        buffer = io.BytesIO()
                        normalized.save(buffer, format='JPEG', optimize=True, quality=82)
                        content = ContentFile(buffer.getvalue())
                        target_ext = '.jpg'
                except Exception:
                    logger.exception('No se pudo normalizar la imagen de licencia del jugador %s', getattr(player, 'id', None))
                    return ''

        target_name = f'player-licenses/player-{player.id}{target_ext}'
        for candidate in player_license_storage_candidates(player):
            try:
                if storage.exists(candidate):
                    storage.delete(candidate)
            except Exception:
                logger.exception('No se pudo limpiar una licencia previa del jugador %s', player.id)
        return storage.save(target_name, content)
    except Exception:
        logger.exception('No se pudo guardar la licencia del jugador %s', getattr(player, 'id', None))
        return ''
