from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from ..assets.manifest import AssetDescriptor
from ..assets.registry import AssetRegistry


class AssetResolver:
    def __init__(self, registry: AssetRegistry, *, theme_key: str = 'premium') -> None:
        self.registry = registry
        self.theme_key = str(theme_key or 'premium')
        self.library_root = Path(__file__).resolve().parent.parent / 'assets_library'
        self._asset_map: Dict[str, Tuple[str, str]] = {
            'PlayerSprite': ('players', 'player_token.svg'),
            'GoalkeeperSprite': ('goalkeepers', 'goalkeeper_token.svg'),
            'BallSprite': ('balls', 'ball.svg'),
            'ConeSprite': ('cones', 'cone.svg'),
            'PoleSprite': ('cones', 'cone.svg'),
            'GoalSprite': ('goals', 'goal.svg'),
            'ArrowSprite': ('arrows', 'arrow.svg'),
            'ZoneSprite': ('zones', 'zone.svg'),
            'LabelSprite': ('badges', 'player_shadow.svg'),
        }

    def resolve_for_sprite(self, sprite: Any) -> Dict[str, Any]:
        sprite_type = sprite.__class__.__name__
        folder, filename = self._asset_map.get(sprite_type, ('badges', 'player_shadow.svg'))
        asset_path = self.library_root / folder / filename
        asset_id = f'{folder}/{filename}'
        descriptor = AssetDescriptor(
            asset_id=asset_id,
            asset_type=folder.rstrip('s'),
            source=str(asset_path),
            variants={'default': str(asset_path)},
            metadata={'sprite_type': sprite_type, 'theme_key': self.theme_key},
        )
        self.registry.register(self.theme_key, descriptor)
        return {
            'asset_id': asset_id,
            'asset_type': descriptor.asset_type,
            'path': str(asset_path),
            'inline_svg': asset_path.read_text(encoding='utf-8') if asset_path.exists() else '',
            'descriptor': descriptor,
        }
