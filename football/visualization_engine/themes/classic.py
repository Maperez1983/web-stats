from __future__ import annotations

from typing import Any, Dict


def get_theme() -> Dict[str, Any]:
    return {
        'key': 'classic',
        'colors': {
            'background': '#0f172a',
            'field_base': '#8fbc4b',
            'field_line': '#ffffff',
            'shadow': 'rgba(15, 23, 42, 0.24)',
            'player_home': '#2563eb',
            'player_away': '#ef4444',
            'goalkeeper': '#f59e0b',
            'ball': '#ffffff',
            'cone': '#facc15',
            'goal': '#94a3b8',
            'arrow': '#ffffff',
            'zone': 'rgba(59, 130, 246, 0.22)',
            'label': '#e5e7eb',
        },
        'grass': {'style': 'classic_stripes', 'stripe_opacity': 0.18},
        'lines': {'width': 2.0, 'opacity': 1.0},
        'shadows': {'enabled': True, 'blur': 10, 'opacity': 0.22},
        'iconography': {'player_shape': 'circle', 'cone_shape': 'triangle'},
        'typography': {'family': 'system-ui', 'size': 12, 'weight': 700},
        'arrows': {'stroke_width': 3.0, 'head_size': 10.0},
    }
