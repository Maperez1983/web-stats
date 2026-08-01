# Stadium Model Audit

Date: 2026-06-30

## Goal

Find a realistic football stadium base that is:

- reusable in the web 3D viewer
- legally safe to ship
- light enough to be adapted for browser rendering

## Current usable candidates

### 1. Estadio Unico Madre de Ciudades

- Local path:
  - `Downloads/estadio-unico-madre-de-ciudades/estadio_unico_madre_de_ciudades.glb`
- Source:
  - https://sketchfab.com/3d-models/estadio-unico-madre-de-ciudades-35ff110e81ea45dfb5294803dd13c3da
- Author:
  - A1905
- License:
  - CC-BY-4.0
- Status:
  - Best legal base found so far
- Notes:
  - Loads in the task detail 3D viewer
  - Contains separate materials and textures for stadium, seats, fences and field
  - Needs scene filtering and re-normalization because the raw hierarchy is too large/noisy for direct web use

### 2. Dragon Stadium

- Local path:
  - `Downloads/Nueva carpeta con ítems 2/dragon_stadium.glb`
- Source:
  - https://sketchfab.com/3d-models/dragon-stadium-58f5045de95c43c4a7dfdc9679bfb549
- Author:
  - Razny
- License:
  - Sketchfab Standard
- Status:
  - Reference only
- Notes:
  - Very heavy
  - Not the right legal base for direct product integration

## Other local sources checked

### Stad de tanger.blend

- Local path:
  - `Downloads/Stad de tanger.blend`
- Status:
  - Not currently usable in this environment
- Notes:
  - Blender crashes when opened headless on this machine

### FM26 3D Stadium Megapack

- Local path:
  - `Downloads/FM26 3D Stadium Megapack Version 3.0 - The Total Rebirth`
- Status:
  - Reference library only
- Notes:
  - Huge pack
  - Not web-ready
  - Does not expose simple `.glb` / `.gltf` stadium files ready to drop into the current browser viewer

## Technical decision

The correct base for the product right now is:

- `estadio_unico_madre_de_ciudades.glb` as the legal geometry source

The correct engineering approach is:

1. Keep the current browser field and goals.
2. Reuse only the useful stadium subgraph from the CC-BY model.
3. Strip or hide noisy world geometry that breaks scaling and framing.
4. Rebuild corner stands, roof transitions and seating density on top of that cleaned base.

## Why not keep searching blindly

Search engines and asset marketplaces are heavily challenge-protected in this environment. That makes automated exhaustive search unreliable.

The best practical workflow is:

1. Use the open-license stadium already identified.
2. Keep closed-license or challenge-protected models only as visual references.
3. Continue targeted search only when a source is clearly better than the current CC-BY base.

## Next recommended step

Clean and isolate the `Estadio Unico Madre de Ciudades` model hierarchy inside the viewer loader, then re-test screenshots from the real task detail 3D card.
