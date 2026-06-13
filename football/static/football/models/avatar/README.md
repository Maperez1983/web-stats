# Task Player Humanoid

`player_humanoid.glb` is based on `Xbot.glb` from the official Three.js examples repository.

- Source: https://github.com/mrdoob/three.js/blob/dev/examples/models/gltf/Xbot.glb
- License: MIT, Three.js authors
- Refresh script: `node scripts/build_task_player_humanoid_glb.mjs`

The tactical task 3D view recolors and scales this model at runtime.

## Premium replacement

For a production-quality footballer model, use a legally licensed `.glb` and configure one of:

- `TASK_PLAYER_MODEL_URL`: absolute URL to a CORS-enabled `.glb`.
- `TASK_PLAYER_MODEL_STATIC_PATH`: static path inside Django static files, for example `football/models/avatar/player_premium.glb`.

If neither is configured, the app falls back to `player_humanoid.glb`.
