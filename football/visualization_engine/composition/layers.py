from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CompositionLayer:
    name: str
    z_index: int
    items: List[Dict[str, Any]] = field(default_factory=list)
    visibility: bool = True
    opacity: float = 1.0

    def add_item(self, item: Dict[str, Any]) -> None:
        self.items.append(item)

    def as_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'z_index': self.z_index,
            'visibility': self.visibility,
            'opacity': self.opacity,
            'item_count': len(self.items),
            'items': [dict(item) for item in self.items],
        }
