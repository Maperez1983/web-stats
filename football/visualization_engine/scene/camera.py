from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Camera:
    mode: str
    zoom: float = 1.0
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    x: float = 0.5
    y: float = 0.5
    z: float = 1.0

    def as_dict(self) -> Dict[str, float | str]:
        return {
            'mode': self.mode,
            'zoom': self.zoom,
            'pitch': self.pitch,
            'yaw': self.yaw,
            'roll': self.roll,
            'x': self.x,
            'y': self.y,
            'z': self.z,
        }


def top_down_camera() -> Camera:
    return Camera(mode='top2d', zoom=1.0, pitch=90.0, z=1.0)


def perspective_camera() -> Camera:
    return Camera(mode='perspective3d', zoom=1.0, pitch=58.0, z=1.25)
