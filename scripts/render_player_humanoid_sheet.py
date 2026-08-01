import bpy
import math
import os
from mathutils import Vector


MODEL_PATH = "/Volumes/Mac Satecchi/Mac/Web-stats/football/static/football/models/avatar/player_humanoid.glb"
OUT_DIR = "/Volumes/Mac Satecchi/Mac/Downloads/player_sheet"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_name in ("meshes", "materials", "images", "lights", "cameras", "worlds"):
        block = getattr(bpy.data, block_name)
        for item in list(block):
            try:
                block.remove(item)
            except Exception:
                pass


def setup_world():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.film_transparent = True
    scene.eevee.taa_render_samples = 64
    world = bpy.data.worlds.new("SheetWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[1].default_value = 0.0


def setup_lights():
    bpy.ops.object.light_add(type="AREA", location=(3.6, -4.8, 5.6))
    key = bpy.context.active_object
    key.data.energy = 4500
    key.data.shape = "RECTANGLE"
    key.data.size = 5.4
    key.data.size_y = 5.4
    key.rotation_euler = (math.radians(54), 0, math.radians(34))

    bpy.ops.object.light_add(type="AREA", location=(-4.2, 2.6, 3.4))
    fill = bpy.context.active_object
    fill.data.energy = 1800
    fill.data.shape = "RECTANGLE"
    fill.data.size = 4.8
    fill.data.size_y = 4.8
    fill.rotation_euler = (math.radians(65), 0, math.radians(-128))

    bpy.ops.object.light_add(type="SUN", location=(0, 0, 6))
    sun = bpy.context.active_object
    sun.data.energy = 1.4
    sun.rotation_euler = (math.radians(38), math.radians(4), math.radians(22))


def import_model():
    bpy.ops.import_scene.gltf(filepath=MODEL_PATH)


def mesh_world_bounds(obj):
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for corner in obj.bound_box:
        world = obj.matrix_world @ Vector(corner)
        for i in range(3):
            mins[i] = min(mins[i], world[i])
            maxs[i] = max(maxs[i], world[i])
    return mins, maxs


def setup_camera(mins, maxs):
    cx = (mins[0] + maxs[0]) / 2
    cy = (mins[1] + maxs[1]) / 2
    cz = (mins[2] + maxs[2]) / 2
    sx = maxs[0] - mins[0]
    sy = maxs[1] - mins[1]
    sz = maxs[2] - mins[2]
    radius = max(sx, sy, sz, 1.0)
    bpy.ops.object.camera_add(location=(cx, cy - radius * 2.2, cz + radius * 0.42))
    cam = bpy.context.active_object
    cam.rotation_euler = (math.radians(80), 0, 0)
    cam.data.lens = 70
    bpy.context.scene.camera = cam
    return cam


def render_mesh(target_obj, path):
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            obj.hide_render = obj.name != target_obj.name
    mins, maxs = mesh_world_bounds(target_obj)
    if bpy.context.scene.camera:
        bpy.data.objects.remove(bpy.context.scene.camera, do_unlink=True)
    setup_camera(mins, maxs)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    clear_scene()
    setup_world()
    setup_lights()
    import_model()
    os.makedirs(OUT_DIR, exist_ok=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.name.startswith("Object_")]
    for mesh in meshes:
        render_mesh(mesh, os.path.join(OUT_DIR, f"{mesh.name}.png"))


if __name__ == "__main__":
    main()
