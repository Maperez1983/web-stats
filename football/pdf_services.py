import base64
import inspect
import logging
import os
import re

from django.http import HttpResponse

logger = logging.getLogger(__name__)

try:
    import contextlib
    import io as _io

    with contextlib.redirect_stdout(_io.StringIO()), contextlib.redirect_stderr(_io.StringIO()):
        import weasyprint
except Exception:  # pragma: no cover
    weasyprint = None


def parse_version_tuple(raw_version: str):
    parts = [int(p) for p in re.findall(r'\d+', str(raw_version or ''))[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def pydyf_compat_status():
    try:
        import pydyf  # noqa: WPS433

        version = str(getattr(pydyf, '__version__', '') or '')
        parsed = parse_version_tuple(version)
        ok = (0, 10, 0) <= parsed < (0, 11, 0)
        try:
            pdf_cls = getattr(pydyf, 'PDF', None)
            sig = inspect.signature(pdf_cls) if pdf_cls else None
            params = list(getattr(sig, 'parameters', {}).values()) if sig else []
            if len(params) < 2:
                ok = False
        except Exception:
            pass
        return ok, version or 'unknown'
    except Exception:
        return False, 'not installed'


def _safe_url_fetcher(url, timeout=4, ssl_context=None):
    try:
        raw_url = str(url or '').strip()
        if raw_url.startswith('data:') and ',' in raw_url:
            import urllib.parse  # noqa: WPS433

            header, payload = raw_url.split(',', 1)
            mime = header[5:].split(';', 1)[0].strip() or 'application/octet-stream'
            if ';base64' in header:
                content = base64.b64decode(payload.encode('ascii'))
            else:
                content = urllib.parse.unquote_to_bytes(payload)
            return {'string': content, 'mime_type': mime}
    except Exception:
        pass
    try:
        default_fetcher = getattr(weasyprint, 'default_url_fetcher', None) if weasyprint else None
        if callable(default_fetcher):
            return default_fetcher(url, timeout=timeout, ssl_context=ssl_context)
    except Exception:
        pass
    return {'string': b'', 'mime_type': 'text/plain'}


def _write_pdf_bytes(request, html: str):
    return weasyprint.HTML(
        string=html,
        base_url=request.build_absolute_uri('/'),
        url_fetcher=_safe_url_fetcher,
    ).write_pdf()


def _current_build_id() -> str:
    return (
        os.getenv('RENDER_GIT_COMMIT')
        or os.getenv('RENDER_DEPLOY_ID')
        or os.getenv('SOURCE_VERSION')
        or os.getenv('GIT_SHA')
        or ''
    ).strip()


def render_pdf_bytes(request, html: str):
    if not weasyprint:
        return None
    pydyf_ok, _pydyf_version = pydyf_compat_status()
    if not pydyf_ok:
        return None
    try:
        return _write_pdf_bytes(request, html)
    except Exception:
        logger.exception('WeasyPrint: error generando PDF')
        return None


def render_pdf_bytes_with_error(request, html: str):
    if not weasyprint:
        return None, 'weasyprint not available'
    pydyf_ok, pydyf_version = pydyf_compat_status()
    if not pydyf_ok:
        return None, f'pydyf incompatible ({pydyf_version}); requires 0.10.x for weasyprint 57.x'
    try:
        return _write_pdf_bytes(request, html), ''
    except Exception as exc:
        logger.exception('WeasyPrint: error generando PDF (debug)')
        return None, f'{exc.__class__.__name__}: {exc}'


def build_pdf_response_or_html_fallback(request, html: str, filename: str, *, inline: bool = False, force_pdf: bool = False):
    if not weasyprint:
        if force_pdf:
            return HttpResponse('PDF no disponible en este servidor.', status=503)
        return HttpResponse(html, content_type='text/html; charset=utf-8')
    pydyf_ok, pydyf_version = pydyf_compat_status()
    if not pydyf_ok:
        message = f'PDF no disponible: servidor desactualizado (pydyf {pydyf_version}).'
        if force_pdf:
            return HttpResponse(message, status=503, content_type='text/plain; charset=utf-8')
        return HttpResponse(html, content_type='text/html; charset=utf-8')
    pdf_file, pdf_error = render_pdf_bytes_with_error(request, html)
    if pdf_file:
        response = HttpResponse(pdf_file, content_type='application/pdf')
        disposition = 'inline' if inline else 'attachment'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}.pdf"'
        response['Cache-Control'] = 'no-store, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        build_id = _current_build_id()
        if build_id:
            response['X-2J-Build'] = build_id
        return response
    logger.exception('WeasyPrint: error generando PDF (response): %s', pdf_error or 'unknown')
    if force_pdf:
        debug = str(request.GET.get('debug') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
        debug_allowed = bool(getattr(getattr(request, 'user', None), 'is_authenticated', False))
        if debug and debug_allowed:
            detail = (pdf_error or '').strip() or 'unknown'
            resp = HttpResponse(
                f'No se pudo generar el PDF. {detail}',
                status=503,
                content_type='text/plain; charset=utf-8',
            )
            resp['Cache-Control'] = 'no-store'
            return resp
        resp = HttpResponse('No se pudo generar el PDF.', status=503, content_type='text/plain; charset=utf-8')
        resp['Cache-Control'] = 'no-store'
        return resp
    return HttpResponse(html, content_type='text/html; charset=utf-8')
