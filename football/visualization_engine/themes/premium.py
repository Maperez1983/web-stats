from __future__ import annotations

from typing import Any, Dict


def get_theme() -> Dict[str, Any]:
    return {
        'key': 'premium',
        'colors': {
            'background': '#06111d',
            'field_base': '#2f8a57',
            'field_line': '#f6fbff',
            'shadow': 'rgba(3, 10, 18, 0.34)',
            'player_home': '#1f8fff',
            'player_away': '#ff7d3b',
            'goalkeeper': '#f5c84c',
            'ball': '#ffffff',
            'cone': '#ff8a4c',
            'goal': '#dce7f2',
            'arrow': '#f4fbff',
            'zone': 'rgba(183, 255, 94, 0.2)',
            'label': '#f8fbff',
            'panel': '#0b1725',
            'frame_outer': '#dfe7f2',
            'frame_inner': '#94a9bc',
            'highlight': '#ffffff',
            'grass_dark': '#256945',
            'grass_light': '#56b777',
            'grass_mid': '#3f9960',
            'arrow_glow': 'rgba(255,255,255,0.22)',
            'token_ring': '#eef6ff',
            'token_shadow': 'rgba(0,0,0,0.28)',
            'goal_net': '#f4f8fc',
        },
        'grass': {
            'style': 'premium_broadcast',
            'stripe_opacity': 0.16,
            'noise_opacity': 0.28,
            'glow_opacity': 0.13,
            'bands': 11,
        },
        'lines': {'width': 2.2, 'opacity': 0.99, 'secondary_opacity': 0.24},
        'shadows': {'enabled': True, 'blur': 16, 'opacity': 0.32, 'field_blur': 24},
        'iconography': {'player_shape': 'token', 'cone_shape': 'disc'},
        'typography': {'family': 'system-ui', 'size': 12, 'weight': 800, 'label_size': 15},
        'arrows': {'stroke_width': 4.2, 'head_size': 16.0, 'glow_width': 7.8, 'curve_factor': 0.22},
        'players': {'radius': 22, 'ring': 4, 'shadow_y': 10, 'orientation_width': 4.6},
        'field_frame': {'outer_radius': 42, 'inner_radius': 34, 'panel_padding': 18},
        'goals': {'stroke_width': 3.4, 'net_opacity': 0.64},
        'zones': {'stroke_width': 2.4, 'dash': '10 10'},
    }
