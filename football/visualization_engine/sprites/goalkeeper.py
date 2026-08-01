from __future__ import annotations

from dataclasses import dataclass

from .player import PlayerSprite


@dataclass
class GoalkeeperSprite(PlayerSprite):
    semantic_role: str = 'goalkeeper'
    role: str = 'goalkeeper'
    z_index: int = 41
