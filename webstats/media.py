import mimetypes
import os
from typing import Iterator, Optional, Tuple

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.utils._os import safe_join


def _parse_range_header(range_header: str, size: int) -> Optional[Tuple[int, int]]:
    """
    Parse a single HTTP Range header of form: "bytes=start-end".
    Returns (start, end) inclusive, or None if invalid/unsatisfiable.
    """
    if not range_header:
        return None
    value = str(range_header).strip().lower()
    if not value.startswith('bytes='):
        return None
    value = value.replace('bytes=', '', 1).strip()
    if ',' in value:
        # Multiple ranges not supported.
        return None
    if '-' not in value:
        return None
    start_raw, end_raw = value.split('-', 1)
    start_raw = start_raw.strip()
    end_raw = end_raw.strip()

    try:
        if start_raw == '':
            # Suffix range: last N bytes.
            suffix_len = int(end_raw)
            if suffix_len <= 0:
                return None
            if suffix_len >= size:
                return 0, max(0, size - 1)
            return max(0, size - suffix_len), max(0, size - 1)
        start = int(start_raw)
        end = int(end_raw) if end_raw else (size - 1)
    except (TypeError, ValueError):
        return None

    if start < 0:
        return None
    if start >= size:
        return None
    if end < start:
        return None
    end = min(end, size - 1)
    return start, end


def _iter_file_range(path: str, start: int, end: int, chunk_size: int = 1024 * 256) -> Iterator[bytes]:
    remaining = (end - start) + 1
    with open(path, 'rb') as f:
        f.seek(start)
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@login_required
def protected_media_serve(request, path: str):
    """
    Serve /media/ files from MEDIA_ROOT with support for single Range requests.

    This is critical for HTML5 <video> playback on Safari/iOS, which heavily
    relies on Range (206 Partial Content) to load metadata and seek reliably.
    """
    # Only used when MEDIA_URL is local (non-S3) and routed by webstats/urls.py.
    media_root = str(getattr(settings, 'MEDIA_ROOT', '') or '')
    if not media_root:
        raise Http404('MEDIA_ROOT no configurado')

    try:
        absolute_path = safe_join(media_root, path)
    except Exception as exc:
        raise Http404('Ruta inválida') from exc

    if not os.path.exists(absolute_path) or not os.path.isfile(absolute_path):
        raise Http404('Archivo no encontrado')

    size = os.path.getsize(absolute_path)
    content_type = mimetypes.guess_type(absolute_path)[0] or 'application/octet-stream'

    range_header = request.META.get('HTTP_RANGE', '')
    parsed = _parse_range_header(range_header, size=size)
    if not parsed:
        resp = FileResponse(open(absolute_path, 'rb'), content_type=content_type)
        resp['Accept-Ranges'] = 'bytes'
        resp['Content-Length'] = str(size)
        resp['Cache-Control'] = 'private, max-age=0'
        return resp

    start, end = parsed
    response = StreamingHttpResponse(
        _iter_file_range(absolute_path, start=start, end=end),
        status=206,
        content_type=content_type,
    )
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str((end - start) + 1)
    response['Content-Range'] = f'bytes {start}-{end}/{size}'
    response['Cache-Control'] = 'private, max-age=0'
    return response

