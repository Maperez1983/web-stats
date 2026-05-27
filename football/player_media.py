from pathlib import Path

from django.conf import settings
from django.template.defaultfilters import slugify

from .event_taxonomy import normalize_label


def resolve_player_photo_static_path(player):
    if not player:
        return ''
    players_dir = Path(settings.BASE_DIR) / 'static' / 'football' / 'images' / 'players'
    if not players_dir.exists():
        return ''

    team_obj = getattr(player, 'team', None)
    team_id = getattr(team_obj, 'id', None)
    team_slug = str(getattr(team_obj, 'slug', '') or '').strip()
    try:
        team_category = normalize_label(getattr(team_obj, 'category', '') or '')
    except Exception:
        team_category = ''
    try:
        is_primary_team = bool(getattr(team_obj, 'is_primary', False))
    except Exception:
        is_primary_team = False
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
    if len(wildcard_matches) == 1:
        return _relative_static_path(wildcard_matches[0])
    if wildcard_matches:
        try:
            tokens = [token for token in str(name_slug or '').split('-') if token]

            def _score(path_obj):
                fname = str(path_obj.name or '').lower()
                return sum(1 for token in tokens if token and token in fname)

            scored = sorted(((int(_score(path_obj)), path_obj) for path_obj in wildcard_matches), key=lambda item: (-item[0], item[1].name))
            best_score, best_path = scored[0]
            if is_primary_team or best_score > 0:
                return _relative_static_path(best_path)
        except Exception:
            if is_primary_team:
                return _relative_static_path(wildcard_matches[0])
    return ''
