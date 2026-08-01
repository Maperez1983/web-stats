from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..scene.transforms import points_bounds


@dataclass
class ZoneSprite:
    sprite_id: str
    points: List[Dict[str, float]] = field(default_factory=list)
    zone_type: str = 'unknown_zone'
    semantic_role: str = 'zone'
    z_index: int = 10
    rotation: float = 0.0
    scale: float = 1.0

    def render(self, ctx: Dict[str, object]) -> Dict[str, object]:
        return {
            'sprite_id': self.sprite_id,
            'sprite_type': 'zone',
            'points': list(self.points),
            'zone_type': self.zone_type,
            'rotation': self.rotation,
            'scale': self.scale,
            'z_index': self.z_index,
            'semantic_role': self.semantic_role,
            'theme': ctx.get('theme_key'),
        }

    def bounds(self) -> Dict[str, float]:
        return points_bounds(self.points)

    def anchor(self) -> Dict[str, float]:
        bounds = self.bounds()
        return {'x': bounds['x'] + (bounds['width'] / 2.0), 'y': bounds['y'] + (bounds['height'] / 2.0)}
