from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List

from .layers import VisualizationLayer


@dataclass
class VisualizationScene:
    background: Dict[str, Any] = dc_field(default_factory=dict)
    field: Dict[str, Any] = dc_field(default_factory=dict)
    layers: List[VisualizationLayer] = dc_field(default_factory=list)
    camera: Dict[str, Any] = dc_field(default_factory=dict)
    lighting: Dict[str, Any] = dc_field(default_factory=dict)
    metadata: Dict[str, Any] = dc_field(default_factory=dict)
    warnings: List[str] = dc_field(default_factory=list)

    def all_sprites(self) -> List[Any]:
        sprites: List[Any] = []
        for layer in sorted(self.layers, key=lambda current: current.z_index):
            if not layer.visibility:
                continue
            sprites.extend(layer.sprites)
        return sprites

    def visible_layers(self) -> Iterable[VisualizationLayer]:
        for layer in sorted(self.layers, key=lambda current: current.z_index):
            if layer.visibility:
                yield layer

    def as_dict(self) -> Dict[str, Any]:
        return {
            'background': dict(self.background or {}),
            'field': dict(self.field or {}),
            'layers': [layer.as_dict() for layer in sorted(self.layers, key=lambda current: current.z_index)],
            'camera': dict(self.camera or {}),
            'lighting': dict(self.lighting or {}),
            'metadata': dict(self.metadata or {}),
            'warnings': list(self.warnings or []),
        }
