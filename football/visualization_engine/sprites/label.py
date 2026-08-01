from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class LabelSprite:
    sprite_id: str
    x: float
    y: float
    text: str
    semantic_role: str = 'label'
    z_index: int = 70
    rotation: float = 0.0
    scale: float = 1.0

    def render(self, ctx: Dict[str, object]) -> Dict[str, object]:
        return {
            'sprite_id': self.sprite_id,
            'sprite_type': 'label',
            'position': self.anchor(),
            'text': self.text,
            'rotation': self.rotation,
            'scale': self.scale,
            'z_index': self.z_index,
            'semantic_role': self.semantic_role,
            'theme': ctx.get('theme_key'),
        }

    def bounds(self) -> Dict[str, float]:
        width = max(0.04, len(self.text) * 0.008 * self.scale)
        height = 0.02 * self.scale
        return {'x': self.x - width / 2.0, 'y': self.y - height / 2.0, 'width': width, 'height': height}

    def anchor(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y}
