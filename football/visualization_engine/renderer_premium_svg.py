from __future__ import annotations

import html
import math
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .scene.scene import VisualizationScene


SVG_WIDTH = 1600
SVG_HEIGHT = 1020
FIELD_MARGIN_X = 120
FIELD_MARGIN_Y = 92


def _theme_colors(theme: Dict[str, Any]) -> Dict[str, str]:
    colors = theme.get('colors') if isinstance(theme.get('colors'), dict) else {}
    background = str(colors.get('background') or '#07111f')
    field_line = str(colors.get('field_line') or '#f8fafc')
    return {
        'background': background,
        'field_base': str(colors.get('field_base') or '#2e8b57'),
        'field_line': field_line,
        'shadow': str(colors.get('shadow') or 'rgba(2, 6, 23, 0.32)'),
        'player_home': str(colors.get('player_home') or '#38bdf8'),
        'player_away': str(colors.get('player_away') or '#f97316'),
        'goalkeeper': str(colors.get('goalkeeper') or '#fde047'),
        'ball': str(colors.get('ball') or '#ffffff'),
        'cone': str(colors.get('cone') or '#fb7185'),
        'goal': str(colors.get('goal') or '#cbd5e1'),
        'arrow': str(colors.get('arrow') or '#e2e8f0'),
        'zone': str(colors.get('zone') or 'rgba(74, 222, 128, 0.18)'),
        'label': str(colors.get('label') or '#f8fafc'),
        'panel': str(colors.get('panel') or '#0b1725'),
        'frame_outer': str(colors.get('frame_outer') or '#dfe7f2'),
        'frame_inner': str(colors.get('frame_inner') or '#94a9bc'),
        'highlight': str(colors.get('highlight') or '#ffffff'),
        'grass_dark': str(colors.get('grass_dark') or '#256945'),
        'grass_light': str(colors.get('grass_light') or '#56b777'),
        'grass_mid': str(colors.get('grass_mid') or '#3f9960'),
        'arrow_glow': str(colors.get('arrow_glow') or 'rgba(255,255,255,0.22)'),
        'token_ring': str(colors.get('token_ring') or field_line),
        'token_shadow': str(colors.get('token_shadow') or 'rgba(0,0,0,0.28)'),
        'goal_net': str(colors.get('goal_net') or field_line),
        'contrast_dark': background,
        'accent_light': field_line,
    }


def _field_box() -> Dict[str, float]:
    return {
        'x': FIELD_MARGIN_X,
        'y': FIELD_MARGIN_Y,
        'width': SVG_WIDTH - (FIELD_MARGIN_X * 2.0),
        'height': SVG_HEIGHT - (FIELD_MARGIN_Y * 2.0),
    }


def _coord_x(x: float) -> float:
    box = _field_box()
    return box['x'] + (box['width'] * max(0.0, min(1.0, float(x))))


def _coord_y(y: float) -> float:
    box = _field_box()
    return box['y'] + (box['height'] * max(0.0, min(1.0, float(y))))


def _escape(value: Any) -> str:
    return html.escape(str(value or ''))


def _parse_rgba(value: str, fallback_opacity: float = 0.18) -> Tuple[str, float]:
    raw = str(value or '').strip()
    if raw.startswith('rgba(') and raw.endswith(')'):
        parts = [item.strip() for item in raw[5:-1].split(',')]
        if len(parts) == 4:
            try:
                r = int(float(parts[0]))
                g = int(float(parts[1]))
                b = int(float(parts[2]))
                a = float(parts[3])
                return f'#{r:02x}{g:02x}{b:02x}', a
            except (TypeError, ValueError):
                pass
    return raw or '#4ade80', fallback_opacity


def _player_color(sprite: Any, colors: Dict[str, str]) -> str:
    role = str(getattr(sprite, 'semantic_role', '') or '')
    team = str(getattr(sprite, 'team', '') or '')
    if role == 'goalkeeper':
        return colors['goalkeeper']
    if role == 'opponent' or team == 'away':
        return colors['player_away']
    return colors['player_home']


def _shadow_filter_id() -> str:
    return 'premiumShadow'


def _field_shadow_filter_id() -> str:
    return 'fieldShadow'


class PremiumSVGRenderer:
    def __init__(self, theme: Dict[str, Any]) -> None:
        self.theme = theme
        self.colors = _theme_colors(theme)
        self.typography = theme.get('typography') if isinstance(theme.get('typography'), dict) else {}
        self.arrow_theme = theme.get('arrows') if isinstance(theme.get('arrows'), dict) else {}
        self.line_theme = theme.get('lines') if isinstance(theme.get('lines'), dict) else {}
        self.grass_theme = theme.get('grass') if isinstance(theme.get('grass'), dict) else {}
        self.player_theme = theme.get('players') if isinstance(theme.get('players'), dict) else {}
        self.frame_theme = theme.get('field_frame') if isinstance(theme.get('field_frame'), dict) else {}
        self.goal_theme = theme.get('goals') if isinstance(theme.get('goals'), dict) else {}
        self.zone_theme = theme.get('zones') if isinstance(theme.get('zones'), dict) else {}
        self.shadow_theme = theme.get('shadows') if isinstance(theme.get('shadows'), dict) else {}
        self.draw_calls: List[Dict[str, Any]] = []

    def render(self, scene: VisualizationScene) -> Dict[str, Any]:
        started = time.perf_counter()
        self.draw_calls = []
        svg_parts: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img" aria-label="Visualization premium SVG">',
            self._defs(),
            self._background(scene),
            self._field(scene),
        ]
        for layer in scene.visible_layers():
            if layer.name == 'field':
                continue
            svg_parts.append(f'<g data-layer="{_escape(layer.name)}" opacity="{layer.opacity}">')
            for sprite in layer.sprites:
                fragment = self._render_sprite(sprite)
                if fragment:
                    svg_parts.append(fragment)
            svg_parts.append('</g>')
        svg_parts.append('</svg>')
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {
            'svg': ''.join(svg_parts),
            'draw_calls': list(self.draw_calls),
            'render_time_ms': elapsed_ms,
            'sprite_count': len(scene.all_sprites()),
            'theme': self.theme,
        }

    def _defs(self) -> str:
        field = _field_box()
        zone_color, zone_opacity = _parse_rgba(self.colors['zone'], 0.16)
        shadow_color, shadow_opacity = _parse_rgba(self.colors['shadow'], 0.28)
        arrow_glow_color, arrow_glow_opacity = _parse_rgba(self.colors['arrow_glow'], 0.22)
        token_shadow_color, token_shadow_opacity = _parse_rgba(self.colors['token_shadow'], 0.28)
        return f"""
<defs>
  <linearGradient id="grassGradient" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0%" stop-color="{self.colors['grass_light']}" stop-opacity="0.98"/>
    <stop offset="45%" stop-color="{self.colors['field_base']}" stop-opacity="0.96"/>
    <stop offset="100%" stop-color="{self.colors['grass_dark']}" stop-opacity="0.96"/>
  </linearGradient>
  <linearGradient id="frameGradient" x1="0" x2="0" y1="0" y2="1">
    <stop offset="0%" stop-color="{self.colors['frame_outer']}" stop-opacity="0.98"/>
    <stop offset="100%" stop-color="{self.colors['frame_inner']}" stop-opacity="0.92"/>
  </linearGradient>
  <radialGradient id="pitchLight" cx="50%" cy="28%" r="78%">
    <stop offset="0%" stop-color="{self.colors['highlight']}" stop-opacity="0.16"/>
    <stop offset="46%" stop-color="{self.colors['highlight']}" stop-opacity="0.05"/>
    <stop offset="100%" stop-color="{self.colors['highlight']}" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="fieldHalo" cx="50%" cy="42%" r="65%">
    <stop offset="0%" stop-color="{self.colors['accent_light']}" stop-opacity="0.08"/>
    <stop offset="100%" stop-color="{self.colors['accent_light']}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="zoneGradient" x1="0" x2="1" y1="0" y2="1">
    <stop offset="0%" stop-color="{zone_color}" stop-opacity="{min(1.0, zone_opacity + 0.12)}"/>
    <stop offset="100%" stop-color="{zone_color}" stop-opacity="{max(0.06, zone_opacity * 0.6)}"/>
  </linearGradient>
  <filter id="{_shadow_filter_id()}" x="-50%" y="-50%" width="200%" height="200%">
    <feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="{shadow_color}" flood-opacity="{shadow_opacity}"/>
  </filter>
  <filter id="{_field_shadow_filter_id()}" x="-10%" y="-10%" width="120%" height="120%">
    <feDropShadow dx="0" dy="22" stdDeviation="22" flood-color="{shadow_color}" flood-opacity="{max(0.14, shadow_opacity * 0.78)}"/>
  </filter>
  <filter id="tokenShadow" x="-70%" y="-70%" width="240%" height="240%">
    <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="{token_shadow_color}" flood-opacity="{token_shadow_opacity}"/>
  </filter>
  <filter id="arrowGlow" x="-70%" y="-70%" width="240%" height="240%">
    <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="{arrow_glow_color}" flood-opacity="{arrow_glow_opacity}"/>
  </filter>
  <pattern id="grassNoise" width="140" height="140" patternUnits="userSpaceOnUse">
    <path d="M10 22 L18 6 M42 48 L48 30 M88 26 L98 8 M124 68 L132 48 M78 118 L88 102 M20 110 L30 90" stroke="{self.colors['accent_light']}" stroke-opacity="0.06" stroke-width="2" stroke-linecap="round"/>
  </pattern>
  <pattern id="grassFibers" width="90" height="90" patternUnits="userSpaceOnUse">
    <path d="M8 60 C16 42, 18 26, 20 8 M44 84 C48 62, 56 36, 64 12 M72 76 C78 58, 82 40, 88 20" stroke="{self.colors['grass_mid']}" stroke-opacity="0.20" stroke-width="1.1" stroke-linecap="round"/>
  </pattern>
  <pattern id="goalNet" width="12" height="12" patternUnits="userSpaceOnUse">
    <path d="M0 0 L12 12 M12 0 L0 12" stroke="{self.colors['goal_net']}" stroke-opacity="{self.goal_theme.get('net_opacity', 0.64)}" stroke-width="0.8"/>
  </pattern>
  <marker id="arrowHead" markerWidth="14" markerHeight="14" refX="10" refY="7" orient="auto" markerUnits="userSpaceOnUse">
    <path d="M0,0 L14,7 L0,14 Q4,7 0,0 Z" fill="{self.colors['arrow']}"/>
  </marker>
  <clipPath id="fieldClip">
    <rect x="{field['x']}" y="{field['y']}" width="{field['width']}" height="{field['height']}" rx="34"/>
  </clipPath>
</defs>
"""

    def _background(self, scene: VisualizationScene) -> str:
        return (
            f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="{self.colors["background"]}"/>'
            f'<rect x="{FIELD_MARGIN_X * 0.35}" y="{FIELD_MARGIN_Y * 0.38}" width="{SVG_WIDTH - FIELD_MARGIN_X * 0.7}" height="{SVG_HEIGHT - FIELD_MARGIN_Y * 0.76}" rx="60" fill="{self.colors["panel"]}" opacity="0.96"/>'
            f'<rect x="{FIELD_MARGIN_X * 0.41}" y="{FIELD_MARGIN_Y * 0.45}" width="{SVG_WIDTH - FIELD_MARGIN_X * 0.82}" height="{SVG_HEIGHT - FIELD_MARGIN_Y * 0.9}" rx="56" fill="{self.colors["accent_light"]}" opacity="0.045"/>'
        )

    def _field(self, scene: VisualizationScene) -> str:
        box = _field_box()
        line = self.colors['field_line']
        line_width = float(self.line_theme.get('width') or 2.4)
        outer_radius = float(self.frame_theme.get('outer_radius') or 42.0)
        inner_radius = float(self.frame_theme.get('inner_radius') or 34.0)
        panel_padding = float(self.frame_theme.get('panel_padding') or 18.0)
        penalty_width = box['width'] * 0.165
        six_width = box['width'] * 0.062
        penalty_depth = box['height'] * 0.18
        six_depth = box['height'] * 0.07
        center_circle = box['width'] * 0.092
        penalty_spot_offset = box['height'] * 0.12
        arc_radius = box['width'] * 0.055
        stripes: List[str] = []
        stripe_count = int(self.grass_theme.get('bands') or 11)
        stripe_width = box['width'] / stripe_count
        for index in range(stripe_count):
            opacity = float(self.grass_theme.get('stripe_opacity') or 0.16) if index % 2 == 0 else 0.045
            stripes.append(
                f'<rect x="{box["x"] + stripe_width * index}" y="{box["y"]}" width="{stripe_width}" height="{box["height"]}" fill="{self.colors["highlight"]}" opacity="{opacity}"/>'
            )
        self.draw_calls.append({'kind': 'field_base', 'box': box})
        return f"""
<g data-layer="field">
  <rect x="{box['x'] - panel_padding}" y="{box['y'] - panel_padding}" width="{box['width'] + panel_padding * 2}" height="{box['height'] + panel_padding * 2}" rx="{outer_radius}" fill="url(#frameGradient)" filter="url(#{_field_shadow_filter_id()})"/>
  <rect x="{box['x'] - (panel_padding * 0.55)}" y="{box['y'] - (panel_padding * 0.55)}" width="{box['width'] + panel_padding * 1.1}" height="{box['height'] + panel_padding * 1.1}" rx="{inner_radius}" fill="{self.colors['panel']}" opacity="0.92"/>
  <rect x="{box['x']}" y="{box['y']}" width="{box['width']}" height="{box['height']}" rx="34" fill="url(#grassGradient)" filter="url(#{_field_shadow_filter_id()})"/>
  {''.join(stripes)}
  <rect x="{box['x']}" y="{box['y']}" width="{box['width']}" height="{box['height']}" rx="34" fill="url(#grassNoise)" opacity="{self.grass_theme.get('noise_opacity', 0.28)}" clip-path="url(#fieldClip)"/>
  <rect x="{box['x']}" y="{box['y']}" width="{box['width']}" height="{box['height']}" rx="34" fill="url(#grassFibers)" opacity="0.34" clip-path="url(#fieldClip)"/>
  <rect x="{box['x']}" y="{box['y']}" width="{box['width']}" height="{box['height']}" rx="34" fill="url(#pitchLight)" opacity="0.86"/>
  <ellipse cx="{box['x'] + (box['width'] / 2)}" cy="{box['y'] + (box['height'] / 2)}" rx="{box['width'] * 0.36}" ry="{box['height'] * 0.32}" fill="url(#fieldHalo)" opacity="{self.grass_theme.get('glow_opacity', 0.13)}"/>
  <rect x="{box['x']}" y="{box['y']}" width="{box['width']}" height="{box['height']}" rx="34" fill="none" stroke="{self.colors['frame_inner']}" stroke-width="{line_width * 4.1}" opacity="0.22"/>
  <rect x="{box['x']}" y="{box['y']}" width="{box['width']}" height="{box['height']}" rx="34" fill="none" stroke="{line}" stroke-width="{line_width * 1.22}"/>
  <line x1="{box['x'] + (box['width'] / 2)}" y1="{box['y']}" x2="{box['x'] + (box['width'] / 2)}" y2="{box['y'] + box['height']}" stroke="{line}" stroke-width="{line_width}"/>
  <circle cx="{box['x'] + (box['width'] / 2)}" cy="{box['y'] + (box['height'] / 2)}" r="{center_circle}" fill="none" stroke="{line}" stroke-width="{line_width}"/>
  <circle cx="{box['x'] + (box['width'] / 2)}" cy="{box['y'] + (box['height'] / 2)}" r="{line_width * 1.2}" fill="{line}"/>

  <rect x="{box['x'] + (box['width'] - penalty_width) / 2}" y="{box['y']}" width="{penalty_width}" height="{penalty_depth}" fill="none" stroke="{line}" stroke-width="{line_width}"/>
  <rect x="{box['x'] + (box['width'] - six_width) / 2}" y="{box['y']}" width="{six_width}" height="{six_depth}" fill="none" stroke="{line}" stroke-width="{line_width}"/>
  <circle cx="{box['x'] + (box['width'] / 2)}" cy="{box['y'] + penalty_spot_offset}" r="{line_width * 1.1}" fill="{line}"/>
  <path d="M {box['x'] + (box['width'] / 2) - arc_radius} {box['y'] + penalty_depth} A {arc_radius} {arc_radius} 0 0 0 {box['x'] + (box['width'] / 2) + arc_radius} {box['y'] + penalty_depth}" fill="none" stroke="{line}" stroke-width="{line_width}"/>

  <rect x="{box['x'] + (box['width'] - penalty_width) / 2}" y="{box['y'] + box['height'] - penalty_depth}" width="{penalty_width}" height="{penalty_depth}" fill="none" stroke="{line}" stroke-width="{line_width}"/>
  <rect x="{box['x'] + (box['width'] - six_width) / 2}" y="{box['y'] + box['height'] - six_depth}" width="{six_width}" height="{six_depth}" fill="none" stroke="{line}" stroke-width="{line_width}"/>
  <circle cx="{box['x'] + (box['width'] / 2)}" cy="{box['y'] + box['height'] - penalty_spot_offset}" r="{line_width * 1.1}" fill="{line}"/>
  <path d="M {box['x'] + (box['width'] / 2) - arc_radius} {box['y'] + box['height'] - penalty_depth} A {arc_radius} {arc_radius} 0 0 1 {box['x'] + (box['width'] / 2) + arc_radius} {box['y'] + box['height'] - penalty_depth}" fill="none" stroke="{line}" stroke-width="{line_width}"/>
</g>
"""

    def _render_sprite(self, sprite: Any) -> str:
        sprite_type = sprite.__class__.__name__
        if sprite_type == 'PlayerSprite':
            return self._render_player(sprite)
        if sprite_type == 'GoalkeeperSprite':
            return self._render_goalkeeper(sprite)
        if sprite_type == 'BallSprite':
            return self._render_ball(sprite)
        if sprite_type == 'ConeSprite':
            return self._render_cone(sprite)
        if sprite_type == 'PoleSprite':
            return self._render_pole(sprite)
        if sprite_type == 'GoalSprite':
            return self._render_goal(sprite)
        if sprite_type == 'ArrowSprite':
            return self._render_arrow(sprite)
        if sprite_type == 'ZoneSprite':
            return self._render_zone(sprite)
        if sprite_type == 'LabelSprite':
            return self._render_label(sprite)
        self.draw_calls.append({'kind': 'unknown_sprite', 'sprite_id': getattr(sprite, 'sprite_id', '')})
        return ''

    def _render_player(self, sprite: Any) -> str:
        cx = _coord_x(float(sprite.x))
        cy = _coord_y(float(sprite.y))
        radius = float(self.player_theme.get('radius') or 22.0) * float(getattr(sprite, 'scale', 1.0) or 1.0)
        ring = float(self.player_theme.get('ring') or 4.0)
        shadow_y = float(self.player_theme.get('shadow_y') or 10.0)
        orientation_width = float(self.player_theme.get('orientation_width') or 4.6)
        color = _player_color(sprite, self.colors)
        rotation = math.radians(float(getattr(sprite, 'rotation', 0.0) or 0.0))
        dx = math.cos(rotation) * radius * 0.88
        dy = math.sin(rotation) * radius * 0.88
        self.draw_calls.append({'kind': 'player', 'sprite_id': sprite.sprite_id})
        return f"""
<g transform="translate({cx} {cy})" filter="url(#tokenShadow)">
  <ellipse cx="0" cy="{shadow_y + radius * 0.62}" rx="{radius * 0.98}" ry="{radius * 0.36}" fill="{self.colors['contrast_dark']}" opacity="0.24"/>
  <circle cx="0" cy="0" r="{radius + ring}" fill="{self.colors['token_ring']}" opacity="0.98"/>
  <circle cx="0" cy="0" r="{radius + 0.9}" fill="{self.colors['contrast_dark']}" opacity="0.12"/>
  <circle cx="0" cy="0" r="{radius}" fill="{color}"/>
  <circle cx="{dx * 0.15}" cy="{dy * 0.15}" r="{radius * 0.72}" fill="{self.colors['highlight']}" opacity="0.10"/>
  <path d="M0 0 L{dx:.2f} {dy:.2f}" stroke="{self.colors['accent_light']}" stroke-width="{orientation_width}" stroke-linecap="round" opacity="0.96"/>
  <circle cx="{dx:.2f}" cy="{dy:.2f}" r="{radius * 0.22}" fill="{self.colors['accent_light']}"/>
  <text x="0" y="{radius * 0.33}" text-anchor="middle" fill="{self.colors['accent_light']}" font-family="{_escape(self.typography.get('family') or 'system-ui')}" font-size="{radius * 0.95}" font-weight="{self.typography.get('weight') or 800}">{_escape(getattr(sprite, 'number', '') or '')}</text>
</g>
"""

    def _render_goalkeeper(self, sprite: Any) -> str:
        cx = _coord_x(float(sprite.x))
        cy = _coord_y(float(sprite.y))
        radius = (float(self.player_theme.get('radius') or 22.0) + 2.0) * float(getattr(sprite, 'scale', 1.0) or 1.0)
        ring = float(self.player_theme.get('ring') or 4.0)
        color = self.colors['goalkeeper']
        rotation = math.radians(float(getattr(sprite, 'rotation', 0.0) or 0.0))
        dx = math.cos(rotation) * radius * 0.9
        dy = math.sin(rotation) * radius * 0.9
        self.draw_calls.append({'kind': 'goalkeeper', 'sprite_id': sprite.sprite_id})
        return f"""
<g transform="translate({cx} {cy})" filter="url(#tokenShadow)">
  <ellipse cx="0" cy="{radius * 1.16}" rx="{radius * 1.0}" ry="{radius * 0.40}" fill="{self.colors['contrast_dark']}" opacity="0.22"/>
  <path d="M 0 {-radius - ring} L {radius + ring} 0 L 0 {radius + ring} L {-radius - ring} 0 Z" fill="{self.colors['token_ring']}" opacity="0.98"/>
  <path d="M 0 {-radius} L {radius} 0 L 0 {radius} L {-radius} 0 Z" fill="{color}"/>
  <path d="M0 0 L{dx:.2f} {dy:.2f}" stroke="{self.colors['contrast_dark']}" stroke-width="3.4" stroke-linecap="round" opacity="0.92"/>
  <circle cx="{dx:.2f}" cy="{dy:.2f}" r="{radius * 0.17}" fill="{self.colors['contrast_dark']}"/>
  <text x="0" y="{radius * 0.26}" text-anchor="middle" fill="{self.colors['contrast_dark']}" font-family="{_escape(self.typography.get('family') or 'system-ui')}" font-size="{radius * 0.82}" font-weight="{self.typography.get('weight') or 800}">{_escape(getattr(sprite, 'number', '') or '')}</text>
</g>
"""

    def _render_ball(self, sprite: Any) -> str:
        cx = _coord_x(float(sprite.x))
        cy = _coord_y(float(sprite.y))
        radius = 10.0 * float(getattr(sprite, 'scale', 1.0) or 1.0)
        self.draw_calls.append({'kind': 'ball', 'sprite_id': sprite.sprite_id})
        return f"""
<g transform="translate({cx} {cy})" filter="url(#tokenShadow)">
  <circle cx="0" cy="{radius * 1.25}" r="{radius * 0.68}" fill="{self.colors['contrast_dark']}" opacity="0.22"/>
  <circle cx="0" cy="0" r="{radius}" fill="{self.colors['ball']}" stroke="{self.colors['contrast_dark']}" stroke-width="1.7"/>
  <circle cx="-{radius * 0.2}" cy="-{radius * 0.22}" r="{radius * 0.34}" fill="{self.colors['highlight']}" opacity="0.16"/>
  <path d="M0 {-radius * 0.78} L{radius * 0.68} {-radius * 0.2} L{radius * 0.42} {radius * 0.62} L{-radius * 0.42} {radius * 0.62} L{-radius * 0.68} {-radius * 0.2} Z" fill="{self.colors['contrast_dark']}"/>
</g>
"""

    def _render_cone(self, sprite: Any) -> str:
        cx = _coord_x(float(sprite.x))
        cy = _coord_y(float(sprite.y))
        size = 19.0 * float(getattr(sprite, 'scale', 1.0) or 1.0)
        self.draw_calls.append({'kind': 'cone', 'sprite_id': sprite.sprite_id})
        return f"""
<g transform="translate({cx} {cy})" filter="url(#tokenShadow)">
  <ellipse cx="0" cy="{size * 0.62}" rx="{size * 0.72}" ry="{size * 0.24}" fill="{self.colors['contrast_dark']}" opacity="0.18"/>
  <path d="M0 {-size * 0.92} L{size * 0.70} {size * 0.68} L{-size * 0.70} {size * 0.68} Z" fill="{self.colors['cone']}"/>
  <path d="M0 {-size * 0.52} L{size * 0.44} {size * 0.48} L{-size * 0.44} {size * 0.48} Z" fill="{self.colors['accent_light']}" opacity="0.24"/>
  <rect x="-{size * 0.52}" y="{size * 0.54}" width="{size * 1.04}" height="{size * 0.18}" rx="{size * 0.09}" fill="{self.colors['contrast_dark']}" opacity="0.18"/>
</g>
"""

    def _render_pole(self, sprite: Any) -> str:
        cx = _coord_x(float(sprite.x))
        cy = _coord_y(float(sprite.y))
        width = max(8.0, float(getattr(sprite, 'width', 0.01) or 0.01) * _field_box()['width'])
        height = max(28.0, float(getattr(sprite, 'height', 0.06) or 0.06) * _field_box()['height'])
        self.draw_calls.append({'kind': 'pole', 'sprite_id': sprite.sprite_id})
        return f"""
<g transform="translate({cx} {cy}) rotate({float(getattr(sprite, 'rotation', 0.0) or 0.0)})" filter="url(#tokenShadow)">
  <rect x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}" rx="{width / 2}" fill="{self.colors['cone']}"/>
  <rect x="{-width / 3}" y="{-height / 2}" width="{width / 3}" height="{height}" rx="{width / 6}" fill="{self.colors['accent_light']}" opacity="0.28"/>
  <rect x="-{width * 0.62}" y="{height * 0.36}" width="{width * 1.24}" height="{height * 0.15}" rx="{width * 0.08}" fill="{self.colors['contrast_dark']}" opacity="0.18"/>
</g>
"""

    def _render_goal(self, sprite: Any) -> str:
        cx = _coord_x(float(sprite.x))
        cy = _coord_y(float(sprite.y))
        width = max(56.0, float(getattr(sprite, 'width', 0.12) or 0.12) * _field_box()['width'])
        height = max(18.0, float(getattr(sprite, 'height', 0.03) or 0.03) * _field_box()['height'])
        stroke_width = float(self.goal_theme.get('stroke_width') or 3.4)
        self.draw_calls.append({'kind': 'goal', 'sprite_id': sprite.sprite_id})
        return f"""
<g transform="translate({cx} {cy})" opacity="0.96">
  <rect x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}" rx="2" fill="none" stroke="{self.colors['goal']}" stroke-width="{stroke_width}"/>
  <rect x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}" rx="2" fill="url(#goalNet)" opacity="0.55"/>
  <rect x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}" rx="2" fill="none" stroke="{self.colors['accent_light']}" stroke-opacity="0.22" stroke-width="1.2"/>
</g>
"""

    def _render_arrow(self, sprite: Any) -> str:
        points = list(getattr(sprite, 'points', []) or [])
        if len(points) < 2:
            return ''
        start = points[0]
        end = points[-1]
        sx = _coord_x(float(start.get('x') or 0.0))
        sy = _coord_y(float(start.get('y') or 0.0))
        ex = _coord_x(float(end.get('x') or 0.0))
        ey = _coord_y(float(end.get('y') or 0.0))
        mx = (sx + ex) / 2.0
        my = (sy + ey) / 2.0
        curve_factor = float(self.arrow_theme.get('curve_factor') or 0.22)
        curvature = min(92.0, math.dist((sx, sy), (ex, ey)) * curve_factor)
        cx1 = (sx * 0.72) + (mx * 0.28)
        cy1 = sy - curvature
        cx2 = (ex * 0.72) + (mx * 0.28)
        cy2 = ey - curvature
        stroke_width = float(self.arrow_theme.get('stroke_width') or 3.4)
        glow_width = float(self.arrow_theme.get('glow_width') or max(stroke_width + 3.0, 7.8))
        self.draw_calls.append({'kind': 'arrow', 'sprite_id': sprite.sprite_id, 'action_type': getattr(sprite, 'action_type', '')})
        return f"""
<g filter="url(#arrowGlow)">
  <path d="M {sx:.2f} {sy:.2f} C {cx1:.2f} {cy1:.2f}, {cx2:.2f} {cy2:.2f}, {ex:.2f} {ey:.2f}" fill="none" stroke="{self.colors['accent_light']}" stroke-opacity="0.22" stroke-width="{glow_width}" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M {sx:.2f} {sy:.2f} C {cx1:.2f} {cy1:.2f}, {cx2:.2f} {cy2:.2f}, {ex:.2f} {ey:.2f}" fill="none" stroke="{self.colors['arrow']}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#arrowHead)"/>
</g>
"""

    def _render_zone(self, sprite: Any) -> str:
        points = list(getattr(sprite, 'points', []) or [])
        if len(points) < 3:
            return ''
        path_points = ' '.join(f'{_coord_x(float(point.get("x") or 0.0)):.2f},{_coord_y(float(point.get("y") or 0.0)):.2f}' for point in points)
        zone_color, zone_opacity = _parse_rgba(self.colors['zone'], 0.18)
        zone_stroke = float(self.zone_theme.get('stroke_width') or 2.4)
        zone_dash = str(self.zone_theme.get('dash') or '10 10')
        self.draw_calls.append({'kind': 'zone', 'sprite_id': sprite.sprite_id, 'zone_type': getattr(sprite, 'zone_type', '')})
        return f"""
<g>
  <polygon points="{path_points}" fill="url(#zoneGradient)" opacity="{zone_opacity + 0.08}" stroke="{zone_color}" stroke-width="{zone_stroke}" stroke-dasharray="{zone_dash}"/>
</g>
"""

    def _render_label(self, sprite: Any) -> str:
        cx = _coord_x(float(sprite.x))
        cy = _coord_y(float(sprite.y))
        text = str(getattr(sprite, 'text', '') or '').strip()
        if not text:
            return ''
        font_size = max(16.0, float(self.typography.get('label_size') or self.typography.get('size') or 12) * float(getattr(sprite, 'scale', 1.0) or 1.0))
        self.draw_calls.append({'kind': 'label', 'sprite_id': sprite.sprite_id})
        return f"""
<g transform="translate({cx} {cy})" filter="url(#{_shadow_filter_id()})">
  <rect x="-16" y="-{font_size * 0.92}" width="{max(126, len(text) * font_size * 0.64)}" height="{font_size * 1.5}" rx="14" fill="{self.colors['contrast_dark']}" opacity="0.78"/>
  <text x="0" y="0" fill="{self.colors['label']}" font-family="{_escape(self.typography.get('family') or 'system-ui')}" font-size="{font_size}" font-weight="{self.typography.get('weight') or 800}" dominant-baseline="middle">{_escape(text)}</text>
</g>
"""


def render_visualization_scene_to_svg(scene: VisualizationScene, theme: Dict[str, Any]) -> Dict[str, Any]:
    renderer = PremiumSVGRenderer(theme)
    return renderer.render(scene)


def build_premium_svg_debug_html(scene: VisualizationScene, theme: Dict[str, Any]) -> str:
    payload = render_visualization_scene_to_svg(scene, theme)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visualization Premium SVG Debug</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #08111d;
      color: #e5e7eb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: #0f172a;
      border: 1px solid rgba(148, 163, 184, .14);
      border-radius: 12px;
      padding: 12px;
    }}
    .stat small {{
      display: block;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 6px;
    }}
    .card {{
      background: #111827;
      border: 1px solid rgba(148, 163, 184, .14);
      border-radius: 16px;
      overflow: hidden;
      margin-bottom: 18px;
      box-shadow: 0 18px 42px rgba(0, 0, 0, .24);
    }}
    .card h2 {{
      margin: 0;
      padding: 14px 18px;
      font-size: 17px;
      background: #0f172a;
      border-bottom: 1px solid rgba(148, 163, 184, .14);
    }}
    .body {{ padding: 16px 18px; }}
    .svg-shell {{
      background: #020617;
      border-radius: 16px;
      overflow: auto;
      padding: 12px;
    }}
    svg {{ max-width: 100%; height: auto; display: block; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.45;
      color: #cbd5e1;
    }}
  </style>
</head>
<body>
  <div class="stats">
    <div class="stat"><small>Tiempo render</small><strong>{payload['render_time_ms']} ms</strong></div>
    <div class="stat"><small>Sprites</small><strong>{payload['sprite_count']}</strong></div>
    <div class="stat"><small>Draw calls</small><strong>{len(payload['draw_calls'])}</strong></div>
    <div class="stat"><small>Theme</small><strong>{_escape((payload['theme'] or {}).get('key') or '-')}</strong></div>
  </div>
  <section class="card">
    <h2>SVG generado</h2>
    <div class="body svg-shell">{payload['svg']}</div>
  </section>
  <section class="card">
    <h2>Draw calls</h2>
    <div class="body"><pre>{_escape(str(payload['draw_calls']))}</pre></div>
  </section>
  <section class="card">
    <h2>Theme utilizado</h2>
    <div class="body"><pre>{_escape(str(payload['theme']))}</pre></div>
  </section>
</body>
</html>"""


def write_premium_svg_debug_html(scene: VisualizationScene, theme: Dict[str, Any], out_path: str | Path) -> Path:
    target = Path(out_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_premium_svg_debug_html(scene, theme), encoding='utf-8')
    return target
