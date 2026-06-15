# Task Player Humanoid

`player_humanoid.glb` uses the Universal Base Characters male footballer mesh as
the default human task avatar. It keeps a 65-bone humanoid rig and embeds named
football clips used by the tactical 3D task view for avatar motion.

- Source file: `~/Downloads/Universal_Base_Characters_Standard_extracted/Universal Base Characters[Standard]/Base Characters/Godot - UE/Superhero_Male_FullBody.gltf`
- Refresh script: `Blender -b --python scripts/build_task_player_quaternius_footballer.py`
- Preview script: `node scripts/capture_task_player_avatar_preview.mjs`
- Embedded clips: `idle`, `run`, `pass`, `cross`, `shot`, `press`, `control`
- Optional mocap source: set `TASK_PLAYER_MOCAP_SOURCE=/path/to/actions.glb` before
  running the refresh script to append compatible external action clips.

The tactical task 3D view scales this model at runtime and can tint its skin-like
materials. A `footballer_*` material marker is kept so the runtime does not add
the older rigid procedural clothing overlay on top of the animated mesh.

The tactical 3D view also adds contextual ball cues for pass, cross, shot,
control and carry actions. The bundled clips are procedural first-pass actions,
not final mocap. For high-end action recreation, retarget licensed mocap
football clips onto this rig or replace it with a licensed footballer GLB using
a compatible humanoid rig.

## Premium replacement

For a higher-end photoreal footballer model, use a legally licensed `.glb` and configure one of:

- `TASK_PLAYER_MODEL_URL`: absolute URL to a CORS-enabled `.glb`.
- `TASK_PLAYER_MODEL_STATIC_PATH`: static path inside Django static files, for example `football/models/avatar/player_premium.glb`.

If neither is configured, the app falls back to `player_humanoid.glb`.
