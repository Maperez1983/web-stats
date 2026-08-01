from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class LightSource:
    name: str
    kind: str
    intensity: float
    color: str = '#ffffff'
    direction: Dict[str, float] = field(default_factory=dict)
    position: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'kind': self.kind,
            'intensity': self.intensity,
            'color': self.color,
            'direction': dict(self.direction or {}),
            'position': dict(self.position or {}),
        }


@dataclass(frozen=True)
class LightingRig:
    mode: str
    ambient: float = 0.55
    shadows_enabled: bool = True
    lights: List[LightSource] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode,
            'ambient': self.ambient,
            'shadows_enabled': self.shadows_enabled,
            'lights': [light.as_dict() for light in self.lights],
        }


def stadium_lighting() -> LightingRig:
    return LightingRig(
        mode='stadium',
        ambient=0.58,
        shadows_enabled=True,
        lights=[
            LightSource(
                name='key',
                kind='directional',
                intensity=1.0,
                direction={'x': -0.28, 'y': -0.72, 'z': -0.62},
            ),
            LightSource(
                name='fill',
                kind='directional',
                intensity=0.48,
                direction={'x': 0.34, 'y': -0.18, 'z': -0.42},
            ),
            LightSource(
                name='rim',
                kind='directional',
                intensity=0.25,
                direction={'x': 0.0, 'y': 0.82, 'z': -0.24},
            ),
        ],
    )
