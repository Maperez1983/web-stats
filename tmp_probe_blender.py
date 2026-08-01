import bpy
import sys
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/Volumes/Mac Satecchi/Mac/Downloads/football_soccer_players_animated_rigged_gltf/scene.gltf")
print("OBJECTS")
for obj in bpy.data.objects:
    print(obj.name, obj.type, tuple(round(v,3) for v in obj.location), obj.parent.name if obj.parent else None)
print("ACTIONS", [a.name for a in bpy.data.actions])
