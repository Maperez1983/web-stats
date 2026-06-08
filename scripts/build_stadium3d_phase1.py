import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "football" / "static" / "football" / "models" / "stadium3d"
IMAGE_DIR = ROOT / "football" / "static" / "football" / "images" / "stadium3d"
OUT_BLEND = MODEL_DIR / "stadium3d_phase1_pitch.blend"
OUT_GLB = MODEL_DIR / "stadium3d_phase1_pitch.glb"
OUT_RENDER = IMAGE_DIR / "stadium3d_phase1_pitch.png"

PITCH_X = 105.0
PITCH_Y = 68.0
HALF_X = PITCH_X / 2
HALF_Y = PITCH_Y / 2
LINE = 0.13
GOAL_W = 7.32
GOAL_H = 2.44

M = {}


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 96
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1050
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.color = (0.72, 0.88, 0.98)


def material(name, color, roughness=0.72, metallic=0.0, alpha=1.0, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next((node for node in mat.node_tree.nodes if getattr(node, "type", "") == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color[:3], alpha)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = "BLEND"
            mat.use_screen_refraction = True
        if emission and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission[:3], 1.0)
            bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def init_materials():
    M.update(
        {
            "grass_dark": material("phase1_grass_deep", (0.035, 0.33, 0.095), 0.88),
            "grass_light": material("phase1_grass_cut_light", (0.13, 0.48, 0.12), 0.86),
            "grass_detail": material("phase1_grass_blades", (0.055, 0.27, 0.07), 0.9),
            "line": material("phase1_pitch_line_white", (0.96, 0.98, 0.93), 0.48),
            "post": material("phase1_goal_post_white", (0.98, 0.99, 0.96), 0.38),
            "net": material("phase1_goal_net_translucent", (0.92, 0.96, 0.95), 0.62, alpha=0.56),
            "rubber": material("phase1_black_rubber", (0.012, 0.014, 0.013), 0.8),
            "concrete": material("phase1_concrete_runoff", (0.46, 0.49, 0.48), 0.9),
            "bench": material("phase1_bench_green", (0.02, 0.26, 0.13), 0.66),
            "glass": material("phase1_dugout_glass", (0.52, 0.82, 0.96), 0.36, alpha=0.34),
            "light": material("phase1_low_led_strip", (0.92, 1.0, 0.78), 0.25, emission=(0.8, 1.0, 0.72), strength=1.3),
        }
    )


def cube(name, loc, scale, mat_name, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(M[mat_name])
    if bevel:
        mod = obj.modifiers.new(f"{name}_bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def cylinder_between(name, start, end, radius, mat_name, vertices=18):
    start_v = Vector(start)
    end_v = Vector(end)
    mid = (start_v + end_v) / 2
    direction = end_v - start_v
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length, location=mid)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(M[mat_name])
    return obj


def add_curve_line(name, points, mat_name, bevel_depth=0.055):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 2
    poly = curve.splines.new("POLY")
    poly.points.add(len(points) - 1)
    for point, co in zip(poly.points, points):
        point.co = (co[0], co[1], co[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(M[mat_name])
    return obj


def add_circle(name, center, radius, mat_name, segments=144, fill=False):
    if fill:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=0.026, location=center)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(M[mat_name])
        return obj
    pts = []
    for i in range(segments + 1):
        a = math.tau * i / segments
        pts.append((center[0] + math.cos(a) * radius, center[1] + math.sin(a) * radius, center[2]))
    return add_curve_line(name, pts, mat_name, LINE / 2)


def add_arc(name, center, radius, side):
    pts = []
    limit = HALF_X - 16.5
    for i in range(181):
        a = math.tau * i / 180
        x = center[0] + math.cos(a) * radius
        y = center[1] + math.sin(a) * radius
        if (side > 0 and x < limit) or (side < 0 and x > -limit):
            pts.append((x, y, 0.155))
    if len(pts) > 2:
        add_curve_line(name, pts, "line", LINE / 2)


def add_pitch_surface():
    cube("phase1_pitch_runoff_slab", (0, 0, -0.055), (PITCH_X + 18, PITCH_Y + 16, 0.11), "concrete", 0.02)
    stripe_w = PITCH_X / 12
    for i in range(12):
        x = -HALF_X + stripe_w * (i + 0.5)
        mat = "grass_light" if i % 2 == 0 else "grass_dark"
        cube(f"phase1_mown_grass_band_{i:02d}", (x, 0, 0.0), (stripe_w + 0.03, PITCH_Y, 0.08), mat, 0.0)
    cube("phase1_outer_touchline_grass_blend", (0, 0, -0.01), (PITCH_X + 8.5, PITCH_Y + 7.5, 0.04), "grass_dark", 0.0)

    blades = []
    for i in range(950):
        x = -HALF_X + 1.5 + ((i * 17.37) % (PITCH_X - 3.0))
        y = -HALF_Y + 1.2 + ((i * 31.11) % (PITCH_Y - 2.4))
        h = 0.035 + (i % 6) * 0.007
        blades.append(((x, y, 0.08 + h / 2), (0.018, 0.08, h)))
    mesh_boxes("phase1_individual_grass_blade_cluster", blades, "grass_detail")


def mesh_boxes(name, boxes, mat_name):
    verts, faces = [], []
    for loc, scale in boxes:
        lx, ly, lz = loc
        sx, sy, sz = scale[0] / 2, scale[1] / 2, scale[2] / 2
        base = len(verts)
        verts.extend(
            [
                (lx - sx, ly - sy, lz - sz),
                (lx + sx, ly - sy, lz - sz),
                (lx + sx, ly + sy, lz - sz),
                (lx - sx, ly + sy, lz - sz),
                (lx - sx, ly - sy, lz + sz),
                (lx + sx, ly - sy, lz + sz),
                (lx + sx, ly + sy, lz + sz),
                (lx - sx, ly + sy, lz + sz),
            ]
        )
        faces.extend(
            [
                (base, base + 1, base + 2, base + 3),
                (base + 4, base + 7, base + 6, base + 5),
                (base, base + 4, base + 5, base + 1),
                (base + 1, base + 5, base + 6, base + 2),
                (base + 2, base + 6, base + 7, base + 3),
                (base + 3, base + 7, base + 4, base),
            ]
        )
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(M[mat_name])
    return obj


def add_pitch_markings():
    z = 0.13
    cube("phase1_line_touch_north", (0, HALF_Y, z), (PITCH_X, LINE, 0.035), "line")
    cube("phase1_line_touch_south", (0, -HALF_Y, z), (PITCH_X, LINE, 0.035), "line")
    cube("phase1_line_goal_east", (HALF_X, 0, z), (LINE, PITCH_Y, 0.035), "line")
    cube("phase1_line_goal_west", (-HALF_X, 0, z), (LINE, PITCH_Y, 0.035), "line")
    cube("phase1_line_halfway", (0, 0, z + 0.004), (LINE, PITCH_Y, 0.035), "line")
    add_circle("phase1_center_circle", (0, 0, z + 0.012), 9.15, "line")
    add_circle("phase1_center_spot", (0, 0, z + 0.025), 0.22, "line", fill=True)

    for side, label in [(1, "east"), (-1, "west")]:
        goal_x = side * HALF_X
        penalty_x = goal_x - side * 16.5
        six_x = goal_x - side * 5.5
        spot_x = goal_x - side * 11.0
        cube(f"phase1_{label}_penalty_box_front", ((goal_x + penalty_x) / 2, 20.16, z), (16.5, LINE, 0.035), "line")
        cube(f"phase1_{label}_penalty_box_back", ((goal_x + penalty_x) / 2, -20.16, z), (16.5, LINE, 0.035), "line")
        cube(f"phase1_{label}_penalty_box_inner", (penalty_x, 0, z), (LINE, 40.32, 0.035), "line")
        cube(f"phase1_{label}_six_box_front", ((goal_x + six_x) / 2, 9.16, z), (5.5, LINE, 0.035), "line")
        cube(f"phase1_{label}_six_box_back", ((goal_x + six_x) / 2, -9.16, z), (5.5, LINE, 0.035), "line")
        cube(f"phase1_{label}_six_box_inner", (six_x, 0, z), (LINE, 18.32, 0.035), "line")
        add_circle(f"phase1_{label}_penalty_spot", (spot_x, 0, z + 0.025), 0.22, "line", fill=True)
        add_arc(f"phase1_{label}_penalty_arc", (spot_x, 0, z + 0.018), 9.15, side)

    for sx in [-1, 1]:
        for sy in [-1, 1]:
            add_curve_line(
                f"phase1_corner_arc_{sx}_{sy}",
                [
                    (sx * HALF_X + math.cos(a) * sx * 1.0, sy * HALF_Y + math.sin(a) * sy * 1.0, z + 0.02)
                    for a in [i * math.pi / 2 / 20 for i in range(21)]
                ],
                "line",
                LINE / 2,
            )


def add_goal(label, side):
    x = side * HALF_X
    back_x = x + side * 2.15
    y1, y2 = -GOAL_W / 2, GOAL_W / 2
    z0, z1 = 0.12, GOAL_H + 0.12
    r = 0.08
    cylinder_between(f"phase1_goal_{label}_post_left", (x, y1, z0), (x, y1, z1), r, "post")
    cylinder_between(f"phase1_goal_{label}_post_right", (x, y2, z0), (x, y2, z1), r, "post")
    cylinder_between(f"phase1_goal_{label}_crossbar", (x, y1, z1), (x, y2, z1), r, "post")
    cylinder_between(f"phase1_goal_{label}_back_left", (back_x, y1, z0), (back_x, y1, z1 * 0.84), 0.045, "post")
    cylinder_between(f"phase1_goal_{label}_back_right", (back_x, y2, z0), (back_x, y2, z1 * 0.84), 0.045, "post")
    cylinder_between(f"phase1_goal_{label}_rear_top", (back_x, y1, z1 * 0.84), (back_x, y2, z1 * 0.84), 0.045, "post")

    for i in range(9):
        y = y1 + (GOAL_W * i / 8)
        cylinder_between(f"phase1_net_{label}_roof_y_{i}", (x, y, z1), (back_x, y, z1 * 0.84), 0.012, "net", 8)
    for i in range(6):
        z = z0 + (z1 * 0.84 - z0) * i / 5
        cylinder_between(f"phase1_net_{label}_back_z_{i}", (back_x, y1, z), (back_x, y2, z), 0.012, "net", 8)
    for i in range(9):
        y = y1 + (GOAL_W * i / 8)
        cylinder_between(f"phase1_net_{label}_back_y_{i}", (back_x, y, z0), (back_x, y, z1 * 0.84), 0.012, "net", 8)
    for y, side_name in [(y1, "left"), (y2, "right")]:
        for i in range(5):
            z = z0 + (z1 - z0) * i / 4
            cylinder_between(f"phase1_net_{label}_side_{side_name}_{i}", (x, y, z), (back_x, y, z * 0.84 + z0 * 0.16), 0.012, "net", 8)


def add_technical_areas():
    for x, label in [(-19, "home"), (19, "away")]:
        cube(f"phase1_{label}_dugout_base", (x, -HALF_Y - 5.2, 0.36), (13.0, 2.4, 0.32), "rubber", 0.02)
        cube(f"phase1_{label}_dugout_roof", (x, -HALF_Y - 5.55, 2.65), (13.8, 2.7, 0.28), "bench", 0.04)
        cube(f"phase1_{label}_dugout_back_glass", (x, -HALF_Y - 6.55, 1.55), (13.2, 0.18, 2.05), "glass", 0.02)
        for i in range(8):
            cube(f"phase1_{label}_bench_seat_{i}", (x - 4.55 + i * 1.3, -HALF_Y - 4.98, 0.88), (0.82, 0.42, 0.42), "bench", 0.025)
        cube(f"phase1_{label}_technical_area_front", (x, -HALF_Y - 1.4, 0.16), (13.0, LINE, 0.035), "line")
        cube(f"phase1_{label}_technical_area_left", (x - 6.5, -HALF_Y - 3.0, 0.16), (LINE, 3.2, 0.035), "line")
        cube(f"phase1_{label}_technical_area_right", (x + 6.5, -HALF_Y - 3.0, 0.16), (LINE, 3.2, 0.035), "line")


def add_lighting_camera():
    bpy.ops.object.light_add(type="SUN", location=(-50, -70, 90))
    sun = bpy.context.object
    sun.name = "phase1_sun_key"
    sun.data.energy = 1.55
    sun.rotation_euler = (math.radians(45), 0, math.radians(-32))
    for loc in [(-40, -42, 18), (40, 42, 18)]:
        bpy.ops.object.light_add(type="AREA", location=loc)
        area = bpy.context.object
        area.name = "phase1_soft_area_light"
        area.data.energy = 170
        area.data.size = 26
    bpy.ops.object.camera_add(location=(-72, -64, 35), rotation=(math.radians(62), 0, math.radians(-43)))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    cam.data.lens = 30


def build():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    reset_scene()
    init_materials()
    add_pitch_surface()
    add_pitch_markings()
    add_goal("east", 1)
    add_goal("west", -1)
    add_technical_areas()
    add_lighting_camera()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB", export_yup=True)
    bpy.context.scene.render.filepath = str(OUT_RENDER)
    bpy.ops.render.render(write_still=True)
    print(f"BLEND={OUT_BLEND}")
    print(f"GLB={OUT_GLB}")
    print(f"RENDER={OUT_RENDER}")


if __name__ == "__main__":
    build()
