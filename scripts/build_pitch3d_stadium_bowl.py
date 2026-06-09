import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "football/static/football/models/pitch3d/stadium_bowl_premium.glb"
MATERIALS = ROOT / "football/static/football/materials/pitch3d/ambientcg"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def mat(name, color, roughness=0.55, metallic=0.0, alpha=1.0, emission=None, emission_strength=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Alpha"].default_value = alpha
        if emission:
            try:
                bsdf.inputs["Emission Color"].default_value = emission
                bsdf.inputs["Emission Strength"].default_value = emission_strength
            except Exception:
                pass
    if alpha < 1:
        material.blend_method = "BLEND"
        material.use_screen_refraction = True
    return material


def pbr_mat(name, asset_id, color, roughness=0.55, metallic=0.0):
    material = mat(name, color, roughness, metallic)
    asset_dir = MATERIALS / asset_id
    color_map = asset_dir / f"{asset_id}_1K-JPG_Color.jpg"
    roughness_map = asset_dir / f"{asset_id}_1K-JPG_Roughness.jpg"
    metalness_map = asset_dir / f"{asset_id}_1K-JPG_Metalness.jpg"
    normal_map = asset_dir / f"{asset_id}_1K-JPG_NormalGL.jpg"
    if not color_map.exists():
        return material

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return material

    def texture_node(path, label, colorspace="sRGB"):
        node = nodes.new("ShaderNodeTexImage")
        node.label = label
        node.image = bpy.data.images.load(str(path))
        node.image.colorspace_settings.name = colorspace
        return node

    color_node = texture_node(color_map, f"{asset_id} color")
    links.new(color_node.outputs["Color"], bsdf.inputs["Base Color"])

    if roughness_map.exists():
        roughness_node = texture_node(roughness_map, f"{asset_id} roughness", "Non-Color")
        links.new(roughness_node.outputs["Color"], bsdf.inputs["Roughness"])
    if metalness_map.exists():
        metalness_node = texture_node(metalness_map, f"{asset_id} metalness", "Non-Color")
        links.new(metalness_node.outputs["Color"], bsdf.inputs["Metallic"])
    if normal_map.exists():
        normal_tex = texture_node(normal_map, f"{asset_id} normal", "Non-Color")
        normal_node = nodes.new("ShaderNodeNormalMap")
        normal_node.inputs["Strength"].default_value = 0.34
        links.new(normal_tex.outputs["Color"], normal_node.inputs["Color"])
        links.new(normal_node.outputs["Normal"], bsdf.inputs["Normal"])

    return material


def cube(name, loc, scale, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    try:
        bevel = obj.modifiers.new(name="soft_bevel", type="BEVEL")
        bevel.width = 0.025
        bevel.segments = 1
        obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    except Exception:
        pass
    return obj


def cyl(name, loc, radius, depth, material, rot=(0, 0, 0), vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    try:
        obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    except Exception:
        pass
    return obj


def add_stand(name, side, length, center, mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light):
    group = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(group)

    def add(obj):
        for c in obj.users_collection:
            c.objects.unlink(obj)
        group.objects.link(obj)
        return obj

    x, y = center
    if side in {"north", "south"}:
        rot = 0 if side == "north" else math.pi
        loc_base = (x, y, 0)
        axis = "x"
    elif side == "east":
        rot = -math.pi / 2
        loc_base = (x, y, 0)
        axis = "y"
    else:
        rot = math.pi / 2
        loc_base = (x, y, 0)
        axis = "y"

    # Local stand coordinates: X = along stand, Y = depth away from pitch, Z = height.
    def tr(px, py, pz):
        ca = math.cos(rot)
        sa = math.sin(rot)
        return (loc_base[0] + px * ca - py * sa, loc_base[1] + px * sa + py * ca, pz)

    add(cube(f"{name}_continuous_podium", tr(0, 7.8, 0.45), (length + 8, 25.5, 0.9), mat_concrete, (0, 0, rot)))
    add(cube(f"{name}_pitch_fascia_TEAM_ACCENT", tr(0, -3.2, 1.00), (length + 4.0, 0.48, 1.25), mat_team, (0, 0, rot)))
    add(cube(f"{name}_lower_shadow_plenum", tr(0, 0.0, 0.74), (length + 2.0, 0.40, 0.92), mat_dark, (0, 0, rot)))

    row_counts = (22, 16, 11)
    row_origins = ((-0.4, 0.86), (12.8, 6.48), (22.2, 11.95))
    row_widths = (1.00, 0.92, 0.84)
    for tier, rows in enumerate(row_counts):
        base_y, base_z = row_origins[tier]
        width_factor = row_widths[tier]
        if tier:
            add(cube(f"{name}_concourse_{tier}", tr(0, base_y - 0.75, base_z - 0.18), (length * (width_factor + 0.08), 1.68, 0.48), mat_concrete, (0, 0, rot)))
            add(cube(f"{name}_glass_rail_{tier}", tr(0, base_y - 1.55, base_z + 0.36), (length * (width_factor + 0.03), 0.14, 0.44), mat_glass, (0, 0, rot)))
        for r in range(rows):
            py = base_y + r * 0.70
            pz = base_z + r * 0.36
            add(cube(f"{name}_riser_{tier}_{r:02d}", tr(0, py, pz), (length * width_factor, 0.55, 0.22), mat_concrete, (-0.055, 0, rot)))
            add(cube(f"{name}_seat_band_TEAM_PRIMARY_{tier}_{r:02d}", tr(0, py - 0.08, pz + 0.17), (length * (width_factor - 0.035), 0.36, 0.18), mat_team, (-0.09, 0, rot)))

    for ratio in (-0.40, -0.24, 0.0, 0.24, 0.40):
        px = ratio * length
        add(cube(f"{name}_stair_concrete_{ratio:.2f}", tr(px, 5.6, 3.45), (1.1, 14.0, 0.20), mat_concrete, (-0.055, 0, rot)))
        add(cube(f"{name}_vomitory_{ratio:.2f}", tr(px, 0.18, 2.25), (3.25, 0.34, 1.85), mat_dark, (0, 0, rot)))
        add(cube(f"{name}_upper_vomitory_{ratio:.2f}", tr(px, 15.4, 8.05), (3.25, 0.38, 1.55), mat_dark, (0, 0, rot)))

    add(cube(f"{name}_rear_facade_TEAM_ACCENT", tr(0, 31.8, 8.8), (length + 12.0, 0.62, 10.8), mat_team, (0, 0, rot)))
    add(cube(f"{name}_continuous_roof_TEAM_SECONDARY", tr(0, 28.4, 18.35), (length + 14, 12.6, 0.42), mat_roof, (-0.025, 0, rot)))
    add(cube(f"{name}_roof_front_truss", tr(0, 21.8, 16.80), (length + 9, 0.28, 0.28), mat_metal, (0, 0, rot)))
    add(cube(f"{name}_roof_rear_truss", tr(0, 32.4, 17.95), (length + 14, 0.30, 0.30), mat_metal, (0, 0, rot)))
    add(cube(f"{name}_light_bar", tr(0, 21.35, 16.32), (length * 0.88, 0.24, 0.18), mat_light, (0, 0, rot)))
    for i in range(-12, 13):
        if i % 2 == 0:
            add(cube(f"{name}_individual_floodlight_{i}", tr(i * (length / 24), 21.05, 16.16), (0.82, 0.18, 0.26), mat_light, (0, 0, rot)))
    for i in range(-6, 7):
        px = i * (length / 12)
        add(cube(f"{name}_roof_rib_{i}", tr(px, 27.4, 17.58), (0.16, 11.4, 0.18), mat_metal, (0, 0, rot)))
        if i % 2 == 0:
            add(cube(f"{name}_rear_mast_{i}", tr(px, 32.4, 10.6), (0.30, 0.30, 12.0), mat_concrete, (0, 0, rot)))
            add(cube(f"{name}_cantilever_brace_{i}", tr(px, 27.1, 14.0), (0.18, 8.8, 0.20), mat_metal, (0.48, 0, rot)))


def add_corner(name, x, y, rot, mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats

    def tr(px, py, pz):
        ca = math.cos(rot)
        sa = math.sin(rot)
        return (x + px * ca - py * sa, y + px * sa + py * ca, pz)

    add = lambda obj: obj
    add(cube(f"{name}_corner_podium", tr(0, 8.0, 0.45), (33, 26, 0.9), mat_concrete, (0, 0, rot)))
    add(cube(f"{name}_corner_fascia_TEAM_ACCENT", tr(0, -2.9, 1.02), (31, 0.48, 1.22), mat_team, (0, 0, rot)))
    for r in range(23):
        py = -0.65 + r * 0.72
        pz = 0.86 + r * 0.36
        width = 30 - r * 0.36
        add(cube(f"{name}_corner_riser_{r:02d}", tr(0, py, pz), (width, 0.50, 0.20), mat_concrete, (-0.055, 0, rot)))
        add(cube(f"{name}_corner_seats_TEAM_PRIMARY_{r:02d}", tr(0, py - 0.08, pz + 0.16), (max(5, width - 1.4), 0.32, 0.15), mat_team, (-0.09, 0, rot)))
    add(cube(f"{name}_corner_rear_facade_TEAM_ACCENT", tr(0, 31.2, 8.8), (33, 0.58, 10.6), mat_team, (0, 0, rot)))
    add(cube(f"{name}_corner_roof_TEAM_SECONDARY", tr(0, 27.8, 18.35), (36, 12.2, 0.40), mat_roof, (-0.025, 0, rot)))
    add(cube(f"{name}_corner_light_bar", tr(0, 21.1, 16.28), (25.0, 0.22, 0.16), mat_light, (0, 0, rot)))
    add(cube(f"{name}_corner_roof_front_truss", tr(0, 21.6, 16.78), (32, 0.26, 0.26), mat_metal, (0, 0, rot)))
    for ratio in (-0.35, 0.35):
        add(cube(f"{name}_corner_rear_mast_{ratio}", tr(ratio * 28, 32.2, 10.8), (0.30, 0.30, 12.0), mat_concrete, (0, 0, rot)))
        add(cube(f"{name}_corner_roof_brace_{ratio}", tr(ratio * 22, 27.0, 14.1), (0.18, 8.2, 0.20), mat_metal, (0.48, 0, rot)))


def add_tunnel_and_benches(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    y = -41
    cube("integrated_players_tunnel_frame", (0, y, 1.45), (9.2, 0.55, 2.35), mat_concrete)
    cube("integrated_players_tunnel_opening", (0, y - 0.34, 1.25), (6.4, 0.12, 1.62), mat_dark)
    cube("integrated_players_tunnel_recessed_floor", (0, y + 2.5, 0.10), (7.4, 7.4, 0.14), mat_dark, (-0.04, 0, 0))
    cube("integrated_players_tunnel_sidewall_l", (-4.1, y + 2.1, 1.05), (0.34, 6.8, 1.7), mat_concrete, (-0.04, 0, 0))
    cube("integrated_players_tunnel_sidewall_r", (4.1, y + 2.1, 1.05), (0.34, 6.8, 1.7), mat_concrete, (-0.04, 0, 0))
    cube("integrated_players_tunnel_roof_TEAM_SECONDARY", (0, y + 2.0, 2.72), (9.8, 7.4, 0.36), mat_roof, (-0.04, 0, 0))
    cube("integrated_players_tunnel_header_TEAM_ACCENT", (0, y - 0.68, 2.38), (9.6, 0.28, 0.88), mat_team)
    for x in (-8.0, 8.0):
        cube(f"premium_dugout_platform_{x}", (x, y + 2.6, 0.18), (11.2, 2.3, 0.20), mat_dark)
        cube(f"premium_dugout_glass_{x}", (x, y + 1.62, 1.18), (10.8, 0.12, 1.20), mat_glass)
        cube(f"premium_dugout_roof_{x}", (x, y + 2.45, 2.20), (11.4, 2.0, 0.12), mat_glass, (-0.18, 0, 0))
        for seat in range(8):
            sx = x - 4.1 + seat * 1.18
            cube(f"premium_dugout_seat_TEAM_PRIMARY_{x}_{seat}", (sx, y + 2.72, 0.68), (0.72, 0.58, 0.22), mat_team)


def add_pitchside_ad_boards(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    mat_board_blue = mat("AD_BOARD_DEEP_BLUE", (0.02, 0.09, 0.18, 1), 0.42, 0.04)
    mat_board_face = mat("AD_BOARD_FACE_TEAM_ACCENT", (0.02, 0.42, 0.35, 1), 0.38, 0.04)

    def board(name, loc, scale, rot=(0, 0, 0)):
        cube(f"{name}_concrete_base", (loc[0], loc[1], 0.18), (scale[0] + 0.38, scale[1] + 0.12, 0.18), mat_concrete, rot)
        cube(f"{name}_dark_backplate", (loc[0], loc[1], 0.64), (scale[0] + 0.18, scale[1] + 0.10, 0.82), mat_dark, rot)
        cube(f"{name}_display_FACE_TEAM_ACCENT", (loc[0], loc[1], 0.76), scale, mat_board_face, rot)
        cube(f"{name}_top_trim_TEAM_SECONDARY", (loc[0], loc[1], 1.21), (scale[0], scale[1] + 0.02, 0.08), mat_secondary, rot)

    for i, x in enumerate((-40, -20, 0, 20, 40)):
        board(f"north_pitchside_ad_{i}", (x, 37.35, 0), (14.5, 0.14, 0.92))
        board(f"south_pitchside_ad_{i}", (x, -37.35, 0), (14.5, 0.14, 0.92))
    for i, y in enumerate((-24, -8, 8, 24)):
        board(f"east_pitchside_ad_{i}", (56.25, y, 0), (0.14, 12.5, 0.92))
        board(f"west_pitchside_ad_{i}", (-56.25, y, 0), (0.14, 12.5, 0.92))


def add_architectural_finish(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    mat_service = mat("SERVICE_PAVEMENT", (0.08, 0.10, 0.12, 1), 0.78, 0.02)
    mat_led = mat("LED_BOARD_FACE", (0.02, 0.13, 0.20, 1), 0.28, 0.02, 1.0, (0.08, 0.52, 0.70, 1), 0.28)
    mat_white_light = mat("LED_BOARD_TEXT_LINES", (0.88, 0.98, 1.0, 1), 0.20, 0.0, 1.0, (0.62, 0.92, 1.0, 1), 0.45)

    # Dark service ring and green shoulder eliminate white suspended-looking voids around the field.
    cube("service_ring_north_grounded", (0, 39.25, 0.015), (122, 2.2, 0.03), mat_service)
    cube("service_ring_south_grounded", (0, -39.25, 0.015), (122, 2.2, 0.03), mat_service)
    cube("service_ring_east_grounded", (58.55, 0, 0.015), (2.2, 84, 0.03), mat_service)
    cube("service_ring_west_grounded", (-58.55, 0, 0.015), (2.2, 84, 0.03), mat_service)
    cube("inner_green_apron_north", (0, 36.75, 0.035), (119, 1.10, 0.04), mat_team)
    cube("inner_green_apron_south", (0, -36.75, 0.035), (119, 1.10, 0.04), mat_team)
    cube("inner_green_apron_east", (56.75, 0, 0.035), (1.10, 81, 0.04), mat_team)
    cube("inner_green_apron_west", (-56.75, 0, 0.035), (1.10, 81, 0.04), mat_team)

    # Continuous LED ribbons with repeated luminous strokes for sharper advertising in render.
    for x in range(-48, 49, 12):
        cube(f"north_led_panel_{x}", (x, 37.15, 0.86), (8.9, 0.08, 0.70), mat_led)
        cube(f"north_led_text_{x}", (x, 37.08, 0.94), (5.8, 0.035, 0.08), mat_white_light)
        cube(f"south_led_panel_{x}", (x, -37.15, 0.86), (8.9, 0.08, 0.70), mat_led)
        cube(f"south_led_text_{x}", (x, -37.08, 0.94), (5.8, 0.035, 0.08), mat_white_light)
    for y in range(-30, 31, 12):
        cube(f"east_led_panel_{y}", (56.05, y, 0.86), (0.08, 8.9, 0.70), mat_led)
        cube(f"east_led_text_{y}", (55.98, y, 0.94), (0.035, 5.8, 0.08), mat_white_light)
        cube(f"west_led_panel_{y}", (-56.05, y, 0.86), (0.08, 8.9, 0.70), mat_led)
        cube(f"west_led_text_{y}", (-55.98, y, 0.94), (0.035, 5.8, 0.08), mat_white_light)

    # Visible individual premium seats in the near/broadcast areas.
    for side, y, rot in (("south", -42.6, math.pi), ("north", 42.6, 0)):
        for row in range(7):
            z = 1.05 + row * 0.34
            yy = y + (1 if side == "south" else -1) * row * 0.68
            for col in range(-28, 29):
                if abs(col) in {5, 6, 17, 18}:
                    continue
                cube(f"{side}_individual_seat_{row}_{col}", (col * 0.82, yy, z), (0.42, 0.32, 0.20), mat_team, (-0.10, 0, rot))
                cube(f"{side}_individual_back_{row}_{col}", (col * 0.82, yy + (0.15 if side == "south" else -0.15), z + 0.18), (0.42, 0.08, 0.34), mat_team, (-0.18, 0, rot))

    # Facade louvres and access portals make the bowl read as a building from outside.
    for x in range(-62, 63, 8):
        cube(f"north_facade_louver_{x}", (x, 72.55, 8.4), (0.32, 0.18, 7.2), mat_secondary)
        cube(f"south_facade_louver_{x}", (x, -72.55, 8.4), (0.32, 0.18, 7.2), mat_secondary)
        if x % 16 == 0:
            cube(f"north_public_access_{x}", (x, 72.85, 1.9), (3.5, 0.18, 2.2), mat_dark)
            cube(f"south_public_access_{x}", (x, -72.85, 1.9), (3.5, 0.18, 2.2), mat_dark)
    for y in range(-50, 51, 8):
        cube(f"east_facade_louver_{y}", (92.15, y, 8.4), (0.18, 0.32, 7.2), mat_secondary)
        cube(f"west_facade_louver_{y}", (-92.15, y, 8.4), (0.18, 0.32, 7.2), mat_secondary)

    # Handrails and vomitory alignment.
    for x in (-38, -24, -12, 0, 12, 24, 38):
        cube(f"north_aisle_handrail_l_{x}", (x - 0.72, 45.0, 4.0), (0.08, 8.2, 1.0), mat_metal, (-0.05, 0, 0))
        cube(f"north_aisle_handrail_r_{x}", (x + 0.72, 45.0, 4.0), (0.08, 8.2, 1.0), mat_metal, (-0.05, 0, 0))
        cube(f"south_aisle_handrail_l_{x}", (x - 0.72, -45.0, 4.0), (0.08, 8.2, 1.0), mat_metal, (0.05, 0, 0))
        cube(f"south_aisle_handrail_r_{x}", (x + 0.72, -45.0, 4.0), (0.08, 8.2, 1.0), mat_metal, (0.05, 0, 0))

    # Extra triangular roof language: repeated diagonal members under the front edge.
    for x in range(-58, 59, 8):
        cube(f"north_roof_diagonal_a_{x}", (x, 60.0, 17.05), (0.14, 6.2, 0.18), mat_metal, (0.42, 0, 0))
        cube(f"north_roof_diagonal_b_{x}", (x + 3.8, 60.0, 17.05), (0.14, 6.2, 0.18), mat_metal, (-0.42, 0, 0))
        cube(f"south_roof_diagonal_a_{x}", (x, -60.0, 17.05), (0.14, 6.2, 0.18), mat_metal, (-0.42, 0, 0))
        cube(f"south_roof_diagonal_b_{x}", (x + 3.8, -60.0, 17.05), (0.14, 6.2, 0.18), mat_metal, (0.42, 0, 0))
    for y in range(-44, 45, 8):
        cube(f"east_roof_diagonal_a_{y}", (80.0, y, 17.05), (6.2, 0.14, 0.18), mat_metal, (0, 0.42, 0))
        cube(f"west_roof_diagonal_a_{y}", (-80.0, y, 17.05), (6.2, 0.14, 0.18), mat_metal, (0, -0.42, 0))


def add_unified_roof_and_facade(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    cube("full_roof_north_link_TEAM_SECONDARY", (0, 68.6, 18.48), (134, 5.4, 0.34), mat_roof, (-0.015, 0, 0))
    cube("full_roof_south_link_TEAM_SECONDARY", (0, -68.6, 18.48), (134, 5.4, 0.34), mat_roof, (0.015, 0, 0))
    cube("full_roof_east_link_TEAM_SECONDARY", (88.2, 0, 18.48), (5.4, 116, 0.34), mat_roof)
    cube("full_roof_west_link_TEAM_SECONDARY", (-88.2, 0, 18.48), (5.4, 116, 0.34), mat_roof)
    cube("continuous_front_light_north", (0, 56.8, 16.24), (112, 0.20, 0.15), mat_light)
    cube("continuous_front_light_south", (0, -56.8, 16.24), (112, 0.20, 0.15), mat_light)
    cube("continuous_front_light_east", (76.8, 0, 16.24), (0.20, 94, 0.15), mat_light)
    cube("continuous_front_light_west", (-76.8, 0, 16.24), (0.20, 94, 0.15), mat_light)
    cube("outer_facade_north_TEAM_ACCENT", (0, 72.1, 7.1), (136, 0.46, 8.6), mat_team)
    cube("outer_facade_south_TEAM_ACCENT", (0, -72.1, 7.1), (136, 0.46, 8.6), mat_team)
    cube("outer_facade_east_TEAM_ACCENT", (91.7, 0, 7.1), (0.46, 118, 8.6), mat_team)
    cube("outer_facade_west_TEAM_ACCENT", (-91.7, 0, 7.1), (0.46, 118, 8.6), mat_team)


def add_bowl_unification_pass(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    mat_shadow = mat("ROOF_SOFT_SHADOW", (0.035, 0.045, 0.050, 1), 0.72, 0.02)
    mat_terrace = mat("CONTINUOUS_TERRACE_CONCRETE", (0.70, 0.74, 0.72, 1), 0.82, 0.02)

    # A continuous lower bowl rim hides per-stand seams and makes the pitch perimeter read as one object.
    cube("continuous_inner_parapet_north_TEAM_ACCENT", (0, 38.60, 1.30), (119.0, 0.42, 1.30), mat_team)
    cube("continuous_inner_parapet_south_TEAM_ACCENT", (0, -38.60, 1.30), (119.0, 0.42, 1.30), mat_team)
    cube("continuous_inner_parapet_east_TEAM_ACCENT", (57.55, 0, 1.30), (0.42, 82.0, 1.30), mat_team)
    cube("continuous_inner_parapet_west_TEAM_ACCENT", (-57.55, 0, 1.30), (0.42, 82.0, 1.30), mat_team)

    # Corner fascia pieces are deliberately oversized so the four stands no longer feel separated.
    for name, x, y, rot in (
        ("nw", -52.6, 39.0, math.radians(42)),
        ("ne", 52.6, 39.0, math.radians(-42)),
        ("sw", -52.6, -39.0, math.radians(138)),
        ("se", 52.6, -39.0, math.radians(-138)),
    ):
        cube(f"continuous_corner_parapet_{name}_TEAM_ACCENT", (x, y, 1.30), (22.0, 0.44, 1.30), mat_team, (0, 0, rot))
        cube(f"corner_lower_infill_mass_{name}", (x, y, 0.54), (23.0, 6.2, 1.08), mat_concrete, (0, 0, rot))
        cube(f"corner_mid_concourse_{name}", (x, y + (2.0 if y > 0 else -2.0), 7.42), (25.0, 2.05, 0.50), mat_terrace, (0, 0, rot))
        cube(f"corner_upper_terrace_lip_{name}", (x, y + (5.2 if y > 0 else -5.2), 12.20), (23.5, 1.85, 0.44), mat_terrace, (0, 0, rot))

    # A dark soffit under every roof creates the premium covered-stand silhouette seen in real stadiums.
    cube("roof_soffit_north_continuous", (0, 61.4, 17.90), (132, 8.8, 0.16), mat_shadow, (-0.015, 0, 0))
    cube("roof_soffit_south_continuous", (0, -61.4, 17.90), (132, 8.8, 0.16), mat_shadow, (0.015, 0, 0))
    cube("roof_soffit_east_continuous", (81.0, 0, 17.90), (8.8, 114, 0.16), mat_shadow)
    cube("roof_soffit_west_continuous", (-81.0, 0, 17.90), (8.8, 114, 0.16), mat_shadow)
    for name, x, y, rot in (
        ("nw", -76.0, 58.2, math.radians(45)),
        ("ne", 76.0, 58.2, math.radians(-45)),
        ("sw", -76.0, -58.2, math.radians(135)),
        ("se", 76.0, -58.2, math.radians(-135)),
    ):
        cube(f"roof_corner_soffit_{name}", (x, y, 17.88), (25.0, 8.8, 0.16), mat_shadow, (0, 0, rot))
        cube(f"roof_corner_cap_{name}_TEAM_SECONDARY", (x, y, 18.58), (27.0, 9.8, 0.30), mat_roof, (0, 0, rot))

    # Repeated truss triangles and vertical supports, aligned to the roof edge instead of dangling pillars.
    for x in range(-60, 61, 10):
        cube(f"north_front_truss_post_{x}", (x, 56.9, 14.7), (0.18, 0.18, 3.3), mat_metal)
        cube(f"south_front_truss_post_{x}", (x, -56.9, 14.7), (0.18, 0.18, 3.3), mat_metal)
        cube(f"north_front_truss_diag_{x}", (x + 2.2, 57.2, 15.5), (0.16, 4.8, 0.18), mat_metal, (0.40, 0, 0))
        cube(f"south_front_truss_diag_{x}", (x + 2.2, -57.2, 15.5), (0.16, 4.8, 0.18), mat_metal, (-0.40, 0, 0))
    for y in range(-50, 51, 10):
        cube(f"east_front_truss_post_{y}", (76.9, y, 14.7), (0.18, 0.18, 3.3), mat_metal)
        cube(f"west_front_truss_post_{y}", (-76.9, y, 14.7), (0.18, 0.18, 3.3), mat_metal)
        cube(f"east_front_truss_diag_{y}", (77.2, y + 2.2, 15.5), (4.8, 0.16, 0.18), mat_metal, (0, 0.40, 0))
        cube(f"west_front_truss_diag_{y}", (-77.2, y + 2.2, 15.5), (4.8, 0.16, 0.18), mat_metal, (0, -0.40, 0))

    # Broadcast ribbon and concourse bands add horizontal continuity like the reference stadium.
    cube("mid_bowl_broadcast_ribbon_north_TEAM_SECONDARY", (0, 52.7, 8.95), (106, 0.26, 0.52), mat_secondary)
    cube("mid_bowl_broadcast_ribbon_south_TEAM_SECONDARY", (0, -52.7, 8.95), (86, 0.26, 0.52), mat_secondary)
    cube("mid_bowl_broadcast_ribbon_east_TEAM_SECONDARY", (72.5, 0, 8.95), (0.26, 84, 0.52), mat_secondary)
    cube("mid_bowl_broadcast_ribbon_west_TEAM_SECONDARY", (-72.5, 0, 8.95), (0.26, 84, 0.52), mat_secondary)
    cube("upper_bowl_dark_shadow_north", (0, 58.8, 13.18), (111, 0.26, 0.70), mat_dark)
    cube("upper_bowl_dark_shadow_south", (0, -58.8, 13.18), (91, 0.26, 0.70), mat_dark)
    cube("upper_bowl_dark_shadow_east", (78.4, 0, 13.18), (0.26, 89, 0.70), mat_dark)
    cube("upper_bowl_dark_shadow_west", (-78.4, 0, 13.18), (0.26, 89, 0.70), mat_dark)


def add_reference_detail_pass(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    mat_screen = mat("SCOREBOARD_FACE", (0.01, 0.08, 0.11, 1), 0.24, 0.02, 1.0, (0.02, 0.26, 0.34, 1), 0.45)
    mat_pitch_wall = mat("PITCH_WALL_DARK_GREEN_TEAM_ACCENT", (0.01, 0.18, 0.13, 1), 0.46, 0.02)
    mat_rail = mat("RAIL_BRUSHED_STEEL", (0.72, 0.76, 0.74, 1), 0.30, 0.25)

    # Thicker pitch wall and safety rail, matching the enclosed bowl feel of modern stadiums.
    cube("premium_pitch_wall_north_TEAM_ACCENT", (0, 36.15, 0.74), (118, 0.22, 0.86), mat_pitch_wall)
    cube("premium_pitch_wall_south_TEAM_ACCENT", (0, -36.15, 0.74), (118, 0.22, 0.86), mat_pitch_wall)
    cube("premium_pitch_wall_east_TEAM_ACCENT", (55.15, 0, 0.74), (0.22, 80, 0.86), mat_pitch_wall)
    cube("premium_pitch_wall_west_TEAM_ACCENT", (-55.15, 0, 0.74), (0.22, 80, 0.86), mat_pitch_wall)
    cube("inner_safety_rail_north", (0, 35.82, 1.56), (116, 0.08, 0.08), mat_rail)
    cube("inner_safety_rail_south", (0, -35.82, 1.56), (116, 0.08, 0.08), mat_rail)
    cube("inner_safety_rail_east", (54.82, 0, 1.56), (0.08, 78, 0.08), mat_rail)
    cube("inner_safety_rail_west", (-54.82, 0, 1.56), (0.08, 78, 0.08), mat_rail)

    # Seat colour fields stay in the team colour; contrast belongs to aisles, rails and signage.
    for x in range(-42, 43, 14):
        cube(f"north_upper_seat_fill_TEAM_PRIMARY_{x}", (x, 54.15, 10.9), (7.8, 0.42, 0.32), mat_team, (-0.08, 0, 0))
        cube(f"north_mid_seat_fill_TEAM_PRIMARY_{x}", (x + 5, 48.4, 6.1), (5.5, 0.40, 0.28), mat_team, (-0.08, 0, 0))
        cube(f"south_upper_seat_fill_TEAM_PRIMARY_{x}", (x, -54.15, 10.9), (7.8, 0.42, 0.32), mat_team, (0.08, 0, 0))
        cube(f"south_mid_seat_fill_TEAM_PRIMARY_{x}", (x + 5, -48.4, 6.1), (5.5, 0.40, 0.28), mat_team, (0.08, 0, 0))
    for y in range(-32, 33, 14):
        cube(f"east_upper_seat_fill_TEAM_PRIMARY_{y}", (74.15, y, 10.9), (0.42, 7.8, 0.32), mat_team, (0, -0.08, 0))
        cube(f"west_upper_seat_fill_TEAM_PRIMARY_{y}", (-74.15, y, 10.9), (0.42, 7.8, 0.32), mat_team, (0, 0.08, 0))

    # More believable vomitories: dark openings with concrete cheeks and a small rail header.
    for x in (-42, -28, -14, 0, 14, 28, 42):
        for side, y, sign in (("north", 39.05, 1), ("south", -39.05, -1)):
            cube(f"{side}_lower_vomitory_dark_{x}", (x, y, 2.05), (3.1, 0.24, 1.45), mat_dark)
            cube(f"{side}_lower_vomitory_lintel_{x}", (x, y + sign * 0.08, 2.88), (3.6, 0.22, 0.18), mat_concrete)
            cube(f"{side}_lower_vomitory_cheek_l_{x}", (x - 1.85, y + sign * 0.03, 2.05), (0.22, 0.22, 1.40), mat_concrete)
            cube(f"{side}_lower_vomitory_cheek_r_{x}", (x + 1.85, y + sign * 0.03, 2.05), (0.22, 0.22, 1.40), mat_concrete)
    for y in (-32, -16, 0, 16, 32):
        for side, x, sign in (("east", 58.0, 1), ("west", -58.0, -1)):
            cube(f"{side}_lower_vomitory_dark_{y}", (x, y, 2.05), (0.24, 3.1, 1.45), mat_dark)
            cube(f"{side}_lower_vomitory_lintel_{y}", (x + sign * 0.08, y, 2.88), (0.22, 3.6, 0.18), mat_concrete)

    # Scoreboards and club badge zone create the same broadcast focal points as the references.
    cube("north_central_video_board_frame", (0, 60.10, 13.35), (13.0, 0.34, 5.2), mat_dark)
    cube("north_central_video_board_face", (0, 59.88, 13.35), (11.8, 0.08, 4.3), mat_screen)
    cube("north_video_board_lower_caption_TEAM_SECONDARY", (0, 59.78, 11.05), (8.2, 0.06, 0.32), mat_secondary)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=2.45, depth=0.16, location=(-27.0, 58.9, 12.2), rotation=(math.pi / 2, 0, 0))
    crest = bpy.context.object
    crest.name = "upper_bowl_round_crest_TEAM_PRIMARY"
    crest.data.materials.append(mat_team)
    cube("upper_bowl_crest_ring_TEAM_SECONDARY", (-27.0, 58.78, 12.2), (4.2, 0.06, 0.28), mat_secondary)

    # Modular roof light clusters: visible lamps instead of only long bars.
    for x in range(-52, 53, 8):
        cube(f"north_roof_lamp_cluster_{x}", (x, 56.25, 16.08), (2.4, 0.16, 0.16), mat_light)
        cube(f"south_roof_lamp_cluster_{x}", (x, -56.25, 16.08), (2.4, 0.16, 0.16), mat_light)
    for y in range(-40, 41, 8):
        cube(f"east_roof_lamp_cluster_{y}", (76.25, y, 16.08), (0.16, 2.4, 0.16), mat_light)
        cube(f"west_roof_lamp_cluster_{y}", (-76.25, y, 16.08), (0.16, 2.4, 0.16), mat_light)

    # Tunnel is now a built-in portal under the stand instead of a cover sitting in front of it.
    cube("tunnel_integrated_back_shadow", (0, -40.95, 2.80), (13.2, 0.32, 2.30), mat_dark)
    cube("tunnel_integrated_upper_slab", (0, -40.25, 3.82), (15.0, 2.30, 0.34), mat_concrete, (0.02, 0, 0))
    cube("tunnel_integrated_side_mass_l", (-7.35, -40.15, 2.15), (0.38, 2.40, 2.25), mat_concrete)
    cube("tunnel_integrated_side_mass_r", (7.35, -40.15, 2.15), (0.38, 2.40, 2.25), mat_concrete)


def add_gap_closure_pass(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    mat_foundation = mat("FOUNDATION_SHADOW_CONCRETE", (0.30, 0.34, 0.33, 1), 0.84, 0.02)
    mat_underseat = mat("UNDER_STAND_DARK_CONCRETE", (0.11, 0.13, 0.13, 1), 0.80, 0.02)

    # Continuous foundations: the eye should always find a grounded mass below the seating bowl.
    cube("foundation_north_ground_mass", (0, 47.8, 1.10), (126, 19.0, 2.20), mat_foundation)
    cube("foundation_south_ground_mass", (0, -47.8, 1.10), (126, 19.0, 2.20), mat_foundation)
    cube("foundation_east_ground_mass", (66.8, 0, 1.10), (19.0, 92.0, 2.20), mat_foundation)
    cube("foundation_west_ground_mass", (-66.8, 0, 1.10), (19.0, 92.0, 2.20), mat_foundation)

    # Diagonal corner blocks close the visible gaps where straight stands meet.
    for name, x, y, rot in (
        ("nw", -56.0, 43.8, math.radians(45)),
        ("ne", 56.0, 43.8, math.radians(-45)),
        ("sw", -56.0, -43.8, math.radians(135)),
        ("se", 56.0, -43.8, math.radians(-135)),
    ):
        cube(f"{name}_corner_foundation_diagonal_mass", (x, y, 1.45), (34.0, 15.5, 2.90), mat_foundation, (0, 0, rot))
        cube(f"{name}_corner_understand_shadow", (x, y, 3.15), (30.0, 12.0, 2.20), mat_underseat, (0, 0, rot))
        cube(f"{name}_corner_concourse_joiner_slab", (x, y, 4.55), (32.0, 13.4, 0.46), mat_concrete, (0.02, 0, rot))
        cube(f"{name}_corner_outer_ground_skirt", (x, y, 2.65), (35.0, 0.72, 4.4), mat_foundation, (0, 0, rot))
        cube(f"{name}_corner_inner_ground_skirt", (x * 0.86, y * 0.86, 2.40), (24.0, 0.55, 3.7), mat_foundation, (0, 0, rot))
        cube(f"{name}_corner_inner_support_wall_TEAM_ACCENT", (x * 0.91, y * 0.91, 2.25), (22.0, 0.44, 2.10), mat_team, (0, 0, rot))
        for offset in (-9.0, 0.0, 9.0):
            cube(f"{name}_corner_vertical_buttress_{offset}", (x + math.cos(rot) * offset, y + math.sin(rot) * offset, 4.0), (0.46, 0.46, 6.0), mat_concrete)
        for row in range(5):
            y_off = -3.2 + row * 1.35
            cube(
                f"{name}_corner_infill_seating_band_{row}_TEAM_PRIMARY",
                (x + math.sin(rot) * y_off, y - math.cos(rot) * y_off, 4.88 + row * 0.32),
                (24.0 - row * 1.7, 0.42, 0.22),
                mat_team,
                (0.08, 0, rot),
            )

    # South tunnel: build a real seating bridge above the portal so the stand is not open to the sky.
    cube("tunnel_bridge_left_retaining_wall", (-11.6, -39.65, 2.25), (9.8, 0.62, 2.70), mat_foundation)
    cube("tunnel_bridge_right_retaining_wall", (11.6, -39.65, 2.25), (9.8, 0.62, 2.70), mat_foundation)
    cube("tunnel_bridge_header_retaining_wall", (0, -39.65, 3.58), (31.5, 0.62, 0.44), mat_foundation)
    cube("tunnel_bridge_structural_slab", (0, -42.40, 3.12), (35.0, 8.0, 0.42), mat_concrete, (0.02, 0, 0))
    cube("tunnel_bridge_dark_recess", (0, -41.95, 2.15), (12.8, 0.34, 2.55), mat_dark)
    cube("tunnel_bridge_front_left_facade_TEAM_PRIMARY", (-14.2, -39.42, 3.05), (5.2, 0.18, 1.25), mat_team)
    cube("tunnel_bridge_front_right_facade_TEAM_PRIMARY", (14.2, -39.42, 3.05), (5.2, 0.18, 1.25), mat_team)
    cube("tunnel_bridge_left_cheek", (-17.4, -42.0, 2.55), (0.55, 7.2, 3.35), mat_concrete)
    cube("tunnel_bridge_right_cheek", (17.4, -42.0, 2.55), (0.55, 7.2, 3.35), mat_concrete)
    cube("tunnel_bridge_left_side_joiner", (-25.8, -42.2, 3.15), (16.8, 6.9, 2.10), mat_foundation, (0.03, 0, 0))
    cube("tunnel_bridge_right_side_joiner", (25.8, -42.2, 3.15), (16.8, 6.9, 2.10), mat_foundation, (0.03, 0, 0))
    for row in range(9):
        y = -43.0 - row * 0.70
        z = 2.82 + row * 0.36
        cube(f"tunnel_bridge_riser_{row}", (0, y, z), (35.5, 0.52, 0.20), mat_concrete, (0.055, 0, 0))
        cube(f"tunnel_bridge_seats_TEAM_PRIMARY_{row}", (0, y - 0.08, z + 0.17), (34.6, 0.34, 0.18), mat_team, (0.09, 0, 0))

    # Pitchside corners get low green infill so the bowl does not expose white/empty wedges.
    for name, x, y, rot in (
        ("nw", -54.4, 36.8, math.radians(45)),
        ("ne", 54.4, 36.8, math.radians(-45)),
        ("sw", -54.4, -36.8, math.radians(135)),
        ("se", 54.4, -36.8, math.radians(-135)),
    ):
        cube(f"{name}_pitch_corner_green_infill_TEAM_PRIMARY", (x, y, 0.18), (12.5, 8.6, 0.18), mat_team, (0, 0, rot))
        cube(f"{name}_pitch_corner_wall_infill_TEAM_ACCENT", (x, y, 0.92), (13.0, 0.32, 1.10), mat_team, (0, 0, rot))


def main():
    clear_scene()
    mat_team = mat("TEAM_PRIMARY", (0.02, 0.47, 0.34, 1), 0.58, 0.02)
    mat_secondary = mat("TEAM_SECONDARY", (0.96, 0.98, 0.99, 1), 0.52, 0.02)
    mat_accent = mat("TEAM_ACCENT", (0.03, 0.23, 0.20, 1), 0.50, 0.06)
    mat_concrete = pbr_mat("CONCRETE_SOFT", "Concrete048", (0.78, 0.82, 0.80, 1), 0.78, 0.02)
    mat_dark = mat("DARK_OPENING", (0.01, 0.02, 0.04, 1), 0.86, 0.02)
    mat_glass = mat("GLASS_RAIL", (0.80, 0.95, 1.0, 0.38), 0.18, 0.02, 0.38)
    mat_metal = pbr_mat("ROOF_METAL", "Metal049A", (0.63, 0.68, 0.70, 1), 0.30, 0.35)
    mat_roof = pbr_mat("ROOF_PANEL_METAL", "CorrugatedSteel009", (0.72, 0.76, 0.77, 1), 0.36, 0.45)
    mat_light = mat("STADIUM_LIGHTS", (0.90, 0.96, 1.0, 1), 0.12, 0.0, 1.0, (0.70, 0.88, 1.0, 1), 2.0)

    mats = (mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light)
    add_stand("north_main", "north", 96, (0, 40.2), *mats)
    add_stand("south_main", "south", 76, (0, -40.2), *mats)
    add_stand("east_main", "east", 74, (60.0, 0), *mats)
    add_stand("west_main", "west", 74, (-60.0, 0), *mats)
    add_corner("north_west", -48, 36, math.radians(45), mats)
    add_corner("north_east", 48, 36, math.radians(-45), mats)
    add_corner("south_west", -48, -36, math.radians(135), mats)
    add_corner("south_east", 48, -36, math.radians(-135), mats)
    add_tunnel_and_benches(mats)
    add_pitchside_ad_boards(mats)
    add_architectural_finish(mats)
    add_unified_roof_and_facade(mats)
    add_bowl_unification_pass(mats)
    add_reference_detail_pass(mats)
    add_gap_closure_pass(mats)

    # Continuous roof links make the stadium read as one closed object.
    cube("roof_link_north_TEAM_SECONDARY", (0, 67.8, 18.52), (128, 4.6, 0.30), mat_roof, (-0.015, 0, 0))
    cube("roof_link_south_TEAM_SECONDARY", (0, -67.8, 18.52), (128, 4.6, 0.30), mat_roof, (0.015, 0, 0))
    cube("roof_link_east_TEAM_SECONDARY", (87.4, 0, 18.52), (4.6, 108, 0.30), mat_roof)
    cube("roof_link_west_TEAM_SECONDARY", (-87.4, 0, 18.52), (4.6, 108, 0.30), mat_roof)

    # Pitch apron, kept in the team primary family.
    cube("green_runoff_TEAM_PRIMARY_north", (0, 35.4, 0.04), (118, 5.0, 0.06), mat_team)
    cube("green_runoff_TEAM_PRIMARY_south", (0, -35.4, 0.04), (118, 5.0, 0.06), mat_team)
    cube("green_runoff_TEAM_PRIMARY_east", (55.8, 0, 0.04), (5.0, 80, 0.06), mat_team)
    cube("green_runoff_TEAM_PRIMARY_west", (-55.8, 0, 0.04), (5.0, 80, 0.06), mat_team)

    # Badge placeholder disk above main stand.
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=3.1, depth=0.16, location=(0, 45.5, 9.0), rotation=(math.pi / 2, 0, 0))
    badge = bpy.context.object
    badge.name = "main_badge_TEAM_PRIMARY"
    badge.data.materials.append(mat_team)

    for obj in bpy.context.scene.objects:
        obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT),
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
        export_draco_mesh_compression_enable=False,
    )


if __name__ == "__main__":
    main()
