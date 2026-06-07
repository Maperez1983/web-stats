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
OUT_PRODUCTION_RENDER = ROOT / "football" / "static" / "football" / "images" / "stadium" / "benagalbon-production-render.png"
OUT_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
REFERENCE_TEX_DIR = Path("/Volumes/Mac Satecchi/Mac/Downloads/Nueva carpeta con ítems 2/dragon_stadium/textures")

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
    scale_x = 3
    scale_y = 3
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
    scene.cycles.samples = 160
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = -0.55
    scene.view_settings.gamma = 1
    scene.world = bpy.data.worlds.new("stadium_sky")
    scene.world.color = (0.55, 0.72, 0.88)
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.55, 0.72, 0.88, 1)
        bg.inputs["Strength"].default_value = 0.75


def material(name, color, roughness=0.75, metallic=0.0, alpha=1.0, emission=None, emission_strength=0.0, texture=None, texture_mix=0.55, bump=False):
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
        if texture and Path(texture).exists() and "Base Color" in bsdf.inputs:
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = bpy.data.images.load(str(texture), check_existing=True)
            tint = mat.node_tree.nodes.new("ShaderNodeRGB")
            tint.outputs["Color"].default_value = (color[0], color[1], color[2], 1)
            mix = mat.node_tree.nodes.new("ShaderNodeMixRGB")
            mix.blend_type = "MULTIPLY"
            mix.inputs["Fac"].default_value = texture_mix
            mat.node_tree.links.new(tex.outputs["Color"], mix.inputs["Color1"])
            mat.node_tree.links.new(tint.outputs["Color"], mix.inputs["Color2"])
            mat.node_tree.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
        if bump and "Normal" in bsdf.inputs:
            noise = mat.node_tree.nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = 42
            noise.inputs["Detail"].default_value = 8
            noise.inputs["Roughness"].default_value = 0.56
            bump_node = mat.node_tree.nodes.new("ShaderNodeBump")
            bump_node.inputs["Strength"].default_value = 0.045
            bump_node.inputs["Distance"].default_value = 0.09
            mat.node_tree.links.new(noise.outputs["Fac"], bump_node.inputs["Height"])
            mat.node_tree.links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])
    if alpha < 1:
        mat.blend_method = "BLEND"
        mat.use_screen_refraction = True
    return mat


M = {}


def init_materials():
    grass_tex = REFERENCE_TEX_DIR / "Trawa_03_1_baseColor.png"
    concrete_tex = REFERENCE_TEX_DIR / "Beton_16_0_baseColor.png"
    steel_tex = REFERENCE_TEX_DIR / "Stal_04__szczotkowana_4_baseColor.png"
    M.update(
        {
            "grass_a": material("grass_mowed_deep_textured", (0.10, 0.38, 0.08), 0.91, texture=grass_tex, texture_mix=0.30, bump=True),
            "grass_b": material("grass_mowed_bright_textured", (0.24, 0.54, 0.12), 0.89, texture=grass_tex, texture_mix=0.26, bump=True),
            "mow_broadcast_dark": material("broadcast_mow_dark_green", (0.055, 0.31, 0.065), 0.92),
            "mow_broadcast_light": material("broadcast_mow_light_green", (0.24, 0.50, 0.12), 0.90),
            "grass_detail_dark": material("grass_fine_dark_variation", (0.08, 0.29, 0.08), 0.94),
            "grass_detail_light": material("grass_fine_light_variation", (0.25, 0.50, 0.14), 0.92),
            "grass_wear": material("pitch_worn_grass_subtle", (0.38, 0.54, 0.24), 0.96, 0.0, 0.18),
            "grass_shadow": material("pitch_grain_soft_shadow", (0.03, 0.13, 0.04), 0.96, 0.0, 0.16),
            "grass_blade": material("individual_grass_blades", (0.07, 0.30, 0.07), 0.92, 0.0, 0.68),
            "line_shadow": material("painted_line_soft_edge", (0.82, 0.88, 0.78), 0.72, 0.0, 0.42),
            "white": material("pitch_line_clean_white", (1.0, 1.0, 1.0), 0.50),
            "concrete": material("cast_concrete_light_textured", (0.58, 0.61, 0.60), 0.91, texture=concrete_tex, texture_mix=0.50, bump=True),
            "concrete_dark": material("weathered_concrete_shadow_textured", (0.30, 0.34, 0.35), 0.94, texture=concrete_tex, texture_mix=0.64, bump=True),
            "asphalt": material("service_asphalt", (0.035, 0.045, 0.047), 0.86),
            "green": material("club_deep_green_seats", (0.0, 0.21, 0.085), 0.62),
            "green_dark": material("club_dark_green_fascia", (0.0, 0.07, 0.045), 0.72),
            "seat_white": material("pure_white_seat_mosaic", (1.0, 1.0, 1.0), 0.48),
            "steel": material("galvanized_steel_textured", (0.78, 0.82, 0.82), 0.32, 0.38, texture=steel_tex, texture_mix=0.30),
            "roof": material("dark_roof_metal_textured", (0.035, 0.047, 0.055), 0.44, 0.34, texture=steel_tex, texture_mix=0.42),
            "glass": material("curved_dugout_glass", (0.56, 0.82, 0.96), 0.10, 0.02, 0.38),
            "net": material("goal_net_fine_white", (0.98, 1.0, 1.0), 0.62, 0.0, 0.56),
            "rubber": material("technical_black_rubber", (0.015, 0.018, 0.017), 0.70),
            "screen": material("screen_dark_led", (0.015, 0.025, 0.020), 0.36, emission=(0.0, 0.20, 0.11), emission_strength=0.6),
            "light": material("stadium_warm_led", (1.0, 0.90, 0.68), 0.22, emission=(1.0, 0.84, 0.46), emission_strength=3.5),
            "safety_yellow": material("stair_nosing_safety_yellow", (1.0, 0.72, 0.12), 0.58),
            "led_white": material("cool_white_led_pixels", (0.86, 1.0, 0.92), 0.18, emission=(0.70, 1.0, 0.78), emission_strength=1.8),
            "sky": material("clear_summer_sky", (0.54, 0.75, 0.94), 0.9, emission=(0.54, 0.75, 0.94), emission_strength=0.08),
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
    if bevel == 0.0:
        bevel = 0.006 if max(scale) < 25 else 0.012
    if bevel > 0:
        mod = obj.modifiers.new(f"{name}_bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2 if bevel >= 0.012 else 1
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
    if not boxes:
        return None
    verts, faces = [], []
    for loc, scale in boxes:
        add_box_to_mesh(verts, faces, loc, scale)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vert = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            uv_layer.data[loop_index].uv = (vert.x * 0.045, vert.y * 0.045)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(M[mat_name])
    bevel = obj.modifiers.new(f"{name}_softened_edges", "BEVEL")
    bevel.width = 0.012
    bevel.segments = 1
    obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_vomitory(name, loc, scale, face_axis, sign):
    tunnel = cube(f"{name}_black_tunnel", loc, scale, "asphalt", 0.035)
    frame_scale = (scale[0] + 0.72, scale[1] + 0.18, scale[2] + 0.46)
    frame_loc = (loc[0], loc[1], loc[2] + 0.05)
    if face_axis == "y":
        frame_scale = (scale[0] + 0.78, 0.16, scale[2] + 0.54)
        frame_loc = (loc[0], loc[1] - sign * 0.10, loc[2] + 0.04)
    elif face_axis == "x":
        frame_scale = (0.16, scale[1] + 0.78, scale[2] + 0.54)
        frame_loc = (loc[0] - sign * 0.10, loc[1], loc[2] + 0.04)
    frame = cube(f"{name}_concrete_lintel", frame_loc, frame_scale, "concrete_dark", 0.025)
    tunnel.display_type = "TEXTURED"
    return frame


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


def add_text(name, text, loc, size, mat_name, rot=(0, 0, 0), align="CENTER", extrude=0.0):
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


def add_textured_panel(name, loc, scale, mat_name, rot=(0, 0, 0), bevel=0.02):
    obj = cube(name, loc, scale, mat_name, bevel)
    obj.rotation_euler = rot
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


def add_pitch_professional_detail():
    seed = 91
    dark, wear = [], []
    for i in range(900):
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rx = seed / 0xFFFFFFFF
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        ry = seed / 0xFFFFFFFF
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rr = seed / 0xFFFFFFFF
        x = -HALF_X + rx * PITCH_X
        y = -HALF_Y + ry * PITCH_Y
        if abs(x) > HALF_X - 1 or abs(y) > HALF_Y - 1:
            continue
        sx = 0.35 + rr * 1.4
        sy = 0.018 + rr * 0.035
        target = dark if i % 4 else wear
        target.append(((x, y, 0.118 + i * 0.000001), (sx, sy, 0.006)))
    mesh_boxes("pitch_grain_soft_dark", dark, "grass_shadow")
    mesh_boxes("pitch_worn_subtle_variation", wear, "grass_wear")


def add_low_grass_geometry():
    blades = []
    seed = 441
    for i in range(2600):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        rx = seed / 0x7FFFFFFF
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        ry = seed / 0x7FFFFFFF
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        rr = seed / 0x7FFFFFFF
        x = -HALF_X + rx * PITCH_X
        y = -HALF_Y + ry * PITCH_Y
        if i % 5 and abs(x) < HALF_X - 2 and abs(y) < HALF_Y - 2:
            continue
        blades.append(((x, y, 0.16 + rr * 0.018), (0.035 + rr * 0.025, 0.012, 0.12 + rr * 0.08)))
    mesh_boxes("short_3d_grass_catchlights", blades, "grass_blade")


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
                letter_seat = seat_text_mask("BENAGALBON CD", col, row, 148, rows, start_col=8, end_col=140)
            else:
                letter_seat = seat_text_mask("CDB", col, row, 148, rows, start_col=54, end_col=94)
            random_white = False if sign > 0 else (row + col) % 97 == 0
            target = secondary if letter_seat or random_white else primary
            back_target = backs_primary if sign > 0 and letter_seat else (backs_secondary if target is secondary else backs_primary)
            target.append(((x, y - sign * 0.04, z + 0.05), (0.40, 0.30, 0.16)))
            back_target.append(((x, y + sign * 0.12, z + 0.30), (0.40, 0.08, 0.38)))
    mesh_boxes(f"{name}_green_seats", primary, "green")
    mesh_boxes(f"{name}_white_seats", secondary, "seat_white")
    mesh_boxes(f"{name}_green_seat_backs", backs_primary, "green")
    mesh_boxes(f"{name}_white_seat_backs", backs_secondary, "seat_white")
    cube(f"{name}_front_fascia", (0, base_y - sign * 1.2, 2.1), (PITCH_X + 32, 0.8, 1.25), "green_dark", 0.04)
    cube(f"{name}_middle_concourse_ring", (0, base_y + sign * 11.4, 8.7), (PITCH_X + 31, 1.25, 1.25), "concrete_dark", 0.03)
    cube(f"{name}_rear_service_wall", (0, base_y + sign * 27.4, 11.8), (PITCH_X + 45, 1.05, 10.5), "concrete", 0.03)
    add_upper_long_ring(name, sign, base_y)
    add_top_long_ring(name, sign, base_y)
    for ix, x in enumerate([-42, -24, 0, 24, 42]):
        add_vomitory(f"{name}_lower_vomitory_{ix}", (x, base_y + sign * 10.7, 6.2), (5.2, 0.56, 3.0), "y", sign)
    for ix, x in enumerate([-36, -12, 12, 36]):
        add_vomitory(f"{name}_upper_vomitory_{ix}", (x, base_y + sign * 21.2, 12.5), (4.4, 0.52, 2.55), "y", sign)
    for row in [5, 11, 18, 25]:
        y = base_y + sign * (row * 0.78 + 0.28)
        z = 1.55 + row * 0.48
        cylinder_between(f"{name}_spectator_rail_low_{row}", (-PITCH_X / 2 - 12, y, z), (PITCH_X / 2 + 12, y, z), 0.038, "steel", 10)
        cylinder_between(f"{name}_spectator_rail_high_{row}", (-PITCH_X / 2 - 12, y, z + 0.42), (PITCH_X / 2 + 12, y, z + 0.42), 0.030, "steel", 10)
    cube(f"{name}_roof_canopy", (0, base_y + sign * 31.6, 22.0), (PITCH_X + 58, 20.0, 0.52), "roof", 0.03)
    cube(f"{name}_roof_front_lip", (0, base_y + sign * 18.3, 20.4), (PITCH_X + 53, 0.62, 1.0), "steel", 0.03)
    cube(f"{name}_roof_rear_lip", (0, base_y + sign * 41.6, 21.5), (PITCH_X + 58, 0.74, 1.15), "steel", 0.03)
    cube(f"{name}_roof_glass_strip", (0, base_y + sign * 24.6, 21.1), (PITCH_X + 40, 6.0, 0.16), "glass")
    for i in range(15):
        x = -PITCH_X / 2 - 8 + i * ((PITCH_X + 16) / 14)
        cylinder_between(f"{name}_roof_truss_{i}", (x, base_y + sign * 17.4, 15.0), (x + 3.2, base_y + sign * 33.0, 22.6), 0.14, "steel")
        cylinder_between(f"{name}_roof_support_{i}", (x, base_y + sign * 21.5, 9.6), (x + 0.8, base_y + sign * 30.8, 21.8), 0.10, "steel")
        cylinder_between(f"{name}_roof_crossbrace_{i}", (x - 1.8, base_y + sign * 19.6, 18.7), (x + 2.8, base_y + sign * 30.4, 21.7), 0.055, "steel")
        cylinder_between(f"{name}_roof_reverse_crossbrace_{i}", (x + 2.4, base_y + sign * 19.8, 18.4), (x - 1.5, base_y + sign * 31.0, 21.9), 0.045, "steel", 10)
        cube(f"{name}_light_bar_{i}", (x, base_y + sign * 17.2, 19.7), (3.8, 0.24, 0.24), "light")
    for rail_idx, z in enumerate([18.8, 20.2, 21.6]):
        cylinder_between(f"{name}_roof_front_long_chord_{rail_idx}", (-PITCH_X / 2 - 18, base_y + sign * 18.8, z), (PITCH_X / 2 + 18, base_y + sign * 18.8, z + 0.15), 0.075, "steel", 12)
        cylinder_between(f"{name}_roof_rear_long_chord_{rail_idx}", (-PITCH_X / 2 - 22, base_y + sign * 34.5, z + 1.0), (PITCH_X / 2 + 22, base_y + sign * 34.5, z + 1.15), 0.068, "steel", 12)
    for i in range(18):
        x = -PITCH_X / 2 - 16 + i * ((PITCH_X + 32) / 17)
        cylinder_between(f"{name}_roof_sawtooth_lower_{i}", (x, base_y + sign * 18.9, 19.05), (x + 4.0, base_y + sign * 28.8, 22.0), 0.040, "steel", 8)
        cylinder_between(f"{name}_roof_sawtooth_upper_{i}", (x + 4.0, base_y + sign * 18.9, 19.20), (x, base_y + sign * 28.8, 21.8), 0.038, "steel", 8)
    # Las letras grandes deben leerse como mosaico de asientos, no como texto flotante.
    # El patron de asientos blancos ya crea la banda visual sin bloquear la vista.


def add_upper_long_ring(name, sign, base_y):
    rows = 12
    primary, secondary = [], []
    for row in range(rows):
        y = base_y + sign * (15.2 + row * 0.72)
        z = 10.25 + row * 0.42
        width = PITCH_X + 22 - row * 0.28
        cube(f"{name}_upper_step_{row:02d}", (0, y, z - 0.11), (width, 0.68, 0.22), "concrete")
        for col in range(130):
            nx = col / 129 - 0.5
            if abs(nx) < 0.018 or abs(nx - 0.30) < 0.014 or abs(nx + 0.30) < 0.014:
                continue
            x = nx * (width - 3)
            target = secondary if (row + col) % 61 == 0 else primary
            target.append(((x, y - sign * 0.04, z + 0.05), (0.36, 0.28, 0.14)))
    mesh_boxes(f"{name}_upper_green_seats", primary, "green")
    mesh_boxes(f"{name}_upper_white_seats", secondary, "seat_white")


def add_top_long_ring(name, sign, base_y):
    rows = 8
    primary, secondary, backs = [], [], []
    for row in range(rows):
        y = base_y + sign * (24.6 + row * 0.66)
        z = 15.3 + row * 0.36
        width = PITCH_X + 12 - row * 0.35
        cube(f"{name}_top_step_{row:02d}", (0, y, z - 0.10), (width, 0.62, 0.20), "concrete_dark")
        for col in range(108):
            nx = col / 107 - 0.5
            if abs(nx) < 0.020 or abs(nx - 0.34) < 0.014 or abs(nx + 0.34) < 0.014:
                continue
            x = nx * (width - 2.6)
            target = secondary if (row + col) % 47 == 0 else primary
            target.append(((x, y - sign * 0.04, z + 0.05), (0.32, 0.25, 0.13)))
            backs.append(((x, y + sign * 0.10, z + 0.28), (0.32, 0.07, 0.30)))
    mesh_boxes(f"{name}_top_green_seats", primary, "green")
    mesh_boxes(f"{name}_top_white_seats", secondary, "seat_white")
    mesh_boxes(f"{name}_top_seat_backs", backs, "green")
    cube(f"{name}_top_rear_shadow_gap", (0, base_y + sign * 30.3, 18.6), (PITCH_X + 18, 0.92, 1.7), "asphalt", 0.02)


def add_end_stand(name, sign):
    base_x = sign * (HALF_X + 8)
    rows = 20
    primary, secondary, backs = [], [], []
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
            backs.append(((x + sign * 0.14, ny * (depth - 3), z + 0.30), (0.08, 0.40, 0.34)))
    mesh_boxes(f"{name}_green_seats", primary, "green")
    mesh_boxes(f"{name}_white_seats", secondary, "seat_white")
    mesh_boxes(f"{name}_seat_backs", backs, "green")
    cube(f"{name}_front_fascia", (base_x - sign * 1.2, 0, 2.0), (0.8, PITCH_Y + 30, 1.15), "green_dark", 0.04)
    cube(f"{name}_middle_concourse_ring", (base_x + sign * 10.5, 0, 8.2), (1.2, PITCH_Y + 29, 1.1), "concrete_dark", 0.03)
    cube(f"{name}_rear_wall", (base_x + sign * 19.0, 0, 8.4), (1.0, PITCH_Y + 39, 12.4), "concrete", 0.03)
    for iy, y in enumerate([-24, -8, 8, 24]):
        add_vomitory(f"{name}_vomitory_{iy}", (base_x + sign * 10.2, y, 5.9), (0.52, 4.2, 2.7), "x", sign)
    cube(f"{name}_roof", (base_x + sign * 24.0, 0, 17.4), (19, PITCH_Y + 47, 0.44), "roof", 0.03)
    for i in range(9):
        y = -PITCH_Y / 2 - 11 + i * ((PITCH_Y + 22) / 8)
        cylinder_between(f"{name}_roof_truss_{i}", (base_x + sign * 12.8, y, 12.0), (base_x + sign * 26.5, y + 1.5, 17.8), 0.11, "steel")
        cylinder_between(f"{name}_roof_crossbrace_{i}", (base_x + sign * 15.5, y - 3.0, 14.0), (base_x + sign * 27.2, y + 3.0, 18.1), 0.042, "steel", 8)
        cube(f"{name}_roof_light_bar_{i}", (base_x + sign * 14.0, y, 16.2), (0.22, 3.2, 0.22), "light")


def add_corner_stands():
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            center_x = sx * (HALF_X + 4.4)
            center_y = sy * (HALF_Y + 4.4)
            primary, secondary = [], []
            aisle, backs = [], []
            angle_start, angle_end = 0, math.pi / 2
            if sx < 0 and sy > 0:
                angle_start, angle_end = math.pi / 2, math.pi
            elif sx < 0 and sy < 0:
                angle_start, angle_end = math.pi, 1.5 * math.pi
            elif sx > 0 and sy < 0:
                angle_start, angle_end = 1.5 * math.pi, 2 * math.pi
            for row in range(24):
                radius = 6.5 + row * 0.86
                z = 1.10 + row * 0.44
                step_count = 30 + row // 2
                for col in range(step_count):
                    t = col / max(1, step_count - 1)
                    angle = angle_start + (angle_end - angle_start) * t
                    x = center_x + math.cos(angle) * radius
                    y = center_y + math.sin(angle) * radius
                    if abs(x) < HALF_X + 2.4 or abs(y) < HALF_Y + 2.4:
                        continue
                    if col in {7, 15, 23} or row in {8, 16}:
                        aisle.append(((x, y, z - 0.04), (0.58, 0.50, 0.11)))
                        continue
                    target = secondary if (row + col) % 43 == 0 else primary
                    target.append(((x, y, z + 0.06), (0.36, 0.36, 0.15)))
                    backs.append(((x, y, z + 0.32), (0.36, 0.08, 0.34)))
            mesh_boxes(f"corner_{sx}_{sy}_curved_green_seats", primary, "green")
            mesh_boxes(f"corner_{sx}_{sy}_curved_white_seats", secondary, "seat_white")
            mesh_boxes(f"corner_{sx}_{sy}_curved_aisles", aisle, "concrete")
            mesh_boxes(f"corner_{sx}_{sy}_seat_backs", backs, "green")
            cube(f"corner_{sx}_{sy}_lower_concourse_mass", (sx * (HALF_X + 13.6), sy * (HALF_Y + 13.6), 5.6), (22, 2.0, 1.2), "concrete_dark", 0.02)
            cube(f"corner_{sx}_{sy}_upper_concourse_mass", (sx * (HALF_X + 20.2), sy * (HALF_Y + 20.2), 12.8), (28, 2.1, 1.3), "concrete_dark", 0.02)
            cube(f"corner_{sx}_{sy}_curved_roof_corner_plate", (sx * (HALF_X + 27.6), sy * (HALF_Y + 27.6), 20.0), (30, 18, 0.46), "roof", 0.03)
            for i in range(5):
                angle = angle_start + (angle_end - angle_start) * (i + 0.5) / 5
                x1 = center_x + math.cos(angle) * 17
                y1 = center_y + math.sin(angle) * 17
                x2 = center_x + math.cos(angle) * 31
                y2 = center_y + math.sin(angle) * 31
                cylinder_between(f"corner_{sx}_{sy}_roof_radial_truss_{i}", (x1, y1, 12.5), (x2, y2, 20.4), 0.095, "steel", 10)


def add_boards():
    labels = ["2J FOOTBALL INTELLIGENCE", "BENAGALBON CD", "SPONSOR", "PARTNER"]
    idx = 0
    for x in range(-51, 52, 17):
        for sign in [-1, 1]:
            y = sign * (HALF_Y + 4.0)
            cube(f"board_panel_back_{idx}", (x, y + sign * 0.10, 1.26), (15.8, 0.34, 2.64), "rubber", 0.02)
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
        for i in range(7):
            yy = -w / 2 + i * (w / 6)
            cylinder_between(f"goal_net_roof_{sign}_{i}", (x, yy, h), (x + back, yy, h * 0.82), 0.012, "net", 6)
            cylinder_between(f"goal_net_back_{sign}_{i}", (x + back, yy, 0.1), (x + back, yy, h * 0.82), 0.010, "net", 6)
        for i in range(5):
            zz = 0.38 + i * (h * 0.70 / 4)
            cylinder_between(f"goal_net_horizontal_{sign}_{i}", (x + back, -w / 2, zz), (x + back, w / 2, zz), 0.010, "net", 6)
        for i in range(9):
            yy = -w / 2 + i * (w / 8)
            cylinder_between(f"goal_net_front_vertical_{sign}_{i}", (x + sign * 0.03, yy, 0.04), (x + sign * 0.03, yy, h), 0.008, "net", 5)
        for i in range(6):
            zz = i * h / 5
            cylinder_between(f"goal_net_front_horizontal_{sign}_{i}", (x + sign * 0.03, -w / 2, zz), (x + sign * 0.03, w / 2, zz), 0.008, "net", 5)
    for side, x in enumerate([-22, 22]):
        cube(f"dugout_base_{side}", (x, -HALF_Y - 8.0, 0.55), (13, 1.25, 0.38), "green_dark", 0.04)
        cube(f"dugout_floor_rubber_{side}", (x, -HALF_Y - 7.65, 0.78), (12.4, 0.55, 0.08), "rubber", 0.02)
        cube(f"dugout_glass_front_{side}", (x, -HALF_Y - 8.6, 1.62), (13.5, 0.20, 2.1), "glass", 0.02)
        cube(f"dugout_glass_roof_{side}", (x, -HALF_Y - 8.0, 2.75), (13.5, 1.55, 0.18), "glass", 0.02)
        for rib in range(7):
            rx = x - 6.0 + rib * 2.0
            cylinder_between(f"dugout_arc_rib_{side}_{rib}_front", (rx, -HALF_Y - 8.68, 0.85), (rx, -HALF_Y - 8.68, 2.75), 0.035, "steel", 8)
            cylinder_between(f"dugout_arc_rib_{side}_{rib}_roof", (rx, -HALF_Y - 8.68, 2.75), (rx, -HALF_Y - 7.25, 2.40), 0.035, "steel", 8)
        for i in range(9):
            cube(f"dugout_seat_{side}_{i}", (x - 4.4 + i * 1.1, -HALF_Y - 7.8, 0.92), (0.62, 0.50, 0.28), "green", 0.03)


def add_players_tunnel_and_technical_area():
    y = -HALF_Y - 6.35
    cube("players_tunnel_recess_black", (0, y - 0.72, 1.75), (8.4, 1.0, 3.3), "asphalt", 0.04)
    cube("players_tunnel_concrete_frame_top", (0, y - 0.98, 3.55), (10.0, 0.55, 0.58), "concrete", 0.035)
    cube("players_tunnel_concrete_frame_left", (-5.15, y - 0.98, 1.95), (0.58, 0.55, 3.5), "concrete", 0.035)
    cube("players_tunnel_concrete_frame_right", (5.15, y - 0.98, 1.95), (0.58, 0.55, 3.5), "concrete", 0.035)
    cube("players_tunnel_rubber_walkway", (0, y + 2.2, 0.08), (8.2, 7.4, 0.04), "rubber", 0.02)
    cube("technical_area_left_dash", (-15, -HALF_Y - 1.0, 0.11), (12.0, 0.10, 0.035), "white")
    cube("technical_area_right_dash", (15, -HALF_Y - 1.0, 0.11), (12.0, 0.10, 0.035), "white")
    add_text("tunnel_crest_letters", "CDB", (0, y + 1.25, 0.16), 1.1, "seat_white", rot=(0, 0, 0), extrude=0.01)
    for x in [-7.0, 7.0]:
        cylinder_between(f"tunnel_guardrail_{x}_top", (x, y - 1.0, 1.25), (x, y + 5.5, 1.25), 0.035, "steel", 8)
        for i in range(4):
            yy = y - 0.6 + i * 1.9
            cylinder_between(f"tunnel_guardrail_{x}_post_{i}", (x, yy, 0.12), (x, yy, 1.3), 0.026, "steel", 8)


def add_inner_bowl_finishing_details():
    for sign in [-1, 1]:
        y = sign * (HALF_Y + 1.05)
        cube(f"pitch_inner_black_drain_channel_{sign}", (0, y, 0.13), (PITCH_X + 7.0, 0.28, 0.11), "rubber", 0.015)
        cube(f"pitch_inner_concrete_kerb_{sign}", (0, sign * (HALF_Y + 1.55), 0.22), (PITCH_X + 9.0, 0.34, 0.22), "concrete", 0.02)
        for i, x in enumerate([-48, -32, -16, 0, 16, 32, 48]):
            cube(f"board_steel_frame_top_{sign}_{i}", (x, sign * (HALF_Y + 3.82), 2.66), (14.9, 0.16, 0.16), "steel", 0.012)
            cube(f"board_steel_frame_bottom_{sign}_{i}", (x, sign * (HALF_Y + 3.82), 0.16), (14.9, 0.16, 0.14), "steel", 0.012)
            for px in [-7.25, 7.25]:
                cylinder_between(f"board_steel_frame_post_{sign}_{i}_{px}", (x + px, sign * (HALF_Y + 3.82), 0.08), (x + px, sign * (HALF_Y + 3.82), 2.72), 0.026, "steel", 8)
    for sign in [-1, 1]:
        x = sign * (HALF_X + 1.05)
        cube(f"goal_inner_black_drain_channel_{sign}", (x, 0, 0.13), (0.28, PITCH_Y + 7.0, 0.11), "rubber", 0.015)
        cube(f"goal_inner_concrete_kerb_{sign}", (sign * (HALF_X + 1.55), 0, 0.22), (0.34, PITCH_Y + 9.0, 0.22), "concrete", 0.02)
    for side, x in enumerate([-22, 22]):
        base_y = -HALF_Y - 9.22
        for i in range(4):
            cube(f"dugout_equipment_case_{side}_{i}", (x - 5.4 + i * 3.6, base_y, 0.62), (1.25, 0.62, 0.72), "rubber", 0.025)
            cylinder_between(f"dugout_case_handle_{side}_{i}", (x - 5.8 + i * 3.6, base_y - 0.34, 1.05), (x - 5.0 + i * 3.6, base_y - 0.34, 1.05), 0.025, "steel", 8)
        cylinder_between(f"dugout_front_guardrail_{side}", (x - 7.1, -HALF_Y - 6.95, 1.25), (x + 7.1, -HALF_Y - 6.95, 1.25), 0.035, "steel", 10)
        for i in range(6):
            px = x - 6.0 + i * 2.4
            cylinder_between(f"dugout_front_guardrail_post_{side}_{i}", (px, -HALF_Y - 6.95, 0.25), (px, -HALF_Y - 6.95, 1.35), 0.024, "steel", 8)
            cube(f"dugout_seat_back_cushion_{side}_{i}", (px, -HALF_Y - 7.52, 1.22), (0.72, 0.18, 0.42), "green", 0.025)
    for x in [-48, -24, 0, 24, 48]:
        cube(f"touchline_access_plate_{x}", (x, -HALF_Y - 2.95, 0.16), (4.6, 1.4, 0.06), "concrete_dark", 0.012)
        cylinder_between(f"touchline_access_rail_left_{x}", (x - 2.2, -HALF_Y - 3.65, 0.22), (x - 2.2, -HALF_Y - 1.95, 1.05), 0.022, "steel", 8)
        cylinder_between(f"touchline_access_rail_right_{x}", (x + 2.2, -HALF_Y - 3.65, 0.22), (x + 2.2, -HALF_Y - 1.95, 1.05), 0.022, "steel", 8)


def add_architectural_quality_pass():
    for sign in [-1, 1]:
        base_y = sign * (HALF_Y + 8)
        cube(f"main_stand_shadowed_under_tier_{sign}", (0, base_y + sign * 12.9, 7.5), (PITCH_X + 30, 1.25, 0.85), "asphalt", 0.02)
        cube(f"main_stand_upper_shadowed_under_tier_{sign}", (0, base_y + sign * 24.0, 14.2), (PITCH_X + 20, 1.05, 0.75), "asphalt", 0.02)
        for x in [-51, -34, -17, 17, 34, 51]:
            cylinder_between(f"main_stand_vertical_roof_hanger_{sign}_{x}", (x, base_y + sign * 18.6, 10.2), (x, base_y + sign * 22.5, 20.0), 0.055, "steel", 10)
            cube(f"main_stand_vomitory_depth_shadow_{sign}_{x}", (x, base_y + sign * 11.0, 5.4), (4.2, 0.26, 1.9), "asphalt", 0.018)
            cube(f"main_stand_vomitory_threshold_{sign}_{x}", (x, base_y + sign * 9.98, 4.62), (4.6, 0.34, 0.26), "concrete", 0.018)
        for row, z in enumerate([3.45, 5.9, 8.35, 10.8, 13.25, 15.7]):
            y = base_y + sign * (3.9 + row * 3.05)
            cylinder_between(f"main_stand_glass_balustrade_top_{sign}_{row}", (-PITCH_X / 2 - 9, y, z + 0.62), (PITCH_X / 2 + 9, y, z + 0.62), 0.018, "steel", 8)
            cube(f"main_stand_glass_balustrade_{sign}_{row}", (0, y, z + 0.36), (PITCH_X + 15, 0.08, 0.58), "glass", 0.006)
    for sign in [-1, 1]:
        base_x = sign * (HALF_X + 8)
        for y in [-34, -18, 0, 18, 34]:
            cube(f"end_stand_entry_shadow_{sign}_{y}", (base_x + sign * 10.8, y, 4.8), (0.24, 3.4, 1.55), "asphalt", 0.018)
            cube(f"end_stand_entry_lintel_{sign}_{y}", (base_x + sign * 10.5, y, 5.82), (0.38, 4.2, 0.26), "concrete", 0.018)
        for z in [6.8, 10.6, 14.4]:
            cylinder_between(f"end_stand_long_balustrade_{sign}_{z}", (base_x + sign * 8.7, -HALF_Y - 10, z), (base_x + sign * 8.7, HALF_Y + 10, z), 0.026, "steel", 10)
    for i, x in enumerate([-48, -32, -16, 0, 16, 32, 48]):
        cube(f"broadcast_touchline_led_reflector_{i}", (x, -HALF_Y - 4.15, 2.83), (13.5, 0.12, 0.32), "light", 0.01)
        cube(f"broadcast_touchline_board_lip_{i}", (x, -HALF_Y - 4.32, 2.53), (14.2, 0.18, 0.18), "steel", 0.01)
    for side, x in enumerate([-22, 22]):
        cube(f"dugout_rear_black_shadow_{side}", (x, -HALF_Y - 7.22, 1.72), (13.2, 0.18, 1.95), "asphalt", 0.02)
        cube(f"dugout_club_disc_{side}", (x - 5.7, -HALF_Y - 8.76, 1.65), (1.1, 0.08, 1.1), "green", 0.02)
        add_text(f"dugout_club_letters_{side}", "CDB", (x - 5.7, -HALF_Y - 8.83, 1.66), 0.26, "white", rot=(math.radians(90), 0, 0), extrude=0.006)
        for rib in range(6):
            rx = x - 5.0 + rib * 2.0
            cylinder_between(f"dugout_curved_roof_crossbar_{side}_{rib}", (rx, -HALF_Y - 8.58, 2.74), (rx + 0.85, -HALF_Y - 7.30, 2.42), 0.025, "steel", 8)
    for x in [-36, -18, 0, 18, 36]:
        cylinder_between(f"pitchside_microphone_stand_{x}", (x, -HALF_Y - 5.2, 0.18), (x, -HALF_Y - 5.2, 1.05), 0.018, "steel", 8)
        cube(f"pitchside_microphone_head_{x}", (x, -HALF_Y - 5.2, 1.12), (0.22, 0.12, 0.12), "rubber", 0.01)


def add_broadcast_and_matchday_details():
    for i, (x, y, rz) in enumerate([(-35, -HALF_Y - 13, 0), (35, -HALF_Y - 13, 0), (-HALF_X - 9, 0, 90), (HALF_X + 9, 0, -90)]):
        cube(f"camera_platform_{i}", (x, y, 3.25), (4.2, 2.2, 0.28), "concrete_dark", 0.03)
        cylinder_between(f"camera_tripod_{i}_a", (x, y, 3.25), (x - 0.75, y - 0.45, 2.05), 0.035, "steel", 8)
        cylinder_between(f"camera_tripod_{i}_b", (x, y, 3.25), (x + 0.75, y - 0.45, 2.05), 0.035, "steel", 8)
        cylinder_between(f"camera_tripod_{i}_c", (x, y, 3.25), (x, y + 0.75, 2.05), 0.035, "steel", 8)
        cam_body = cube(f"broadcast_camera_body_{i}", (x, y, 3.8), (0.75, 0.42, 0.34), "roof", 0.025)
        cam_body.rotation_euler.z = math.radians(rz)
        lens = cylinder_between(f"broadcast_camera_lens_{i}", (x, y, 3.8), (x + math.cos(math.radians(rz)) * 0.85, y + math.sin(math.radians(rz)) * 0.85, 3.8), 0.12, "steel", 16)
        lens.rotation_euler.z += math.radians(90)
    for i, (x, y) in enumerate([(-HALF_X, -HALF_Y), (-HALF_X, HALF_Y), (HALF_X, -HALF_Y), (HALF_X, HALF_Y)]):
        pole_x = x + (1.0 if x < 0 else -1.0)
        pole_y = y + (1.0 if y < 0 else -1.0)
        cylinder_between(f"corner_flag_pole_{i}", (pole_x, pole_y, 0.12), (pole_x, pole_y, 2.0), 0.025, "white", 10)
        cube(f"corner_flag_club_{i}", (pole_x + (0.28 if x < 0 else -0.28), pole_y, 1.74), (0.56, 0.035, 0.34), "green", 0.01)
    for i, x in enumerate([-52, -26, 0, 26, 52]):
        cube(f"roof_speaker_cluster_north_{i}", (x, HALF_Y + 18.2, 18.6), (0.7, 0.42, 0.9), "roof", 0.025)
        cube(f"roof_speaker_cluster_south_{i}", (x, -HALF_Y - 18.2, 18.6), (0.7, 0.42, 0.9), "roof", 0.025)


def add_outer_facade_and_pitch_details():
    cube("continuous_outer_roof_rim_north", (0, HALF_Y + 48.0, 21.1), (PITCH_X + 72, 1.6, 2.2), "roof", 0.04)
    cube("continuous_outer_roof_rim_south", (0, -HALF_Y - 48.0, 21.1), (PITCH_X + 72, 1.6, 2.2), "roof", 0.04)
    cube("continuous_outer_roof_rim_east", (HALF_X + 37.0, 0, 17.5), (1.6, PITCH_Y + 78, 2.0), "roof", 0.04)
    cube("continuous_outer_roof_rim_west", (-HALF_X - 37.0, 0, 17.5), (1.6, PITCH_Y + 78, 2.0), "roof", 0.04)
    cube("outside_concrete_facade_north", (0, HALF_Y + 49.0, 9.1), (PITCH_X + 68, 1.0, 14.6), "concrete", 0.03)
    cube("outside_concrete_facade_south", (0, -HALF_Y - 49.0, 9.1), (PITCH_X + 68, 1.0, 14.6), "concrete", 0.03)
    for x in [-60, -40, -20, 0, 20, 40, 60]:
        cube(f"facade_vertical_shadow_north_{x}", (x, HALF_Y + 48.45, 8.8), (1.0, 0.22, 11.4), "concrete_dark", 0.01)
        cube(f"facade_vertical_shadow_south_{x}", (x, -HALF_Y - 48.45, 8.8), (1.0, 0.22, 11.4), "concrete_dark", 0.01)
    for sign in [-1, 1]:
        y = sign * (HALF_Y + 2.65)
        cylinder_between(f"pitch_front_guardrail_{sign}_top", (-HALF_X - 4, y, 1.55), (HALF_X + 4, y, 1.55), 0.04, "steel", 10)
        cylinder_between(f"pitch_front_guardrail_{sign}_mid", (-HALF_X - 4, y, 1.02), (HALF_X + 4, y, 1.02), 0.032, "steel", 10)
        for i in range(22):
            x = -HALF_X - 4 + i * ((PITCH_X + 8) / 21)
            cylinder_between(f"pitch_front_guardrail_{sign}_post_{i}", (x, y, 0.15), (x, y, 1.65), 0.025, "steel", 8)
    for sign in [-1, 1]:
        x = sign * (HALF_X + 2.65)
        cylinder_between(f"pitch_goal_guardrail_{sign}_top", (x, -HALF_Y - 3, 1.48), (x, HALF_Y + 3, 1.48), 0.04, "steel", 10)
        cylinder_between(f"pitch_goal_guardrail_{sign}_mid", (x, -HALF_Y - 3, 0.98), (x, HALF_Y + 3, 0.98), 0.032, "steel", 10)
        for i in range(16):
            y = -HALF_Y - 3 + i * ((PITCH_Y + 6) / 15)
            cylinder_between(f"pitch_goal_guardrail_{sign}_post_{i}", (x, y, 0.15), (x, y, 1.55), 0.025, "steel", 8)
    # Keep the central bowl open for the interactive camera. Foreground roof geometry
    # blocked too much of the pitch in still previews.


def add_broadcast_foreground_roof():
    y = -HALF_Y - 31.5
    cube("broadcast_near_roof_dark_overhang", (-18, y, 27.5), (128, 15.5, 0.78), "roof", 0.04)
    cube("broadcast_near_roof_front_steel_lip", (-18, y + 7.6, 26.75), (126, 0.72, 1.28), "steel", 0.03)
    for i in range(14):
        x = -78 + i * 9.2
        cylinder_between(f"broadcast_near_roof_truss_{i}", (x, y + 6.9, 21.0), (x + 4.8, y - 6.2, 28.0), 0.095, "steel", 10)
        cylinder_between(f"broadcast_near_roof_cross_{i}", (x + 5.0, y + 6.8, 22.6), (x - 1.8, y - 4.2, 27.3), 0.052, "steel", 8)
        cube(f"broadcast_near_roof_light_{i}", (x + 1.8, y + 6.9, 23.5), (3.2, 0.20, 0.20), "light")


def add_screen_and_crest():
    cube("scoreboard_frame", (0, HALF_Y + 29, 14.5), (14, 0.7, 8.2), "steel", 0.04)
    cube("scoreboard_screen", (0, HALF_Y + 28.55, 14.5), (12.8, 0.16, 7.0), "screen", 0.02)
    add_text("scoreboard_cdb", "CDB", (0, HALF_Y + 28.42, 15.4), 2.0, "white", rot=(math.radians(90), 0, 0))
    add_text("scoreboard_name", "BENAGALBON CD", (0, HALF_Y + 28.40, 12.7), 0.64, "white", rot=(math.radians(90), 0, 0))
    add_text("scoreboard_cdb_rear", "CDB", (0, HALF_Y + 28.78, 15.4), 2.0, "white", rot=(math.radians(90), 0, math.radians(180)))
    add_text("scoreboard_name_rear", "BENAGALBON CD", (0, HALF_Y + 28.80, 12.7), 0.64, "white", rot=(math.radians(90), 0, math.radians(180)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=3.8, depth=0.14, location=(0, HALF_Y + 30.5, 22.0))
    crest = bpy.context.object
    crest.name = "round_cdb_crest_disc"
    crest.rotation_euler.x = math.radians(90)
    crest.data.materials.append(M["green"])
    add_text("crest_text", "CDB", (0, HALF_Y + 30.36, 22.0), 1.45, "white", rot=(math.radians(90), 0, 0))
    add_text("crest_text_rear", "CDB", (0, HALF_Y + 30.64, 22.0), 1.45, "white", rot=(math.radians(90), 0, math.radians(180)))


def add_environment():
    for i in range(14):
        x = -170 + i * 20
        y = 128 + math.sin(i * 1.7) * 8
        z = 50 + (i % 4) * 2.5
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1, location=(x, y, z))
        cloud = bpy.context.object
        cloud.name = f"soft_cloud_{i:02d}"
        cloud.scale = (9 + (i % 3) * 3, 1.55, 0.72 + (i % 2) * 0.35)
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


def add_reference_render_polish():
    stripe_w = PITCH_X / 12
    for i in range(12):
        x = -HALF_X + stripe_w * (i + 0.5)
        mat = "mow_broadcast_light" if i % 2 == 0 else "mow_broadcast_dark"
        cube(f"render_model_mow_band_{i:02d}", (x, 0, 0.125 + i * 0.0001), (stripe_w - 0.05, PITCH_Y - 0.12, 0.012), mat, 0.0)

    sign = 1
    base_y = sign * (HALF_Y + 8)
    rows = 30
    cols = 178
    name_seats = []
    for row in range(5, 23):
        y = base_y + sign * (row * 0.77)
        z = 1.34 + row * 0.48
        width = PITCH_X + 29 - row * 0.34
        for col in range(8, cols - 8):
            nx = col / (cols - 1) - 0.5
            if abs(nx) < 0.020 or abs(nx - 0.23) < 0.014 or abs(nx + 0.23) < 0.014 or abs(nx - 0.39) < 0.014 or abs(nx + 0.39) < 0.014:
                continue
            if not seat_text_mask("BENAGALBON CD", col, row, cols, rows, start_col=12, end_col=166):
                continue
            x = nx * (width - 3.4)
            name_seats.append(((x, y - sign * 0.08, z + 0.24), (0.50, 0.36, 0.09)))
            name_seats.append(((x, y + sign * 0.11, z + 0.52), (0.50, 0.09, 0.44)))
    mesh_boxes("render_model_clean_benagalbon_cd_name_seats", name_seats, "seat_white")

    for roof_sign, prefix in [(1, "main"), (-1, "opposite")]:
        roof_y = roof_sign * (HALF_Y + 8)
        for i in range(18):
            x = -PITCH_X / 2 - 9 + i * ((PITCH_X + 18) / 17)
            cube(f"render_model_{prefix}_front_light_tile_{i}", (x, roof_y + roof_sign * 17.1, 19.85), (2.8, 0.18, 0.18), "light", 0.01)
            cylinder_between(
                f"render_model_{prefix}_thin_roof_dropper_{i}",
                (x, roof_y + roof_sign * 18.0, 18.0),
                (x + 0.8, roof_y + roof_sign * 31.0, 21.8),
                0.028,
                "steel",
                8,
            )

    for sign, label in [(1, "north"), (-1, "south")]:
        y = sign * (HALF_Y + 4.15)
        add_text(
            f"render_model_fascia_club_name_{label}",
            "BENAGALBON CD",
            (0, y - sign * 0.23, 2.10),
            1.05,
            "white",
            rot=(math.radians(90), 0, math.radians(180) if sign < 0 else 0),
            extrude=0.012,
        )
        for x in [-38, 38]:
            add_text(
                f"render_model_fascia_partner_{label}_{x}",
                "2J FOOTBALL INTELLIGENCE",
                (x, y - sign * 0.23, 1.34),
                0.48,
                "white",
                rot=(math.radians(90), 0, math.radians(180) if sign < 0 else 0),
                extrude=0.008,
            )

    for sign, label in [(1, "east"), (-1, "west")]:
        x = sign * (HALF_X + 4.15)
        add_text(
            f"render_model_goal_fascia_name_{label}",
            "CDB",
            (x - sign * 0.23, 0, 2.0),
            1.2,
            "white",
            rot=(math.radians(90), 0, math.radians(-90) if sign > 0 else math.radians(90)),
            extrude=0.012,
        )

    for x, side_name in [(-30, "left"), (30, "right")]:
        cube(f"render_model_press_box_glass_{side_name}", (x, HALF_Y + 18.9, 16.35), (18.0, 0.16, 2.15), "glass", 0.012)
        cube(f"render_model_press_box_roof_shadow_{side_name}", (x, HALF_Y + 18.7, 17.55), (18.5, 0.30, 0.28), "roof", 0.012)
        for pane in range(5):
            px = x - 7.2 + pane * 3.6
            cube(f"render_model_press_box_mullion_{side_name}_{pane}", (px, HALF_Y + 18.58, 16.35), (0.08, 0.15, 2.05), "steel", 0.006)

    for x, zrot, name in [(-HALF_X - 7.6, math.radians(90), "west"), (HALF_X + 7.6, math.radians(-90), "east")]:
        cube(f"render_model_side_scoreboard_frame_{name}", (x, HALF_Y + 5.0, 8.4), (0.38, 8.6, 4.8), "steel", 0.02)
        cube(f"render_model_side_scoreboard_screen_{name}", (x, HALF_Y + 5.0, 8.4), (0.18, 7.8, 4.1), "screen", 0.012)
        add_text(
            f"render_model_side_scoreboard_cdb_{name}",
            "CDB",
            (x - (0.12 if x > 0 else -0.12), HALF_Y + 5.0, 8.75),
            0.92,
            "white",
            rot=(math.radians(90), 0, zrot),
            extrude=0.008,
        )

    for sign, label in [(1, "north"), (-1, "south")]:
        y = sign * (HALF_Y + 2.25)
        for x in range(-48, 49, 12):
            cube(f"render_model_pitchside_led_glow_{label}_{x}", (x, y, 2.72), (8.0, 0.055, 0.24), "light", 0.006)

    for sign, label in [(1, "north"), (-1, "south")]:
        y = sign * (HALF_Y + 47.6)
        for x in range(-60, 61, 12):
            cube(f"render_model_outer_facade_panel_{label}_{x}", (x, y, 10.3), (6.0, 0.16, 8.4), "concrete_dark", 0.01)
            cube(f"render_model_outer_facade_highlight_{label}_{x}", (x - 2.5, y - sign * 0.11, 10.3), (0.10, 0.08, 8.1), "concrete", 0.004)


def add_final_stadium_refinement_pass():
    for sign, label in [(1, "main"), (-1, "opposite")]:
        base_y = sign * (HALF_Y + 8)
        front_y = base_y + sign * 17.25
        rear_y = base_y + sign * 40.9
        for i, x in enumerate([-58, -46, -34, -22, -10, 2, 14, 26, 38, 50, 62]):
            cylinder_between(
                f"final_{label}_roof_under_web_{i}",
                (x, front_y, 19.35),
                (x + 5.2, rear_y, 22.35),
                0.035,
                "steel",
                8,
            )
            cube(f"final_{label}_roof_led_cell_{i}", (x + 1.8, front_y - sign * 0.12, 19.62), (2.35, 0.055, 0.13), "led_white", 0.004)
        for bay in range(10):
            x = -57 + bay * 12.6
            cube(f"final_{label}_roof_panel_seam_{bay}", (x, base_y + sign * 31.4, 22.32), (0.10, 18.2, 0.035), "steel", 0.002)
        for row, z in enumerate([2.0, 4.9, 7.8, 10.7, 13.6, 16.5]):
            y = base_y + sign * (1.8 + row * 4.0)
            for x in [-39, -24, -9, 9, 24, 39]:
                cube(f"final_{label}_aisle_nosing_{row}_{x}", (x, y, z), (4.8, 0.11, 0.045), "safety_yellow", 0.002)
        for x in [-54, -42, -30, -18, -6, 6, 18, 30, 42, 54]:
            cube(f"final_{label}_rear_shadow_louver_{x}", (x, base_y + sign * 27.95, 12.4), (0.22, 0.16, 6.6), "asphalt", 0.004)

    for sign, label in [(1, "north"), (-1, "south")]:
        y = sign * (HALF_Y + 4.0)
        for x in range(-51, 52, 17):
            cube(f"final_{label}_adboard_rear_mask_{x}", (x, y + sign * 0.34, 1.38), (15.6, 0.10, 2.18), "green_dark", 0.006)
            for px in [-5.6, -2.8, 0, 2.8, 5.6]:
                cube(f"final_{label}_adboard_led_pixel_{x}_{px}", (x + px, y - sign * 0.23, 2.17), (0.16, 0.035, 0.11), "led_white", 0.002)

    for sign, label in [(1, "east"), (-1, "west")]:
        x = sign * (HALF_X + 4.0)
        for y in range(-28, 29, 14):
            cube(f"final_{label}_adboard_rear_mask_{y}", (x + sign * 0.34, y, 1.38), (0.10, 12.6, 2.18), "green_dark", 0.006)

    seed = 7221
    touchline_scuffs = []
    for i in range(160):
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        rx = seed / 0xFFFFFFFF
        seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
        ry = seed / 0xFFFFFFFF
        x = -HALF_X + rx * PITCH_X
        y = (-HALF_Y - 2.2) + ry * 4.4
        touchline_scuffs.append(((x, y, 0.172 + i * 0.000003), (0.42 + (i % 5) * 0.11, 0.035, 0.008)))
    mesh_boxes("final_touchline_boot_scuffs", touchline_scuffs, "grass_wear")


def add_lighting_and_camera():
    bpy.ops.object.light_add(type="SUN", location=(-70, -95, 110))
    sun = bpy.context.object
    sun.name = "late_morning_sun"
    sun.data.energy = 4.2
    sun.rotation_euler = (math.radians(48), 0, math.radians(-37))
    for x in [-45, -15, 15, 45]:
        for y in [HALF_Y + 21, -HALF_Y - 21]:
            bpy.ops.object.light_add(type="AREA", location=(x, y, 18))
            light = bpy.context.object
            light.name = "warm_roof_floodlight"
            light.data.energy = 230
            light.data.size = 6
            direction = Vector((0, 0, 0)) - Vector(light.location)
            light.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.camera_add(location=(-96, -64, 58), rotation=(math.radians(62), 0, math.radians(-42)))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    direction = Vector((0, 0, 5.4)) - Vector(cam.location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 23
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = 110
    cam.data.dof.aperture_fstop = 8.0


def main():
    reset_scene()
    init_materials()
    add_pitch()
    add_pitch_professional_detail()
    add_low_grass_geometry()
    add_grass_fine_variation()
    add_long_stand("south_main_stand", 1)
    add_long_stand("north_stand", -1)
    add_end_stand("east_goal_stand", 1)
    add_end_stand("west_goal_stand", -1)
    add_corner_stands()
    add_boards()
    add_goals_and_benches()
    add_players_tunnel_and_technical_area()
    add_inner_bowl_finishing_details()
    add_architectural_quality_pass()
    add_broadcast_and_matchday_details()
    add_outer_facade_and_pitch_details()
    add_screen_and_crest()
    add_environment()
    add_reference_render_polish()
    add_final_stadium_refinement_pass()
    add_lighting_and_camera()

    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB", export_yup=True)
    scene = bpy.context.scene
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1012
    scene.render.filepath = str(OUT_PREVIEW)
    bpy.ops.render.render(write_still=True)
    scene.render.resolution_x = 2400
    scene.render.resolution_y = 1350
    scene.render.filepath = str(OUT_PRODUCTION_RENDER)
    bpy.ops.render.render(write_still=True)
    print(f"BLEND={OUT_BLEND}")
    print(f"GLB={OUT_GLB}")
    print(f"PREVIEW={OUT_PREVIEW}")
    print(f"PRODUCTION_RENDER={OUT_PRODUCTION_RENDER}")


if __name__ == "__main__":
    main()
