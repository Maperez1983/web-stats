from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from .camera import perspective_camera
from .layers import LAYER_MAP, LAYERS, VisualizationLayer, build_visualization_layers
from .lighting import stadium_lighting
from .scene import VisualizationScene


def _background_payload(theme_key: str, theme: Dict[str, Any]) -> Dict[str, Any]:
    colors = theme.get('colors') if isinstance(theme.get('colors'), dict) else {}
    return {
        'style': 'stadium-shell',
        'theme_key': theme_key,
        'base_color': colors.get('background', '#0b1220'),
    }


def _layer_name_for_sprite(sprite: Any) -> str:
    z_index = int(getattr(sprite, 'z_index', 0) or 0)
    candidate_name = 'overlay'
    candidate_order = -1
    for layer in LAYERS:
        if z_index >= layer.order and layer.order >= candidate_order:
            candidate_name = layer.key
            candidate_order = layer.order
    return candidate_name


@dataclass
class SceneComposer:
    theme_key: str = 'broadcast'

    def compose(
        self,
        semantic_graph: Dict[str, Any],
        *,
        sprites: Iterable[Any],
        theme: Dict[str, Any] | None = None,
    ) -> VisualizationScene:
        theme_payload = dict(theme or {})
        metadata = dict(semantic_graph.get('metadata') or {})
        metadata.setdefault('theme_key', self.theme_key)
        if theme_payload:
            metadata.setdefault('theme', theme_payload)

        field_payload = dict(semantic_graph.get('field') or {})
        background = _background_payload(self.theme_key, theme_payload)
        lighting = stadium_lighting().as_dict()
        camera = perspective_camera().as_dict()

        layer_list = build_visualization_layers()
        layer_map: Dict[str, VisualizationLayer] = {layer.name: layer for layer in layer_list}

        for sprite in list(sprites):
            layer_name = _layer_name_for_sprite(sprite)
            layer_map.setdefault(
                layer_name,
                VisualizationLayer(name=layer_name, z_index=int(getattr(sprite, 'z_index', LAYER_MAP['overlay']) or 0)),
            ).add_sprite(sprite)

        for layer in layer_map.values():
            layer.sort_sprites()

        warnings: List[str] = list(semantic_graph.get('warnings') or [])
        warnings.extend(self._scene_warnings(layer_map.values()))

        return VisualizationScene(
            background=background,
            field=field_payload,
            layers=sorted(layer_map.values(), key=lambda current: current.z_index),
            camera=camera,
            lighting=lighting,
            metadata=metadata,
            warnings=warnings,
        )

    def _scene_warnings(self, layers: Iterable[VisualizationLayer]) -> List[str]:
        warnings: List[str] = []
        for layer in layers:
            for sprite in layer.sprites:
                sprite_id = str(getattr(sprite, 'sprite_id', '') or '')
                if not sprite_id:
                    warnings.append(f'Layer {layer.name} contiene un sprite sin sprite_id.')
        return warnings
