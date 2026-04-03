import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from football.models import Team, TeamStanding
from football.services import PREFERENTE_BASE_URL, _preferente_headers, normalize_player_name


def _norm(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', normalize_player_name(text or ''))

_STOP_TOKENS = {
    'cd',
    'ud',
    'cf',
    'fc',
    'sad',
    'pvo',
    'atco',
    'atletico',
    'balompie',
    'club',
    'de',
    'del',
    'la',
    'el',
}


def _tokenize(text: str) -> list[str]:
    slug = normalize_player_name(text or '')
    tokens = [t for t in re.split(r'[-_]+', slug) if t]
    # Ojo: NO eliminamos "cp" para poder distinguir "C.P. Almería" de "U.D. Almería".
    return [t for t in tokens if t not in _STOP_TOKENS and len(t) >= 2]


@dataclass(frozen=True)
class PreferenteCandidate:
    team_id: str
    label: str
    category: str
    locality: str

    @property
    def url(self) -> str:
        return f'{PREFERENTE_BASE_URL}?IDequipo={self.team_id}'


def _score_candidate(expected: str, candidate: PreferenteCandidate) -> int:
    expected_tokens = _tokenize(expected)
    label_tokens = _tokenize(candidate.label)
    target = _norm(expected)
    label_key = _norm(candidate.label)
    score = 0

    if label_key == target and target:
        score += 80

    overlap = len(set(expected_tokens) & set(label_tokens)) if expected_tokens and label_tokens else 0
    if expected_tokens:
        # Si esperamos 2+ tokens (ej. "cp almeria"), exigimos que coincidan al menos 2
        # para evitar emparejar con equipos genéricos de la ciudad.
        required = 2 if len(expected_tokens) >= 2 else 1
        if overlap < required:
            return -999
        score += overlap * 28
        if overlap >= len(expected_tokens):
            score += 35
    else:
        # Fallback: contains por si la tokenización deja vacío
        if target and (target in label_key or label_key in target):
            score += 35
    category_lower = (candidate.category or '').lower()
    label_lower = (candidate.label or '').lower()
    expected_lower = (expected or '').lower()
    is_senior = ('senior' in category_lower) or ('senior' in label_lower)
    expects_youth = any(token in expected_lower for token in ('juvenil', 'cadete', 'infantil', 'alevin', 'benjamin', 'benjam'))
    expects_veterans = 'veteran' in expected_lower
    expects_female = 'femenin' in expected_lower
    if not is_senior and not (expects_youth or expects_veterans or expects_female):
        return -999
    if is_senior:
        score += 20
    # Penaliza categorías que no son senior (para nuestra liga senior).
    if any(token in category_lower for token in ('juvenil', 'cadete', 'infantil', 'alevin', 'benjamin')):
        score -= 45
    if any(token in label_lower for token in ('juvenil', 'cadete', 'infantil', 'alevín', 'benjamín')):
        score -= 45
    if 'veteran' in category_lower or 'veteran' in label_lower:
        score -= 55
    if 'femenin' in category_lower or 'femenin' in label_lower:
        score -= 55
    # Penaliza filiales/otros equipos si el nombre esperado no parece un "B".
    if ' b ' in f' {label_lower} ' and ' b' not in expected.lower():
        score -= 35
    if not label_key:
        score -= 10
    return score


def search_preferente_team(
    session: requests.Session,
    query: str,
    *,
    expected_name: Optional[str] = None,
) -> Optional[PreferenteCandidate]:
    query = (query or '').strip()
    if len(query) < 3:
        return None
    try:
        response = session.get(
            urljoin(PREFERENTE_BASE_URL, 'json/buscaEquipos.php'),
            params={'q': query},
            headers=_preferente_headers(PREFERENTE_BASE_URL),
            timeout=20,
        )
    except requests.RequestException:
        return None
    if not response.ok:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    results = payload.get('results') if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results:
        return None

    expected = (expected_name or query or '').strip()
    candidates: list[tuple[int, PreferenteCandidate]] = []
    for item in results[:20]:
        if not isinstance(item, dict):
            continue
        team_id = str(item.get('id') or '').strip()
        if not team_id.isdigit():
            continue
        label = str(item.get('nombre') or item.get('text') or '').strip()
        category = str(item.get('categoria') or '').strip()
        locality = str(item.get('localidad') or '').strip()
        candidate = PreferenteCandidate(team_id=team_id, label=label, category=category, locality=locality)
        score = _score_candidate(expected, candidate)
        if score < 0:
            continue
        candidates.append((score, candidate))
    candidates.sort(key=lambda row: row[0], reverse=True)
    return candidates[0][1] if candidates else None


def simplify_team_name(name: str) -> str:
    """
    Intenta limpiar abreviaturas habituales para mejorar la búsqueda en LaPreferente.
    Ej: "C.D. ATCO DE MARBELLA BALOMPIE" -> "Atletico Marbella"
    """
    raw = (name or '').strip()
    if not raw:
        return ''
    # Normaliza abreviaturas muy comunes
    text = raw
    replacements = {
        'ATCO': 'ATLETICO',
        'ATL.': 'ATLETICO',
        'A.D.': '',
        'C.D.': '',
        'U.D.': '',
        'C.F.': '',
        'F.C.': '',
        'C.P.': '',
        'S.A.D.': '',
    }
    for key, value in replacements.items():
        text = re.sub(rf'\b{re.escape(key)}\b', value, text, flags=re.IGNORECASE)
    text = re.sub(r'[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ ]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Si queda muy largo, quédate con 3-4 palabras más significativas
    tokens = [t for t in text.split(' ') if len(t) >= 3]
    if len(tokens) > 5:
        tokens = tokens[:5]
    return ' '.join(tokens).strip()

def resolve_preferente_team(session: requests.Session, expected_name: str) -> Optional[PreferenteCandidate]:
    expected = (expected_name or '').strip()
    if len(expected) < 3:
        return None

    # Alias puntuales cuando en nuestra BD el nombre difiere del alias que usa LaPreferente.
    # Ej: en algunas fuentes aparece "C.P. ALMERIA", pero en LaPreferente el equipo es "Poli Almería".
    alias_map = {
        'cpalmeria': ['Poli Almería', 'Poli Almeria', 'Polideportivo Almeria'],
    }

    queries: list[tuple[str, str]] = []
    queries.append((expected, expected))

    normalized = _norm(expected)
    for alias in alias_map.get(normalized, []):
        if alias and alias.lower() != expected.lower():
            # Para alias usamos el propio alias como nombre esperado (score) para que case con el resultado.
            queries.append((alias, alias))

    simplified = simplify_team_name(expected)
    if simplified and simplified.lower() != expected.lower():
        queries.append((simplified, expected))
        tokens = simplified.split()
        if len(tokens) >= 2:
            queries.append((' '.join(tokens[:2]), expected))
            queries.append((' '.join(tokens[-2:]), expected))
        if len(tokens) >= 3:
            queries.append((' '.join(tokens[:3]), expected))

    seen = set()
    for query, expected_for_score in queries:
        q = (query or '').strip()
        if len(q) < 3:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        candidate = search_preferente_team(session, q, expected_name=expected_for_score)
        if candidate:
            return candidate
    return None


class Command(BaseCommand):
    help = (
        'Busca en LaPreferente la URL de cada equipo de la liga (grupo) y la guarda en Team.preferente_url.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Guarda los cambios en base de datos (si no, solo muestra lo que haría).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Recalcula aunque el equipo ya tenga preferente_url.',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.35,
            help='Pausa (segundos) entre peticiones a LaPreferente para evitar bloqueo.',
        )
        parser.add_argument(
            '--group-id',
            type=int,
            default=0,
            help='ID del grupo (Group.id). Si no se indica, usa el grupo del último standing del equipo principal.',
        )

    def handle(self, *args, **options):
        apply = bool(options['apply'])
        force = bool(options['force'])
        delay = float(options['sleep'] or 0)
        group_id = int(options['group_id'] or 0)

        if not group_id:
            primary = Team.objects.filter(is_primary=True).order_by('id').first()
            standing = (
                TeamStanding.objects.select_related('group')
                .filter(team=primary)
                .order_by('-last_updated', '-id')
                .first()
                if primary
                else None
            )
            group_id = int(getattr(getattr(standing, 'group', None), 'id', 0) or 0)

        # Trabajamos sobre equipos que realmente están en la clasificación del grupo (TeamStanding),
        # para evitar nombres "sucios" o equipos fuera de contexto.
        standings_qs = TeamStanding.objects.select_related('team')
        if group_id:
            standings_qs = standings_qs.filter(group_id=group_id)
        else:
            latest_group_id = (
                TeamStanding.objects.order_by('-last_updated', '-id').values_list('group_id', flat=True).first()
            )
            if latest_group_id:
                group_id = int(latest_group_id)
                standings_qs = standings_qs.filter(group_id=group_id)
        standings_rows = list(standings_qs.order_by('position', 'id'))

        session = requests.Session()
        try:
            session.get(PREFERENTE_BASE_URL, headers=_preferente_headers(PREFERENTE_BASE_URL), timeout=10)
        except requests.RequestException:
            pass

        updated = 0
        skipped = 0
        not_found = 0
        rows: list[str] = []
        for standing in standings_rows:
            team = standing.team
            existing = (team.preferente_url or '').strip()
            if existing and not force:
                skipped += 1
                rows.append(f'⏭️  {team.name}: ya tiene URL ({existing})')
                continue

            candidate = resolve_preferente_team(session, team.name)
            if not candidate:
                not_found += 1
                rows.append(f'❌ {team.name}: no encontrado en LaPreferente')
                continue

            url = candidate.url
            rows.append(f'✅ {team.name}: {url}  [{candidate.label}]')
            if apply:
                with transaction.atomic():
                    Team.objects.filter(id=team.id).update(preferente_url=url)
                updated += 1
            time.sleep(max(0.0, delay))

        for line in rows:
            self.stdout.write(line)

        mode = 'APLICADO' if apply else 'SIMULACIÓN'
        self.stdout.write(
            self.style.SUCCESS(
                f'[{mode}] Equipos: {len(standings_rows)} · actualizados: {updated} · omitidos: {skipped} · no encontrados: {not_found}'
            )
        )
