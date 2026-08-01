from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class AssetDescriptor:
    asset_id: str
    asset_type: str
    family: str = ''
    variant: str = 'default'
    source: str = ''
    variants: Dict[str, str] = field(default_factory=dict)
    theme_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    fallback_asset_id: str = ''
    resolution_independent: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetManifest:
    theme_key: str
    assets: List[AssetDescriptor] = field(default_factory=list)
    families: Dict[str, List[str]] = field(default_factory=dict)
    fallbacks: Dict[str, str] = field(default_factory=dict)
    compatible_themes: List[str] = field(default_factory=list)

    def register(self, descriptor: AssetDescriptor) -> None:
        self.assets = [asset for asset in self.assets if asset.asset_id != descriptor.asset_id]
        self.assets.append(descriptor)
        family = str(descriptor.family or descriptor.asset_type or 'default')
        family_assets = self.families.setdefault(family, [])
        if descriptor.asset_id not in family_assets:
            family_assets.append(descriptor.asset_id)
        if descriptor.fallback_asset_id:
            self.fallbacks[descriptor.asset_id] = descriptor.fallback_asset_id
        if self.theme_key not in self.compatible_themes:
            self.compatible_themes.append(self.theme_key)

    def find(self, asset_id: str) -> AssetDescriptor | None:
        for descriptor in self.assets:
            if descriptor.asset_id == asset_id:
                return descriptor
        return None

    def family_assets(self, family: str) -> List[AssetDescriptor]:
        asset_ids = self.families.get(str(family or ''), [])
        return [descriptor for descriptor in self.assets if descriptor.asset_id in asset_ids]

    def as_dict(self) -> Dict[str, Any]:
        return {
            'theme_key': self.theme_key,
            'families': {key: list(value) for key, value in self.families.items()},
            'fallbacks': dict(self.fallbacks),
            'compatible_themes': list(self.compatible_themes),
            'assets': [
                {
                    'asset_id': descriptor.asset_id,
                    'asset_type': descriptor.asset_type,
                    'family': descriptor.family,
                    'variant': descriptor.variant,
                    'source': descriptor.source,
                    'variants': dict(descriptor.variants),
                    'theme_overrides': dict(descriptor.theme_overrides),
                    'fallback_asset_id': descriptor.fallback_asset_id,
                    'resolution_independent': bool(descriptor.resolution_independent),
                    'metadata': dict(descriptor.metadata),
                }
                for descriptor in self.assets
            ],
        }
