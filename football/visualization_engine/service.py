from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .assets.registry import AssetRegistry
from .composition.asset_resolver import AssetResolver
from .composition.composer import CompositionEngine, CompositionScene
from .normalizer import (
    build_scene_graph_from_canvas_state,
    build_scene_graph_from_tactical_layout,
    scene_graph_diagnostic_payload,
)
from .renderers.perspective3d import Perspective3DRenderer
from .renderers.top2d import Top2DRenderer
from .scene.composer import SceneComposer
from .scene.layers import LAYER_MAP
from .scene.scene import VisualizationScene
from .semantic_graph import build_semantic_graph_from_scene_graph
from .sprites.arrow import ArrowSprite
from .sprites.ball import BallSprite
from .sprites.cone import ConeSprite
from .sprites.goal import GoalSprite
from .sprites.goalkeeper import GoalkeeperSprite
from .sprites.label import LabelSprite
from .sprites.player import PlayerSprite
from .sprites.pole import PoleSprite
from .sprites.zone import ZoneSprite
from .themes import broadcast, classic, premium


THEME_LOADERS = {
    'classic': classic.get_theme,
    'premium': premium.get_theme,
    'broadcast': broadcast.get_theme,
}


def get_theme_definition(theme_key: str = 'broadcast') -> Dict[str, Any]:
    theme_name = str(theme_key or 'broadcast').strip().lower() or 'broadcast'
    return THEME_LOADERS.get(theme_name, broadcast.get_theme)()


@dataclass
class SpriteFactory:
    theme_key: str = 'broadcast'

    def build(self, semantic_graph: Dict[str, Any]) -> List[Any]:
        sprites: List[Any] = []
        for entity in semantic_graph.get('entities') or []:
            sprite = self._sprite_from_entity(entity)
            if sprite is not None:
                sprites.append(sprite)
        for action in semantic_graph.get('actions') or []:
            sprite = self._sprite_from_action(action)
            if sprite is not None:
                sprites.append(sprite)
        return sprites

    def _sprite_from_entity(self, entity: Dict[str, Any]) -> Any | None:
        role = str(entity.get('semantic_role') or '')
        kind = str(entity.get('kind') or '')
        position = entity.get('position') if isinstance(entity.get('position'), dict) else {}
        x = float(position.get('x') or 0.0)
        y = float(position.get('y') or 0.0)
        sprite_id = str(entity.get('id') or 'sprite')

        if role in {'player', 'neutral', 'opponent'}:
            return PlayerSprite(
                sprite_id=sprite_id,
                x=x,
                y=y,
                number=str(entity.get('number') or ''),
                team=str(entity.get('team') or 'unknown'),
                role=str(entity.get('role') or 'outfield'),
                semantic_role=role,
                rotation=float(entity.get('body_orientation') or entity.get('rotation') or 0.0),
                scale=float(entity.get('scale') or 1.0),
                z_index=LAYER_MAP['players'],
            )
        if role == 'goalkeeper':
            return GoalkeeperSprite(
                sprite_id=sprite_id,
                x=x,
                y=y,
                number=str(entity.get('number') or ''),
                team=str(entity.get('team') or 'unknown'),
                rotation=float(entity.get('body_orientation') or entity.get('rotation') or 0.0),
                scale=float(entity.get('scale') or 1.0),
                z_index=LAYER_MAP['players'] + 1,
            )
        if role == 'ball':
            return BallSprite(
                sprite_id=sprite_id,
                x=x,
                y=y,
                owner=str(entity.get('owner') or '') or None,
                scale=float(entity.get('scale') or 1.0),
                z_index=LAYER_MAP['ball'],
            )
        if kind == 'cone':
            return ConeSprite(
                sprite_id=sprite_id,
                x=x,
                y=y,
                scale=float(entity.get('scale') or 1.0),
                z_index=LAYER_MAP['equipment'],
            )
        if kind == 'pole':
            size = entity.get('size') if isinstance(entity.get('size'), dict) else {}
            return PoleSprite(
                sprite_id=sprite_id,
                x=x,
                y=y,
                width=float(size.get('width') or 0.01),
                height=float(size.get('height') or 0.06),
                rotation=float(entity.get('rotation') or 0.0),
                scale=float(entity.get('scale') or 1.0),
                z_index=LAYER_MAP['equipment'],
            )
        if kind == 'goal':
            size = entity.get('size') if isinstance(entity.get('size'), dict) else {}
            return GoalSprite(
                sprite_id=sprite_id,
                x=x,
                y=y,
                width=float(size.get('width') or 0.12),
                height=float(size.get('height') or 0.03),
                rotation=float(entity.get('rotation') or 0.0),
                scale=float(entity.get('scale') or 1.0),
                z_index=LAYER_MAP['goals'],
            )
        if role == 'text':
            return LabelSprite(
                sprite_id=sprite_id,
                x=x,
                y=y,
                text=str(entity.get('text') or ''),
                rotation=float(entity.get('rotation') or 0.0),
                scale=float(entity.get('scale') or 1.0),
                z_index=LAYER_MAP['labels'],
            )
        return None

    def _sprite_from_action(self, action: Dict[str, Any]) -> Any | None:
        action_type = str(action.get('type') or '')
        points = [point for point in (action.get('points') or []) if isinstance(point, dict)]
        sprite_id = str(action.get('id') or 'action')
        if action_type.endswith('_zone') or action_type in {'occupation_zone', 'pressing_zone', 'finishing_zone', 'build_up_zone', 'unknown_zone'}:
            return ZoneSprite(sprite_id=sprite_id, points=points, zone_type=action_type, z_index=LAYER_MAP['zones'])
        if points:
            return ArrowSprite(sprite_id=sprite_id, points=points, action_type=action_type or 'unknown_action', z_index=LAYER_MAP['arrows'])
        return None


def build_visualization_blueprint(task: Any, *, theme_key: str = 'broadcast') -> Dict[str, Any]:
    scene_graph = build_scene_graph_from_task(task)
    semantic_graph = build_semantic_graph_from_scene_graph(scene_graph)
    theme = get_theme_definition(theme_key)
    factory = SpriteFactory(theme_key=theme_key)
    sprites = factory.build(semantic_graph)
    visualization_scene = SceneComposer(theme_key=theme_key).compose(semantic_graph, sprites=sprites, theme=theme)
    registry = AssetRegistry()
    composition_scene = CompositionEngine(
        AssetResolver(registry, theme_key=theme_key),
    ).compose(visualization_scene, theme=theme)
    return {
        'theme': theme,
        'scene_graph': scene_graph,
        'semantic_graph': semantic_graph,
        'sprites': sprites,
        'visualization_scene': visualization_scene,
        'composition_scene': composition_scene,
        'asset_registry': registry,
        'renderer_top2d': Top2DRenderer(theme),
        'renderer_perspective3d': Perspective3DRenderer(theme),
    }


def build_visualization_scene(task: Any, *, theme_key: str = 'broadcast') -> VisualizationScene:
    blueprint = build_visualization_blueprint(task, theme_key=theme_key)
    scene = blueprint.get('visualization_scene')
    if isinstance(scene, VisualizationScene):
        return scene
    return SceneComposer(theme_key=theme_key).compose(
        blueprint.get('semantic_graph') or {},
        sprites=blueprint.get('sprites') or [],
        theme=blueprint.get('theme') or {},
    )


def build_visualization_composition(task: Any, *, theme_key: str = 'broadcast') -> CompositionScene:
    blueprint = build_visualization_blueprint(task, theme_key=theme_key)
    composition_scene = blueprint.get('composition_scene')
    if isinstance(composition_scene, CompositionScene):
        return composition_scene
    return CompositionEngine(
        AssetResolver(blueprint.get('asset_registry') or AssetRegistry(), theme_key=theme_key),
    ).compose(
        blueprint.get('visualization_scene'),
        theme=blueprint.get('theme') or {},
    )


def summarize_visualization_blueprint(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    sprites: Iterable[Any] = blueprint.get('sprites') or []
    sprite_list = list(sprites)
    visualization_scene = blueprint.get('visualization_scene')
    return {
        'theme_key': ((blueprint.get('theme') or {}).get('key') or 'broadcast'),
        'sprite_count': len(sprite_list),
        'sprite_types': [sprite.__class__.__name__ for sprite in sprite_list],
        'semantic_entity_count': len((blueprint.get('semantic_graph') or {}).get('entities') or []),
        'action_count': len((blueprint.get('semantic_graph') or {}).get('actions') or []),
        'layer_count': len(getattr(visualization_scene, 'layers', []) or []),
        'composition_layer_count': len(getattr((blueprint.get('composition_scene')), 'layers', []) or []),
    }


def _extract_task_canvas_state(task: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    tactical_layout = getattr(task, 'tactical_layout', None)
    safe_layout = tactical_layout if isinstance(tactical_layout, dict) else {}
    meta = safe_layout.get('meta') if isinstance(safe_layout.get('meta'), dict) else {}
    canvas_state = {
        'version': str(safe_layout.get('version') or '5.3.0'),
        'width': int((((meta.get('graphic_editor') or {}).get('canvas_width')) if isinstance(meta.get('graphic_editor'), dict) and (meta.get('graphic_editor') or {}).get('canvas_width') else 1054)),
        'height': int((((meta.get('graphic_editor') or {}).get('canvas_height')) if isinstance(meta.get('graphic_editor'), dict) and (meta.get('graphic_editor') or {}).get('canvas_height') else 684)),
        'objects': safe_layout.get('objects') if isinstance(safe_layout.get('objects'), list) else [],
    }
    return canvas_state, meta


def build_scene_graph_from_task(task: Any) -> Dict[str, Any]:
    tactical_layout = getattr(task, 'tactical_layout', None)
    if isinstance(tactical_layout, dict) and tactical_layout:
        scene_graph = build_scene_graph_from_tactical_layout(tactical_layout)
        metadata = dict(scene_graph.get('metadata') or {})
        metadata.update(
            {
                'task_id': getattr(task, 'id', None),
                'task_title': str(getattr(task, 'title', '') or '').strip(),
                'session_id': getattr(task, 'session_id', None),
            }
        )
        scene_graph['metadata'] = metadata
        return scene_graph

    canvas_state, meta = _extract_task_canvas_state(task)
    scene_graph = build_scene_graph_from_canvas_state(canvas_state, meta=meta)
    metadata = dict(scene_graph.get('metadata') or {})
    metadata.update(
        {
            'task_id': getattr(task, 'id', None),
            'task_title': str(getattr(task, 'title', '') or '').strip(),
            'session_id': getattr(task, 'session_id', None),
        }
    )
    scene_graph['metadata'] = metadata
    return scene_graph


def build_scene_graph_diagnostic(task: Any) -> Dict[str, Any]:
    return scene_graph_diagnostic_payload(build_scene_graph_from_task(task))


def build_semantic_graph_from_task(task: Any) -> Dict[str, Any]:
    return build_semantic_graph_from_scene_graph(build_scene_graph_from_task(task))


__all__ = [
    'build_scene_graph_from_task',
    'build_scene_graph_from_canvas_state',
    'build_scene_graph_from_tactical_layout',
    'build_scene_graph_diagnostic',
    'build_semantic_graph_from_task',
    'build_visualization_blueprint',
    'build_visualization_composition',
    'summarize_visualization_blueprint',
    'SpriteFactory',
    'get_theme_definition',
]
