from django.test import SimpleTestCase

from football.preferente_competition_services import parse_preferente_standings

_HEADER = (
    "<tr><th>Pos</th><th></th><th>Equipo</th><th>PT</th><th>PJ</th><th>PG</th>"
    "<th>PE</th><th>PP</th><th>GF</th><th>GC</th><th>DG</th></tr>"
)


def _row(pos, name, escudo_cell):
    zeros = "".join("<td>0</td>" for _ in range(8))
    return (
        f"<tr><td>{pos}</td>{escudo_cell}"
        f"<td><a href='/E{pos}00C1-1/{name}'>{name}</a></td>{zeros}</tr>"
    )


def _table(*rows):
    return f"<table id='tableClasif'>{_HEADER}{''.join(rows)}</table>"


class PreferenteCrestExtractionTests(SimpleTestCase):
    def test_relative_img_src_becomes_absolute(self):
        html = _table(_row(1, "Garrucha", "<td><img src='/img/escudos/E100.png'></td>"))
        rows = parse_preferente_standings(html)
        self.assertEqual(rows[0]["crest_url"], "https://www.lapreferente.com/img/escudos/E100.png")

    def test_protocol_relative_data_src(self):
        html = _table(_row(2, "Guadix", "<td><img data-src='//cdn.lapreferente.com/e/E200.png'></td>"))
        rows = parse_preferente_standings(html)
        self.assertEqual(rows[0]["crest_url"], "https://cdn.lapreferente.com/e/E200.png")

    def test_background_image_fallback(self):
        html = _table(_row(3, "Benagalbon", "<td><span style=\"background-image:url('/e/E300.png')\"></span></td>"))
        rows = parse_preferente_standings(html)
        self.assertEqual(rows[0]["crest_url"], "https://www.lapreferente.com/e/E300.png")

    def test_placeholder_is_ignored(self):
        html = _table(_row(4, "Martos", "<td><img src='/img/blank.gif'></td>"))
        rows = parse_preferente_standings(html)
        self.assertEqual(rows[0]["crest_url"], "")

    def test_no_image_gives_empty(self):
        html = _table(_row(5, "Loja", "<td></td>"))
        rows = parse_preferente_standings(html)
        self.assertEqual(rows[0]["crest_url"], "")
