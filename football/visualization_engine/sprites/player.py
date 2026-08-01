from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PlayerSprite:
    sprite_id: str
    x: float
    y: float
    number: str = ''
    team: str = 'unknown'
    role: str = 'outfield'
    semantic_role: str = 'player'
    z_index: int = 40
    rotation: float = 0.0
    scale: float = 1.0
    style: Dict[str, Any] = field(default_factory=dict)

    def render(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'sprite_id': self.sprite_id,
            'sprite_type': 'player',
            'position': self.anchor(),
            'rotation': self.rotation,
            'scale': self.scale,
            'z_index': self.z_index,
            'semantic_role': self.semantic_role,
            'team': self.team,
            'number': self.number,
            'role': self.role,
            'theme': ctx.get('theme_key'),
        }

    def bounds(self) -> Dict[str, float]:
        size = 0.035 * self.scale
        return {'x': self.x - size / 2.0, 'y': self.y - size / 2.0, 'width': size, 'height': size}

    def anchor(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y}
