# Pitch 3D Stadium Material Library

Curated PBR material set downloaded from ambientCG for the professional stadium
modeling workflow. ambientCG assets are distributed under CC0 1.0 Universal.

Source license: https://ambientcg.com/license

Downloaded quality: `1K-JPG`

## Assets

| Asset | Source | Intended use |
| --- | --- | --- |
| Grass005 | https://ambientcg.com/a/Grass005 | Short premium pitch grass reference and texture source |
| Grass001 | https://ambientcg.com/a/Grass001 | Dense natural grass variation |
| Concrete048 | https://ambientcg.com/a/Concrete048 | Main stadium concrete, tiers, podiums, vomitories |
| Concrete034 | https://ambientcg.com/a/Concrete034 | Secondary concrete variation for concourses and walls |
| Metal049A | https://ambientcg.com/a/Metal049A | Clean structural steel and rail details |
| CorrugatedSteel009 | https://ambientcg.com/a/CorrugatedSteel009 | Roof panels, cladding, ribbed metal surfaces |
| Road012A | https://ambientcg.com/a/Road012A | Dark service pavement and perimeter walkways |
| Plastic013A | https://ambientcg.com/a/Plastic013A | Seat plastic roughness and normal detail source |
| Fabric082A | https://ambientcg.com/a/Fabric082A | Woven fabric detail for nets, banners, and mesh surfaces |

## Integration Notes

- `scripts/download_pitch3d_materials.sh` can refresh this set from ambientCG.
- `scripts/build_pitch3d_stadium_bowl.py` currently embeds concrete and metal PBR
  maps into the generated GLB while preserving team-color materials for seats,
  fascia, roof accents, and badge placeholders.
- Keep web delivery in mind before increasing beyond 1K texture packs.
