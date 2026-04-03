import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Diagnóstico rápido de sesión/token y endpoints de Universo RFAF.'

    def add_arguments(self, parser):
        parser.add_argument('--group-id', default=os.getenv('RIVAL_ROSTER_GROUP_ID', '').strip())

    def handle(self, *args, **options):
        from football.views import (
            _fetch_universo_access_token_via_login,
            _load_universo_access_token,
            _load_universo_access_token_expires,
            _universo_api_post,
        )

        group_id = str(options.get('group_id') or '').strip()
        self.stdout.write('== Universo RFAF diagnostics ==')
        self.stdout.write(f'RFAF_USER set: {bool(str(os.getenv("RFAF_USER", "") or "").strip())}')
        self.stdout.write(f'RFAF_PASS set: {bool(str(os.getenv("RFAF_PASS", "") or "").strip())}')
        self.stdout.write(f'RFAF_ACCESS_TOKEN set: {bool(str(os.getenv("RFAF_ACCESS_TOKEN", "") or "").strip())}')

        token = _load_universo_access_token()
        memo = getattr(_load_universo_access_token, '_memo', None)
        expires = _load_universo_access_token_expires()
        self.stdout.write(f'Token loaded: {bool(token)}')
        if isinstance(memo, dict) and memo.get('error'):
            self.stdout.write(f'Token error: {memo.get("error")}')
        if expires:
            try:
                dt = datetime.fromtimestamp(float(expires), tz=timezone.utc).astimezone(timezone.get_current_timezone())
                self.stdout.write(f'Token expires: {dt.strftime("%Y-%m-%d %H:%M:%S %Z")}')
                self.stdout.write(f'Token expired?: {dt <= timezone.now()}')
            except Exception:
                self.stdout.write(f'Token expires ts: {expires}')

        if not group_id:
            self.stdout.write('No group-id provided. Use --group-id 45030656')
            # Igual mostramos el diagnóstico de login.
        login_token, login_exp, login_error = _fetch_universo_access_token_via_login()
        if login_error:
            self.stdout.write(f'Login error: {login_error}')
        else:
            self.stdout.write(f'Login token received: {bool(login_token)}')
            if login_exp:
                try:
                    dt = datetime.fromtimestamp(float(login_exp), tz=timezone.utc).astimezone(timezone.get_current_timezone())
                    self.stdout.write(f'Login token expires: {dt.strftime("%Y-%m-%d %H:%M:%S %Z")}')
                except Exception:
                    self.stdout.write(f'Login token expires ts: {login_exp}')
        if not group_id:
            return

        payload = _universo_api_post('competition/get-classification', {'id_group': group_id})
        ok = bool(payload and isinstance(payload, dict) and str(payload.get('estado') or '').strip() == '1')
        rows = payload.get('clasificacion') if isinstance(payload, dict) else None
        self.stdout.write(f'Classification ok: {ok}')
        self.stdout.write(f'Classification rows: {len(rows) if isinstance(rows, list) else 0}')
        if isinstance(payload, dict):
            self.stdout.write(f'Classification keys: {sorted(list(payload.keys()))[:25]}')
