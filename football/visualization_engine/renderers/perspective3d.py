from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from ..scene.camera import perspective_camera
from ..scene.scene import VisualizationScene


@dataclass
class Perspective3DRenderer:
    theme: Dict[str, Any]
    camera: Dict[str, Any] = field(default_factory=lambda: perspective_camera().as_dict())

    def render(self, sprites: Iterable[Any], *, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ctx = {
            'renderer': 'perspective3d',
            'camera': self.camera,
            'theme_key': self.theme.get('key'),
            'theme': self.theme,
            'metadata': dict(metadata or {}),
        }
        draw_calls: List[Dict[str, Any]] = []
        for sprite in sorted(list(sprites), key=lambda item: getattr(item, 'z_index', 0)):
            draw_calls.append(sprite.render(ctx))
        return {
            'renderer': 'perspective3d',
            'camera': self.camera,
            'theme': self.theme,
            'draw_calls': draw_calls,
            'metadata': dict(metadata or {}),
        }

    def render_scene(self, scene: VisualizationScene, *, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        merged_metadata = dict(scene.metadata or {})
        merged_metadata.update(dict(metadata or {}))
        return self.render(scene.all_sprites(), metadata=merged_metadata)
