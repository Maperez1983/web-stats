import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "football/static/football/models/pitch3d/stadium_architectural_complete.glb"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def mat(name, color, roughness=0.55, metallic=0.0, alpha=1.0, emission=None, emission_strength=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
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
        material.show_transparent_back = False
    return material


def rounded_rect_points(half_x, half_y, radius, steps=18):
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


def loop(half_x, half_y, radius, z):
    return [(x, y, z) for x, y in rounded_rect_points(half_x, half_y, radius)]


def mesh_from_loops(name, loops, material, smooth=False):
    verts = []
    faces = []
    count = len(loops[0])
    for lp in loops:
        verts.extend(lp)
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
    for poly in obj.data.polygons:
        poly.use_smooth = smooth
    try:
        obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    except Exception:
        pass
    return obj


def flat_ring(name, ix, iy, ox, oy, ir, orad, z, material):
    return mesh_from_loops(name, (loop(ix, iy, ir, z), loop(ox, oy, orad, z)), material)


def vertical_ring(name, hx, hy, radius, z0, z1, material):
    return mesh_from_loops(name, (loop(hx, hy, radius, z0), loop(hx, hy, radius, z1)), material)


def sloped_ring(name, ix, iy, radius, d0, d1, z0, z1, material, segments=18):
    loops = []
    for i in range(segments + 1):
        t = i / segments
        d = d0 + (d1 - d0) * t
        z = z0 + (z1 - z0) * t
        loops.append(loop(ix + d, iy + d, radius + d, z))
    return mesh_from_loops(name, loops, material)


def cube(name, loc, scale, material, rot=(0, 0, 0), bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel:
        try:
            mod = obj.modifiers.new(name="beveled_edges", type="BEVEL")
            mod.width = bevel
            mod.segments = 1
            obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
        except Exception:
            pass
    return obj


def add_seat_rows(prefix, ix, iy, radius, start, end, z0, rise, seat_mat, step_mat, rows):
    step = (end - start) / rows
    for row in range(rows):
        d = start + row * step
        z = z0 + row * rise
        flat_ring(f"{prefix}_seat_row_{row:02d}_TEAM_PRIMARY", ix + d, iy + d, ix + d + step * 0.78, iy + d + step * 0.78, radius + d, radius + d + step * 0.78, z + 0.06, seat_mat)
        if row % 5 == 0:
            flat_ring(f"{prefix}_thin_concrete_nosing_{row:02d}", ix + d + step * 0.82, iy + d + step * 0.82, ix + d + step * 0.91, iy + d + step * 0.91, radius + d + step * 0.82, radius + d + step * 0.91, z + 0.02, step_mat)


def add_architectural_stadium():
    primary = mat("TEAM_PRIMARY", (0.015, 0.38, 0.25, 1), 0.50, 0.02)
    primary_alt = mat("TEAM_PRIMARY_DARKER_SEAT_FIELD", (0.010, 0.27, 0.19, 1), 0.56, 0.01)
    accent = mat("TEAM_ACCENT", (0.025, 0.14, 0.12, 1), 0.48, 0.04)
    secondary = mat("TEAM_SECONDARY", (0.92, 0.94, 0.90, 1), 0.50, 0.03)
    concrete = mat("ARCH_PRECAST_CONCRETE", (0.58, 0.62, 0.58, 1), 0.82, 0.02)
    dark_concrete = mat("ARCH_DARK_CONCRETE_STRUCTURE", (0.24, 0.27, 0.27, 1), 0.86, 0.02)
    black = mat("ARCH_DEEP_RECESSES", (0.006, 0.008, 0.011, 1), 0.90, 0)
    metal = mat("ARCH_STEEL_TRUSS", (0.46, 0.52, 0.54, 1), 0.32, 0.38)
    glass = mat("ARCH_GLASS_GUARDRAIL", (0.74, 0.93, 1.0, 0.34), 0.12, 0.0, 0.34)
    roof = mat("ARCH_CONTINUOUS_ROOF_SKIN_TEAM_SECONDARY", (0.84, 0.86, 0.83, 1), 0.38, 0.30)
    led = mat("ARCH_LED_RIBBON_FACE_TEAM_ACCENT", (0.0, 0.05, 0.07, 1), 0.28, 0.08, 1, (0.04, 0.36, 0.40, 1), 0.60)
    light = mat("ARCH_FLOODLIGHT_LINE", (0.94, 0.98, 1, 1), 0.12, 0.0, 1, (0.75, 0.92, 1, 1), 2.8)
    asphalt = mat("ARCH_DARK_SERVICE_RING", (0.035, 0.040, 0.043, 1), 0.88, 0.01)

    ix, iy, r = 58.0, 40.0, 8.0

    # Building base, exterior facade and service podium.
    flat_ring("arch_pitchside_dark_service_lane", 53.4, 35.4, 57.2, 39.2, 3.8, 7.4, 0.06, asphalt)
    flat_ring("arch_inner_team_apron_TEAM_PRIMARY", 51.6, 33.6, 53.8, 35.8, 2.2, 4.2, 0.09, primary)
    vertical_ring("arch_continuous_lower_building_mass", 80.0, 62.0, 30.0, 0.0, 9.4, dark_concrete)
    vertical_ring("arch_continuous_outer_facade_TEAM_ACCENT", 100.0, 82.0, 50.0, 4.4, 19.0, accent)
    flat_ring("arch_public_concourse_ring", 79.5, 61.5, 101.5, 83.5, 29.5, 51.5, 8.0, concrete)

    # Continuous lower, middle and upper seating bowl.
    sloped_ring("arch_lower_solid_bowl_shell", ix, iy, r, 0, 19, 0.90, 8.0, dark_concrete)
    sloped_ring("arch_lower_seat_carpet_TEAM_PRIMARY", ix + 0.9, iy + 0.9, r + 0.9, 1.2, 18.0, 2.2, 8.4, primary)
    add_seat_rows("arch_lower", ix, iy, r, 2.2, 18.0, 2.25, 0.27, primary, concrete, 24)
    flat_ring("arch_mid_shadow_concourse", ix + 19.0, iy + 19.0, ix + 23.0, iy + 23.0, r + 19.0, r + 23.0, 8.15, black)
    flat_ring("arch_mid_glass_guardrail", ix + 18.5, iy + 18.5, ix + 19.0, iy + 19.0, r + 18.5, r + 19.0, 8.85, glass)
    sloped_ring("arch_upper_solid_bowl_shell", ix, iy, r, 23.0, 40.0, 8.55, 18.2, dark_concrete)
    sloped_ring("arch_upper_seat_carpet_TEAM_PRIMARY", ix + 1.1, iy + 1.1, r + 1.1, 24.0, 39.0, 9.3, 18.65, primary)
    add_seat_rows("arch_upper", ix, iy, r, 24.0, 38.8, 9.35, 0.34, primary, concrete, 27)
    flat_ring("arch_upper_glass_guardrail", ix + 39.0, iy + 39.0, ix + 39.6, iy + 39.6, r + 39.0, r + 39.6, 19.0, glass)

    # Extra green fields at corners and over the tunnel to read as a closed bowl from the tactical camera.
    for sx in (-1, 1):
        for sy in (-1, 1):
            cube(f"arch_corner_lower_mass_{sx}_{sy}", (sx * 75.0, sy * 56.0, 4.2), (30.0, 30.0, 8.2), dark_concrete, bevel=0.04)
            cube(f"arch_corner_lower_seat_plate_TEAM_PRIMARY_{sx}_{sy}", (sx * 68.5, sy * 50.5, 7.9), (29.0, 23.0, 0.48), primary, (-0.13 * sy, 0.12 * sx, 0), bevel=0.015)
            cube(f"arch_corner_upper_seat_plate_TEAM_PRIMARY_{sx}_{sy}", (sx * 84.0, sy * 66.0, 17.9), (25.0, 23.0, 0.50), primary, (-0.18 * sy, 0.14 * sx, 0), bevel=0.015)
            cube(f"arch_corner_outer_wall_TEAM_ACCENT_{sx}_{sy}", (sx * 91.0, sy * 72.0, 12.0), (12.0, 1.0, 11.0), accent, bevel=0.02)
            cube(f"arch_corner_side_wall_TEAM_ACCENT_{sx}_{sy}", (sx * 96.0, sy * 62.0, 12.0), (1.0, 18.0, 11.0), accent, bevel=0.02)

    # Main stand tunnel and integrated grandstand over it.
    cube("arch_players_tunnel_black_mouth", (0, -39.2, 2.7), (13.2, 1.0, 3.3), black, bevel=0.03)
    cube("arch_players_tunnel_left_cheek", (-16.0, -47.0, 5.1), (20.0, 17.0, 9.6), dark_concrete, (0.035, 0, 0), bevel=0.04)
    cube("arch_players_tunnel_right_cheek", (16.0, -47.0, 5.1), (20.0, 17.0, 9.6), dark_concrete, (0.035, 0, 0), bevel=0.04)
    cube("arch_tunnel_lintel_and_vomitory_frame", (0, -40.0, 5.1), (20.0, 1.2, 1.0), concrete, bevel=0.03)
    cube("arch_tunnel_overbuild_seat_deck_TEAM_PRIMARY", (0, -54.0, 12.6), (96.0, 19.0, 0.62), primary, (0.13, 0, 0), bevel=0.015)
    cube("arch_tunnel_rear_opaque_wall_TEAM_ACCENT", (0, -63.5, 13.6), (106.0, 1.2, 10.8), accent, bevel=0.03)

    # Vomitories, stairs, handrails and sector breaks.
    for x in (-54, -36, -18, 0, 18, 36, 54):
        for side, y, sign in (("north", 40.1, 1), ("south", -40.1, -1)):
            cube(f"arch_{side}_lower_vomitory_{x}", (x, y, 3.8), (4.2, 0.70, 2.7), black, bevel=0.015)
            cube(f"arch_{side}_upper_stair_aisle_{x}", (x, y + sign * 15.0, 10.5), (1.28, 28.0, 0.30), concrete, (-0.10 * sign, 0, 0), bevel=0.008)
            cube(f"arch_{side}_aisle_handrail_l_{x}", (x - 0.82, y + sign * 15.0, 11.0), (0.07, 26.0, 0.72), metal, (-0.10 * sign, 0, 0), bevel=0.004)
            cube(f"arch_{side}_aisle_handrail_r_{x}", (x + 0.82, y + sign * 15.0, 11.0), (0.07, 26.0, 0.72), metal, (-0.10 * sign, 0, 0), bevel=0.004)
    for y in (-36, -18, 0, 18, 36):
        for side, x, sign in (("east", 58.1, 1), ("west", -58.1, -1)):
            cube(f"arch_{side}_lower_vomitory_{y}", (x, y, 3.8), (0.70, 4.2, 2.7), black, bevel=0.015)
            cube(f"arch_{side}_upper_stair_aisle_{y}", (x + sign * 15.0, y, 10.5), (28.0, 1.28, 0.30), concrete, (0, -0.10 * sign, 0), bevel=0.008)

    # Pitchside wall and crisp LED advertising ribbon.
    flat_ring("arch_black_pitch_retaining_wall", 54.5, 36.5, 56.1, 38.1, 4.5, 6.1, 1.10, black)
    flat_ring("arch_led_pitchside_ribbon_FACE_TEAM_ACCENT", 54.8, 36.8, 55.8, 37.8, 4.8, 5.8, 1.58, led)

    # Roof: one continuous plate with inner lip, outer lip, trusses, masts and daylight floodlights.
    flat_ring("arch_roof_dark_soffit", 72.0, 54.0, 102.5, 84.5, 22.0, 52.5, 19.2, black)
    flat_ring("arch_roof_single_continuous_skin_TEAM_SECONDARY", 74.0, 56.0, 106.0, 88.0, 24.0, 56.0, 20.9, roof)
    vertical_ring("arch_roof_outer_thick_edge_TEAM_SECONDARY", 106.0, 88.0, 56.0, 20.2, 21.6, roof)
    flat_ring("arch_roof_front_steel_lip", 71.0, 53.0, 73.0, 55.0, 21.0, 23.0, 18.7, metal)
    flat_ring("arch_roof_rear_steel_lip", 101.5, 83.5, 103.2, 85.2, 51.5, 53.2, 21.1, metal)
    for x in range(-78, 79, 8):
        cube(f"arch_north_roof_truss_{x}", (x, 66.0, 20.0), (0.16, 21.0, 0.18), metal, (0.54, 0, 0), bevel=0.004)
        cube(f"arch_south_roof_truss_{x}", (x, -66.0, 20.0), (0.16, 21.0, 0.18), metal, (-0.54, 0, 0), bevel=0.004)
        cube(f"arch_north_floodlight_bank_{x}", (x, 53.7, 18.25), (5.0, 0.14, 0.18), light, bevel=0.004)
        cube(f"arch_south_floodlight_bank_{x}", (x, -53.7, 18.25), (5.0, 0.14, 0.18), light, bevel=0.004)
    for y in range(-58, 59, 8):
        cube(f"arch_east_roof_truss_{y}", (85.0, y, 20.0), (21.0, 0.16, 0.18), metal, (0, 0.54, 0), bevel=0.004)
        cube(f"arch_west_roof_truss_{y}", (-85.0, y, 20.0), (21.0, 0.16, 0.18), metal, (0, -0.54, 0), bevel=0.004)
        cube(f"arch_east_floodlight_bank_{y}", (73.5, y, 18.25), (0.14, 5.0, 0.18), light, bevel=0.004)
        cube(f"arch_west_floodlight_bank_{y}", (-73.5, y, 18.25), (0.14, 5.0, 0.18), light, bevel=0.004)

    # Exterior rhythm: gates, vertical fins, service road.
    flat_ring("arch_outer_service_road", 108.0, 90.0, 126.0, 108.0, 58.0, 76.0, 0.03, asphalt)
    for x in range(-78, 79, 12):
        cube(f"arch_north_public_gate_{x}", (x, 87.0, 2.1), (5.2, 0.5, 2.8), black, bevel=0.02)
        cube(f"arch_south_public_gate_{x}", (x, -87.0, 2.1), (5.2, 0.5, 2.8), black, bevel=0.02)
        cube(f"arch_north_facade_fin_{x}", (x, 80.0, 11.5), (0.28, 0.34, 12.0), concrete, bevel=0.006)
        cube(f"arch_south_facade_fin_{x}", (x, -80.0, 11.5), (0.28, 0.34, 12.0), concrete, bevel=0.006)
    for y in range(-62, 63, 12):
        cube(f"arch_east_public_gate_{y}", (102.0, y, 2.1), (0.5, 5.2, 2.8), black, bevel=0.02)
        cube(f"arch_west_public_gate_{y}", (-102.0, y, 2.1), (0.5, 5.2, 2.8), black, bevel=0.02)
        cube(f"arch_east_facade_fin_{y}", (98.0, y, 11.5), (0.34, 0.28, 12.0), concrete, bevel=0.006)
        cube(f"arch_west_facade_fin_{y}", (-98.0, y, 11.5), (0.34, 0.28, 12.0), concrete, bevel=0.006)

    # Simple scoreboard and crest placeholder, both recolorable from the app palette.
    cube("arch_main_scoreboard_frame", (0, 58.0, 15.8), (17.0, 0.45, 5.4), black, bevel=0.03)
    cube("arch_main_scoreboard_face_FACE_TEAM_ACCENT", (0, 57.7, 15.8), (15.3, 0.08, 4.3), led, bevel=0.01)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=3.5, depth=0.18, location=(0, 57.5, 19.7), rotation=(math.pi / 2, 0, 0))
    crest = bpy.context.object
    crest.name = "arch_round_roof_crest_TEAM_PRIMARY"
    crest.data.materials.append(primary_alt)


def add_lighting():
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 60))
    sun = bpy.context.object
    sun.name = "arch_preview_sun"
    sun.data.energy = 2.2
    sun.rotation_euler = (math.radians(45), 0, math.radians(-34))
    bpy.ops.object.light_add(type="AREA", location=(0, -20, 28))
    area = bpy.context.object
    area.name = "arch_preview_softbox"
    area.data.energy = 380
    area.data.size = 90


def main():
    clear_scene()
    add_architectural_stadium()
    add_lighting()
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
