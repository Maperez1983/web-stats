import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "football" / "static" / "football" / "models" / "stadium"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_BLEND = OUT_DIR / "benagalbon-hyperrealistic-stadium.blend"
OUT_GLB = OUT_DIR / "benagalbon-hyperrealistic-stadium.glb"
OUT_PREVIEW = ROOT / "football" / "static" / "football" / "images" / "stadium" / "benagalbon-hyperrealistic-preview.png"
OUT_PREVIEW.parent.mkdir(parents=True, exist_ok=True)

PITCH_X = 105.0
PITCH_Y = 68.0
HALF_X = PITCH_X / 2
HALF_Y = PITCH_Y / 2

LETTER_5X7 = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def seat_text_mask(text, col, row, cols, rows, start_col=16, end_col=132):
    glyph_w = 5
    glyph_h = 7
    scale_x = 2
    scale_y = 2
    gap = 1
    bitmap_w = sum((glyph_w * scale_x + gap) for _ in text) - gap
    bitmap_h = glyph_h * scale_y
    region_w = max(1, end_col - start_col)
    region_h = bitmap_h
    top_row = max(0, (rows - region_h) // 2 + 1)
    if col < start_col or col >= end_col or row < top_row or row >= top_row + region_h:
        return False
    local_x = int((col - start_col) * bitmap_w / region_w)
    local_y = int((row - top_row) * bitmap_h / region_h)
    cursor = 0
    for ch in text.upper():
        glyph = LETTER_5X7.get(ch, LETTER_5X7[" "])
        width = glyph_w * scale_x
        if cursor <= local_x < cursor + width:
            gx = (local_x - cursor) // scale_x
            gy = local_y // scale_y
            return glyph[gy][gx] == "1"
        cursor += width + gap
    return False


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = -0.35
    scene.view_settings.gamma = 1
    scene.world = bpy.data.worlds.new("stadium_sky")
    scene.world.color = (0.62, 0.78, 0.94)


def material(name, color, roughness=0.75, metallic=0.0, alpha=1.0, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (color[0], color[1], color[2], alpha)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], alpha)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if alpha < 1 and "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if emission and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (emission[0], emission[1], emission[2], 1)
        if emission and "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1:
        mat.blend_method = "BLEND"
        mat.use_screen_refraction = True
    return mat


M = {}


def init_materials():
    M.update(
        {
            "grass_a": material("grass_mowed_deep", (0.10, 0.34, 0.10), 0.90),
            "grass_b": material("grass_mowed_bright", (0.22, 0.48, 0.13), 0.88),
            "grass_detail_dark": material("grass_fine_dark_variation", (0.08, 0.29, 0.08), 0.94),
            "grass_detail_light": material("grass_fine_light_variation", (0.25, 0.50, 0.14), 0.92),
            "white": material("pitch_line_clean_white", (0.98, 0.99, 0.96), 0.56),
            "concrete": material("cast_concrete_light", (0.52, 0.56, 0.57), 0.91),
            "concrete_dark": material("weathered_concrete_shadow", (0.32, 0.36, 0.38), 0.94),
            "asphalt": material("service_asphalt", (0.035, 0.045, 0.047), 0.86),
            "green": material("club_deep_green_seats", (0.0, 0.23, 0.10), 0.66),
            "green_dark": material("club_dark_green_fascia", (0.0, 0.10, 0.07), 0.72),
            "seat_white": material("pure_white_seat_mosaic", (0.99, 1.0, 0.96), 0.58),
            "steel": material("galvanized_steel", (0.70, 0.77, 0.79), 0.34, 0.35),
            "roof": material("dark_roof_metal", (0.07, 0.10, 0.12), 0.46, 0.25),
            "glass": material("curved_dugout_glass", (0.56, 0.82, 0.96), 0.10, 0.02, 0.38),
            "screen": material("screen_dark_led", (0.015, 0.025, 0.020), 0.36, emission=(0.0, 0.20, 0.11), emission_strength=0.6),
            "light": material("stadium_warm_led", (1.0, 0.90, 0.68), 0.22, emission=(1.0, 0.84, 0.46), emission_strength=3.5),
            "sky": material("clear_summer_sky", (0.54, 0.75, 0.94), 0.9, emission=(0.54, 0.75, 0.94), emission_strength=0.22),
            "cloud": material("soft_white_cloud", (0.92, 0.96, 1.0), 0.95),
            "tree": material("distant_tree_canopy", (0.10, 0.32, 0.16), 0.84),
            "city": material("distant_city_blocks", (0.62, 0.67, 0.70), 0.82),
            "baked_shadow": material("soft_roof_shadow_overlay", (0.02, 0.05, 0.05), 0.96, 0.0, 0.09),
        }
    )


def cube(name, loc, scale, mat_name, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(M[mat_name])
    if bevel > 0:
        mod = obj.modifiers.new(f"{name}_bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_box_to_mesh(verts, faces, loc, scale):
    x, y, z = loc
    sx, sy, sz = scale[0] / 2, scale[1] / 2, scale[2] / 2
    base = len(verts)
    verts.extend(
        [
            (x - sx, y - sy, z - sz),
            (x + sx, y - sy, z - sz),
            (x + sx, y + sy, z - sz),
            (x - sx, y + sy, z - sz),
            (x - sx, y - sy, z + sz),
            (x + sx, y - sy, z + sz),
            (x + sx, y + sy, z + sz),
            (x - sx, y + sy, z + sz),
        ]
    )
    faces.extend(
        [
            (base + 0, base + 1, base + 2, base + 3),
            (base + 4, base + 7, base + 6, base + 5),
            (base + 0, base + 4, base + 5, base + 1),
            (base + 1, base + 5, base + 6, base + 2),
            (base + 2, base + 6, base + 7, base + 3),
            (base + 3, base + 7, base + 4, base + 0),
        ]
    )


def mesh_boxes(name, boxes, mat_name):
    verts, faces = [], []
    for loc, scale in boxes:
        add_box_to_mesh(verts, faces, loc, scale)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(M[mat_name])
    obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def cylinder_between(name, start, end, radius, mat_name, vertices=16):
    start_v = Vector(start)
    end_v = Vector(end)
    direction = end_v - start_v
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=direction.length, location=(start_v + end_v) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(M[mat_name])
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return obj


def add_text(name, text, loc, size, mat_name, rot=(0, 0, 0), align="CENTER", extrude=0.02):
    bpy.ops.object.text_add(location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = text
    obj.data.align_x = align
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = extrude
    obj.data.materials.append(M[mat_name])
    return obj


def add_pitch():
    cube("service_apron_asphalt", (0, 0, -0.055), (140, 100, 0.08), "asphalt")
    stripe_w = PITCH_X / 14
    for i in range(14):
        x = -HALF_X + stripe_w * (i + 0.5)
        cube(f"grass_stripe_{i:02d}", (x, 0, 0), (stripe_w + 0.02, PITCH_Y, 0.05), "grass_a" if i % 2 else "grass_b")
    z = 0.075
    line = 0.18
    cube("line_touch_north", (0, HALF_Y, z), (PITCH_X, line, 0.035), "white")
    cube("line_touch_south", (0, -HALF_Y, z), (PITCH_X, line, 0.035), "white")
    cube("line_goal_east", (HALF_X, 0, z), (line, PITCH_Y, 0.035), "white")
    cube("line_goal_west", (-HALF_X, 0, z), (line, PITCH_Y, 0.035), "white")
    cube("line_halfway", (0, 0, z), (line, PITCH_Y, 0.035), "white")
    for side in [-1, 1]:
        x = side * HALF_X
        cube(f"penalty_box_{side}_top", (x - side * 16.5 / 2, 20.16, z), (16.5, line, 0.035), "white")
        cube(f"penalty_box_{side}_bottom", (x - side * 16.5 / 2, -20.16, z), (16.5, line, 0.035), "white")
        cube(f"penalty_box_{side}_front", (x - side * 16.5, 0, z), (line, 40.32, 0.035), "white")
        cube(f"six_box_{side}_top", (x - side * 5.5 / 2, 9.16, z), (5.5, line, 0.035), "white")
        cube(f"six_box_{side}_bottom", (x - side * 5.5 / 2, -9.16, z), (5.5, line, 0.035), "white")
        cube(f"six_box_{side}_front", (x - side * 5.5, 0, z), (line, 18.32, 0.035), "white")
    add_circle_line("center_circle", (0, 0, z + 0.01), 9.15, "white")
    add_circle_line("center_spot", (0, 0, z + 0.02), 0.42, "white", fill=True)


def add_grass_fine_variation():
    dark = []
    light = []
    seed = 17
    for i in range(520):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        rx = (seed / 0x7FFFFFFF)
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        ry = (seed / 0x7FFFFFFF)
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        rr = (seed / 0x7FFFFFFF)
        x = -HALF_X + rx * PITCH_X
        y = -HALF_Y + ry * PITCH_Y
        sx = 0.22 + rr * 0.95
        sy = 0.028 + rr * 0.035
        target = light if i % 3 == 0 else dark
        target.append(((x, y, 0.105 + i * 0.000002), (sx, sy, 0.012)))
    mesh_boxes("grass_random_dark_blades", dark, "grass_detail_dark")
    mesh_boxes("grass_random_light_blades", light, "grass_detail_light")


def add_baked_pitch_shadows():
    shadow_specs = [
        ("main_roof_shadow", (-18, -13, 0.13), (86, 30, 0.025), math.radians(-5)),
        ("near_roof_shadow", (24, -28, 0.14), (70, 18, 0.025), math.radians(-5)),
    ]
    for name, loc, scale, rot in shadow_specs:
        obj = cube(name, loc, scale, "baked_shadow")
        obj.rotation_euler.z = rot


def add_circle_line(name, center, radius, mat_name, fill=False):
    if fill:
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=0.035, location=center)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(M[mat_name])
        return obj
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_depth = 0.075
    curve.bevel_resolution = 2
    spl = curve.splines.new("POLY")
    spl.points.add(96)
    for i, p in enumerate(spl.points):
        a = math.tau * i / 96
        p.co = (center[0] + math.cos(a) * radius, center[1] + math.sin(a) * radius, center[2], 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(M[mat_name])
    return obj


def add_long_stand(name, sign):
    base_y = sign * (HALF_Y + 8)
    rows = 28
    primary, secondary = [], []
    backs_primary, backs_secondary = [], []
    for row in range(rows):
        y = base_y + sign * (row * 0.78)
        z = 1.25 + row * 0.48
        width = PITCH_X + 26 - row * 0.35
        cube(f"{name}_concrete_step_{row:02d}", (0, y, z - 0.12), (width, 0.72, 0.25), "concrete")
        for col in range(148):
            nx = col / 147 - 0.5
            if abs(nx) < 0.018 or abs(nx - 0.23) < 0.014 or abs(nx + 0.23) < 0.014 or abs(nx - 0.39) < 0.014 or abs(nx + 0.39) < 0.014:
                continue
            x = nx * (width - 3)
            if sign > 0:
                letter_seat = seat_text_mask("BENAGALBON CD", col, row, 148, rows, start_col=13, end_col=135)
            else:
                letter_seat = seat_text_mask("CDB", col, row, 148, rows, start_col=54, end_col=94)
            target = secondary if letter_seat or (row + col) % 73 == 0 else primary
            back_target = backs_secondary if target is secondary else backs_primary
            target.append(((x, y - sign * 0.04, z + 0.05), (0.40, 0.30, 0.16)))
            back_target.append(((x, y + sign * 0.12, z + 0.30), (0.40, 0.08, 0.38)))
    mesh_boxes(f"{name}_green_seats", primary, "green")
    mesh_boxes(f"{name}_white_seats", secondary, "seat_white")
    mesh_boxes(f"{name}_green_seat_backs", backs_primary, "green")
    mesh_boxes(f"{name}_white_seat_backs", backs_secondary, "seat_white")
    cube(f"{name}_front_fascia", (0, base_y - sign * 1.2, 2.1), (PITCH_X + 32, 0.8, 1.25), "green_dark", 0.04)
    cube(f"{name}_rear_wall", (0, base_y + sign * 24.5, 8.2), (PITCH_X + 42, 1.1, 15.0), "concrete", 0.03)
    cube(f"{name}_upper_concourse_shadow", (0, base_y + sign * 12.5, 9.6), (PITCH_X + 28, 0.5, 1.2), "concrete_dark")
    cube(f"{name}_roof_canopy", (0, base_y + sign * 30.0, 19.0), (PITCH_X + 52, 18.0, 0.48), "roof", 0.03)
    cube(f"{name}_roof_glass_strip", (0, base_y + sign * 22.0, 18.7), (PITCH_X + 36, 5.6, 0.16), "glass")
    for i in range(15):
        x = -PITCH_X / 2 - 8 + i * ((PITCH_X + 16) / 14)
        cylinder_between(f"{name}_roof_truss_{i}", (x, base_y + sign * 17.0, 13.0), (x + 2.8, base_y + sign * 31.5, 19.4), 0.14, "steel")
        cylinder_between(f"{name}_roof_support_{i}", (x, base_y + sign * 21.5, 8.5), (x + 0.8, base_y + sign * 29.8, 18.4), 0.10, "steel")
        cube(f"{name}_light_bar_{i}", (x, base_y + sign * 16.4, 17.2), (3.6, 0.24, 0.24), "light")
    # Las letras grandes deben leerse como mosaico de asientos, no como texto flotante.
    # El patron de asientos blancos ya crea la banda visual sin bloquear la vista.


def add_end_stand(name, sign):
    base_x = sign * (HALF_X + 8)
    rows = 20
    primary, secondary = [], []
    for row in range(rows):
        x = base_x + sign * row * 0.78
        z = 1.2 + row * 0.45
        depth = PITCH_Y + 24 - row * 0.45
        cube(f"{name}_step_{row:02d}", (x, 0, z - 0.1), (0.72, depth, 0.25), "concrete")
        for col in range(108):
            ny = col / 107 - 0.5
            if abs(ny) < 0.02 or abs(ny - 0.31) < 0.014 or abs(ny + 0.31) < 0.014:
                continue
            target = secondary if (row in range(8, 13) and abs(ny) < 0.34) or (row + col) % 57 == 0 else primary
            target.append(((x + sign * 0.05, ny * (depth - 3), z + 0.05), (0.30, 0.40, 0.16)))
    mesh_boxes(f"{name}_green_seats", primary, "green")
    mesh_boxes(f"{name}_white_seats", secondary, "seat_white")
    cube(f"{name}_front_fascia", (base_x - sign * 1.2, 0, 2.0), (0.8, PITCH_Y + 30, 1.15), "green_dark", 0.04)
    cube(f"{name}_rear_wall", (base_x + sign * 18.5, 0, 7.6), (1.0, PITCH_Y + 38, 13.2), "concrete", 0.03)
    cube(f"{name}_roof", (base_x + sign * 23.5, 0, 16.5), (18, PITCH_Y + 45, 0.44), "roof", 0.03)


def add_corner_stands():
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            base_x = sx * (HALF_X + 9.5)
            base_y = sy * (HALF_Y + 9.5)
            primary, secondary = [], []
            for row in range(18):
                z = 1.15 + row * 0.43
                width = 28 - row * 0.52
                depth = 25 - row * 0.46
                cube(f"corner_step_{sx}_{sy}_{row}", (base_x + sx * row * 0.50, base_y + sy * row * 0.50, z - 0.1), (width, depth, 0.24), "concrete")
                for ix in range(28):
                    for iy in range(22):
                        nx = ix / 27 - 0.5
                        ny = iy / 21 - 0.5
                        if nx * sx < -0.18 or ny * sy < -0.18:
                            continue
                        if (ix + iy + row) % 4:
                            continue
                        x = base_x + sx * row * 0.50 + nx * (width - 2)
                        y = base_y + sy * row * 0.50 + ny * (depth - 2)
                        target = secondary if (row + ix + iy) % 31 == 0 else primary
                        target.append(((x, y, z + 0.04), (0.34, 0.34, 0.15)))
            mesh_boxes(f"corner_{sx}_{sy}_green_seats", primary, "green")
            mesh_boxes(f"corner_{sx}_{sy}_white_seats", secondary, "seat_white")


def add_boards():
    labels = ["2J FOOTBALL INTELLIGENCE", "BENAGALBON CD", "SPONSOR", "PARTNER"]
    idx = 0
    for x in range(-51, 52, 17):
        for sign in [-1, 1]:
            y = sign * (HALF_Y + 4.0)
            cube(f"board_panel_{idx}", (x, y, 1.35), (15.2, 0.32, 2.4), "green_dark", 0.02)
            add_text(f"board_text_{idx}", labels[idx % len(labels)], (x, y - sign * 0.19, 1.38), 0.72, "white", rot=(math.radians(90), 0, math.radians(180) if sign < 0 else 0))
            idx += 1
    for y in range(-27, 28, 14):
        for sign in [-1, 1]:
            x = sign * (HALF_X + 4.0)
            cube(f"board_end_panel_{idx}", (x, y, 1.35), (0.32, 12.5, 2.4), "green_dark", 0.02)
            add_text(f"board_end_text_{idx}", labels[idx % len(labels)], (x - sign * 0.19, y, 1.38), 0.68, "white", rot=(math.radians(90), 0, math.radians(-90) if sign > 0 else math.radians(90)))
            idx += 1


def add_goals_and_benches():
    for sign in [-1, 1]:
        x = sign * (HALF_X + 0.15)
        w = 7.32
        h = 2.44
        back = sign * 2.1
        pts = [
            (x, -w / 2, 0),
            (x, -w / 2, h),
            (x, w / 2, h),
            (x, w / 2, 0),
            (x + back, -w / 2, 0),
            (x + back, -w / 2, h * 0.82),
            (x + back, w / 2, h * 0.82),
            (x + back, w / 2, 0),
        ]
        for a, b in [(0, 1), (1, 2), (2, 3), (1, 5), (2, 6), (5, 6), (4, 5), (6, 7), (0, 4), (3, 7)]:
            cylinder_between(f"goal_{sign}_{a}_{b}", pts[a], pts[b], 0.055, "white", 12)
    for side, x in enumerate([-22, 22]):
        cube(f"dugout_base_{side}", (x, -HALF_Y - 8.0, 0.55), (13, 1.25, 0.38), "green_dark", 0.04)
        cube(f"dugout_glass_{side}", (x, -HALF_Y - 8.6, 1.62), (13.5, 0.28, 2.1), "glass", 0.02)
        for i in range(9):
            cube(f"dugout_seat_{side}_{i}", (x - 4.4 + i * 1.1, -HALF_Y - 7.8, 0.92), (0.62, 0.50, 0.28), "green", 0.03)


def add_screen_and_crest():
    cube("scoreboard_frame", (0, HALF_Y + 29, 14.5), (14, 0.7, 8.2), "steel", 0.04)
    cube("scoreboard_screen", (0, HALF_Y + 28.55, 14.5), (12.8, 0.16, 7.0), "screen", 0.02)
    add_text("scoreboard_cdb", "CDB", (0, HALF_Y + 28.42, 15.4), 2.0, "white", rot=(math.radians(90), 0, 0))
    add_text("scoreboard_name", "BENAGALBON CD", (0, HALF_Y + 28.40, 12.7), 0.64, "white", rot=(math.radians(90), 0, 0))
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=3.8, depth=0.14, location=(0, HALF_Y + 30.5, 22.0))
    crest = bpy.context.object
    crest.name = "round_cdb_crest_disc"
    crest.rotation_euler.x = math.radians(90)
    crest.data.materials.append(M["green"])
    add_text("crest_text", "CDB", (0, HALF_Y + 30.36, 22.0), 1.45, "white", rot=(math.radians(90), 0, 0))


def add_environment():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=420, location=(0, 0, 0))
    sky = bpy.context.object
    sky.name = "soft_blue_sky_dome"
    sky.data.materials.append(M["sky"])
    try:
        sky.visible_shadow = False
    except Exception:
        pass
    for i in range(18):
        x = -170 + i * 20
        y = 128 + math.sin(i * 1.7) * 8
        z = 42 + (i % 4) * 3
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(x, y, z))
        cloud = bpy.context.object
        cloud.name = f"soft_cloud_{i:02d}"
        cloud.scale = (8 + (i % 3) * 3, 2.0, 1.1 + (i % 2) * 0.5)
        cloud.data.materials.append(M["cloud"])
        try:
            cloud.visible_shadow = False
        except Exception:
            pass
    for i in range(46):
        x = -135 + i * 6
        y = 95 + math.sin(i * 0.9) * 5
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=2.1 + (i % 3) * 0.35, location=(x, y, 4.0))
        tree = bpy.context.object
        tree.name = f"distant_tree_{i:02d}"
        tree.scale = (1.0, 0.8, 1.35)
        tree.data.materials.append(M["tree"])
    for i in range(20):
        x = -110 + i * 11
        y = 142 + (i % 4) * 5
        h = 8 + (i % 5) * 3
        cube(f"distant_city_block_{i:02d}", (x, y, h / 2 - 0.2), (6.5, 5.5, h), "city", 0.02)


def add_lighting_and_camera():
    bpy.ops.object.light_add(type="SUN", location=(-70, -95, 110))
    sun = bpy.context.object
    sun.name = "late_morning_sun"
    sun.data.energy = 4.8
    sun.rotation_euler = (math.radians(43), 0, math.radians(-32))
    for x in [-45, -15, 15, 45]:
        for y in [HALF_Y + 21, -HALF_Y - 21]:
            bpy.ops.object.light_add(type="AREA", location=(x, y, 18))
            light = bpy.context.object
            light.name = "warm_roof_floodlight"
            light.data.energy = 280
            light.data.size = 6
            direction = Vector((0, 0, 0)) - Vector(light.location)
            light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add(location=(-72, -72, 45), rotation=(math.radians(62), 0, math.radians(-42)))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    direction = Vector((0, 0, 4)) - Vector(cam.location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 22
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 92
    cam.data.dof.aperture_fstop = 7.5


def main():
    reset_scene()
    init_materials()
    add_pitch()
    add_grass_fine_variation()
    add_baked_pitch_shadows()
    add_long_stand("south_main_stand", 1)
    add_long_stand("north_stand", -1)
    add_end_stand("east_goal_stand", 1)
    add_end_stand("west_goal_stand", -1)
    add_corner_stands()
    add_boards()
    add_goals_and_benches()
    add_screen_and_crest()
    add_environment()
    add_lighting_and_camera()

    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB", export_yup=True)
    scene = bpy.context.scene
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1012
    scene.render.filepath = str(OUT_PREVIEW)
    bpy.ops.render.render(write_still=True)
    print(f"BLEND={OUT_BLEND}")
    print(f"GLB={OUT_GLB}")
    print(f"PREVIEW={OUT_PREVIEW}")


if __name__ == "__main__":
    main()
