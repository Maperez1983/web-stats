from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class LayerSpec:
    key: str
    order: int


@dataclass
class VisualizationLayer:
    name: str
    z_index: int
    sprites: List[Any] = field(default_factory=list)
    visibility: bool = True
    opacity: float = 1.0

    def add_sprite(self, sprite: Any) -> None:
        self.sprites.append(sprite)

    def sort_sprites(self) -> None:
        self.sprites.sort(key=lambda sprite: getattr(sprite, 'z_index', self.z_index))

    def as_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'z_index': self.z_index,
            'visibility': self.visibility,
            'opacity': self.opacity,
            'sprite_count': len(self.sprites),
            'sprites': [
                {
                    'id': getattr(sprite, 'sprite_id', ''),
                    'type': sprite.__class__.__name__,
                    'semantic_role': getattr(sprite, 'semantic_role', ''),
                    'z_index': getattr(sprite, 'z_index', self.z_index),
                    'rotation': getattr(sprite, 'rotation', 0.0),
                    'scale': getattr(sprite, 'scale', 1.0),
                }
                for sprite in self.sprites
            ],
        }


LAYERS: List[LayerSpec] = [
    LayerSpec('field', 0),
    LayerSpec('zones', 10),
    LayerSpec('goals', 20),
    LayerSpec('equipment', 30),
    LayerSpec('players', 40),
    LayerSpec('ball', 50),
    LayerSpec('arrows', 60),
    LayerSpec('labels', 70),
    LayerSpec('overlay', 80),
]


LAYER_MAP: Dict[str, int] = {layer.key: layer.order for layer in LAYERS}


def build_visualization_layers() -> List[VisualizationLayer]:
    return [VisualizationLayer(name=layer.key, z_index=layer.order) for layer in LAYERS]


def iter_layer_names() -> Iterable[str]:
    for layer in LAYERS:
        yield layer.key
