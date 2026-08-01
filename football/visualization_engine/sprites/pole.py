from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class PoleSprite:
    sprite_id: str
    x: float
    y: float
    width: float = 0.01
    height: float = 0.06
    semantic_role: str = 'pole'
    z_index: int = 30
    rotation: float = 0.0
    scale: float = 1.0

    def render(self, ctx: Dict[str, object]) -> Dict[str, object]:
        return {
            'sprite_id': self.sprite_id,
            'sprite_type': 'pole',
            'position': self.anchor(),
            'size': {'width': self.width, 'height': self.height},
            'rotation': self.rotation,
            'scale': self.scale,
            'z_index': self.z_index,
            'semantic_role': self.semantic_role,
            'theme': ctx.get('theme_key'),
        }

    def bounds(self) -> Dict[str, float]:
        return {'x': self.x - self.width / 2.0, 'y': self.y - self.height / 2.0, 'width': self.width, 'height': self.height}

    def anchor(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y}
