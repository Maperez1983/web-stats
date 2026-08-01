from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .manifest import AssetDescriptor, AssetManifest


class AssetRegistry:
    def __init__(self) -> None:
        self._manifests: Dict[str, AssetManifest] = {}

    def ensure_manifest(self, theme_key: str) -> AssetManifest:
        if theme_key not in self._manifests:
            self._manifests[theme_key] = AssetManifest(theme_key=theme_key)
        return self._manifests[theme_key]

    def register(self, theme_key: str, descriptor: AssetDescriptor) -> None:
        self.ensure_manifest(theme_key).register(descriptor)

    def manifest_for(self, theme_key: str) -> AssetManifest:
        return self.ensure_manifest(theme_key)

    def all_manifests(self) -> Iterable[AssetManifest]:
        return self._manifests.values()

    def find(self, theme_key: str, asset_id: str) -> Optional[AssetDescriptor]:
        manifest = self._manifests.get(theme_key)
        if manifest:
            descriptor = manifest.find(asset_id)
            if descriptor:
                return descriptor
        for fallback_theme in self._theme_fallback_chain(theme_key):
            fallback_manifest = self._manifests.get(fallback_theme)
            if fallback_manifest:
                descriptor = fallback_manifest.find(asset_id)
                if descriptor:
                    return descriptor
        return None

    def find_variant(
        self,
        theme_key: str,
        asset_id: str,
        *,
        variant: str = 'default',
    ) -> Optional[str]:
        descriptor = self.find(theme_key, asset_id)
        if not descriptor:
            return None
        requested_variant = str(variant or 'default')
        override_map = descriptor.theme_overrides.get(theme_key) if isinstance(descriptor.theme_overrides, dict) else None
        if isinstance(override_map, dict):
            themed_variant = override_map.get(requested_variant) or override_map.get('default')
            if themed_variant:
                return str(themed_variant)
        if requested_variant == descriptor.variant and descriptor.source:
            return descriptor.source
        if requested_variant in descriptor.variants:
            return str(descriptor.variants[requested_variant])
        if descriptor.source:
            return descriptor.source
        if descriptor.fallback_asset_id and descriptor.fallback_asset_id != descriptor.asset_id:
            return self.find_variant(theme_key, descriptor.fallback_asset_id, variant=requested_variant)
        return None

    def family_assets(self, theme_key: str, family: str) -> Iterable[AssetDescriptor]:
        manifest = self.ensure_manifest(theme_key)
        assets = manifest.family_assets(family)
        if assets:
            return assets
        for fallback_theme in self._theme_fallback_chain(theme_key):
            fallback_manifest = self._manifests.get(fallback_theme)
            if fallback_manifest:
                fallback_assets = fallback_manifest.family_assets(family)
                if fallback_assets:
                    return fallback_assets
        return []

    def manifest_summary(self) -> Dict[str, Any]:
        return {
            manifest.theme_key: manifest.as_dict()
            for manifest in self.all_manifests()
        }

    def _theme_fallback_chain(self, theme_key: str) -> Iterable[str]:
        normalized = str(theme_key or '').strip().lower()
        fallback_order = {
            'premium': ['broadcast', 'classic'],
            'broadcast': ['classic'],
            'academy': ['broadcast', 'classic'],
            'classic': [],
        }
        return fallback_order.get(normalized, ['broadcast', 'classic'])
