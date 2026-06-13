# Task Player Humanoid

`player_humanoid.glb` is based on Quaternius' Universal Base Characters
`Superhero_Male_FullBody` model, converted into a task-footballer avatar with
embedded kit materials and a neutral ready pose.

- Source pack: Universal Base Characters by Quaternius
- Source license: CC0
- Source file: `~/Downloads/Universal_Base_Characters_Standard_extracted/Universal Base Characters[Standard]/Base Characters/Godot - UE/Superhero_Male_FullBody.gltf`
- Refresh script: `Blender -b --gpu-backend opengl --python scripts/build_task_player_quaternius_footballer.py`
- Preview script: `node scripts/capture_task_player_avatar_preview.mjs`

The tactical task 3D view scales this model at runtime and can still tint kit
materials from team colors. If the embedded `footballer_*` materials are present,
the runtime skips the older procedural clothing overlay.

## Premium replacement

For a higher-end photoreal footballer model, use a legally licensed `.glb` and configure one of:

- `TASK_PLAYER_MODEL_URL`: absolute URL to a CORS-enabled `.glb`.
- `TASK_PLAYER_MODEL_STATIC_PATH`: static path inside Django static files, for example `football/models/avatar/player_premium.glb`.

If neither is configured, the app falls back to `player_humanoid.glb`.
