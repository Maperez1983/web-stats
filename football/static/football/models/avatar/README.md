# Task Player Humanoid

`player_humanoid.glb` is based on the CC0 `hm08` basemesh included with MPFB
(MakeHuman Plugin For Blender), with procedural football training kit geometry
generated in-repo.

- Source mesh: `~/Library/Application Support/Blender/5.1/extensions/user_default/mpfb/data/3dobjs/base.obj`
- Source mesh license: CC0, MakeHuman Community / Data Collection AB
- Refresh script: `node scripts/build_task_player_mpfb_avatar.mjs`
- Preview script: `node scripts/capture_task_player_avatar_preview.mjs`

The tactical task 3D view recolors and scales this model at runtime.

## Premium replacement

For a production-quality footballer model, use a legally licensed `.glb` and configure one of:

- `TASK_PLAYER_MODEL_URL`: absolute URL to a CORS-enabled `.glb`.
- `TASK_PLAYER_MODEL_STATIC_PATH`: static path inside Django static files, for example `football/models/avatar/player_premium.glb`.

If neither is configured, the app falls back to `player_humanoid.glb`.
