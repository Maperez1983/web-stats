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
        material.show_transparent_back = False
    return material


def pbr_mat(name, asset_id, color, roughness=0.55, metallic=0.0, normal_strength=0.35):
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

    def tex(path, label, colorspace="sRGB"):
        node = nodes.new("ShaderNodeTexImage")
        node.label = label
        node.image = bpy.data.images.load(str(path))
        node.image.colorspace_settings.name = colorspace
        return node

    links.new(tex(color_map, f"{asset_id} color").outputs["Color"], bsdf.inputs["Base Color"])
    if roughness_map.exists():
        links.new(tex(roughness_map, f"{asset_id} roughness", "Non-Color").outputs["Color"], bsdf.inputs["Roughness"])
    if metalness_map.exists():
        links.new(tex(metalness_map, f"{asset_id} metalness", "Non-Color").outputs["Color"], bsdf.inputs["Metallic"])
    if normal_map.exists():
        normal_tex = tex(normal_map, f"{asset_id} normal", "Non-Color")
        normal = nodes.new("ShaderNodeNormalMap")
        normal.inputs["Strength"].default_value = normal_strength
        links.new(normal_tex.outputs["Color"], normal.inputs["Color"])
        links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
    return material


def rounded_rect_points(half_x, half_y, radius, steps=14):
    radius = min(radius, half_x - 0.1, half_y - 0.1)
    centers = (
        (half_x - radius, half_y - radius, 0, math.pi / 2),
        (-half_x + radius, half_y - radius, math.pi / 2, math.pi),
        (-half_x + radius, -half_y + radius, math.pi, 3 * math.pi / 2),
        (half_x - radius, -half_y + radius, 3 * math.pi / 2, 2 * math.pi),
    )
    pts = []
    for cx, cy, start, end in centers:
        for i in range(steps + 1):
            if pts and i == 0:
                continue
            a = start + (end - start) * i / steps
            pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    return pts


def mesh_from_loops(name, loops, material, smooth=True):
    verts = []
    faces = []
    count = len(loops[0])
    for loop in loops:
        verts.extend(loop)
    for li in range(len(loops) - 1):
        base = li * count
        nxt = (li + 1) * count
        for i in range(count):
            j = (i + 1) % count
            faces.append((base + i, base + j, nxt + j, nxt + i))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    try:
        obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    except Exception:
        pass
    return obj


def cube(name, loc, scale, material, rot=(0, 0, 0), bevel=0.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    if bevel:
        try:
            mod = obj.modifiers.new(name="soft_bevel", type="BEVEL")
            mod.width = bevel
            mod.segments = 1
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


def contour_loop(half_x, half_y, radius, z, steps=14):
    return [(x, y, z) for x, y in rounded_rect_points(half_x, half_y, radius, steps)]


def sloped_ring(name, inner_x, inner_y, radius, depth0, depth1, z0, z1, material, segments=16):
    loops = []
    for i in range(segments + 1):
        t = i / segments
        d = depth0 + (depth1 - depth0) * t
        z = z0 + (z1 - z0) * t
        loops.append(contour_loop(inner_x + d, inner_y + d, radius + d, z))
    return mesh_from_loops(name, loops, material)


def vertical_ring(name, half_x, half_y, radius, z0, z1, material):
    return mesh_from_loops(
        name,
        (contour_loop(half_x, half_y, radius, z0), contour_loop(half_x, half_y, radius, z1)),
        material,
        smooth=False,
    )


def flat_ring(name, inner_x, inner_y, outer_x, outer_y, inner_radius, outer_radius, z, material):
    return mesh_from_loops(
        name,
        (contour_loop(inner_x, inner_y, inner_radius, z), contour_loop(outer_x, outer_y, outer_radius, z)),
        material,
        smooth=False,
    )


def add_row_bands(prefix, inner_x, inner_y, radius, depth_start, depth_end, z_start, slope, mats, count):
    mat_seat, mat_step = mats
    step = (depth_end - depth_start) / count
    for row in range(count):
        d0 = depth_start + row * step
        d1 = d0 + step * 0.34
        z = z_start + (d0 - depth_start) * slope
        flat_ring(f"{prefix}_seat_band_{row:02d}_TEAM_PRIMARY", inner_x + d0, inner_y + d0, inner_x + d1, inner_y + d1, radius + d0, radius + d1, z + 0.10, mat_seat)
        if row % 3 == 0:
            flat_ring(f"{prefix}_concrete_tread_{row:02d}", inner_x + d0 + step * 0.42, inner_y + d0 + step * 0.42, inner_x + d0 + step * 0.52, inner_y + d0 + step * 0.52, radius + d0 + step * 0.42, radius + d0 + step * 0.52, z, mat_step)


def add_stadium(mats):
    concrete = mats["concrete"]
    dark_concrete = mats["dark_concrete"]
    seat = mats["seat"]
    accent = mats["accent"]
    roof = mats["roof"]
    metal = mats["metal"]
    glass = mats["glass"]
    light = mats["light"]
    led = mats["led"]
    asphalt = mats["asphalt"]

    inner_x = 57.0
    inner_y = 39.0
    radius = 7.0

    # Grounding and finished public apron.
    flat_ring("photoreal_dark_pitch_service_lane", 54.8, 36.8, 60.2, 42.2, 4.8, 9.8, 0.03, asphalt)
    flat_ring("photoreal_team_green_inner_apron_TEAM_PRIMARY", 52.9, 34.9, 55.3, 37.3, 3.5, 5.6, 0.06, seat)
    flat_ring("photoreal_outer_public_concourse", 90.0, 70.5, 99.0, 79.5, 40.0, 49.0, 0.08, concrete)

    # Continuous bowl shells: no floating standalone stands.
    sloped_ring("photoreal_lower_precast_bowl_solid_shell", inner_x, inner_y, radius, 0.0, 18.0, 0.90, 7.20, dark_concrete, 18)
    sloped_ring("photoreal_lower_continuous_seating_deck_TEAM_PRIMARY", inner_x + 0.8, inner_y + 0.8, radius + 0.8, 1.4, 16.5, 2.05, 7.75, seat, 18)
    flat_ring("photoreal_mid_concourse_ring", inner_x + 18.0, inner_y + 18.0, inner_x + 21.4, inner_y + 21.4, radius + 18.0, radius + 21.4, 7.95, concrete)
    sloped_ring("photoreal_upper_precast_bowl_solid_shell", inner_x, inner_y, radius, 20.2, 35.0, 8.40, 15.25, dark_concrete, 16)
    sloped_ring("photoreal_upper_continuous_seating_deck_TEAM_PRIMARY", inner_x + 1.2, inner_y + 1.2, radius + 1.2, 21.0, 34.0, 9.20, 15.70, seat, 16)
    flat_ring("photoreal_upper_public_concourse", inner_x + 35.3, inner_y + 35.3, inner_x + 39.0, inner_y + 39.0, radius + 35.3, radius + 39.0, 15.92, concrete)

    # Opaque exterior facade and rear wall behind upper tier.
    vertical_ring("photoreal_lower_exterior_building_wall", 78.2, 60.2, 28.2, 0.20, 8.80, dark_concrete)
    vertical_ring("photoreal_upper_exterior_team_facade_TEAM_ACCENT", 92.0, 74.0, 42.0, 6.0, 18.5, accent)
    vertical_ring("photoreal_inner_dark_broadcast_shadow", 74.8, 56.8, 24.8, 12.8, 14.0, mats["black"])

    add_row_bands("photoreal_lower", inner_x, inner_y, radius, 2.4, 16.0, 2.3, 0.37, (seat, concrete), 24)
    add_row_bands("photoreal_upper", inner_x, inner_y, radius, 22.2, 33.6, 9.4, 0.48, (seat, concrete), 22)

    # Integrated player tunnel: dark mouth with real mass and seating deck above.
    cube("photoreal_players_tunnel_black_mouth", (0, -39.15, 2.65), (12.4, 0.85, 3.20), mats["black"], bevel=0.04)
    cube("photoreal_players_tunnel_left_concrete_cheek", (-14.2, -45.2, 4.20), (17.0, 15.0, 8.0), dark_concrete, (0.03, 0, 0), bevel=0.04)
    cube("photoreal_players_tunnel_right_concrete_cheek", (14.2, -45.2, 4.20), (17.0, 15.0, 8.0), dark_concrete, (0.03, 0, 0), bevel=0.04)
    cube("photoreal_players_tunnel_lintel", (0, -39.8, 4.55), (18.2, 1.1, 0.70), concrete, bevel=0.04)
    cube("photoreal_players_tunnel_covered_ramp", (0, -45.6, 0.18), (11.4, 11.0, 0.22), asphalt, (0.03, 0, 0), bevel=0.01)
    cube("photoreal_tunnel_upper_bridge_deck", (0, -50.6, 8.15), (94.0, 18.0, 1.00), concrete, (0.04, 0, 0), bevel=0.04)
    cube("photoreal_tunnel_upper_seating_plane_TEAM_PRIMARY", (0, -53.2, 10.8), (92.0, 18.0, 0.36), seat, (0.10, 0, 0), bevel=0.02)
    cube("photoreal_tunnel_rear_team_wall_TEAM_ACCENT", (0, -63.2, 14.2), (104.0, 1.1, 9.2), accent, bevel=0.04)

    # Vomitories, aligned and framed as architectural portals.
    for x in (-48, -32, -16, 0, 16, 32, 48):
        for side, y, sign in (("north", 39.55, 1), ("south", -39.55, -1)):
            cube(f"photoreal_{side}_lower_vomitory_black_{x}", (x, y, 3.45), (4.0, 0.66, 2.55), mats["black"], bevel=0.02)
            cube(f"photoreal_{side}_vomitory_lintel_{x}", (x, y + sign * 0.35, 4.95), (5.0, 0.48, 0.42), concrete, bevel=0.03)
            cube(f"photoreal_{side}_stair_spine_{x}", (x, y + sign * 12.0, 7.45), (1.25, 22.0, 0.25), concrete, (-0.06 * sign, 0, 0), bevel=0.01)
            cube(f"photoreal_{side}_stair_glass_l_{x}", (x - 0.82, y + sign * 12.0, 8.10), (0.08, 20.5, 0.72), glass, (-0.06 * sign, 0, 0), bevel=0.01)
            cube(f"photoreal_{side}_stair_glass_r_{x}", (x + 0.82, y + sign * 12.0, 8.10), (0.08, 20.5, 0.72), glass, (-0.06 * sign, 0, 0), bevel=0.01)
    for y in (-34, -17, 0, 17, 34):
        for side, x, sign in (("east", 57.55, 1), ("west", -57.55, -1)):
            cube(f"photoreal_{side}_lower_vomitory_black_{y}", (x, y, 3.45), (0.66, 4.0, 2.55), mats["black"], bevel=0.02)
            cube(f"photoreal_{side}_vomitory_lintel_{y}", (x + sign * 0.35, y, 4.95), (0.48, 5.0, 0.42), concrete, bevel=0.03)
            cube(f"photoreal_{side}_stair_spine_{y}", (x + sign * 12.0, y, 7.45), (22.0, 1.25, 0.25), concrete, (0, -0.06 * sign, 0), bevel=0.01)

    # Pitchside LED boards and premium dugouts.
    flat_ring("photoreal_crisp_pitchside_led_RING_FACE_TEAM_ACCENT", 55.5, 37.5, 56.2, 38.2, 5.5, 6.2, 1.05, led)
    for x in (-10.5, 10.5):
        cube(f"photoreal_dugout_base_{x}", (x, -36.0, 0.28), (15.0, 2.4, 0.24), asphalt, bevel=0.03)
        cube(f"photoreal_dugout_polycarbonate_back_{x}", (x, -36.75, 1.30), (14.4, 0.12, 1.75), glass, bevel=0.02)
        cube(f"photoreal_dugout_curved_roof_{x}", (x, -35.95, 2.20), (14.8, 2.1, 0.16), glass, (-0.16, 0, 0), bevel=0.04)
        for i in range(10):
            cube(f"photoreal_dugout_seat_{x}_{i}_TEAM_PRIMARY", (x - 5.4 + i * 1.2, -35.55, 0.78), (0.62, 0.52, 0.24), seat, bevel=0.04)

    # Continuous cantilever roof with soffit, trusses and floodlights.
    flat_ring("photoreal_roof_dark_soffit", 75.0, 57.0, 95.5, 77.5, 25.0, 45.5, 18.8, mats["black"])
    flat_ring("photoreal_roof_corrugated_outer_skin_TEAM_SECONDARY", 77.0, 59.0, 99.0, 81.0, 27.0, 49.0, 20.0, roof)
    vertical_ring("photoreal_roof_outer_thin_edge_TEAM_SECONDARY", 99.0, 81.0, 49.0, 19.6, 20.4, roof)
    for x in range(-68, 69, 8):
        cube(f"photoreal_north_roof_truss_{x}", (x, 66.5, 19.35), (0.16, 17.0, 0.18), metal, (0.48, 0, 0), bevel=0.01)
        cube(f"photoreal_south_roof_truss_{x}", (x, -66.5, 19.35), (0.16, 17.0, 0.18), metal, (-0.48, 0, 0), bevel=0.01)
        cube(f"photoreal_north_floodlight_bank_{x}", (x, 55.8, 17.0), (4.8, 0.16, 0.22), light, bevel=0.01)
        cube(f"photoreal_south_floodlight_bank_{x}", (x, -55.8, 17.0), (4.8, 0.16, 0.22), light, bevel=0.01)
    for y in range(-56, 57, 8):
        cube(f"photoreal_east_roof_truss_{y}", (84.5, y, 19.35), (17.0, 0.16, 0.18), metal, (0, 0.48, 0), bevel=0.01)
        cube(f"photoreal_west_roof_truss_{y}", (-84.5, y, 19.35), (17.0, 0.16, 0.18), metal, (0, -0.48, 0), bevel=0.01)
        cube(f"photoreal_east_floodlight_bank_{y}", (75.8, y, 17.0), (0.16, 4.8, 0.22), light, bevel=0.01)
        cube(f"photoreal_west_floodlight_bank_{y}", (-75.8, y, 17.0), (0.16, 4.8, 0.22), light, bevel=0.01)

    # Facade fins and broadcast focal points.
    for x in range(-66, 67, 11):
        cube(f"photoreal_north_facade_fin_{x}", (x, 74.2, 10.0), (0.22, 0.22, 8.2), concrete, bevel=0.01)
        cube(f"photoreal_south_facade_fin_{x}", (x, -74.2, 10.0), (0.22, 0.22, 8.2), concrete, bevel=0.01)
    for y in range(-55, 56, 11):
        cube(f"photoreal_east_facade_fin_{y}", (93.6, y, 10.0), (0.22, 0.22, 8.2), concrete, bevel=0.01)
        cube(f"photoreal_west_facade_fin_{y}", (-93.6, y, 10.0), (0.22, 0.22, 8.2), concrete, bevel=0.01)
    cube("photoreal_main_scoreboard_frame", (0, 58.4, 14.6), (16.0, 0.46, 5.2), mats["black"], bevel=0.04)
    cube("photoreal_main_scoreboard_face_FACE_TEAM_ACCENT", (0, 58.05, 14.6), (14.5, 0.08, 4.3), led, bevel=0.02)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=3.3, depth=0.18, location=(0, 57.8, 18.0), rotation=(math.pi / 2, 0, 0))
    crest = bpy.context.object
    crest.name = "photoreal_roof_round_crest_TEAM_PRIMARY"
    crest.data.materials.append(seat)


def add_real_stadium_detail_pass(mats):
    concrete = mats["concrete"]
    dark_concrete = mats["dark_concrete"]
    seat = mats["seat"]
    accent = mats["accent"]
    metal = mats["metal"]
    glass = mats["glass"]
    led = mats["led"]
    asphalt = mats["asphalt"]
    black = mats["black"]
    light = mats["light"]

    # Exterior podium and plaza access details. Real stadiums read as buildings from the
    # outside: plinth, gates, public ramps, service roads and vertical facade rhythm.
    flat_ring("real_detail_outer_plaza_paving", 99.5, 81.5, 116.0, 98.0, 49.5, 66.0, 0.04, concrete)
    flat_ring("real_detail_outer_service_road_asphalt", 119.0, 101.0, 128.0, 110.0, 69.0, 78.0, 0.02, asphalt)
    vertical_ring("real_detail_deep_outer_shadow_plinth", 99.0, 81.0, 49.0, 0.10, 3.20, black)
    vertical_ring("real_detail_precast_outer_podium", 103.0, 85.0, 53.0, 2.60, 7.10, dark_concrete)

    for x in range(-78, 79, 13):
        cube(f"real_detail_north_public_gate_{x}", (x, 86.0, 2.0), (5.4, 0.42, 2.6), black, bevel=0.03)
        cube(f"real_detail_south_public_gate_{x}", (x, -86.0, 2.0), (5.4, 0.42, 2.6), black, bevel=0.03)
        cube(f"real_detail_north_gate_canopy_{x}", (x, 87.0, 3.55), (6.8, 2.0, 0.25), metal, (-0.04, 0, 0), bevel=0.02)
        cube(f"real_detail_south_gate_canopy_{x}", (x, -87.0, 3.55), (6.8, 2.0, 0.25), metal, (0.04, 0, 0), bevel=0.02)
        cube(f"real_detail_north_facade_blade_{x}", (x, 76.0, 10.8), (0.30, 0.34, 11.5), concrete, bevel=0.01)
        cube(f"real_detail_south_facade_blade_{x}", (x, -76.0, 10.8), (0.30, 0.34, 11.5), concrete, bevel=0.01)
    for y in range(-62, 63, 13):
        cube(f"real_detail_east_public_gate_{y}", (96.0, y, 2.0), (0.42, 5.4, 2.6), black, bevel=0.03)
        cube(f"real_detail_west_public_gate_{y}", (-96.0, y, 2.0), (0.42, 5.4, 2.6), black, bevel=0.03)
        cube(f"real_detail_east_gate_canopy_{y}", (97.0, y, 3.55), (2.0, 6.8, 0.25), metal, (0, -0.04, 0), bevel=0.02)
        cube(f"real_detail_west_gate_canopy_{y}", (-97.0, y, 3.55), (2.0, 6.8, 0.25), metal, (0, 0.04, 0), bevel=0.02)
        cube(f"real_detail_east_facade_blade_{y}", (94.6, y, 10.8), (0.34, 0.30, 11.5), concrete, bevel=0.01)
        cube(f"real_detail_west_facade_blade_{y}", (-94.6, y, 10.8), (0.34, 0.30, 11.5), concrete, bevel=0.01)

    # Upper concourse glazing and guardrails add scale and finish to the seating bowl.
    flat_ring("real_detail_lower_transparent_guardrail", 58.0, 40.0, 58.5, 40.5, 8.0, 8.5, 2.15, glass)
    flat_ring("real_detail_mid_transparent_guardrail", 75.4, 57.4, 75.9, 57.9, 25.4, 25.9, 8.40, glass)
    flat_ring("real_detail_upper_transparent_guardrail", 91.5, 73.5, 92.0, 74.0, 41.5, 42.0, 16.35, glass)
    flat_ring("real_detail_upper_dark_broadcast_ribbon", 77.8, 59.8, 79.0, 61.0, 27.8, 29.0, 13.95, black)
    flat_ring("real_detail_upper_led_caption_ribbon_FACE_TEAM_ACCENT", 76.8, 58.8, 77.6, 59.6, 26.8, 27.6, 14.35, led)

    # Stronger roof engineering: front beam, rear beam, diagonals and mast supports.
    flat_ring("real_detail_roof_front_steel_ring", 74.2, 56.2, 75.0, 57.0, 24.2, 25.0, 18.55, metal)
    flat_ring("real_detail_roof_rear_steel_ring", 98.4, 80.4, 99.1, 81.1, 48.4, 49.1, 20.55, metal)
    for x in range(-78, 79, 12):
        cube(f"real_detail_north_roof_vertical_mast_{x}", (x, 76.4, 14.8), (0.24, 0.24, 8.6), metal, bevel=0.01)
        cube(f"real_detail_south_roof_vertical_mast_{x}", (x, -76.4, 14.8), (0.24, 0.24, 8.6), metal, bevel=0.01)
        cube(f"real_detail_north_roof_cross_brace_a_{x}", (x + 3.0, 67.3, 19.1), (0.14, 17.8, 0.16), metal, (0.58, 0, 0), bevel=0.01)
        cube(f"real_detail_south_roof_cross_brace_a_{x}", (x + 3.0, -67.3, 19.1), (0.14, 17.8, 0.16), metal, (-0.58, 0, 0), bevel=0.01)
        cube(f"real_detail_north_lamp_cluster_extra_{x}", (x, 54.4, 16.6), (5.6, 0.15, 0.20), light, bevel=0.01)
        cube(f"real_detail_south_lamp_cluster_extra_{x}", (x, -54.4, 16.6), (5.6, 0.15, 0.20), light, bevel=0.01)
    for y in range(-60, 61, 12):
        cube(f"real_detail_east_roof_vertical_mast_{y}", (94.4, y, 14.8), (0.24, 0.24, 8.6), metal, bevel=0.01)
        cube(f"real_detail_west_roof_vertical_mast_{y}", (-94.4, y, 14.8), (0.24, 0.24, 8.6), metal, bevel=0.01)
        cube(f"real_detail_east_roof_cross_brace_a_{y}", (84.3, y + 3.0, 19.1), (17.8, 0.14, 0.16), metal, (0, 0.58, 0), bevel=0.01)
        cube(f"real_detail_west_roof_cross_brace_a_{y}", (-84.3, y + 3.0, 19.1), (17.8, 0.14, 0.16), metal, (0, -0.58, 0), bevel=0.01)
        cube(f"real_detail_east_lamp_cluster_extra_{y}", (74.4, y, 16.6), (0.15, 5.6, 0.20), light, bevel=0.01)
        cube(f"real_detail_west_lamp_cluster_extra_{y}", (-74.4, y, 16.6), (0.15, 5.6, 0.20), light, bevel=0.01)

    # Seat-field variation and aisles: subtle alternating bands avoid a toy-like single surface.
    alt_seat = mat("TEAM_PRIMARY_ALT_SEAT_SHADE", (0.020, 0.34, 0.24, 1), 0.54, 0.02)
    for idx, d in enumerate((5.0, 8.2, 11.4, 14.6, 24.5, 27.6, 30.7, 33.2)):
        if idx % 2 == 0:
            flat_ring(f"real_detail_subtle_seat_variation_{idx}_TEAM_PRIMARY", 57.0 + d, 39.0 + d, 57.0 + d + 0.40, 39.0 + d + 0.40, 7.0 + d, 7.0 + d + 0.40, 2.3 + idx * 0.95, alt_seat)
    for x in (-54, -36, -18, 0, 18, 36, 54):
        cube(f"real_detail_north_aisle_concrete_cut_{x}", (x, 50.0, 5.6), (1.45, 20.0, 0.30), concrete, (-0.08, 0, 0), bevel=0.01)
        cube(f"real_detail_south_aisle_concrete_cut_{x}", (x, -50.0, 5.6), (1.45, 20.0, 0.30), concrete, (0.08, 0, 0), bevel=0.01)
        cube(f"real_detail_north_aisle_handrail_{x}", (x + 0.86, 50.0, 6.2), (0.08, 18.5, 0.75), metal, (-0.08, 0, 0), bevel=0.01)
        cube(f"real_detail_south_aisle_handrail_{x}", (x + 0.86, -50.0, 6.2), (0.08, 18.5, 0.75), metal, (0.08, 0, 0), bevel=0.01)
    for y in (-42, -28, -14, 0, 14, 28, 42):
        cube(f"real_detail_east_aisle_concrete_cut_{y}", (68.0, y, 5.6), (20.0, 1.45, 0.30), concrete, (0, -0.08, 0), bevel=0.01)
        cube(f"real_detail_west_aisle_concrete_cut_{y}", (-68.0, y, 5.6), (20.0, 1.45, 0.30), concrete, (0, 0.08, 0), bevel=0.01)

    # Pitch realism and technical equipment visible in real aerial references.
    grass_dark = mat("PITCH_MOWING_DARK_STRIPE", (0.035, 0.30, 0.11, 1), 0.62, 0.0)
    grass_light = mat("PITCH_MOWING_LIGHT_STRIPE", (0.10, 0.46, 0.16, 1), 0.58, 0.0)
    for i, x in enumerate(range(-48, 49, 12)):
        cube(f"real_detail_pitch_mowing_stripe_{i}", (x, 0, 0.012), (12.0, 69.0, 0.012), grass_light if i % 2 else grass_dark, bevel=0)
    for x in (-47.8, 47.8):
        cube(f"real_detail_goal_frame_backbar_{x}", (x, 0, 1.25), (0.10, 7.32, 0.10), metal, bevel=0.01)
    for x in (-50, 50):
        for y in (-32, 32):
            cyl(f"real_detail_corner_flag_pole_{x}_{y}", (x, y, 0.75), 0.035, 1.5, metal, vertices=12)
            cube(f"real_detail_corner_flag_{x}_{y}_TEAM_SECONDARY", (x + (0.24 if x < 0 else -0.24), y, 1.35), (0.45, 0.03, 0.28), mats["secondary"], bevel=0.005)


def add_camera_and_lights():
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 35))
    sun = bpy.context.object
    sun.name = "photoreal_sun"
    sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(42), 0, math.radians(-35))
    bpy.ops.object.light_add(type="AREA", location=(0, -18, 24))
    area = bpy.context.object
    area.name = "photoreal_soft_stadium_bounce"
    area.data.energy = 450
    area.data.size = 85


def main():
    clear_scene()
    mats = {
        "seat": mat("TEAM_PRIMARY", (0.015, 0.42, 0.28, 1), 0.50, 0.02),
        "accent": mat("TEAM_ACCENT", (0.02, 0.19, 0.15, 1), 0.48, 0.04),
        "secondary": mat("TEAM_SECONDARY", (0.94, 0.96, 0.94, 1), 0.52, 0.02),
        "concrete": pbr_mat("PHOTOREAL_PRECAST_CONCRETE", "Concrete048", (0.72, 0.74, 0.70, 1), 0.84, 0.02, 0.28),
        "dark_concrete": pbr_mat("PHOTOREAL_DARK_STRUCTURAL_CONCRETE", "Concrete034", (0.40, 0.42, 0.40, 1), 0.88, 0.02, 0.25),
        "metal": pbr_mat("PHOTOREAL_BRUSHED_METAL", "Metal049A", (0.62, 0.66, 0.66, 1), 0.32, 0.35, 0.25),
        "roof": pbr_mat("PHOTOREAL_CORRUGATED_ROOF", "CorrugatedSteel009", (0.76, 0.78, 0.77, 1), 0.38, 0.42, 0.30),
        "asphalt": pbr_mat("PHOTOREAL_SERVICE_ASPHALT", "Road012A", (0.055, 0.060, 0.060, 1), 0.82, 0.02, 0.22),
        "glass": mat("PHOTOREAL_POLYCARBONATE_GLASS", (0.76, 0.93, 1.0, 0.34), 0.16, 0.0, 0.34),
        "black": mat("PHOTOREAL_DEEP_BLACK_RECESS", (0.004, 0.006, 0.007, 1), 0.92, 0.0),
        "light": mat("PHOTOREAL_STADIUM_FLOODLIGHTS", (0.92, 0.98, 1.0, 1), 0.12, 0.0, 1.0, (0.72, 0.90, 1.0, 1), 3.0),
        "led": mat("PHOTOREAL_LED_BOARD_FACE", (0.004, 0.055, 0.080, 1), 0.26, 0.04, 1.0, (0.02, 0.34, 0.48, 1), 0.55),
    }
    add_stadium(mats)
    add_real_stadium_detail_pass(mats)
    add_camera_and_lights()

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
