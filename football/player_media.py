from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.template.defaultfilters import slugify

from .event_taxonomy import normalize_label

# Lo unico que hace falta del equipo para decidir la carpeta de la foto: tres datos que
# cambian una vez al ano. Se guardan por equipo porque `player.team` es una consulta CADA
# vez que se toca, y a esta funcion se le pregunta la foto del mismo jugador muchas veces
# por pagina: en la portada del entrenador salian 362 consultas a football_team.
_DATOS_EQUIPO_TTL = 5 * 60


def _datos_del_equipo(player):
    team_id = getattr(player, 'team_id', None)  # OJO: `team_id` NO consulta; `team` si.
    if not team_id:
        return None, '', '', False
    clave = f'foto-jugador:equipo:{team_id}'
    try:
        guardado = cache.get(clave)
    except Exception:
        guardado = None
    if guardado:
        return (team_id,) + tuple(guardado)

    team_obj = getattr(player, 'team', None)
    slug = str(getattr(team_obj, 'slug', '') or '').strip()
    try:
        categoria = normalize_label(getattr(team_obj, 'category', '') or '')
    except Exception:
        categoria = ''
    try:
        principal = bool(getattr(team_obj, 'is_primary', False))
    except Exception:
        principal = False
    try:
        cache.set(clave, (slug, categoria, principal), _DATOS_EQUIPO_TTL)
    except Exception:
        pass
    return team_id, slug, categoria, principal


def resolve_player_photo_static_path(player):
    if not player:
        return ''
    players_dir = Path(settings.BASE_DIR) / 'static' / 'football' / 'images' / 'players'
    if not players_dir.exists():
        return ''

    team_id, team_slug, team_category, is_primary_team = _datos_del_equipo(player)
    youth_tokens = {
        'prebenjamin',
        'pre benjamin',
        'benjamin',
        'alevin',
        'infantil',
        'cadete',
        'juvenil',
    }
    is_youth_category = any(token in team_category for token in youth_tokens) if team_category else False

    team_dirs = []
    try:
        if team_id:
            team_dirs.append(players_dir / f'team-{int(team_id)}')
        if team_slug:
            team_dirs.append(players_dir / team_slug)
    except Exception:
        team_dirs = []
    team_dirs = [path for path in team_dirs if path and path.exists()]

    name_slug = slugify(player.name or '')
    number_value = player.number if player.number is not None else ''
    id_candidates = [
        f'player-{player.id}.png',
        f'player-{player.id}.jpg',
        f'player-{player.id}.jpeg',
        f'player-{player.id}.webp',
    ]
    candidates = []
    if name_slug and number_value != '':
        candidates.extend(
            [
                f'{name_slug}-n{number_value}-final.png',
                f'{name_slug}-n{number_value}.png',
                f'{name_slug}-{number_value}.png',
            ]
        )
    if name_slug:
        candidates.extend(
            [
                f'{name_slug}-final.png',
                f'{name_slug}.png',
                f'{name_slug}.jpg',
                f'{name_slug}.jpeg',
            ]
        )
    if number_value != '':
        candidates.extend(
            [
                f'n{number_value}-{name_slug}.png',
                f'{name_slug}-n{number_value}-cut.png',
                f'{name_slug}-n{number_value}-crop.png',
            ]
        )

    def _relative_static_path(file_path):
        try:
            rel_dir = file_path.parent.relative_to(players_dir)
            if str(rel_dir) == '.':
                return f'football/images/players/{file_path.name}'
            return f'football/images/players/{rel_dir.as_posix()}/{file_path.name}'
        except Exception:
            return f'football/images/players/{file_path.name}'

    def _resolve_in_dirs(filename, dirs):
        for base_dir in dirs:
            file_path = base_dir / filename
            if file_path.exists():
                return _relative_static_path(file_path)
        return ''

    for filename in id_candidates:
        resolved = _resolve_in_dirs(filename, team_dirs + [players_dir])
        if resolved:
            return resolved

    allow_global_dir = bool(is_primary_team and not is_youth_category)
    name_dirs = team_dirs + ([players_dir] if allow_global_dir else [])
    seen = set()
    for filename in candidates:
        if filename in seen:
            continue
        seen.add(filename)
        resolved = _resolve_in_dirs(filename, name_dirs)
        if resolved:
            return resolved

    if number_value == '':
        return ''
    wildcard_patterns = [
        f'*-n{number_value}-final.*',
        f'*-n{number_value}-cut.*',
        f'*-n{number_value}-crop.*',
        f'*-n{number_value}.*',
    ]
    wildcard_dirs = team_dirs + ([players_dir] if allow_global_dir else [])
    wildcard_matches = []
    try:
        seen_matches = set()
        for pattern in wildcard_patterns:
            for base_dir in wildcard_dirs:
                for file_path in base_dir.glob(pattern):
                    if not file_path.is_file():
                        continue
                    signature = f'{base_dir}:{file_path.name}'
                    if signature in seen_matches:
                        continue
                    seen_matches.add(signature)
                    wildcard_matches.append(file_path)
    except Exception:
        wildcard_matches = []
    if wildcard_matches:
        try:
            tokens = [token for token in str(name_slug or '').split('-') if token]

            def _has_name_affinity(path_obj):
                fname_tokens = [token for token in str(path_obj.stem or '').lower().split('-') if token and not token.startswith('n')]
                for token in tokens:
                    if not token:
                        continue
                    token_stem = token[:-1] if len(token) > 4 and token.endswith('s') else token
                    for fname_token in fname_tokens:
                        fname_stem = fname_token[:-1] if len(fname_token) > 4 and fname_token.endswith('s') else fname_token
                        if token_stem and fname_stem and (token_stem in fname_stem or fname_stem in token_stem):
                            return True
                return False

            def _score(path_obj):
                fname = str(path_obj.name or '').lower()
                return sum(1 for token in tokens if token and token in fname)

            scored = sorted(((int(_score(path_obj)), path_obj) for path_obj in wildcard_matches), key=lambda item: (-item[0], item[1].name))
            best_score, best_path = scored[0]
            if best_score > 0 or _has_name_affinity(best_path):
                return _relative_static_path(best_path)
        except Exception:
            return ''
    if allow_global_dir:
        return ''

    # Fallback para jugadores movidos de categoría: las fotos históricas del club
    # pueden vivir en la carpeta global aunque el jugador ya pertenezca a un equipo filial.
    for filename in dict.fromkeys(candidates):
        resolved = _resolve_in_dirs(filename, [players_dir])
        if resolved:
            return resolved
    if number_value != '':
        global_matches = []
        try:
            seen_global = set()
            for pattern in wildcard_patterns:
                for file_path in players_dir.glob(pattern):
                    if not file_path.is_file():
                        continue
                    if file_path.name in seen_global:
                        continue
                    seen_global.add(file_path.name)
                    global_matches.append(file_path)
        except Exception:
            global_matches = []
        if global_matches:
            tokens = [token for token in str(name_slug or '').split('-') if token]

            def _global_score(path_obj):
                fname = str(path_obj.name or '').lower()
                return sum(1 for token in tokens if token and token in fname)

            def _has_global_name_affinity(path_obj):
                fname_tokens = [token for token in str(path_obj.stem or '').lower().split('-') if token and not token.startswith('n')]
                for token in tokens:
                    if not token:
                        continue
                    token_stem = token[:-1] if len(token) > 4 and token.endswith('s') else token
                    for fname_token in fname_tokens:
                        fname_stem = fname_token[:-1] if len(fname_token) > 4 and fname_token.endswith('s') else fname_token
                        if token_stem and fname_stem and (token_stem in fname_stem or fname_stem in token_stem):
                            return True
                return False

            scored = sorted(
                ((int(_global_score(path_obj)), path_obj) for path_obj in global_matches),
                key=lambda item: (-item[0], item[1].name),
            )
            best_score, best_path = scored[0]
            if best_score > 0 or (len(scored) == 1 and _has_global_name_affinity(best_path)):
                return _relative_static_path(best_path)
    return ''
