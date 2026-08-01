import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/Volumes/Mac Satecchi/Mac/Downloads/football_soccer_players_animated_rigged_gltf/scene.gltf")
print('frame_start', bpy.context.scene.frame_start, 'frame_end', bpy.context.scene.frame_end)
for a in bpy.data.actions:
    print('action', a.name, a.frame_range[:])
