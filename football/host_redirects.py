import os

from django.shortcuts import redirect


def redirect_to_app_host_if_landing(request, *, path: str):
    host = str(getattr(request, 'get_host', lambda: '')() or '').split(':', 1)[0].strip().lower()
    landing_hosts = [
        h.strip().lower()
        for h in (
            os.getenv(
                'LANDING_HOSTS',
                'segundajugada.es,www.segundajugada.es,segundajugada.com,www.segundajugada.com',
            )
            or ''
        ).split(',')
        if h.strip()
    ]
    if host not in landing_hosts:
        return None
    target_host = host[4:] if host.startswith('www.') else host
    app_url = f'https://app.{target_host}'
    return redirect(f'{app_url}{path}')
