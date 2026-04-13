from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import connection


def _dependency_status():
    checks = {}
    try:
        import weasyprint  # noqa: F401

        checks['weasyprint'] = {'ok': True, 'detail': 'available'}
    except Exception as exc:
        checks['weasyprint'] = {'ok': False, 'detail': str(exc)}

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
                pass
        results['paths'][key] = {
            'ok': path.exists(),
            'detail': str(path),
        }
    if use_s3_media:
        results['paths']['media_root'] = {
            'ok': True,
            'detail': 'S3 (USE_S3_MEDIA=true)',
        }

    overall_ok = (
        results['database']['ok']
        and all(item['ok'] for item in results['paths'].values())
    )
    results['ok'] = overall_ok
    return results
