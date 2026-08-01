from __future__ import annotations

from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
SRC = Path("/Volumes/Mac Satecchi/Mac/Downloads/football_soccer_players_animated_rigged_gltf/scene.gltf")
OUT = ROOT / "tmp" / "player_final_hd.png"
RENDER_SIZE = 2048


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def world_bbox(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            mins.x = min(mins.x, w.x)
            mins.y = min(mins.y, w.y)
            mins.z = min(mins.z, w.z)
            maxs.x = max(maxs.x, w.x)
            maxs.y = max(maxs.y, w.y)
            maxs.z = max(maxs.z, w.z)
    return mins, maxs


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SRC))

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = RENDER_SIZE
scene.render.resolution_y = RENDER_SIZE
scene.render.resolution_percentage = 100
scene.eevee.taa_render_samples = 64

root = bpy.data.objects["Metarig Man.011_89"]
arm = bpy.data.objects["GLTF_created_1"]
mesh = bpy.data.objects["Object_53"]

for obj in bpy.data.objects:
    obj.hide_render = True
    obj.hide_viewport = True
for obj in (root, arm, mesh):
    obj.hide_render = False
    obj.hide_viewport = False

root.location = (0.0, 0.0, 0.0)
scene.frame_set(45)

cam_data = bpy.data.cameras.new("SpriteCamFinal")
cam_data.lens = 65
cam_obj = bpy.data.objects.new("SpriteCamFinal", cam_data)
bpy.context.collection.objects.link(cam_obj)
scene.camera = cam_obj

key_light = bpy.data.lights.new(name="KeyLight", type="AREA")
key_light.energy = 6200
key_light.shape = "RECTANGLE"
key_light.size = 5.0
key_light.size_y = 5.0
key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_light)
bpy.context.collection.objects.link(key_obj)

fill_light = bpy.data.lights.new(name="FillLight", type="AREA")
fill_light.energy = 2600
fill_light.shape = "RECTANGLE"
fill_light.size = 6.5
fill_light.size_y = 6.5
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_light)
bpy.context.collection.objects.link(fill_obj)

rim_light = bpy.data.lights.new(name="RimLight", type="AREA")
rim_light.energy = 2000
rim_light.shape = "RECTANGLE"
rim_light.size = 4.0
rim_light.size_y = 4.0
rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_light)
bpy.context.collection.objects.link(rim_obj)

mins, maxs = world_bbox([mesh])
center = (mins + maxs) / 2.0
height = maxs.z - mins.z

cam_obj.location = Vector((center.x + 0.12, center.y - 4.6, center.z + height * 0.60))
look_at(cam_obj, center + Vector((0.0, 0.0, height * 0.10)))

key_obj.location = Vector((center.x + 2.4, center.y - 3.2, center.z + height * 1.40))
look_at(key_obj, center + Vector((0.0, 0.0, height * 0.56)))

fill_obj.location = Vector((center.x - 2.2, center.y - 2.6, center.z + height * 1.15))
look_at(fill_obj, center + Vector((0.0, 0.0, height * 0.46)))

rim_obj.location = Vector((center.x, center.y + 3.6, center.z + height * 1.25))
look_at(rim_obj, center + Vector((0.0, 0.0, height * 0.80)))

scene.render.filepath = str(OUT)
bpy.ops.render.render(write_still=True)
print(str(OUT))
