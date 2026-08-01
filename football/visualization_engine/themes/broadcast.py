from __future__ import annotations

from typing import Any, Dict


def get_theme() -> Dict[str, Any]:
    return {
        'key': 'broadcast',
        'colors': {
            'background': '#0b1220',
            'field_base': '#3f9a5f',
            'field_line': '#ffffff',
            'shadow': 'rgba(0, 0, 0, 0.24)',
            'player_home': '#2563eb',
            'player_away': '#ef4444',
            'goalkeeper': '#f59e0b',
            'ball': '#ffffff',
            'cone': '#facc15',
            'goal': '#cbd5e1',
            'arrow': '#e5e7eb',
            'zone': 'rgba(250, 204, 21, 0.18)',
            'label': '#f8fafc',
        },
        'grass': {'style': 'broadcast_premium', 'stripe_opacity': 0.16},
        'lines': {'width': 2.0, 'opacity': 1.0},
        'shadows': {'enabled': True, 'blur': 12, 'opacity': 0.24},
        'iconography': {'player_shape': 'broadcast_token', 'cone_shape': 'triangle'},
        'typography': {'family': 'system-ui', 'size': 12, 'weight': 700},
        'arrows': {'stroke_width': 3.2, 'head_size': 10.5},
    }
