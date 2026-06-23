import bpy
import math
import os
from mathutils import Vector


MODEL_PATH = "/Volumes/Mac Satecchi/Mac/Web-stats/football/static/football/models/avatar/player_humanoid.glb"
OUT_FRONT = "/Volumes/Mac Satecchi/Mac/Downloads/player_humanoid_front.png"
OUT_ANGLE = "/Volumes/Mac Satecchi/Mac/Downloads/player_humanoid_angle.png"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_name in ("meshes", "materials", "images", "lights", "cameras"):
        block = getattr(bpy.data, block_name)
        for item in list(block):
            try:
                block.remove(item)
            except Exception:
                pass


def setup_world():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.film_transparent = False
    scene.eevee.taa_render_samples = 64
    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.95, 0.97, 1.0, 1.0)
        bg.inputs[1].default_value = 0.85


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


def setup_floor():
    bpy.ops.mesh.primitive_plane_add(size=7.5, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "PreviewFloor"
    mat = bpy.data.materials.new(name="FloorMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.84, 0.89, 0.95, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.92
    floor.data.materials.append(mat)


def import_model():
    bpy.ops.import_scene.gltf(filepath=MODEL_PATH)
    imported = list(bpy.context.scene.objects)
    root = next((obj for obj in imported if obj.name.startswith("PlayerRoot")), None)
    meshes = [obj for obj in imported if obj.type == "MESH"]
    return root, meshes


def world_bounds(meshes):
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for obj in meshes:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            for i in range(3):
                mins[i] = min(mins[i], world[i])
                maxs[i] = max(maxs[i], world[i])
    return mins, maxs


def setup_camera_for_bounds(mins, maxs, angle=False):
    cx = (mins[0] + maxs[0]) / 2
    cy = (mins[1] + maxs[1]) / 2
    cz = (mins[2] + maxs[2]) / 2
    sx = maxs[0] - mins[0]
    sy = maxs[1] - mins[1]
    sz = maxs[2] - mins[2]
    radius = max(sx, sy, sz, 1.0)
    if angle:
        loc = (cx + radius * 0.9, cy - radius * 1.9, cz + radius * 0.38)
        rot = (78, 0, 30)
    else:
        loc = (cx, cy - radius * 1.85, cz + radius * 0.34)
        rot = (80, 0, 0)
    return setup_camera(loc, rot)


def setup_camera(location, rotation_deg):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.active_object
    cam.rotation_euler = tuple(math.radians(v) for v in rotation_deg)
    cam.data.lens = 58
    bpy.context.scene.camera = cam
    return cam


def render_to(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    clear_scene()
    setup_world()
    setup_lights()
    setup_floor()
    _, meshes = import_model()
    mins, maxs = world_bounds(meshes)

    setup_camera_for_bounds(mins, maxs, angle=False)
    render_to(OUT_FRONT)

    bpy.data.objects.remove(bpy.context.scene.camera, do_unlink=True)
    setup_camera_for_bounds(mins, maxs, angle=True)
    render_to(OUT_ANGLE)


if __name__ == "__main__":
    main()
