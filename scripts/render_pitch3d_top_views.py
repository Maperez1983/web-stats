from pathlib import Path
import math

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "football" / "static" / "football" / "models" / "pitch3d" / "stadium_benagalbon_reference.glb"
OUT_H = ROOT / "football" / "static" / "football" / "images" / "pitch3d" / "stadium_rosaleda_top_h.png"
OUT_V = ROOT / "football" / "static" / "football" / "images" / "pitch3d" / "stadium_rosaleda_top_v.png"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def import_model():
    bpy.ops.import_scene.gltf(filepath=str(MODEL_PATH))


def scene_bounds():
    mins = Vector((float("inf"), float("inf"), float("inf")))
    maxs = Vector((float("-inf"), float("-inf"), float("-inf")))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    for obj in meshes:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            mins.x = min(mins.x, world_corner.x)
            mins.y = min(mins.y, world_corner.y)
            mins.z = min(mins.z, world_corner.z)
            maxs.x = max(maxs.x, world_corner.x)
            maxs.y = max(maxs.y, world_corner.y)
            maxs.z = max(maxs.z, world_corner.z)
    return mins, maxs


def setup_world():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 64
    scene.eevee.use_shadows = True
    scene.eevee.shadow_pool_size = "1024"
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.82, 0.90, 0.97, 1.0)
        bg.inputs[1].default_value = 0.9

    bpy.ops.object.light_add(type="SUN", location=(0, 0, 140))
    sun = bpy.context.object
    sun.rotation_euler = (math.radians(12), 0, math.radians(28))
    sun.data.energy = 4.5
    sun.data.angle = math.radians(9)

    bpy.ops.object.light_add(type="AREA", location=(0, 0, 120))
    area = bpy.context.object
    area.scale = (80, 80, 80)
    area.data.energy = 15000


def ensure_camera():
    bpy.ops.object.camera_add(location=(0, 0, 100))
    cam = bpy.context.object
    cam.name = "pitch3d_top_camera"
    cam.data.type = "ORTHO"
    cam.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = cam
    return cam


def render_top(camera, center, half_span_x, half_span_y, resolution_x, resolution_y, out_path):
    scene = bpy.context.scene
    camera.location = (center.x, center.y, center.z + 160)
    camera.rotation_mode = "XYZ"
    camera.rotation_euler = (0.0, 0.0, 0.0)

    aspect = resolution_x / resolution_y
    padding = 1.86 if resolution_x >= resolution_y else 1.34
    fit_span = max(half_span_x, half_span_y * aspect) * padding
    camera.data.ortho_scale = fit_span

    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)


def main():
    clear_scene()
    import_model()
    setup_world()
    cam = ensure_camera()
    mins, maxs = scene_bounds()
    center = (mins + maxs) * 0.5
    span_x = (maxs.x - mins.x) * 0.5
    span_y = (maxs.y - mins.y) * 0.5

    render_top(cam, center, span_x, span_y, 3840, 2160, OUT_H)
    render_top(cam, center, span_x, span_y, 2160, 3840, OUT_V)
    print(f"Rendered {OUT_H}")
    print(f"Rendered {OUT_V}")


if __name__ == "__main__":
    main()
