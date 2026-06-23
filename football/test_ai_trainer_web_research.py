from unittest import mock

from django.test import SimpleTestCase

from football.local_llm import build_ai_trainer_context, build_ai_trainer_prompt
from football.web_research import (
    _ReadableHTMLParser,
    _validate_public_url,
    compact_web_research,
    fetch_web_research_with_browser,
    parse_research_urls,
    search_web_research,
)


class AiTrainerWebResearchTests(SimpleTestCase):
    def test_parse_research_urls_accepts_lines_and_adds_https(self):
        self.assertEqual(
            parse_research_urls('example.com\nhttps://segundajugada.es/path', limit=4),
            ['https://example.com', 'https://segundajugada.es/path'],
        )

    def test_validate_public_url_blocks_localhost(self):
        clean, error = _validate_public_url('http://127.0.0.1:11434/api/tags')
        self.assertIsNone(clean)
        self.assertEqual(error, 'host_not_public')

    def test_validate_public_url_allows_public_resolved_host(self):
        with mock.patch('football.web_research.socket.getaddrinfo') as getaddrinfo:
            getaddrinfo.return_value = [(None, None, None, None, ('93.184.216.34', 0))]
            clean, error = _validate_public_url('https://example.com/report?a=1#frag')
        self.assertEqual(clean, 'https://example.com/report?a=1')
        self.assertEqual(error, '')

    def test_html_parser_removes_script_and_keeps_readable_text(self):
        parser = _ReadableHTMLParser()
        parser.feed('<html><head><title>Informe rival</title><script>bad()</script></head><body><h1>Presiona alto</h1><p>Defiende en 4-4-2.</p></body></html>')
        self.assertEqual(parser.title, 'Informe rival')
        text = parser.readable_text()
        self.assertIn('Presiona alto', text)
        self.assertIn('Defiende en 4-4-2.', text)
        self.assertNotIn('bad()', text)

    def test_local_llm_prompt_includes_external_web_research(self):
        context = build_ai_trainer_context(
            team_name='Equipo',
            profile='senior',
            phase='Defensa',
            goal='Preparar presión alta',
            signals={},
            club_model={},
            learning_memory={},
            suggestions=[],
            proposals=[],
            web_research=compact_web_research(
                [{'url': 'https://example.com/rival', 'ok': True, 'title': 'Rival', 'text': 'El rival inicia corto y pierde en carril central.'}]
            ),
        )
        prompt = build_ai_trainer_prompt(context)
        self.assertIn('external_web_research', prompt)
        self.assertIn('El rival inicia corto', prompt)

    def test_browser_fetch_falls_back_to_http_when_browser_fails(self):
        with mock.patch('football.web_research.fetch_web_research_browser') as browser_fetch, mock.patch('football.web_research.fetch_web_research') as http_fetch:
            browser_fetch.return_value = [{'url': 'https://example.com/', 'ok': False, 'error': 'browser_error', 'method': 'browser'}]
            http_fetch.return_value = [{'url': 'https://example.com/', 'ok': True, 'error': '', 'method': 'http', 'title': 'Fallback', 'text': 'Texto'}]
            rows = fetch_web_research_with_browser('https://example.com', prefer_browser=True)
        self.assertEqual(rows[0]['method'], 'http')
        self.assertEqual(rows[0]['browser_error'], 'browser_error')

    def test_compact_web_research_keeps_method(self):
        rows = compact_web_research([{'url': 'https://example.com/', 'ok': True, 'method': 'browser', 'title': 'T', 'text': 'abc'}])
        self.assertEqual(rows[0]['method'], 'browser')

    def test_search_web_research_parses_public_results(self):
        html = """
        <html><body>
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdoc">Example doc</a>
          <span class="result__snippet">Prueba de snippet</span>
        </body></html>
        """

        class FakeResponse:
            headers = mock.Mock()

            def __init__(self, payload):
                self._payload = payload.encode('utf-8')
                self.headers.get_content_charset.return_value = 'utf-8'

            def read(self, _limit):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        with mock.patch('football.web_research.urllib.request.urlopen', return_value=FakeResponse(html)):
            rows = search_web_research('example query', max_results=4)

        self.assertTrue(rows)
        self.assertEqual(rows[0]['url'], 'https://example.com/doc')
        self.assertEqual(rows[0]['title'], 'Example doc')
        self.assertEqual(rows[0]['snippet'], 'Prueba de snippet')

    def test_search_web_research_applies_domain_filters(self):
        html = """
        <html><body>
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fother.com%2Fdoc">Other doc</a>
          <span class="result__snippet">Snippet other</span>
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fuefa.com%2Fdoc">UEFA doc</a>
          <span class="result__snippet">Snippet uefa</span>
        </body></html>
        """

        class FakeResponse:
            headers = mock.Mock()

            def __init__(self, payload):
                self._payload = payload.encode('utf-8')
                self.headers.get_content_charset.return_value = 'utf-8'

            def read(self, _limit):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        with mock.patch('football.web_research.urllib.request.urlopen', return_value=FakeResponse(html)):
            rows = search_web_research('training session', preferred_domains='uefa.com', blocked_domains='other.com', max_results=4)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], 'https://uefa.com/doc')
        self.assertEqual(rows[0]['title'], 'UEFA doc')
