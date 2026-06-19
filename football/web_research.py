import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


DEFAULT_TIMEOUT = 8
MAX_URLS = 4
MAX_BYTES = 900_000
MAX_TEXT_CHARS = 6000
BROWSER_WAIT_MS = 2500


class _ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''
        self._in_title = False
        self._skip_depth = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        tag = str(tag or '').lower()
        if tag in {'script', 'style', 'noscript', 'svg'}:
            self._skip_depth += 1
        elif tag == 'title':
            self._in_title = True
        elif tag in {'p', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'section', 'article'}:
            self._parts.append('\n')

    def handle_endtag(self, tag):
        tag = str(tag or '').lower()
        if tag in {'script', 'style', 'noscript', 'svg'} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == 'title':
            self._in_title = False
        elif tag in {'p', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'section', 'article'}:
            self._parts.append('\n')

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = str(data or '').strip()
        if not text:
            return
        if self._in_title:
            self.title = (self.title + ' ' + text).strip()[:220]
        self._parts.append(text)
        self._parts.append(' ')

    def readable_text(self):
        raw = ''.join(self._parts)
        lines = []
        seen_blank = False
        for line in raw.replace('\r', '\n').split('\n'):
            clean = ' '.join(str(line or '').split())
            if not clean:
                if not seen_blank and lines:
                    lines.append('')
                seen_blank = True
                continue
            lines.append(clean)
            seen_blank = False
        return '\n'.join(lines).strip()


def parse_research_urls(raw, *, limit=MAX_URLS):
    text = str(raw or '').replace('\r', '\n')
    urls = []
    seen = set()
    for piece in text.replace(',', '\n').splitlines():
        value = str(piece or '').strip()
        if not value:
            continue
        if '://' not in value and '.' in value:
            value = f'https://{value}'
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        urls.append(value)
        if len(urls) >= max(1, int(limit or MAX_URLS)):
            break
    return urls


def _host_is_public(hostname):
    host = str(hostname or '').strip().strip('[]').lower()
    if not host:
        return False
    if host in {'localhost', '0.0.0.0'} or host.endswith('.local'):
        return False
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except Exception:
        return False
    for row in addresses:
        ip_raw = row[4][0]
        try:
            ip = ipaddress.ip_address(ip_raw)
        except Exception:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False
    return True


def _validate_public_url(url):
    parsed = urllib.parse.urlparse(str(url or '').strip())
    if parsed.scheme not in {'http', 'https'}:
        return None, 'scheme_not_allowed'
    if not parsed.netloc:
        return None, 'missing_host'
    if not _host_is_public(parsed.hostname):
        return None, 'host_not_public'
    clean = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path or '/', '', parsed.query, ''))
    return clean, ''


def fetch_web_research(raw_urls, *, timeout=DEFAULT_TIMEOUT, max_urls=MAX_URLS):
    rows = []
    for url in parse_research_urls(raw_urls, limit=max_urls):
        clean_url, validation_error = _validate_public_url(url)
        if validation_error:
            rows.append({'url': str(url or '')[:500], 'ok': False, 'error': validation_error, 'title': '', 'text': ''})
            continue
        req = urllib.request.Request(
            clean_url,
            headers={
                'User-Agent': 'SegundaJugadaAITrainer/1.0 (+local coach research)',
                'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.2',
            },
            method='GET',
        )
        try:
            with urllib.request.urlopen(req, timeout=max(2, int(timeout or DEFAULT_TIMEOUT))) as resp:
                content_type = str(resp.headers.get('Content-Type') or '').lower()
                raw = resp.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    rows.append({'url': clean_url, 'ok': False, 'error': 'response_too_large', 'title': '', 'text': ''})
                    continue
                charset = resp.headers.get_content_charset() or 'utf-8'
        except urllib.error.HTTPError as exc:
            rows.append({'url': clean_url, 'ok': False, 'error': f'http_{exc.code}', 'title': '', 'text': ''})
            continue
        except Exception as exc:
            rows.append({'url': clean_url, 'ok': False, 'error': f'fetch_error:{str(exc)[:120]}', 'title': '', 'text': ''})
            continue

        decoded = raw.decode(charset, errors='replace')
        if 'html' in content_type or '<html' in decoded[:1000].lower():
            parser = _ReadableHTMLParser()
            try:
                parser.feed(decoded)
                text = parser.readable_text()
                title = parser.title
            except Exception:
                text = ' '.join(decoded.split())
                title = ''
        else:
            text = ' '.join(decoded.split())
            title = ''
        rows.append(
            {
                'url': clean_url,
                'ok': True,
                'error': '',
                'method': 'http',
                'title': title[:220],
                'text': str(text or '').strip()[:MAX_TEXT_CHARS],
            }
        )
    return rows


def _route_browser_request(route, request):
    url = str(getattr(request, 'url', '') or '')
    resource_type = str(getattr(request, 'resource_type', '') or '').lower()
    if resource_type in {'image', 'media', 'font'}:
        return route.abort()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {'data', 'blob', 'about'}:
        return route.continue_()
    if parsed.scheme not in {'http', 'https'}:
        return route.abort()
    if not _host_is_public(parsed.hostname):
        return route.abort()
    return route.continue_()


def fetch_web_research_browser(raw_urls, *, timeout=DEFAULT_TIMEOUT, max_urls=MAX_URLS, wait_ms=BROWSER_WAIT_MS):
    urls = parse_research_urls(raw_urls, limit=max_urls)
    rows = []
    valid_urls = []
    for url in urls:
        clean_url, validation_error = _validate_public_url(url)
        if validation_error:
            rows.append({'url': str(url or '')[:500], 'ok': False, 'error': validation_error, 'method': 'browser', 'title': '', 'text': ''})
        else:
            valid_urls.append(clean_url)
    if not valid_urls:
        return rows

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        for url in valid_urls:
            rows.append({'url': url, 'ok': False, 'error': f'playwright_unavailable:{str(exc)[:100]}', 'method': 'browser', 'title': '', 'text': ''})
        return rows

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent='SegundaJugadaAITrainer/1.0 (+local browser research)',
                    java_script_enabled=True,
                    ignore_https_errors=True,
                )
                context.route('**/*', _route_browser_request)
                for url in valid_urls:
                    page = context.new_page()
                    try:
                        page.goto(url, wait_until='domcontentloaded', timeout=max(3000, int(timeout or DEFAULT_TIMEOUT) * 1000))
                        try:
                            page.wait_for_load_state('networkidle', timeout=max(500, int(wait_ms or BROWSER_WAIT_MS)))
                        except PlaywrightTimeoutError:
                            pass
                        title = str(page.title() or '').strip()[:220]
                        text = str(page.locator('body').inner_text(timeout=2000) or '').strip()
                        rows.append({'url': url, 'ok': True, 'error': '', 'method': 'browser', 'title': title, 'text': text[:MAX_TEXT_CHARS]})
                    except Exception as exc:
                        rows.append({'url': url, 'ok': False, 'error': f'browser_error:{str(exc)[:120]}', 'method': 'browser', 'title': '', 'text': ''})
                    finally:
                        try:
                            page.close()
                        except Exception:
                            pass
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as exc:
        existing = {str(row.get('url') or '') for row in rows if isinstance(row, dict)}
        for url in valid_urls:
            if url not in existing:
                rows.append({'url': url, 'ok': False, 'error': f'browser_start_error:{str(exc)[:120]}', 'method': 'browser', 'title': '', 'text': ''})
    return rows


def fetch_web_research_with_browser(raw_urls, *, timeout=DEFAULT_TIMEOUT, max_urls=MAX_URLS, prefer_browser=True):
    if not prefer_browser:
        return fetch_web_research(raw_urls, timeout=timeout, max_urls=max_urls)
    browser_rows = fetch_web_research_browser(raw_urls, timeout=timeout, max_urls=max_urls)
    final_rows = []
    fallback_urls = []
    for row in browser_rows:
        if isinstance(row, dict) and row.get('ok'):
            final_rows.append(row)
        else:
            fallback_urls.append(str(row.get('url') or '') if isinstance(row, dict) else '')
    if fallback_urls:
        http_rows = fetch_web_research('\n'.join([u for u in fallback_urls if u]), timeout=timeout, max_urls=max_urls)
        http_by_url = {str(row.get('url') or ''): row for row in http_rows if isinstance(row, dict)}
        for row in browser_rows:
            if not isinstance(row, dict) or row.get('ok'):
                continue
            replacement = http_by_url.get(str(row.get('url') or ''))
            if replacement and replacement.get('ok'):
                replacement = dict(replacement)
                replacement['browser_error'] = str(row.get('error') or '')[:160]
                final_rows.append(replacement)
            else:
                final_rows.append(row)
    return final_rows


def compact_web_research(rows, *, max_sources=MAX_URLS, max_text_chars=1800):
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = {
            'url': str(row.get('url') or '')[:500],
            'ok': bool(row.get('ok')),
            'title': str(row.get('title') or '')[:180],
            'error': str(row.get('error') or '')[:160],
            'method': str(row.get('method') or '')[:40],
        }
        if item['ok']:
            item['text'] = str(row.get('text') or '')[: max(200, int(max_text_chars or 1800))]
        out.append(item)
        if len(out) >= max(1, int(max_sources or MAX_URLS)):
            break
    return out
