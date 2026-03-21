import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError


def _first_existing(page, selectors):
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            return locator.first, selector
    return None, None


def _first_visible(locator):
    count = locator.count()
    for idx in range(count):
        candidate = locator.nth(idx)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def _dismiss_cookie_banners(page):
    # Try common CMP selectors/buttons used by many Spanish sites.
    selectors = [
        '#qc-cmp2-ui button:has-text("Aceptar todo")',
        '#qc-cmp2-ui button:has-text("Aceptar")',
        '#qc-cmp2-ui button[mode="primary"]',
        'button:has-text("Aceptar cookies")',
        'button:has-text("Accept all")',
        'button[aria-label*="Aceptar"]',
    ]
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            try:
                locator.first.click(timeout=2500)
                return selector
            except Exception:
                continue
    # Fallback: hide known CMP overlays if still intercepting events.
    try:
        page.evaluate(
            """
            () => {
              const ids = ['qc-cmp2-container', 'qc-cmp2-ui', 'qc-cmp2-main'];
              ids.forEach((id) => {
                const el = document.getElementById(id);
                if (el) {
                  el.style.display = 'none';
                  el.style.pointerEvents = 'none';
                }
              });
            }
            """
        )
    except Exception:
        pass
    return None


class Command(BaseCommand):
    help = (
        'Prueba login en Universo RFAF usando navegador (Playwright). '
        'Recomendado para páginas con login renderizado por JavaScript.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--base-url', default=os.getenv('RFAF_UNIVERSO_BASE_URL', 'https://www.universorfaf.es/'))
        parser.add_argument('--login-url', default=os.getenv('RFAF_UNIVERSO_LOGIN_URL', 'https://www.universorfaf.es/login'))
        parser.add_argument('--target-url', default=os.getenv('RFAF_UNIVERSO_TARGET_URL', 'https://www.universorfaf.es/dashboard'))
        parser.add_argument('--timeout-ms', type=int, default=25000)
        parser.add_argument('--headed', action='store_true', help='Abre navegador visible en lugar de headless.')
        parser.add_argument(
            '--manual-auth',
            action='store_true',
            help='No envía credenciales automáticamente. Permite login manual y guarda storage_state.',
        )
        parser.add_argument(
            '--manual-timeout-ms',
            type=int,
            default=180000,
            help='Tiempo de espera para completar login manual (ms).',
        )
        parser.add_argument(
            '--storage-state',
            default=str(Path('data') / 'input' / 'rfaf_storage_state.json'),
            help='Ruta de salida para guardar storage_state tras login válido.',
        )
        parser.add_argument(
            '--screenshot',
            default=str(Path('data') / 'debug' / 'rfaf_login_failure.png'),
            help='Ruta screenshot en caso de fallo de login.',
        )

    def handle(self, *args, **options):
        manual_auth = bool(options['manual_auth'])
        username = (os.getenv('RFAF_USER') or '').strip()
        password = (os.getenv('RFAF_PASS') or '').strip()
        if not manual_auth and (not username or not password):
            raise CommandError('Faltan RFAF_USER / RFAF_PASS en variables de entorno.')

        login_url = (options['login_url'] or '').strip()
        target_url = (options['target_url'] or '').strip()
        timeout_ms = int(options['timeout_ms'])
        manual_timeout_ms = int(options['manual_timeout_ms'])
        headless = not bool(options['headed'])
        screenshot_path = Path(options['screenshot']).expanduser()
        storage_state_path = Path(options['storage_state']).expanduser()

        for label, url in [('login', login_url), ('target', target_url)]:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise CommandError(f'URL inválida para {label}: {url}')

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            raise CommandError(
                'No se pudo importar Playwright. Instala dependencias y navegador: '
                '`pip install playwright && python -m playwright install chromium`'
            ) from exc

        self.stdout.write(f'Abrriendo login browser: {login_url}')

        user_selectors = [
            'input[name="username"]',
            'input[name="user"]',
            'input[name="email"]',
            'input[id="email"]',
            'input[autocomplete="username"]',
            'input[type="email"]',
            'input[type="text"]',
        ]
        pass_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[name*="pass"]',
            'input[id="password"]',
            'input[autocomplete="current-password"]',
        ]
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Iniciar sesión")',
            'button:has-text("Iniciar sesion")',
            'button:has-text("Acceder")',
            'button:has-text("Entrar")',
        ]

        with sync_playwright() as p:
            browser = None
            context = None
            page = None
            try:
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(locale='es-ES')
                page = context.new_page()
                page.set_default_timeout(timeout_ms)
                network_events = []
                console_events = []
                page_errors = []

                def _on_response(response):
                    try:
                        request = response.request
                        method = (request.method or '').upper()
                        if method not in ('POST', 'PUT', 'PATCH'):
                            return
                        url = response.url or ''
                        low_url = url.lower()
                        parsed_url = urlparse(url)
                        parsed_target = urlparse(login_url)
                        same_origin = (
                            parsed_url.scheme == parsed_target.scheme
                            and parsed_url.netloc == parsed_target.netloc
                        )
                        if not same_origin:
                            return
                        if request.resource_type not in ('xhr', 'fetch', 'document'):
                            return
                        if not any(token in low_url for token in ('login', 'auth', 'signin', 'session', 'token')):
                            return
                        network_events.append(
                            {
                                'status': response.status,
                                'url': url,
                                'resource': request.resource_type,
                            }
                        )
                    except Exception:
                        return

                def _on_console(msg):
                    try:
                        mtype = (msg.type or '').lower()
                        text = (msg.text or '').strip()
                        if text:
                            console_events.append({'type': mtype, 'text': text})
                    except Exception:
                        return

                def _on_page_error(exc):
                    try:
                        page_errors.append(str(exc))
                    except Exception:
                        return

                page.on('response', _on_response)
                page.on('console', _on_console)
                page.on('pageerror', _on_page_error)

                page.goto(login_url, wait_until='domcontentloaded')
                try:
                    page.wait_for_load_state('networkidle', timeout=min(timeout_ms, 8000))
                except PlaywrightTimeoutError:
                    pass
                accepted_selector = _dismiss_cookie_banners(page)
                if accepted_selector:
                    self.stdout.write(f'Banner cookies aceptado: {accepted_selector}')

                if manual_auth:
                    self.stdout.write(
                        'Modo manual: completa login en la ventana del navegador y espera confirmación automática.'
                    )
                    try:
                        page.wait_for_url(
                            lambda url: ('/login' not in (url or '').lower()) and url.startswith('http'),
                            timeout=manual_timeout_ms,
                        )
                    except PlaywrightTimeoutError as exc:
                        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(screenshot_path), full_page=True)
                        raise CommandError(
                            'No se confirmó salida de /login en modo manual. '
                            f'URL final: {page.url}. Screenshot: {screenshot_path}'
                        ) from exc

                    storage_state_path.parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=str(storage_state_path))
                    self.stdout.write(self.style.SUCCESS('Login manual confirmado.'))
                    self.stdout.write(self.style.SUCCESS(f'Storage state guardado en: {storage_state_path}'))
                    return

                submit_btn, submit_selector = _first_existing(page, submit_selectors)
                if submit_btn:
                    try:
                        submit_btn.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    form_locator = submit_btn.locator('xpath=ancestor::form[1]')
                    form = _first_visible(form_locator) or page.locator('form').first
                else:
                    form = page.locator('form').first

                user_input = None
                pass_input = None
                user_selector = None
                pass_selector = None

                for selector in user_selectors:
                    candidate = _first_visible(form.locator(selector))
                    if candidate:
                        user_input = candidate
                        user_selector = f'form {selector}'
                        break
                if not user_input:
                    for selector in user_selectors:
                        candidate = _first_visible(page.locator(selector))
                        if candidate:
                            user_input = candidate
                            user_selector = selector
                            break

                for selector in pass_selectors:
                    candidate = _first_visible(form.locator(selector))
                    if candidate:
                        pass_input = candidate
                        pass_selector = f'form {selector}'
                        break
                if not pass_input:
                    for selector in pass_selectors:
                        candidate = _first_visible(page.locator(selector))
                        if candidate:
                            pass_input = candidate
                            pass_selector = selector
                            break

                if not user_input or not pass_input:
                    raise CommandError(
                        f'No se localizaron campos de login en DOM (user={user_selector}, pass={pass_selector}). '
                        'La web puede usar iframes o selectores no estándar; revisamos capturas en siguiente paso.'
                    )

                self.stdout.write(f'Campos detectados: user={user_selector} pass={pass_selector}')
                user_input.click()
                user_input.fill('')
                user_input.type(username, delay=20)
                pass_input.click()
                pass_input.fill('')
                pass_input.type(password, delay=20)

                # Force exact located elements (works better with controlled components).
                try:
                    user_input.evaluate(
                        """
                        (el, value) => {
                          el.focus();
                          el.value = value;
                          el.dispatchEvent(new Event('input', { bubbles: true }));
                          el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        """,
                        username,
                    )
                    pass_input.evaluate(
                        """
                        (el, value) => {
                          el.focus();
                          el.value = value;
                          el.dispatchEvent(new Event('input', { bubbles: true }));
                          el.dispatchEvent(new Event('change', { bubbles: true }));
                          el.dispatchEvent(new Event('blur', { bubbles: true }));
                        }
                        """,
                        password,
                    )
                except Exception:
                    pass

                # Fallback for React/controlled inputs: force value + dispatch events.
                try:
                    page.evaluate(
                        """
                        ({userSelector, passSelector, userValue, passValue}) => {
                          const setNativeValue = (el, value) => {
                            const proto = Object.getPrototypeOf(el);
                            const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                            if (desc && desc.set) {
                              desc.set.call(el, value);
                            } else {
                              el.value = value;
                            }
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new Event('blur', { bubbles: true }));
                          };
                          const u = document.querySelector(userSelector);
                          const p = document.querySelector(passSelector);
                          if (u) setNativeValue(u, userValue);
                          if (p) setNativeValue(p, passValue);
                        }
                        """,
                        {
                            'userSelector': user_selector.replace('form ', ''),
                            'passSelector': pass_selector.replace('form ', ''),
                            'userValue': username,
                            'passValue': password,
                        },
                    )
                except Exception:
                    pass

                # Verify values are present just before submit.
                user_value = ''
                pass_value = ''
                try:
                    user_value = user_input.input_value(timeout=1000)
                    pass_value = pass_input.input_value(timeout=1000)
                except Exception:
                    pass
                if not user_value or not pass_value:
                    raise CommandError(
                        'Los campos de login siguen vacíos tras escribir. '
                        'Puede haber inputs espejo/ocultos o bloqueo JS.'
                    )

                try:
                    validity_message = page.evaluate(
                        """
                        () => {
                          const invalid = Array.from(document.querySelectorAll('input:invalid'));
                          if (!invalid.length) return '';
                          return invalid.map((el) => el.getAttribute('name') || el.getAttribute('id') || 'field').join(', ');
                        }
                        """
                    ) or ''
                    if validity_message:
                        self.stdout.write(f'Campos aún inválidos antes de submit: {validity_message}')
                except Exception:
                    pass

                submit_btn, submit_selector = _first_existing(page, submit_selectors)
                submit_disabled_before = None
                if submit_btn:
                    try:
                        submit_disabled_before = submit_btn.is_disabled()
                    except Exception:
                        submit_disabled_before = None
                    if submit_disabled_before:
                        self.stdout.write('Botón submit detectado como disabled tras rellenar credenciales.')
                    self.stdout.write(f'Enviando login con selector: {submit_selector}')
                    try:
                        submit_btn.click()
                    except Exception:
                        _dismiss_cookie_banners(page)
                        submit_btn.click(force=True)
                else:
                    self.stdout.write('No se encontró botón submit claro, enviando Enter sobre password.')
                    pass_input.press('Enter')
                    try:
                        page.evaluate(
                            """
                            () => {
                              const form = document.querySelector('form');
                              if (form) form.requestSubmit ? form.requestSubmit() : form.submit();
                            }
                            """
                        )
                    except Exception:
                        pass

                try:
                    page.wait_for_load_state('networkidle', timeout=min(timeout_ms, 12000))
                except PlaywrightTimeoutError:
                    pass

                # Optional explicit target verification
                if target_url:
                    page.goto(target_url, wait_until='domcontentloaded')
                    try:
                        page.wait_for_load_state('networkidle', timeout=min(timeout_ms, 8000))
                    except PlaywrightTimeoutError:
                        pass

                current_url = page.url
                has_password = page.locator('input[type="password"]').count() > 0
                page_text = (page.content() or '').lower()
                login_markers = (
                    'iniciar sesión' in page_text
                    or 'iniciar sesion' in page_text
                    or 'acceder' in page_text
                )

                success = (not has_password) and (not login_markers)
                self.stdout.write(f'URL final: {current_url}')

                if success:
                    storage_state_path.parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=str(storage_state_path))
                    self.stdout.write(self.style.SUCCESS('Login confirmado en navegador (Playwright).'))
                    self.stdout.write(self.style.SUCCESS(f'Storage state guardado en: {storage_state_path}'))
                    return

                error_selectors = [
                    '[role="alert"]',
                    '.error',
                    '.alert-danger',
                    '.invalid-feedback',
                    '.login_error',
                    '.text-red-500',
                    '[class*="error"]',
                    '[aria-live="polite"]',
                    '[aria-live="assertive"]',
                ]
                error_text = ''
                for selector in error_selectors:
                    loc = page.locator(selector)
                    count = min(loc.count(), 3)
                    for idx in range(count):
                        candidate = (loc.nth(idx).inner_text(timeout=1000) or '').strip()
                        if candidate:
                            error_text = candidate
                            break
                    if error_text:
                        break
                field_validation = ''
                try:
                    field_validation = page.evaluate(
                        """
                        () => {
                          const invalid = Array.from(document.querySelectorAll('input:invalid, textarea:invalid, select:invalid'));
                          if (!invalid.length) return '';
                          return invalid
                            .map((el) => {
                              const id = el.getAttribute('name') || el.getAttribute('id') || el.type || 'field';
                              const msg = el.validationMessage || 'invalid';
                              return `${id}: ${msg}`;
                            })
                            .join(' | ');
                        }
                        """
                    ) or ''
                except Exception:
                    field_validation = ''
                network_summary = '; '.join(
                    f"{entry['status']}[{entry['resource']}] {entry['url']}" for entry in network_events[-8:]
                )
                console_summary = ' | '.join(
                    f"{entry['type']}: {entry['text']}" for entry in console_events[-8:]
                )
                page_error_summary = ' | '.join(page_errors[-5:])
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), full_page=True)
                raise CommandError(
                    'No se pudo confirmar sesión autenticada en navegador. '
                    'Puede haber MFA/CAPTCHA o flujo adicional tras login. '
                    f'URL final: {current_url}. '
                    + (
                        f'Submit disabled: {submit_disabled_before}. '
                        if submit_disabled_before is not None
                        else ''
                    )
                    + (f'Error detectado: {error_text}. ' if error_text else '')
                    + (f'Validación formulario: {field_validation}. ' if field_validation else '')
                    + (f'Red login: {network_summary}. ' if network_summary else '')
                    + (f'Consola: {console_summary}. ' if console_summary else '')
                    + (f'JS errors: {page_error_summary}. ' if page_error_summary else '')
                    + f'Screenshot: {screenshot_path}'
                )
            except Exception:
                raise
            finally:
                if context:
                    context.close()
                if browser:
                    browser.close()

        # Defensive fallback
        raise CommandError('No se pudo completar la prueba de login en navegador.')
