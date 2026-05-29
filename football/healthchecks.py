from __future__ import annotations

import contextlib
import io
import logging
from pathlib import Path

from django.conf import settings
from django.db import connection

from football import pdf_services


logger = logging.getLogger(__name__)


def _weasyprint_status():
    if not pdf_services.weasyprint:
        return {'ok': False, 'detail': 'weasyprint not available'}
    pydyf_ok, pydyf_version = pdf_services.pydyf_compat_status()
    if not pydyf_ok:
        return {'ok': False, 'detail': f'pydyf incompatible ({pydyf_version})'}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            pdf_prefix = pdf_services.weasyprint.HTML(string='<p>ok</p>').write_pdf()[:4]
        if pdf_prefix != b'%PDF':
            raise RuntimeError('PDF smoke did not return a PDF header')
        return {'ok': True, 'detail': 'available; pdf render ok'}
    except Exception as exc:
        return {'ok': False, 'detail': str(exc)}


def _dependency_status():
    checks = {}
    checks['weasyprint'] = _weasyprint_status()

    try:
        import pytesseract  # noqa: F401

        checks['pytesseract'] = {'ok': True, 'detail': 'available'}
    except Exception as exc:
        checks['pytesseract'] = {'ok': False, 'detail': str(exc)}

    try:
        import PIL  # noqa: F401

        checks['pillow'] = {'ok': True, 'detail': 'available'}
    except Exception as exc:
        checks['pillow'] = {'ok': False, 'detail': str(exc)}

    return checks


def _s3_media_status():
    """
    Best-effort check that the configured S3 bucket works for media storage.

    - Avoids leaking secrets; reports only non-sensitive config.
    - Uses django-storages backend when USE_S3_MEDIA=true.
    """
    if not bool(getattr(settings, 'USE_S3_MEDIA', False)):
        return {'ok': True, 'detail': 'disabled'}
    bucket = str(getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or '').strip()
    region = str(getattr(settings, 'AWS_S3_REGION_NAME', '') or '').strip()
    media_url = str(getattr(settings, 'MEDIA_URL', '') or '').strip()
    detail = {
        'bucket': bucket,
        'region': region,
        'media_url': media_url,
        'can_write': False,
        'note': 'S3 status is best-effort',
    }
    try:
        from django.core.files.base import ContentFile  # noqa: WPS433
        from django.core.files.storage import default_storage  # noqa: WPS433

        key = f'healthcheck/{bucket or "bucket"}/ping.txt'
        saved = default_storage.save(key, ContentFile(b'ping'))
        # Read-back (optional but helps detect permission issues).
        try:
            with default_storage.open(saved, 'rb') as fh:
                _ = fh.read(8)
        except Exception:
            logger.debug('Healthcheck S3 read-back failed.', exc_info=True)
        try:
            default_storage.delete(saved)
        except Exception:
            logger.debug('Healthcheck S3 cleanup failed.', exc_info=True)
        detail['can_write'] = True
        return {'ok': True, 'detail': detail}
    except Exception as exc:
        detail['error'] = f'{exc.__class__.__name__}: {exc}'
        return {'ok': False, 'detail': detail}


def run_system_healthcheck():
    results = {
        'database': {'ok': False, 'detail': 'not checked'},
        'paths': {},
        'dependencies': _dependency_status(),
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        results['database'] = {'ok': True, 'detail': 'query ok'}
    except Exception as exc:
        results['database'] = {'ok': False, 'detail': str(exc)}

    use_s3_media = bool(getattr(settings, 'USE_S3_MEDIA', False))
    expected_paths = {
        'static_root': Path(settings.BASE_DIR) / 'staticfiles',
        'input_dir': Path(settings.BASE_DIR) / 'data' / 'input',
    }
    # Si se usa S3 para media, la carpeta local puede no existir (y no es un fallo).
    if not use_s3_media:
        expected_paths['media_root'] = Path(settings.MEDIA_ROOT)
    for key, path in expected_paths.items():
        # Autorreparación: si media_root no existe, intentamos crearlo (evita 500 en PDFs).
        if key == 'media_root' and not use_s3_media:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception:
                logger.debug('Healthcheck could not create media_root.', exc_info=True)
        results['paths'][key] = {
            'ok': path.exists(),
            'detail': str(path),
        }
    if use_s3_media:
        results['paths']['media_root'] = {
            'ok': True,
            'detail': 'S3 (USE_S3_MEDIA=true)',
        }
        results['s3_media'] = _s3_media_status()

    overall_ok = (
        results['database']['ok']
        and all(item['ok'] for item in results['paths'].values())
    )
    results['ok'] = overall_ok
    return results
