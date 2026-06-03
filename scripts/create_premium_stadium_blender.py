import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "football" / "static" / "football" / "models" / "stadium"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_GLB = OUT_DIR / "premium-bowl-stadium.glb"
OUT_PREVIEW = Path("/Volumes/Mac Satecchi/Mac/Downloads/premium-bowl-stadium-blender-preview.png")


PITCH_X = 105.0
PITCH_Y = 68.0
HALF_X = PITCH_X / 2.0
HALF_Y = PITCH_Y / 2.0


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
    bpy.context.scene.display.shading.color_type = "MATERIAL"
    bpy.context.scene.display.shading.light = "STUDIO"
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.view_settings.look = "Medium High Contrast"
    bpy.context.scene.world.color = (0.02, 0.03, 0.05)


def mat(name, color, roughness=0.75, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return material


MATS = {}


def init_materials():
    MATS.update(
        {
            "concrete": mat("stadium_concrete", (0.48, 0.55, 0.61, 1), 0.88),
            "dark": mat("stadium_dark_shadow", (0.025, 0.035, 0.05, 1), 0.9),
            "rail": mat("stadium_metal_rails", (0.82, 0.86, 0.88, 1), 0.45, 0.18),
            "roof": mat("stadium_roof_metal", (0.10, 0.13, 0.17, 1), 0.62, 0.15),
            "roof_glass": mat("stadium_roof_translucent_panels", (0.62, 0.82, 0.96, 0.32), 0.24, 0.02),
            "glass": mat("stadium_glass", (0.55, 0.77, 0.92, 0.36), 0.2),
            "baked_shadow": mat("stadium_baked_shadow", (0.02, 0.04, 0.06, 0.42), 0.95),
            "club_primary": mat("club_primary_seats", (0.0, 0.22, 0.52, 1), 0.82),
            "club_secondary": mat("club_secondary_seats", (0.92, 0.96, 1.0, 1), 0.80),
            "seat_alt": mat("seat_alternate_pattern", (0.06, 0.33, 0.68, 1), 0.82),
            "light": mat("stadium_light_panels", (1.0, 0.96, 0.82, 1), 0.35),
        }
    )
    MATS["roof_glass"].blend_method = "BLEND"
    MATS["glass"].blend_method = "BLEND"
    MATS["glass"].use_screen_refraction = True
    MATS["baked_shadow"].blend_method = "BLEND"


def cube_obj(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    # Small bevels prevent the realtime GLB from looking like stacked flat photos.
    if min(scale) >= 0.12 and max(scale) <= 170:
        bevel = obj.modifiers.new(f"{name}_soft_edges", "BEVEL")
        bevel.width = min(0.055, max(0.018, min(scale) * 0.18))
        bevel.segments = 2
        obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_box_to_mesh(verts, faces, loc, scale):
    x, y, z = loc
    sx, sy, sz = (scale[0] / 2.0, scale[1] / 2.0, scale[2] / 2.0)
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


def mesh_boxes(name, boxes, material):
    if not boxes:
        return None
    verts = []
    faces = []
    for loc, scale in boxes:
        add_box_to_mesh(verts, faces, loc, scale)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if material:
        mesh.materials.append(material)
    return obj


def cylinder_between(name, start, end, radius, material, vertices=12):
    start_v = Vector(start)
    end_v = Vector(end)
    mid = (start_v + end_v) * 0.5
    direction = end_v - start_v
    length = direction.length
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=mid)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    if material:
        obj.data.materials.append(material)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return obj


def annular_sector_obj(name, center, start, end, r_inner, r_outer, z, thickness, material, segments=28):
    cx, cy = center
    verts = []
    faces = []
    for i in range(segments + 1):
        angle = start + (end - start) * i / segments
        ca = math.cos(angle)
        sa = math.sin(angle)
        verts.append((cx + ca * r_inner, cy + sa * r_inner, z))
        verts.append((cx + ca * r_outer, cy + sa * r_outer, z))
        verts.append((cx + ca * r_inner, cy + sa * r_inner, z - thickness))
        verts.append((cx + ca * r_outer, cy + sa * r_outer, z - thickness))
    for i in range(segments):
        a = i * 4
        b = (i + 1) * 4
        faces.extend(
            [
                (a, b, b + 1, a + 1),
                (a + 2, a + 3, b + 3, b + 2),
                (a, a + 2, b + 2, b),
                (a + 1, b + 1, b + 3, a + 3),
            ]
        )
    faces.append((0, 1, 3, 2))
    last = segments * 4
    faces.append((last, last + 2, last + 3, last + 1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if material:
        mesh.materials.append(material)
    obj.modifiers.new(f"{name}_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_side_stand(name, side):
    sign = -1 if side == "north" else 1
    base_y = sign * (HALF_Y + 8.0)
    primary_seats = []
    secondary_seats = []
    primary_backs = []
    secondary_backs = []
    cube_obj(f"{name}_lower_bowl_slab", (0, base_y + sign * 8.4, 1.0), (PITCH_X + 28, 19.0, 2.0), MATS["concrete"])
    row_index = 0
    for tier in range(3):
        rows = 10 if tier == 0 else 8
        tier_out = tier * 7.4
        tier_z = tier * 5.0
        for row in range(rows):
            y = base_y + sign * (2.8 + tier_out + row * 0.74)
            z = 1.35 + tier_z + row * 0.66
            width = PITCH_X + 24 - tier * 2.0 - row * 0.18
            step = cube_obj(f"{name}_tier_{tier}_step_{row}", (0, y, z - 0.22), (width, 0.72, 0.28), MATS["concrete"])
            step.rotation_euler.x = math.radians(sign * -12)
            cols = 132
            for col in range(cols):
                x = (col / (cols - 1) - 0.5) * (width - 2.2)
                aisle = any(abs(x - a * PITCH_X) < 0.95 for a in (-0.42, -0.25, -0.08, 0.08, 0.25, 0.42))
                if aisle:
                    continue
                pattern = (tier == 1 and 2 <= row <= 5 and abs(x) < PITCH_X * 0.34) or ((col + row_index) % 29 == 0)
                target = secondary_seats if pattern else primary_seats
                back_target = secondary_backs if pattern else primary_backs
                target.append(((x, y - sign * 0.10, z + 0.05), (0.40, 0.30, 0.15)))
                back_target.append(((x, y + sign * 0.08, z + 0.28), (0.40, 0.08, 0.42)))
            row_index += 1
        rail_y = base_y + sign * (3.0 + tier_out + rows * 0.95)
        rail_z = 1.8 + tier_z + rows * 0.55
        cube_obj(f"{name}_concourse_rail_{tier}", (0, rail_y, rail_z), (PITCH_X + 22 - tier * 2, 0.20, 0.35), MATS["rail"])
        cube_obj(f"{name}_dark_concourse_shadow_{tier}", (0, base_y + sign * (8.2 + tier_out), 2.6 + tier_z), (PITCH_X + 23 - tier * 2, 0.45, 1.20), MATS["dark"])
    for x in [-40, -25, -8, 8, 25, 40]:
        cube_obj(f"{name}_vomitory_{x}", (x, base_y + sign * 7.0, 3.0), (3.4, 2.0, 2.0), MATS["dark"])
        cube_obj(f"{name}_aisle_{x}", (x, base_y + sign * 13.5, 5.0), (1.15, 15.0, 0.26), MATS["rail"])
    cube_obj(f"{name}_front_fascia", (0, base_y + sign * 2.25, 2.05), (PITCH_X + 26, 0.55, 1.10), MATS["club_primary"])
    cube_obj(f"{name}_middle_fascia", (0, base_y + sign * 13.6, 6.45), (PITCH_X + 22, 0.55, 1.05), MATS["club_primary"])
    cube_obj(f"{name}_upper_fascia", (0, base_y + sign * 22.6, 10.75), (PITCH_X + 18, 0.55, 1.00), MATS["club_primary"])
    cube_obj(f"{name}_rear_wall", (0, base_y + sign * 28.0, 8.6), (PITCH_X + 34, 0.85, 14.2), MATS["concrete"])
    mesh_boxes(f"{name}_club_primary_seats_mesh", primary_seats, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_seats_mesh", secondary_seats, MATS["club_secondary"])
    mesh_boxes(f"{name}_club_primary_seat_backs_mesh", primary_backs, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_seat_backs_mesh", secondary_backs, MATS["club_secondary"])
    roof_y = base_y + sign * 29.5
    cube_obj(f"{name}_roof_canopy", (0, roof_y, 17.2), (PITCH_X + 42, 16.5, 0.38), MATS["roof"])
    cube_obj(f"{name}_roof_translucent_strip", (0, roof_y - sign * 2.0, 17.0), (PITCH_X + 36, 5.4, 0.14), MATS["roof_glass"])
    cube_obj(f"{name}_roof_baked_shadow_band", (0, base_y + sign * 15.5, 7.8), (PITCH_X + 20, 0.16, 2.6), MATS["baked_shadow"])
    cylinder_between(f"{name}_roof_front_truss", (-(PITCH_X / 2 + 18), roof_y - sign * 7.6, 14.1), ((PITCH_X / 2 + 18), roof_y - sign * 7.6, 14.1), 0.22, MATS["rail"], vertices=16)
    cylinder_between(f"{name}_roof_rear_truss", (-(PITCH_X / 2 + 18), roof_y + sign * 6.8, 15.9), ((PITCH_X / 2 + 18), roof_y + sign * 6.8, 15.9), 0.18, MATS["rail"], vertices=16)
    for i in range(13):
        x = -PITCH_X / 2 + i * PITCH_X / 12
        cylinder_between(f"{name}_roof_truss_{i}", (x, roof_y - sign * 7, 12.2), (x + 3.0, roof_y + sign * 7, 16.4), 0.13, MATS["rail"])
        cylinder_between(f"{name}_roof_support_{i}", (x, base_y + sign * 24.7, 8.5), (x, roof_y + sign * 1.8, 15.2), 0.10, MATS["rail"], vertices=10)
        cube_obj(f"{name}_light_{i}", (x, roof_y - sign * 6.2, 14.0), (2.4, 0.22, 0.22), MATS["light"])
        if i < 12:
            x2 = -PITCH_X / 2 + (i + 1) * PITCH_X / 12
            cylinder_between(f"{name}_roof_cross_brace_a_{i}", (x, roof_y - sign * 7.3, 13.2), (x2, roof_y + sign * 6.2, 15.7), 0.075, MATS["rail"], vertices=8)
            cylinder_between(f"{name}_roof_cross_brace_b_{i}", (x2, roof_y - sign * 7.3, 13.2), (x, roof_y + sign * 6.2, 15.7), 0.075, MATS["rail"], vertices=8)


def add_end_stand(name, side):
    sign = -1 if side == "west" else 1
    base_x = sign * (HALF_X + 8.0)
    primary_seats = []
    secondary_seats = []
    primary_backs = []
    secondary_backs = []
    cube_obj(f"{name}_lower_bowl_slab", (base_x + sign * 8.3, 0, 1.0), (19, PITCH_Y + 24, 2.0), MATS["concrete"])
    for tier in range(3):
        rows = 9
        tier_out = tier * 7.0
        tier_z = tier * 4.8
        for row in range(rows):
            x = base_x + sign * (2.8 + tier_out + row * 0.72)
            z = 1.30 + tier_z + row * 0.64
            depth = PITCH_Y + 18 - tier * 1.7 - row * 0.18
            step = cube_obj(f"{name}_tier_{tier}_step_{row}", (x, 0, z - 0.22), (0.72, depth, 0.28), MATS["concrete"])
            step.rotation_euler.y = math.radians(sign * 12)
            cols = 92
            for col in range(cols):
                y = (col / (cols - 1) - 0.5) * (depth - 2.0)
                aisle = any(abs(y - a * PITCH_Y) < 0.85 for a in (-0.34, -0.12, 0.12, 0.34))
                if aisle:
                    continue
                pattern = (tier == 1 and 2 <= row <= 5 and abs(y) < PITCH_Y * 0.28) or ((col + row) % 23 == 0)
                target = secondary_seats if pattern else primary_seats
                back_target = secondary_backs if pattern else primary_backs
                target.append(((x - sign * 0.10, y, z + 0.05), (0.30, 0.40, 0.15)))
                back_target.append(((x + sign * 0.08, y, z + 0.28), (0.08, 0.40, 0.42)))
        cube_obj(f"{name}_concourse_rail_{tier}", (base_x + sign * (9 + tier * 8), 0, 4 + tier * 4), (0.20, PITCH_Y + 18 - tier * 2, 0.35), MATS["rail"])
        cube_obj(f"{name}_dark_concourse_shadow_{tier}", (base_x + sign * (8.0 + tier_out), 0, 2.5 + tier_z), (0.45, PITCH_Y + 18 - tier * 2, 1.16), MATS["dark"])
    cube_obj(f"{name}_front_fascia", (base_x + sign * 2.25, 0, 2.05), (0.55, PITCH_Y + 20, 1.10), MATS["club_primary"])
    cube_obj(f"{name}_middle_fascia", (base_x + sign * 13.1, 0, 6.35), (0.55, PITCH_Y + 16, 1.05), MATS["club_primary"])
    cube_obj(f"{name}_upper_fascia", (base_x + sign * 21.8, 0, 10.6), (0.55, PITCH_Y + 12, 1.00), MATS["club_primary"])
    cube_obj(f"{name}_rear_wall", (base_x + sign * 27.2, 0, 8.2), (0.85, PITCH_Y + 28, 13.8), MATS["concrete"])
    mesh_boxes(f"{name}_club_primary_seats_mesh", primary_seats, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_seats_mesh", secondary_seats, MATS["club_secondary"])
    mesh_boxes(f"{name}_club_primary_seat_backs_mesh", primary_backs, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_seat_backs_mesh", secondary_backs, MATS["club_secondary"])
    roof_x = base_x + sign * 29.0
    cube_obj(f"{name}_roof_canopy", (roof_x, 0, 16.5), (16.2, PITCH_Y + 36, 0.38), MATS["roof"])
    cube_obj(f"{name}_roof_translucent_strip", (roof_x - sign * 2.0, 0, 16.35), (5.4, PITCH_Y + 30, 0.14), MATS["roof_glass"])
    cube_obj(f"{name}_roof_baked_shadow_band", (base_x + sign * 15.0, 0, 7.4), (0.16, PITCH_Y + 16, 2.4), MATS["baked_shadow"])
    cylinder_between(f"{name}_roof_front_truss", (roof_x - sign * 7.7, -(PITCH_Y / 2 + 15), 13.6), (roof_x - sign * 7.7, (PITCH_Y / 2 + 15), 13.6), 0.20, MATS["rail"], vertices=16)
    cylinder_between(f"{name}_roof_rear_truss", (roof_x + sign * 6.8, -(PITCH_Y / 2 + 15), 15.4), (roof_x + sign * 6.8, (PITCH_Y / 2 + 15), 15.4), 0.16, MATS["rail"], vertices=16)
    for i in range(9):
        y = -PITCH_Y / 2 + i * PITCH_Y / 8
        cylinder_between(f"{name}_roof_truss_{i}", (roof_x - sign * 7, y, 11.8), (roof_x + sign * 7, y + 2.2, 15.5), 0.13, MATS["rail"])
        cylinder_between(f"{name}_roof_support_{i}", (base_x + sign * 24.0, y, 8.2), (roof_x + sign * 1.5, y, 14.7), 0.10, MATS["rail"], vertices=10)
        if i < 8:
            y2 = -PITCH_Y / 2 + (i + 1) * PITCH_Y / 8
            cylinder_between(f"{name}_roof_cross_brace_a_{i}", (roof_x - sign * 7.2, y, 12.8), (roof_x + sign * 6.4, y2, 15.1), 0.075, MATS["rail"], vertices=8)
            cylinder_between(f"{name}_roof_cross_brace_b_{i}", (roof_x + sign * 6.4, y, 12.8), (roof_x - sign * 7.2, y2, 15.1), 0.075, MATS["rail"], vertices=8)


def add_side_stand_render(name, side):
    sign = -1 if side == "north" else 1
    base_y = sign * (HALF_Y + 6.7)
    width_base = PITCH_X + 31
    concrete_mat = MATS["concrete"]
    rail_mat = MATS["rail"]
    dark_mat = MATS["dark"]
    primary_seats = []
    secondary_seats = []
    primary_backs = []
    secondary_backs = []
    cube_obj(f"{name}_lower_structural_shadow", (0, base_y + sign * 17.0, 0.65), (width_base + 8, 30.0, 1.3), dark_mat)

    aisle_xs = [-43, -29, -14, 14, 29, 43]
    for tier in range(3):
        tier_rows = 9 if tier == 0 else 7
        tier_y = 2.5 + tier * 8.4
        tier_z = 1.2 + tier * 4.8
        for row in range(tier_rows):
            y = base_y + sign * (tier_y + row * 0.88)
            z = tier_z + row * 0.58
            width = width_base - tier * 3.4 - row * 0.36
            step = cube_obj(f"{name}_render_step_{tier}_{row}", (0, y, z - 0.16), (width, 0.92, 0.30), concrete_mat)
            step.rotation_euler.x = math.radians(sign * -10)
            seat_mat = MATS["club_secondary"] if tier == 1 and 2 <= row <= 5 else MATS["club_primary"]
            seat = cube_obj(f"{name}_render_seat_band_{tier}_{row}", (0, y - sign * 0.12, z + 0.09), (width - 1.8, 0.48, 0.20), seat_mat)
            seat.rotation_euler.x = math.radians(sign * -10)
            back = cube_obj(f"{name}_render_seat_back_{tier}_{row}", (0, y + sign * 0.18, z + 0.40), (width - 1.8, 0.10, 0.48), seat_mat)
            back.rotation_euler.x = math.radians(sign * -10)
            if row % 2 == 0:
                rail = cube_obj(f"{name}_row_highlight_{tier}_{row}", (0, y + sign * 0.43, z + 0.54), (width - 3.0, 0.08, 0.08), rail_mat)
                rail.rotation_euler.x = math.radians(sign * -10)
            cols = 112
            for col in range(cols):
                x = (col / (cols - 1) - 0.5) * (width - 3.2)
                if any(abs(x - aisle_x) < 1.0 for aisle_x in aisle_xs):
                    continue
                logo_band = tier == 1 and 2 <= row <= 5 and abs(x) < width * 0.34
                random_highlight = (col + row * 7 + tier * 11) % 31 == 0
                target = secondary_seats if logo_band or random_highlight else primary_seats
                back_target = secondary_backs if logo_band or random_highlight else primary_backs
                target.append(((x, y - sign * 0.18, z + 0.25), (0.46, 0.30, 0.16)))
                back_target.append(((x, y + sign * 0.05, z + 0.50), (0.46, 0.08, 0.36)))
        cube_obj(f"{name}_dark_concourse_{tier}", (0, base_y + sign * (tier_y + tier_rows * 0.92 + 0.8), tier_z + tier_rows * 0.58), (width_base - tier * 3.6, 0.74, 1.05), dark_mat)
        cube_obj(f"{name}_front_fascia_{tier}", (0, base_y + sign * (tier_y - 0.52), tier_z + 0.45), (width_base - tier * 3.6, 0.42, 0.92), MATS["club_primary"])
        cube_obj(f"{name}_black_suite_reveal_{tier}", (0, base_y + sign * (tier_y + tier_rows * 0.98 + 1.12), tier_z + tier_rows * 0.64 + 0.12), (width_base - tier * 3.8, 0.56, 1.35), dark_mat)
        cube_obj(f"{name}_vip_box_ring_{tier}", (0, base_y + sign * (tier_y + tier_rows * 0.98 + 1.65), tier_z + tier_rows * 0.64 + 0.55), (width_base - tier * 4.0, 0.62, 0.82), MATS["glass"])
        cube_obj(f"{name}_vip_box_shadow_{tier}", (0, base_y + sign * (tier_y + tier_rows * 0.98 + 1.98), tier_z + tier_rows * 0.64 + 0.30), (width_base - tier * 4.2, 0.38, 0.62), dark_mat)

    for idx, x in enumerate(aisle_xs):
        aisle = cube_obj(f"{name}_vertical_aisle_{idx}", (x, base_y + sign * 14.2, 4.9), (0.88, 20.0, 0.12), concrete_mat)
        aisle.rotation_euler.x = math.radians(sign * -10)
        cube_obj(f"{name}_vomitory_{idx}", (x, base_y + sign * 7.6, 3.0), (3.7, 2.0, 1.65), dark_mat)
        cube_obj(f"{name}_aisle_rail_left_{idx}", (x - 0.58, base_y + sign * 14.0, 5.15), (0.08, 19.0, 0.30), rail_mat)
        cube_obj(f"{name}_aisle_rail_right_{idx}", (x + 0.58, base_y + sign * 14.0, 5.15), (0.08, 19.0, 0.30), rail_mat)

    mesh_boxes(f"{name}_club_primary_individual_seats", primary_seats, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_individual_seats", secondary_seats, MATS["club_secondary"])
    mesh_boxes(f"{name}_club_primary_individual_backs", primary_backs, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_individual_backs", secondary_backs, MATS["club_secondary"])

    cube_obj(f"{name}_rear_wall", (0, base_y + sign * 31.0, 8.4), (width_base + 10, 0.92, 14.8), concrete_mat)
    cube_obj(f"{name}_rear_dark_upper_bowl", (0, base_y + sign * 30.42, 10.4), (width_base + 8, 0.82, 4.6), dark_mat)
    cube_obj(f"{name}_upper_press_gallery", (0, base_y + sign * 30.25, 12.6), (width_base - 8, 0.86, 2.2), MATS["glass"])
    roof_y = base_y + sign * 32.3
    cube_obj(f"{name}_roof_underbelly_shadow", (0, roof_y - sign * 2.6, 16.85), (width_base + 24, 15.8, 0.34), dark_mat)
    cube_obj(f"{name}_roof_canopy", (0, roof_y, 17.74), (width_base + 24, 18.5, 0.46), MATS["roof"])
    cube_obj(f"{name}_roof_glass_strip", (0, roof_y - sign * 2.2, 17.92), (width_base + 15, 5.9, 0.15), MATS["roof_glass"])
    cylinder_between(f"{name}_roof_front_truss", (-(width_base / 2 + 9), roof_y - sign * 9.0, 14.0), ((width_base / 2 + 9), roof_y - sign * 9.0, 14.0), 0.28, rail_mat, vertices=16)
    cylinder_between(f"{name}_roof_mid_truss", (-(width_base / 2 + 8), roof_y - sign * 1.6, 16.1), ((width_base / 2 + 8), roof_y - sign * 1.6, 16.1), 0.22, rail_mat, vertices=16)
    cylinder_between(f"{name}_roof_back_truss", (-(width_base / 2 + 9), roof_y + sign * 7.0, 16.55), ((width_base / 2 + 9), roof_y + sign * 7.0, 16.55), 0.20, rail_mat, vertices=16)
    for i in range(20):
        x = -width_base / 2 + i * width_base / 19
        cylinder_between(f"{name}_roof_tri_a_{i}", (x, roof_y - sign * 8.8, 13.7), (x + 2.2, roof_y + sign * 6.7, 16.6), 0.085, rail_mat, vertices=8)
        cylinder_between(f"{name}_roof_drop_support_{i}", (x, base_y + sign * 26.0, 10.6), (x, roof_y - sign * 5.6, 14.2), 0.095, rail_mat, vertices=8)
        if i < 19:
            x2 = -width_base / 2 + (i + 1) * width_base / 19
            cylinder_between(f"{name}_roof_tri_b_{i}", (x2, roof_y - sign * 8.8, 13.7), (x, roof_y + sign * 6.7, 16.6), 0.085, rail_mat, vertices=8)
        cube_obj(f"{name}_roof_light_{i}", (x, roof_y - sign * 8.0, 13.9), (3.0, 0.20, 0.22), MATS["light"])


def add_end_stand_render(name, side):
    sign = -1 if side == "west" else 1
    base_x = sign * (HALF_X + 6.7)
    depth_base = PITCH_Y + 29
    concrete_mat = MATS["concrete"]
    rail_mat = MATS["rail"]
    dark_mat = MATS["dark"]
    primary_seats = []
    secondary_seats = []
    primary_backs = []
    secondary_backs = []
    cube_obj(f"{name}_lower_structural_shadow", (base_x + sign * 17.0, 0, 0.65), (30.0, depth_base + 6, 1.3), dark_mat)

    aisle_ys = [-28, -15, 0, 15, 28]
    for tier in range(3):
        tier_rows = 8 if tier == 0 else 7
        tier_x = 2.5 + tier * 8.2
        tier_z = 1.15 + tier * 4.65
        for row in range(tier_rows):
            x = base_x + sign * (tier_x + row * 0.86)
            z = tier_z + row * 0.56
            depth = depth_base - tier * 3.0 - row * 0.34
            step = cube_obj(f"{name}_render_step_{tier}_{row}", (x, 0, z - 0.16), (0.92, depth, 0.30), concrete_mat)
            step.rotation_euler.y = math.radians(sign * 10)
            seat_mat = MATS["club_secondary"] if tier == 1 and 2 <= row <= 5 else MATS["club_primary"]
            seat = cube_obj(f"{name}_render_seat_band_{tier}_{row}", (x - sign * 0.12, 0, z + 0.09), (0.48, depth - 1.8, 0.20), seat_mat)
            seat.rotation_euler.y = math.radians(sign * 10)
            back = cube_obj(f"{name}_render_seat_back_{tier}_{row}", (x + sign * 0.18, 0, z + 0.40), (0.10, depth - 1.8, 0.48), seat_mat)
            back.rotation_euler.y = math.radians(sign * 10)
            if row % 2 == 0:
                rail = cube_obj(f"{name}_row_highlight_{tier}_{row}", (x + sign * 0.43, 0, z + 0.54), (0.08, depth - 3.0, 0.08), rail_mat)
                rail.rotation_euler.y = math.radians(sign * 10)
            cols = 82
            for col in range(cols):
                y = (col / (cols - 1) - 0.5) * (depth - 3.0)
                if any(abs(y - aisle_y) < 0.95 for aisle_y in aisle_ys):
                    continue
                logo_band = tier == 1 and 2 <= row <= 5 and abs(y) < depth * 0.30
                random_highlight = (col + row * 5 + tier * 13) % 27 == 0
                target = secondary_seats if logo_band or random_highlight else primary_seats
                back_target = secondary_backs if logo_band or random_highlight else primary_backs
                target.append(((x - sign * 0.18, y, z + 0.25), (0.30, 0.46, 0.16)))
                back_target.append(((x + sign * 0.05, y, z + 0.50), (0.08, 0.46, 0.36)))
        cube_obj(f"{name}_dark_concourse_{tier}", (base_x + sign * (tier_x + tier_rows * 0.9 + 0.8), 0, tier_z + tier_rows * 0.58), (0.74, depth_base - tier * 3.4, 1.05), dark_mat)
        cube_obj(f"{name}_front_fascia_{tier}", (base_x + sign * (tier_x - 0.52), 0, tier_z + 0.45), (0.42, depth_base - tier * 3.6, 0.92), MATS["club_primary"])
        cube_obj(f"{name}_black_suite_reveal_{tier}", (base_x + sign * (tier_x + tier_rows * 0.98 + 1.10), 0, tier_z + tier_rows * 0.64 + 0.12), (0.56, depth_base - tier * 3.8, 1.32), dark_mat)
        cube_obj(f"{name}_vip_box_ring_{tier}", (base_x + sign * (tier_x + tier_rows * 0.98 + 1.55), 0, tier_z + tier_rows * 0.64 + 0.52), (0.62, depth_base - tier * 4.0, 0.82), MATS["glass"])
        cube_obj(f"{name}_vip_box_shadow_{tier}", (base_x + sign * (tier_x + tier_rows * 0.98 + 1.88), 0, tier_z + tier_rows * 0.64 + 0.28), (0.38, depth_base - tier * 4.2, 0.62), dark_mat)

    for idx, y in enumerate(aisle_ys):
        aisle = cube_obj(f"{name}_vertical_aisle_{idx}", (base_x + sign * 14.0, y, 4.8), (20.0, 0.88, 0.12), concrete_mat)
        aisle.rotation_euler.y = math.radians(sign * 10)
        cube_obj(f"{name}_vomitory_{idx}", (base_x + sign * 7.4, y, 2.9), (2.0, 3.7, 1.65), dark_mat)
        cube_obj(f"{name}_aisle_rail_left_{idx}", (base_x + sign * 14.0, y - 0.58, 5.05), (19.0, 0.08, 0.30), rail_mat)
        cube_obj(f"{name}_aisle_rail_right_{idx}", (base_x + sign * 14.0, y + 0.58, 5.05), (19.0, 0.08, 0.30), rail_mat)

    mesh_boxes(f"{name}_club_primary_individual_seats", primary_seats, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_individual_seats", secondary_seats, MATS["club_secondary"])
    mesh_boxes(f"{name}_club_primary_individual_backs", primary_backs, MATS["club_primary"])
    mesh_boxes(f"{name}_club_secondary_individual_backs", secondary_backs, MATS["club_secondary"])

    cube_obj(f"{name}_rear_wall", (base_x + sign * 30.6, 0, 8.1), (0.92, depth_base + 10, 14.3), concrete_mat)
    cube_obj(f"{name}_rear_dark_upper_bowl", (base_x + sign * 30.05, 0, 10.15), (0.82, depth_base + 8, 4.45), dark_mat)
    cube_obj(f"{name}_upper_press_gallery", (base_x + sign * 29.9, 0, 12.2), (0.86, depth_base - 8, 2.1), MATS["glass"])
    roof_x = base_x + sign * 31.8
    cube_obj(f"{name}_roof_underbelly_shadow", (roof_x - sign * 2.7, 0, 16.45), (15.8, depth_base + 22, 0.34), dark_mat)
    cube_obj(f"{name}_roof_canopy", (roof_x, 0, 17.15), (18.0, depth_base + 22, 0.46), MATS["roof"])
    cube_obj(f"{name}_roof_glass_strip", (roof_x - sign * 2.0, 0, 17.32), (5.7, depth_base + 13, 0.15), MATS["roof_glass"])
    cylinder_between(f"{name}_roof_front_truss", (roof_x - sign * 8.8, -(depth_base / 2 + 8), 13.65), (roof_x - sign * 8.8, (depth_base / 2 + 8), 13.65), 0.24, rail_mat, vertices=16)
    cylinder_between(f"{name}_roof_mid_truss", (roof_x - sign * 1.6, -(depth_base / 2 + 7), 15.75), (roof_x - sign * 1.6, (depth_base / 2 + 7), 15.75), 0.21, rail_mat, vertices=16)
    cylinder_between(f"{name}_roof_back_truss", (roof_x + sign * 6.8, -(depth_base / 2 + 8), 16.15), (roof_x + sign * 6.8, (depth_base / 2 + 8), 16.15), 0.19, rail_mat, vertices=16)
    for i in range(15):
        y = -depth_base / 2 + i * depth_base / 14
        cylinder_between(f"{name}_roof_tri_a_{i}", (roof_x - sign * 8.6, y, 13.45), (roof_x + sign * 6.6, y + 1.8, 16.25), 0.085, rail_mat, vertices=8)
        cylinder_between(f"{name}_roof_drop_support_{i}", (base_x + sign * 25.5, y, 10.2), (roof_x - sign * 5.7, y, 13.9), 0.09, rail_mat, vertices=8)
        cube_obj(f"{name}_roof_light_{i}", (roof_x - sign * 8.0, y, 13.65), (0.20, 2.8, 0.22), MATS["light"])


def add_corner_bowl(x_sign, y_sign):
    cx = x_sign * HALF_X
    cy = y_sign * HALF_Y
    if x_sign < 0 and y_sign < 0:
        start, end = math.pi, math.pi * 1.5
    elif x_sign > 0 and y_sign < 0:
        start, end = math.pi * 1.5, math.pi * 2.0
    elif x_sign > 0 and y_sign > 0:
        start, end = 0.0, math.pi * 0.5
    else:
        start, end = math.pi * 0.5, math.pi
    # Corners are modeled as curved bowl rings. This avoids the diagonal "loose stair"
    # look caused by axis-aligned seat blocks in a quarter curve.
    for tier in range(3):
        for row in range(7):
            r_inner = 6.3 + tier * 8.4 + row * 0.88
            r_outer = r_inner + 0.66
            z = 1.0 + tier * 4.05 + row * 0.54
            concrete = annular_sector_obj(
                f"corner_{x_sign}_{y_sign}_tier_{tier}_concrete_row_{row}",
                (cx, cy),
                start,
                end,
                r_inner - 0.10,
                r_outer + 0.10,
                z - 0.16,
                0.22,
                MATS["concrete"],
                segments=34,
            )
            concrete.rotation_euler.z = 0
            seat_mat = MATS["club_secondary"] if tier == 1 and 2 <= row <= 4 else MATS["club_primary"]
            annular_sector_obj(
                f"corner_{x_sign}_{y_sign}_tier_{tier}_seat_band_{row}",
                (cx, cy),
                start + 0.035,
                end - 0.035,
                r_inner + 0.10,
                r_outer - 0.12,
                z + 0.05,
                0.14,
                seat_mat,
                segments=34,
            )
            annular_sector_obj(
                f"corner_{x_sign}_{y_sign}_tier_{tier}_seat_back_band_{row}",
                (cx, cy),
                start + 0.035,
                end - 0.035,
                r_outer - 0.12,
                r_outer + 0.08,
                z + 0.42,
                0.34,
                seat_mat,
                segments=34,
            )
        annular_sector_obj(
            f"corner_{x_sign}_{y_sign}_tier_{tier}_dark_concourse",
            (cx, cy),
            start + 0.02,
            end - 0.02,
            12.0 + tier * 8.4,
            12.8 + tier * 8.4,
            3.2 + tier * 4.05,
            0.70,
            MATS["dark"],
            segments=34,
        )
        annular_sector_obj(
            f"corner_{x_sign}_{y_sign}_tier_{tier}_front_rail",
            (cx, cy),
            start + 0.02,
            end - 0.02,
            11.55 + tier * 8.4,
            11.75 + tier * 8.4,
            3.85 + tier * 4.05,
            0.26,
            MATS["rail"],
            segments=34,
        )
    for angle in (start + (end - start) * 0.34, start + (end - start) * 0.66):
        length = 25.5
        x = cx + math.cos(angle) * 18.8
        y = cy + math.sin(angle) * 18.8
        aisle = cube_obj(f"corner_{x_sign}_{y_sign}_radial_aisle_{angle:.2f}", (x, y, 5.2), (1.0, length, 0.30), MATS["rail"])
        aisle.rotation_euler.z = angle - (math.pi / 2)
    cube_obj(f"corner_{x_sign}_{y_sign}_shadow_concourse", (x_sign * (HALF_X + 17), y_sign * (HALF_Y + 17), 5.2), (11, 11, 1.2), MATS["baked_shadow"]).rotation_euler.z = math.radians(45)
    cube_obj(f"corner_{x_sign}_{y_sign}_roof", (x_sign * (HALF_X + 28), y_sign * (HALF_Y + 28), 14.6), (18, 18, 0.42), MATS["roof"]).rotation_euler.z = math.radians(45)
    cube_obj(f"corner_{x_sign}_{y_sign}_roof_glass", (x_sign * (HALF_X + 26), y_sign * (HALF_Y + 26), 14.45), (8, 8, 0.12), MATS["roof_glass"]).rotation_euler.z = math.radians(45)


def add_pitchside_details():
    # Four perimeter walkways leave the playable pitch open for the dynamic Three.js turf.
    cube_obj("north_outer_walkway", (0, -(HALF_Y + 5.5), 0.02), (PITCH_X + 16, 5.0, 0.05), MATS["dark"])
    cube_obj("south_outer_walkway", (0, HALF_Y + 5.5, 0.02), (PITCH_X + 16, 5.0, 0.05), MATS["dark"])
    cube_obj("west_outer_walkway", (-(HALF_X + 5.5), 0, 0.02), (5.0, PITCH_Y + 16, 0.05), MATS["dark"])
    cube_obj("east_outer_walkway", (HALF_X + 5.5, 0, 0.02), (5.0, PITCH_Y + 16, 0.05), MATS["dark"])
    cube_obj("north_ad_board_socket", (0, -(HALF_Y + 2.85), 0.72), (PITCH_X + 8, 0.30, 1.20), MATS["dark"])
    cube_obj("south_ad_board_socket", (0, HALF_Y + 2.85, 0.72), (PITCH_X + 8, 0.30, 1.20), MATS["dark"])
    cube_obj("west_ad_board_socket", (-(HALF_X + 2.85), 0, 0.72), (0.30, PITCH_Y + 8, 1.20), MATS["dark"])
    cube_obj("east_ad_board_socket", (HALF_X + 2.85, 0, 0.72), (0.30, PITCH_Y + 8, 1.20), MATS["dark"])
    cube_obj("north_pitch_rail", (0, -(HALF_Y + 3.1), 1.0), (PITCH_X + 8, 0.35, 1.2), MATS["rail"])
    cube_obj("south_pitch_rail", (0, HALF_Y + 3.1, 1.0), (PITCH_X + 8, 0.35, 1.2), MATS["rail"])
    cube_obj("west_pitch_rail", (-(HALF_X + 3.1), 0, 1.0), (0.35, PITCH_Y + 8, 1.2), MATS["rail"])
    cube_obj("east_pitch_rail", ((HALF_X + 3.1), 0, 1.0), (0.35, PITCH_Y + 8, 1.2), MATS["rail"])
    for idx, x in enumerate(range(-52, 53, 8)):
        cube_obj(f"north_pitch_fence_post_{idx}", (x, -(HALF_Y + 3.4), 1.25), (0.16, 0.16, 1.7), MATS["rail"])
        cube_obj(f"south_pitch_fence_post_{idx}", (x, HALF_Y + 3.4, 1.25), (0.16, 0.16, 1.7), MATS["rail"])
    for idx, y in enumerate(range(-32, 33, 8)):
        cube_obj(f"west_pitch_fence_post_{idx}", (-(HALF_X + 3.4), y, 1.25), (0.16, 0.16, 1.7), MATS["rail"])
        cube_obj(f"east_pitch_fence_post_{idx}", (HALF_X + 3.4, y, 1.25), (0.16, 0.16, 1.7), MATS["rail"])
    cube_obj("north_clear_pitch_glass", (0, -(HALF_Y + 3.55), 1.55), (PITCH_X + 8, 0.08, 1.05), MATS["glass"])
    cube_obj("south_clear_pitch_glass", (0, HALF_Y + 3.55, 1.55), (PITCH_X + 8, 0.08, 1.05), MATS["glass"])
    cube_obj("west_clear_pitch_glass", (-(HALF_X + 3.55), 0, 1.55), (0.08, PITCH_Y + 8, 1.05), MATS["glass"])
    cube_obj("east_clear_pitch_glass", (HALF_X + 3.55, 0, 1.55), (0.08, PITCH_Y + 8, 1.05), MATS["glass"])
    for x in (-18, 18):
        cube_obj(f"dugout_glass_{x}", (x, HALF_Y + 6.0, 1.45), (12.5, 2.6, 1.9), MATS["glass"])
        cube_obj(f"dugout_roof_{x}", (x, HALF_Y + 6.0, 2.65), (13.0, 3.0, 0.25), MATS["rail"])
        cube_obj(f"dugout_back_{x}", (x, HALF_Y + 7.25, 1.35), (12.5, 0.18, 1.55), MATS["club_primary"])
        cube_obj(f"dugout_floor_{x}", (x, HALF_Y + 5.95, 0.24), (13.1, 3.2, 0.16), MATS["concrete"])
        for rib in range(6):
            rib_x = x - 6.0 + rib * 2.4
            cylinder_between(f"dugout_curved_rib_{x}_{rib}", (rib_x, HALF_Y + 4.75, 0.45), (rib_x, HALF_Y + 6.95, 2.85), 0.055, MATS["rail"], vertices=8)
        for i in range(5):
            cube_obj(f"dugout_seat_{x}_{i}", (x - 4.5 + i * 2.25, HALF_Y + 5.45, 0.85), (1.15, 0.70, 0.28), MATS["club_primary"])
            cube_obj(f"dugout_seat_back_{x}_{i}", (x - 4.5 + i * 2.25, HALF_Y + 5.78, 1.12), (1.15, 0.12, 0.64), MATS["club_primary"])
    for x in (-38, 38):
        cube_obj(f"pitchside_equipment_box_{x}", (x, HALF_Y + 4.05, 0.38), (1.6, 1.0, 0.75), MATS["dark"])
        cube_obj(f"pitchside_equipment_lid_{x}", (x, HALF_Y + 4.05, 0.82), (1.7, 1.1, 0.10), MATS["rail"])
    for x, y, rot in [(-HALF_X, -HALF_Y, 0), (-HALF_X, HALF_Y, 0), (HALF_X, -HALF_Y, 0), (HALF_X, HALF_Y, 0)]:
        cylinder_between(f"corner_flag_pole_{x}_{y}", (x, y, 0.05), (x, y, 1.65), 0.045, MATS["rail"], vertices=8)
        flag = cube_obj(f"corner_flag_cloth_{x}_{y}", (x + (0.36 if x < 0 else -0.36), y, 1.42), (0.72, 0.05, 0.38), MATS["club_primary"])
        flag.rotation_euler.z = rot


def add_exterior_render_details():
    # Low-detail exterior context gives the realtime camera the same "stadium render" depth as the reference.
    cube_obj("service_ring_outer_slab", (0, 0, -0.10), (PITCH_X + 74, PITCH_Y + 74, 0.08), MATS["dark"])
    for side, sign in (("north", -1), ("south", 1)):
        cube_obj(f"{side}_outer_access_deck", (0, sign * (HALF_Y + 43), 0.18), (PITCH_X + 58, 7.5, 0.24), MATS["concrete"])
    for side, sign in (("west", -1), ("east", 1)):
        cube_obj(f"{side}_outer_access_deck", (sign * (HALF_X + 43), 0, 0.18), (7.5, PITCH_Y + 58, 0.24), MATS["concrete"])
    for idx, (x, y) in enumerate(((-66, -52), (66, -52), (-66, 52), (66, 52))):
        cube_obj(f"broadcast_tower_base_{idx}", (x, y, 2.2), (3.8, 3.8, 4.4), MATS["dark"])
        cylinder_between(f"broadcast_tower_mast_{idx}_a", (x - 1.4, y - 1.4, 4.4), (x - 1.4, y - 1.4, 18.5), 0.09, MATS["rail"], vertices=8)
        cylinder_between(f"broadcast_tower_mast_{idx}_b", (x + 1.4, y - 1.4, 4.4), (x + 1.4, y - 1.4, 18.5), 0.09, MATS["rail"], vertices=8)
        cylinder_between(f"broadcast_tower_mast_{idx}_c", (x, y + 1.4, 4.4), (x, y + 1.4, 18.5), 0.09, MATS["rail"], vertices=8)
        cube_obj(f"broadcast_tower_platform_{idx}", (x, y, 17.0), (4.6, 4.6, 0.24), MATS["rail"])
        cube_obj(f"broadcast_tower_lightbar_{idx}", (x, y, 18.0), (3.2, 0.30, 0.30), MATS["light"])
    for i in range(16):
        x = -92 + i * 12.2
        height = 3.0 + ((i * 7) % 9)
        cube_obj(f"distant_city_block_{i}", (x, -(HALF_Y + 72), height / 2), (5.5, 2.8, height), MATS["concrete"])


def add_lighting_and_camera():
    bpy.ops.object.light_add(type="SUN", location=(0, -30, 80))
    sun = bpy.context.object
    sun.name = "stadium_sun"
    sun.data.energy = 3.6
    sun.rotation_euler = (math.radians(52), math.radians(0), math.radians(28))
    bpy.ops.object.light_add(type="AREA", location=(0, -70, 45))
    area = bpy.context.object
    area.name = "stadium_softbox"
    area.data.energy = 480
    area.data.size = 60
    bpy.ops.object.camera_add(location=(-84, -86, 39), rotation=(math.radians(62), 0, math.radians(-43)))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    cam.data.lens = 26
    bpy.context.scene.render.resolution_x = 1800
    bpy.context.scene.render.resolution_y = 1000


def export_model():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB),
        export_format="GLB",
        export_apply=True,
        export_materials="EXPORT",
    )
    bpy.ops.render.render(write_still=True)
    bpy.data.images["Render Result"].save_render(filepath=str(OUT_PREVIEW))


def main():
    reset_scene()
    init_materials()
    add_pitchside_details()
    add_exterior_render_details()
    add_side_stand_render("north_main", "north")
    add_side_stand_render("south_main", "south")
    add_end_stand_render("west_goal", "west")
    add_end_stand_render("east_goal", "east")
    for xs in (-1, 1):
        for ys in (-1, 1):
            add_corner_bowl(xs, ys)
    add_lighting_and_camera()
    export_model()
    print(f"Exported {OUT_GLB}")
    print(f"Rendered {OUT_PREVIEW}")


if __name__ == "__main__":
    main()
