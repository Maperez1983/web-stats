from __future__ import annotations
import bpy
from mathutils import Vector
from pathlib import Path

ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
SRC = Path("/Volumes/Mac Satecchi/Mac/Downloads/football_soccer_players_animated_rigged_gltf/scene.gltf")
OUT = ROOT / "tmp" / "player_men_sheet"
OUT.mkdir(parents=True, exist_ok=True)

def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

def world_bbox(objects):
    mins = Vector((1e9,1e9,1e9))
    maxs = Vector((-1e9,-1e9,-1e9))
    for obj in objects:
        if obj.type != 'MESH':
            continue
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            mins.x=min(mins.x,w.x); mins.y=min(mins.y,w.y); mins.z=min(mins.z,w.z)
            maxs.x=max(maxs.x,w.x); maxs.y=max(maxs.y,w.y); maxs.z=max(maxs.z,w.z)
    return mins, maxs

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SRC))
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE'
scene.render.film_transparent=True
scene.render.image_settings.file_format='PNG'
scene.render.resolution_x=768
scene.render.resolution_y=768

triples=[('Metarig Man.010_44','GLTF_created_0','Object_6','man_a'),('Metarig Man.011_89','GLTF_created_1','Object_53','man_b'),('Metarig Man.012_134','GLTF_created_2','Object_100','man_c')]
cam_data=bpy.data.cameras.new('Cam'); cam_data.lens=52
cam=bpy.data.objects.new('Cam',cam_data); bpy.context.collection.objects.link(cam); scene.camera=cam
light=bpy.data.lights.new(name='Key', type='AREA'); light.energy=4500; light.shape='RECTANGLE'; light.size=5; light.size_y=5
light_obj=bpy.data.objects.new(name='Key', object_data=light); bpy.context.collection.objects.link(light_obj); light_obj.location=(3.8,-5,5.6); look_at(light_obj, Vector((0,0,1)))
fill=bpy.data.lights.new(name='Fill', type='AREA'); fill.energy=1900; fill.shape='RECTANGLE'; fill.size=6; fill.size_y=6
fill_obj=bpy.data.objects.new(name='Fill', object_data=fill); bpy.context.collection.objects.link(fill_obj); fill_obj.location=(-3,-3.8,3.8); look_at(fill_obj, Vector((0,0,1.1)))
for root_name,arm_name,mesh_name,label in triples:
    for obj in bpy.data.objects:
        obj.hide_render=True; obj.hide_viewport=True
    root=bpy.data.objects[root_name]; arm=bpy.data.objects[arm_name]; mesh=bpy.data.objects[mesh_name]
    for obj in (root,arm,mesh,cam,light_obj,fill_obj):
        obj.hide_render=False; obj.hide_viewport=False
    root.location=(0,0,0)
    scene.frame_set(45)
    mins,maxs=world_bbox([mesh]); center=(mins+maxs)/2.0; h=maxs.z-mins.z
    cam.location=Vector((center.x+0.05, center.y-6.0, center.z+h*0.56)); look_at(cam, center+Vector((0,0,h*0.1)))
    scene.render.filepath=str(OUT/f'{label}.png')
    bpy.ops.render.render(write_still=True)
print(str(OUT))
