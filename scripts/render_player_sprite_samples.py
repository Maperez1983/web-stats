from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
SRC = Path("/Volumes/Mac Satecchi/Mac/Downloads/football_soccer_players_animated_rigged_gltf/scene.gltf")
OUT = ROOT / "tmp" / "player_sprite_samples"
OUT.mkdir(parents=True, exist_ok=True)

FRAMES = [1, 15, 30, 45, 60, 75, 90]
RENDER_SIZE = 768


def look_at(camera_obj: bpy.types.Object, target: Vector) -> None:
    direction = target - camera_obj.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    camera_obj.rotation_euler = rot_quat.to_euler()


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

for area in bpy.data.worlds:
    if area.node_tree:
        bg = area.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
            bg.inputs[1].default_value = 0.25

target_empty = bpy.data.objects.get("Metarig Man.010_44")
armature = bpy.data.objects.get("GLTF_created_0")
mesh = bpy.data.objects.get("Object_6")

if not target_empty or not armature or not mesh:
    raise RuntimeError("No se encontró el jugador base esperado")

for obj in bpy.data.objects:
    obj.hide_render = True
    obj.hide_viewport = True

for obj in (target_empty, armature, mesh):
    obj.hide_render = False
    obj.hide_viewport = False

target_empty.location = (0.0, 0.0, 0.0)

cam_data = bpy.data.cameras.new("SpriteCam")
cam_data.lens = 52
cam_obj = bpy.data.objects.new("SpriteCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
scene.camera = cam_obj

key_light = bpy.data.lights.new(name="KeyLight", type="AREA")
key_light.energy = 4500
key_light.shape = "RECTANGLE"
key_light.size = 5
key_light.size_y = 5
key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_light)
bpy.context.collection.objects.link(key_obj)
key_obj.location = (3.8, -5.0, 5.6)
look_at(key_obj, Vector((0.0, 0.0, 1.0)))

fill_light = bpy.data.lights.new(name="FillLight", type="AREA")
fill_light.energy = 1900
fill_light.shape = "RECTANGLE"
fill_light.size = 6
fill_light.size_y = 6
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_light)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = (-3.0, -3.8, 3.8)
look_at(fill_obj, Vector((0.0, 0.0, 1.1)))

rim_light = bpy.data.lights.new(name="RimLight", type="AREA")
rim_light.energy = 1200
rim_light.shape = "RECTANGLE"
rim_light.size = 4
rim_light.size_y = 4
rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_light)
bpy.context.collection.objects.link(rim_obj)
rim_obj.location = (0.0, 4.2, 4.8)
look_at(rim_obj, Vector((0.0, 0.0, 1.4)))

for frame in FRAMES:
    scene.frame_set(frame)
    mins, maxs = world_bbox([mesh])
    center = (mins + maxs) / 2.0
    height = maxs.z - mins.z
    cam_obj.location = Vector((center.x + 0.05, center.y - 6.0, center.z + height * 0.56))
    look_at(cam_obj, center + Vector((0.0, 0.0, height * 0.1)))
    scene.render.filepath = str(OUT / f"player_frame_{frame:03d}.png")
    bpy.ops.render.render(write_still=True)

print(str(OUT))
