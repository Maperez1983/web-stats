from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class BallSprite:
    sprite_id: str
    x: float
    y: float
    owner: str | None = None
    semantic_role: str = 'ball'
    z_index: int = 50
    rotation: float = 0.0
    scale: float = 1.0

    def render(self, ctx: Dict[str, object]) -> Dict[str, object]:
        return {
            'sprite_id': self.sprite_id,
            'sprite_type': 'ball',
            'position': self.anchor(),
            'owner': self.owner,
            'rotation': self.rotation,
            'scale': self.scale,
            'z_index': self.z_index,
            'semantic_role': self.semantic_role,
            'theme': ctx.get('theme_key'),
        }

    def bounds(self) -> Dict[str, float]:
        size = 0.015 * self.scale
        return {'x': self.x - size / 2.0, 'y': self.y - size / 2.0, 'width': size, 'height': size}

    def anchor(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y}
