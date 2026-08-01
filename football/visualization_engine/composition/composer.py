from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .asset_resolver import AssetResolver
from .layers import CompositionLayer
from ..scene.scene import VisualizationScene


@dataclass
class CompositionSpriteBinding:
    sprite_id: str
    sprite_type: str
    layer_name: str
    asset_id: str
    asset_type: str
    x: float
    y: float
    rotation: float
    scale: float
    z_index: int
    semantic_role: str = ''
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'sprite_id': self.sprite_id,
            'sprite_type': self.sprite_type,
            'layer_name': self.layer_name,
            'asset_id': self.asset_id,
            'asset_type': self.asset_type,
            'x': self.x,
            'y': self.y,
            'rotation': self.rotation,
            'scale': self.scale,
            'z_index': self.z_index,
            'semantic_role': self.semantic_role,
            'warnings': list(self.warnings),
        }


@dataclass
class CompositionScene:
    width: int = 1600
    height: int = 1000
    layers: List[CompositionLayer] = field(default_factory=list)
    assets_used: List[Dict[str, Any]] = field(default_factory=list)
    bindings: List[CompositionSpriteBinding] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    theme: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'width': self.width,
            'height': self.height,
            'layers': [layer.as_dict() for layer in self.layers],
            'assets_used': list(self.assets_used),
            'bindings': [binding.as_dict() for binding in self.bindings],
            'warnings': list(self.warnings),
            'metadata': dict(self.metadata),
            'theme': dict(self.theme),
        }


class CompositionEngine:
    def __init__(self, resolver: AssetResolver) -> None:
        self.resolver = resolver

    def compose(self, scene: VisualizationScene, *, theme: Dict[str, Any] | None = None) -> CompositionScene:
        composition_layers: List[CompositionLayer] = []
        bindings: List[CompositionSpriteBinding] = []
        assets_used_map: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = list(scene.warnings or [])

        for layer in scene.visible_layers():
            composition_layer = CompositionLayer(
                name=layer.name,
                z_index=layer.z_index,
                visibility=layer.visibility,
                opacity=layer.opacity,
            )
            for sprite in layer.sprites:
                resolved = self.resolver.resolve_for_sprite(sprite)
                descriptor = resolved['descriptor']
                assets_used_map[descriptor.asset_id] = {
                    'asset_id': descriptor.asset_id,
                    'asset_type': descriptor.asset_type,
                    'source': descriptor.source,
                    'metadata': dict(descriptor.metadata),
                }
                binding = CompositionSpriteBinding(
                    sprite_id=str(getattr(sprite, 'sprite_id', '') or ''),
                    sprite_type=sprite.__class__.__name__,
                    layer_name=layer.name,
                    asset_id=descriptor.asset_id,
                    asset_type=descriptor.asset_type,
                    x=float(getattr(sprite, 'x', 0.5) or 0.5),
                    y=float(getattr(sprite, 'y', 0.5) or 0.5),
                    rotation=float(getattr(sprite, 'rotation', 0.0) or 0.0),
                    scale=float(getattr(sprite, 'scale', 1.0) or 1.0),
                    z_index=int(getattr(sprite, 'z_index', layer.z_index) or layer.z_index),
                    semantic_role=str(getattr(sprite, 'semantic_role', '') or ''),
                )
                if not 0.0 <= binding.x <= 1.0 or not 0.0 <= binding.y <= 1.0:
                    binding.warnings.append('Sprite fuera del campo normalizado.')
                    warnings.append(f'{binding.sprite_id}: fuera del campo normalizado.')
                composition_layer.add_item(
                    {
                        'binding': binding.as_dict(),
                        'asset_id': descriptor.asset_id,
                        'asset_type': descriptor.asset_type,
                        'inline_svg': resolved.get('inline_svg', ''),
                    }
                )
                bindings.append(binding)
            composition_layers.append(composition_layer)

        return CompositionScene(
            layers=composition_layers,
            assets_used=list(assets_used_map.values()),
            bindings=bindings,
            warnings=warnings,
            metadata=dict(scene.metadata or {}),
            theme=dict(theme or {}),
        )


def _svg_body_only(svg_markup: str) -> str:
    raw = str(svg_markup or '').strip()
    if not raw:
        return ''
    start = raw.find('>')
    end = raw.rfind('</svg>')
    if raw.startswith('<svg') and start != -1 and end != -1:
        return raw[start + 1:end]
    return raw


def build_basic_composition_preview_svg(composition_scene: CompositionScene) -> str:
    theme = composition_scene.theme or {}
    colors = (theme.get('colors') or {}) if isinstance(theme.get('colors'), dict) else {}
    width = composition_scene.width
    height = composition_scene.height
    field_x = 110
    field_y = 70
    field_w = width - 220
    field_h = height - 140

    pieces: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Composition preview">',
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="28" fill="{html.escape(str(colors.get("background") or "#08111d"))}"/>',
        f'<rect x="{field_x - 18}" y="{field_y - 18}" width="{field_w + 36}" height="{field_h + 36}" rx="36" fill="{html.escape(str(colors.get("panel") or "#0f172a"))}" opacity="0.96"/>',
        f'<rect x="{field_x}" y="{field_y}" width="{field_w}" height="{field_h}" rx="28" fill="{html.escape(str(colors.get("field_base") or "#2e8b57"))}"/>',
        f'<rect x="{field_x}" y="{field_y}" width="{field_w}" height="{field_h}" rx="28" fill="{html.escape(str(colors.get("highlight") or "#ffffff"))}" opacity="0.05"/>',
        f'<rect x="{field_x}" y="{field_y}" width="{field_w}" height="{field_h}" rx="28" fill="none" stroke="{html.escape(str(colors.get("field_line") or "#f8fafc"))}" stroke-width="4"/>',
        f'<line x1="{field_x + field_w / 2}" y1="{field_y}" x2="{field_x + field_w / 2}" y2="{field_y + field_h}" stroke="{html.escape(str(colors.get("field_line") or "#f8fafc"))}" stroke-width="3"/>',
        f'<circle cx="{field_x + field_w / 2}" cy="{field_y + field_h / 2}" r="{field_w * 0.08}" fill="none" stroke="{html.escape(str(colors.get("field_line") or "#f8fafc"))}" stroke-width="3"/>',
    ]

    for layer in sorted(composition_scene.layers, key=lambda item: item.z_index):
        if not layer.visibility:
            continue
        pieces.append(f'<g data-layer="{html.escape(layer.name)}" opacity="{layer.opacity}">')
        for item in layer.items:
            binding = item.get('binding') or {}
            inline_svg = _svg_body_only(item.get('inline_svg') or '')
            x = field_x + (field_w * float(binding.get('x') or 0.0))
            y = field_y + (field_h * float(binding.get('y') or 0.0))
            scale = float(binding.get('scale') or 1.0)
            rotation = float(binding.get('rotation') or 0.0)
            pieces.append(f'<g transform="translate({x:.2f} {y:.2f}) rotate({rotation:.2f}) scale({scale:.3f})">{inline_svg}</g>')
        pieces.append('</g>')

    pieces.append('</svg>')
    return ''.join(pieces)
