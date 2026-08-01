import bpy
import math
from mathutils import Vector


GLB_PATH = "/Volumes/Mac Satecchi/Mac/Web-stats/football/static/football/models/pitch3d/stadium_zero_rebuild.glb"
OUT_HERO = "/Volumes/Mac Satecchi/Mac/Downloads/stadium-zero-rebuild-hero.png"
OUT_GOAL = "/Volumes/Mac Satecchi/Mac/Downloads/stadium-zero-rebuild-goal.png"


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_model():
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)


def scene_bbox():
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not meshes:
      raise RuntimeError("No mesh objects imported")
    min_corner = Vector((10**9, 10**9, 10**9))
    max_corner = Vector((-10**9, -10**9, -10**9))
    for obj in meshes:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            min_corner.x = min(min_corner.x, world.x)
            min_corner.y = min(min_corner.y, world.y)
            min_corner.z = min(min_corner.z, world.z)
            max_corner.x = max(max_corner.x, world.x)
            max_corner.y = max(max_corner.y, world.y)
            max_corner.z = max(max_corner.z, world.z)
    center = (min_corner + max_corner) * 0.5
    size = max_corner - min_corner
    return center, size, min_corner, max_corner


def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_camera(name, location, target, lens=32):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    look_at(cam, target)
    return cam


def add_lights(center, size):
    sun_data = bpy.data.lights.new("Sun", type="SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(48), 0.0, math.radians(32))

    area_data = bpy.data.lights.new("AreaKey", type="AREA")
    area_data.energy = 30000
    area_data.shape = "RECTANGLE"
    area_data.size = max(size.x, size.y) * 0.45
    area_data.size_y = max(size.x, size.y) * 0.18
    area = bpy.data.objects.new("AreaKey", area_data)
    bpy.context.scene.collection.objects.link(area)
    area.location = center + Vector((-size.x * 0.32, -size.y * 0.52, size.z * 0.82))
    look_at(area, center + Vector((0, 0, size.z * 0.08)))


def configure_world():
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.84, 0.91, 0.98, 1.0)
    bg.inputs[1].default_value = 0.75


def configure_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_object_outline = False


def render_views():
    center, size, min_corner, max_corner = scene_bbox()
    configure_world()
    configure_render()
    add_lights(center, size)

    scene = bpy.context.scene
    hero_target = center + Vector((0, 0, size.z * 0.12))
    hero_cam = add_camera(
        "HeroCam",
        Vector((min_corner.x - size.x * 0.22, min_corner.y - size.y * 0.58, min_corner.z + size.z * 0.40)),
        hero_target,
        lens=34,
    )
    scene.camera = hero_cam
    scene.render.filepath = OUT_HERO
    bpy.ops.render.render(write_still=True)

    goal_target = center + Vector((0, size.y * 0.08, size.z * 0.05))
    goal_cam = add_camera(
        "GoalCam",
        Vector((0, min_corner.y - size.y * 0.46, min_corner.z + size.z * 0.18)),
        goal_target,
        lens=42,
    )
    scene.camera = goal_cam
    scene.render.filepath = OUT_GOAL
    bpy.ops.render.render(write_still=True)


clear_scene()
import_model()
render_views()
