from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..scene.transforms import points_bounds


@dataclass
class ArrowSprite:
    sprite_id: str
    points: List[Dict[str, float]] = field(default_factory=list)
    action_type: str = 'unknown_action'
    semantic_role: str = 'arrow'
    z_index: int = 60
    rotation: float = 0.0
    scale: float = 1.0

    def render(self, ctx: Dict[str, object]) -> Dict[str, object]:
        return {
            'sprite_id': self.sprite_id,
            'sprite_type': 'arrow',
            'points': list(self.points),
            'action_type': self.action_type,
            'rotation': self.rotation,
            'scale': self.scale,
            'z_index': self.z_index,
            'semantic_role': self.semantic_role,
            'theme': ctx.get('theme_key'),
        }

    def bounds(self) -> Dict[str, float]:
        return points_bounds(self.points)

    def anchor(self) -> Dict[str, float]:
        if self.points:
            return {'x': float(self.points[0].get('x') or 0.0), 'y': float(self.points[0].get('y') or 0.0)}
        return {'x': 0.0, 'y': 0.0}
