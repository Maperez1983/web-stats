#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/football/static/football/materials/pitch3d/ambientcg"
TMP="${TMPDIR:-/tmp}/pitch3d_ambientcg_materials"
QUALITY="${1:-1K-JPG}"

ASSETS=(
  "Grass005:short clean stadium-style grass"
  "Grass001:dense natural grass variation"
  "Concrete048:stadium concrete tiers and vomitories"
  "Concrete034:secondary concrete variation"
  "Metal049A:clean structural metal"
  "CorrugatedSteel009:ribbed roof and cladding metal"
  "Road012A:dark service pavement around the pitch"
  "Plastic013A:seat plastic roughness/detail source"
  "Fabric082A:fine woven fabric for netting and banners"
)

mkdir -p "$DEST" "$TMP"

for asset in "${ASSETS[@]}"; do
  id="${asset%%:*}"
  zip="$TMP/${id}_${QUALITY}.zip"
  target="$DEST/$id"

  mkdir -p "$target"
  if find "$target" -type f -name "${id}_${QUALITY}_*.jpg" | grep -q .; then
    echo "skip $id already extracted"
    continue
  fi

  echo "download $id"
  curl -fL --retry 3 --retry-delay 2 \
    "https://ambientcg.com/get?file=${id}_${QUALITY}.zip" \
    -o "$zip"
  unzip -oq "$zip" -d "$target"
done

echo "done $DEST"
