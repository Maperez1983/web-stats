import os
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError


COMMON_USER_FIELDS = [
    'username',
    'user',
    'usuario',
    'email',
    'login',
    'UserName',
    'Email',
]
COMMON_PASS_FIELDS = [
    'password',
    'pass',
    'clave',
    'passwd',
    'Password',
]


def _pick_form(soup: BeautifulSoup):
    forms = soup.find_all('form')
    if not forms:
        return None
    # Prefer a form that has password input
    for form in forms:
        if form.find('input', attrs={'type': 'password'}):
            return form
    return forms[0]


def _field_name(form, kind: str):
    if form is None:
        return None
    inputs = form.find_all('input')
    if kind == 'password':
        names = COMMON_PASS_FIELDS
        target_type = 'password'
    else:
        names = COMMON_USER_FIELDS
        target_type = None

    # Exact known names first
    for candidate in names:
        if form.find('input', attrs={'name': candidate}):
            return candidate

    # Heuristic by type and name
    for inp in inputs:
        name = (inp.get('name') or '').strip()
        if not name:
            continue
        input_type = (inp.get('type') or '').strip().lower()
        low_name = name.lower()
        if kind == 'password':
            if input_type == 'password' or any(token in low_name for token in ('pass', 'clave')):
                return name
        else:
            if input_type in ('text', 'email') and any(token in low_name for token in ('user', 'mail', 'login', 'usuario')):
                return name

    # As last resort use first text/email for user
    if kind != 'password':
        for inp in inputs:
            name = (inp.get('name') or '').strip()
            input_type = (inp.get('type') or '').strip().lower()
            if name and input_type in ('text', 'email'):
                return name
    return None


def _build_payload(form):
    payload = {}
    if not form:
        return payload
    for inp in form.find_all('input'):
        name = (inp.get('name') or '').strip()
        if not name:
            continue
        input_type = (inp.get('type') or '').strip().lower()
        value = inp.get('value')
        if input_type in ('hidden', 'submit') and value is not None:
            payload[name] = value
    return payload


class Command(BaseCommand):
    help = 'Prueba login autenticado en Universo RFAF usando variables de entorno.'

    def add_arguments(self, parser):
        parser.add_argument('--base-url', default=os.getenv('RFAF_UNIVERSO_BASE_URL', 'https://universo.rfaf.es/'))
        parser.add_argument('--login-url', default=os.getenv('RFAF_UNIVERSO_LOGIN_URL', '').strip())
        parser.add_argument('--target-url', default=os.getenv('RFAF_UNIVERSO_TARGET_URL', '').strip())
        parser.add_argument('--timeout', type=int, default=25)

    def handle(self, *args, **options):
        username = (os.getenv('RFAF_USER') or '').strip()
        password = (os.getenv('RFAF_PASS') or '').strip()
        if not username or not password:
            raise CommandError('Faltan RFAF_USER / RFAF_PASS en variables de entorno.')

        base_url = (options['base_url'] or '').strip()
        login_url = (options['login_url'] or '').strip() or base_url
        target_url = (options['target_url'] or '').strip()
        timeout = options['timeout']

        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            raise CommandError(f'Base URL inválida: {base_url}')

        session = requests.Session()
        ua = (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/123.0.0.0 Safari/537.36'
        )
        headers = {
            'User-Agent': ua,
            'Accept-Language': 'es-ES,es;q=0.9',
        }

        self.stdout.write(f'Abriendo login: {login_url}')
        try:
            login_get = session.get(login_url, headers=headers, timeout=timeout, allow_redirects=True)
            login_get.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f'No se pudo abrir login: {exc}') from exc

        soup = BeautifulSoup(login_get.text, 'html.parser')
        form = _pick_form(soup)
        if not form:
            raise CommandError('No se encontró formulario de login en la página.')

        action = (form.get('action') or '').strip()
        post_url = urljoin(login_get.url, action) if action else login_get.url
        user_field = _field_name(form, 'user')
        pass_field = _field_name(form, 'password')
        if not user_field or not pass_field:
            raise CommandError(
                f'No se identificaron campos de credenciales (user={user_field}, pass={pass_field}).'
            )

        payload = _build_payload(form)
        payload[user_field] = username
        payload[pass_field] = password

        post_headers = dict(headers)
        post_headers['Referer'] = login_get.url
        origin = f"{parsed.scheme}://{parsed.netloc}"
        post_headers['Origin'] = origin

        self.stdout.write(
            f'Enviando credenciales a {post_url} (campos detectados: {user_field}/{pass_field})'
        )
        try:
            login_post = session.post(
                post_url,
                data=payload,
                headers=post_headers,
                timeout=timeout,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            raise CommandError(f'Fallo al enviar login: {exc}') from exc

        final_url = login_post.url
        final_html = login_post.text or ''
        lower_html = final_html.lower()
        likely_login_page = (
            'type="password"' in lower_html
            or 'iniciar sesión' in lower_html
            or 'iniciar sesion' in lower_html
            or 'login' in urlparse(final_url).path.lower()
        )

        success = login_post.status_code < 400 and not likely_login_page
        self.stdout.write(f'Respuesta login: {login_post.status_code} · URL final: {final_url}')

        if target_url:
            self.stdout.write(f'Probando acceso autenticado a: {target_url}')
            try:
                target_resp = session.get(target_url, headers=headers, timeout=timeout, allow_redirects=True)
                self.stdout.write(
                    f'Respuesta target: {target_resp.status_code} · URL final: {target_resp.url}'
                )
                if target_resp.status_code < 400 and 'type="password"' not in (target_resp.text or '').lower():
                    success = True
            except requests.RequestException as exc:
                self.stderr.write(f'No se pudo consultar target: {exc}')

        if success:
            self.stdout.write(self.style.SUCCESS('Login aparentemente correcto en Universo RFAF.'))
            return

        raise CommandError(
            'No se pudo confirmar login. Revisa URL de login/campos/cookies o posibles protecciones anti-bot.'
        )
