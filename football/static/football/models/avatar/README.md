# Task Player Humanoid

`player_humanoid.glb` currently uses the Three.js `Xbot.glb` humanoid base as a
stable mocap-ready task avatar. The source rig keeps its embedded `idle`, `walk`
and `run` clips, which are used by the tactical 3D task view for avatar motion.

- Source file: `~/Downloads/Xbot_threejs.glb`
- Refresh script: `Blender -b --python scripts/build_task_player_mocap_xbot_avatar.py`
- Preview script: `node scripts/capture_task_player_avatar_preview.mjs`

The tactical task 3D view scales this model at runtime and can tint its skin-like
materials. A `footballer_*` material marker is kept so the runtime does not add
the older rigid procedural clothing overlay on top of the animated mesh.

This is an interim mocap-stable mannequin, not a final photoreal footballer. For
high-end action recreation, replace it with a licensed footballer GLB using a
compatible humanoid rig and football-specific clips.

## Premium replacement

For a higher-end photoreal footballer model, use a legally licensed `.glb` and configure one of:

- `TASK_PLAYER_MODEL_URL`: absolute URL to a CORS-enabled `.glb`.
- `TASK_PLAYER_MODEL_STATIC_PATH`: static path inside Django static files, for example `football/models/avatar/player_premium.glb`.

If neither is configured, the app falls back to `player_humanoid.glb`.
