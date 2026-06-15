import math
import os
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("PITCH3D_STADIUM_OUT") or ROOT / "football/static/football/models/pitch3d/stadium_architectural_complete.glb")


def rgba_env(name, fallback):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    if raw.startswith("#") and len(raw) in (7, 9):
        try:
            r = int(raw[1:3], 16) / 255
            g = int(raw[3:5], 16) / 255
            b = int(raw[5:7], 16) / 255
            a = int(raw[7:9], 16) / 255 if len(raw) == 9 else fallback[3]
            return (r, g, b, a)
        except Exception:
            return fallback
    return fallback


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


def sloped_box(name, xmin, xmax, ymin, ymax, z0, z1, material, axis="y"):
    if axis == "y":
        top = (
            z0 if ymin < 0 else z1,
            z0 if ymax < 0 else z1,
        )
        if ymin > 0:
            top = (z0, z1)
        elif ymax < 0:
            top = (z1, z0)
        verts = [
            (xmin, ymin, 0.0), (xmax, ymin, 0.0), (xmax, ymax, 0.0), (xmin, ymax, 0.0),
            (xmin, ymin, top[0]), (xmax, ymin, top[0]), (xmax, ymax, top[1]), (xmin, ymax, top[1]),
        ]
    else:
        top = (z0, z1) if xmin > 0 else (z1, z0)
        verts = [
            (xmin, ymin, 0.0), (xmax, ymin, 0.0), (xmax, ymax, 0.0), (xmin, ymax, 0.0),
            (xmin, ymin, top[0]), (xmax, ymin, top[1]), (xmax, ymax, top[1]), (xmin, ymax, top[0]),
        ]
    faces = (
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    )
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    try:
        obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    except Exception:
        pass
    return obj


def sloped_panel(name, xmin, xmax, ymin, ymax, z0, z1, material, axis="y"):
    if axis == "y":
        if ymin > 0:
            top = (z0, z1)
        elif ymax < 0:
            top = (z1, z0)
        else:
            top = (z0, z1)
        verts = [(xmin, ymin, top[0]), (xmax, ymin, top[0]), (xmax, ymax, top[1]), (xmin, ymax, top[1])]
    else:
        top = (z0, z1) if xmin > 0 else (z1, z0)
        verts = [(xmin, ymin, top[0]), (xmax, ymin, top[1]), (xmax, ymax, top[1]), (xmin, ymax, top[0])]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    try:
        obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    except Exception:
        pass
    return obj


def add_dugout(prefix, x, y, label, primary, secondary, black, metal, glass):
    cube(f"{prefix}_dark_technical_plinth", (x, y, 0.20), (16.6, 3.2, 0.22), black, bevel=0.025)
    cube(f"{prefix}_rear_kick_wall_TEAM_PRIMARY", (x, y + 1.20, 0.62), (15.8, 0.22, 0.82), primary, bevel=0.018)
    cube(f"{prefix}_front_clear_guard", (x, y - 1.08, 0.88), (15.2, 0.08, 1.02), glass, (math.radians(-4), 0, 0), bevel=0.006)
    cube(f"{prefix}_left_clear_side", (x - 7.85, y, 0.95), (0.10, 2.72, 1.55), glass, bevel=0.006)
    cube(f"{prefix}_right_clear_side", (x + 7.85, y, 0.95), (0.10, 2.72, 1.55), glass, bevel=0.006)
    for i in range(7):
        t = i / 6
        z = 1.15 + math.sin(t * math.pi * 0.72) * 1.05
        yy = y - 0.92 + t * 1.92
        cube(f"{prefix}_curved_polycarbonate_roof_{i:02d}", (x, yy, z), (15.8, 0.10, 0.40), glass, (math.radians(24 - t * 30), 0, 0), bevel=0.006)
    cube(f"{prefix}_front_aluminium_rail", (x, y - 1.22, 1.38), (16.0, 0.10, 0.10), metal, bevel=0.004)
    cube(f"{prefix}_top_aluminium_spine", (x, y + 0.10, 2.22), (16.1, 0.12, 0.12), metal, bevel=0.004)
    for sx in (-7.8, -5.2, -2.6, 0, 2.6, 5.2, 7.8):
        cube(f"{prefix}_canopy_rib_{sx:.1f}", (x + sx, y, 1.42), (0.08, 2.56, 0.08), metal, (math.radians(-10), 0, 0), bevel=0.003)
    for idx in range(10):
        sx = x - 5.85 + idx * 1.30
        cube(f"{prefix}_individual_blue_seat_{idx:02d}", (sx, y + 0.26, 0.60), (0.82, 0.62, 0.22), primary, bevel=0.035)
        cube(f"{prefix}_individual_blue_back_{idx:02d}", (sx, y + 0.58, 1.02), (0.82, 0.13, 0.82), primary, (math.radians(-12), 0, 0), bevel=0.028)
        cube(f"{prefix}_seat_metal_leg_l_{idx:02d}", (sx - 0.31, y + 0.12, 0.34), (0.08, 0.08, 0.36), metal, bevel=0.002)
        cube(f"{prefix}_seat_metal_leg_r_{idx:02d}", (sx + 0.31, y + 0.12, 0.34), (0.08, 0.08, 0.36), metal, bevel=0.002)
    bpy.ops.object.text_add(location=(x, y - 1.34, 1.05), rotation=(math.radians(76), 0, 0))
    text = bpy.context.object
    text.name = f"{prefix}_front_brand_{label.replace(' ', '_')}_TEAM_SECONDARY"
    text.data.body = label
    text.data.align_x = "CENTER"
    text.data.align_y = "CENTER"
    text.data.size = 0.82
    text.data.extrude = 0.018
    text.data.materials.append(secondary)


def add_seat_rows(prefix, ix, iy, radius, start, end, z0, rise, seat_mat, step_mat, rows):
    step = (end - start) / rows
    for row in range(rows):
        d = start + row * step
        z = z0 + row * rise
        flat_ring(f"{prefix}_seat_row_{row:02d}_TEAM_PRIMARY", ix + d, iy + d, ix + d + step * 0.78, iy + d + step * 0.78, radius + d, radius + d + step * 0.78, z + 0.06, seat_mat)
        if row % 5 == 0:
            flat_ring(f"{prefix}_thin_concrete_nosing_{row:02d}", ix + d + step * 0.82, iy + d + step * 0.82, ix + d + step * 0.91, iy + d + step * 0.91, radius + d + step * 0.82, radius + d + step * 0.91, z + 0.02, step_mat)


def add_architectural_stadium():
    primary = mat("TEAM_PRIMARY", rgba_env("PITCH3D_TEAM_PRIMARY", (0.015, 0.38, 0.25, 1)), 0.50, 0.02)
    primary_alt = mat("TEAM_PRIMARY_DARKER_SEAT_FIELD", rgba_env("PITCH3D_TEAM_PRIMARY_DARK", (0.010, 0.27, 0.19, 1)), 0.56, 0.01)
    accent = mat("TEAM_ACCENT", rgba_env("PITCH3D_TEAM_ACCENT", (0.025, 0.14, 0.12, 1)), 0.48, 0.04)
    secondary = mat("TEAM_SECONDARY", rgba_env("PITCH3D_TEAM_SECONDARY", (0.92, 0.94, 0.90, 1)), 0.50, 0.03)
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
    cube("arch_north_rear_grandstand_wall_TEAM_ACCENT", (0, 82.0, 10.6), (168.0, 2.2, 17.5), accent, bevel=0.025)
    cube("arch_south_rear_grandstand_wall_TEAM_ACCENT", (0, -82.0, 10.6), (168.0, 2.2, 17.5), accent, bevel=0.025)
    cube("arch_east_rear_grandstand_wall_TEAM_ACCENT", (100.0, 0, 10.6), (2.2, 124.0, 17.5), accent, bevel=0.025)
    cube("arch_west_rear_grandstand_wall_TEAM_ACCENT", (-100.0, 0, 10.6), (2.2, 124.0, 17.5), accent, bevel=0.025)
    cube("arch_north_lower_backfill_plinth", (0, 68.2, 4.1), (150.0, 20.0, 8.0), dark_concrete, bevel=0.03)
    cube("arch_south_lower_backfill_plinth", (0, -68.2, 4.1), (150.0, 20.0, 8.0), dark_concrete, bevel=0.03)
    cube("arch_east_lower_backfill_plinth", (86.5, 0, 4.1), (20.0, 105.0, 8.0), dark_concrete, bevel=0.03)
    cube("arch_west_lower_backfill_plinth", (-86.5, 0, 4.1), (20.0, 105.0, 8.0), dark_concrete, bevel=0.03)
    sloped_box("arch_north_visible_grandstand_solid_bowl", -82.0, 82.0, 37.0, 82.0, 1.2, 18.4, dark_concrete, axis="y")
    sloped_box("arch_south_visible_grandstand_solid_bowl", -82.0, 82.0, -82.0, -37.0, 1.2, 18.4, dark_concrete, axis="y")
    sloped_box("arch_east_visible_grandstand_solid_bowl", 57.0, 101.0, -53.0, 53.0, 1.2, 18.2, dark_concrete, axis="x")
    sloped_box("arch_west_visible_grandstand_solid_bowl", -101.0, -57.0, -53.0, 53.0, 1.2, 18.2, dark_concrete, axis="x")
    sloped_panel("arch_north_completed_green_seating_field_TEAM_PRIMARY", -74.0, 74.0, 40.0, 78.0, 2.2, 18.65, primary, axis="y")
    sloped_panel("arch_south_completed_green_seating_field_TEAM_PRIMARY", -74.0, 74.0, -78.0, -40.0, 2.2, 18.65, primary, axis="y")
    sloped_panel("arch_east_completed_green_seating_field_TEAM_PRIMARY", 60.0, 97.0, -45.0, 45.0, 2.2, 18.45, primary, axis="x")
    sloped_panel("arch_west_completed_green_seating_field_TEAM_PRIMARY", -97.0, -60.0, -45.0, 45.0, 2.2, 18.45, primary, axis="x")
    for x in (-54, -30, -6, 18, 42, 66):
        sloped_panel(f"arch_north_concrete_aisle_cut_{x}", x, x + 4.2, 40.0, 78.0, 2.35, 18.78, concrete, axis="y")
        sloped_panel(f"arch_south_concrete_aisle_cut_{x}", x, x + 4.2, -78.0, -40.0, 2.35, 18.78, concrete, axis="y")
    for y in (-36, -12, 12, 36):
        sloped_panel(f"arch_east_concrete_aisle_cut_{y}", 60.0, 97.0, y, y + 4.2, 2.35, 18.58, concrete, axis="x")
        sloped_panel(f"arch_west_concrete_aisle_cut_{y}", -97.0, -60.0, y, y + 4.2, 2.35, 18.58, concrete, axis="x")
    cube("arch_northeast_corner_solid_bowl_fill", (79.0, 61.0, 8.8), (45.0, 42.0, 17.2), dark_concrete, bevel=0.035)
    cube("arch_northwest_corner_solid_bowl_fill", (-79.0, 61.0, 8.8), (45.0, 42.0, 17.2), dark_concrete, bevel=0.035)
    cube("arch_southeast_corner_solid_bowl_fill", (79.0, -61.0, 8.8), (45.0, 42.0, 17.2), dark_concrete, bevel=0.035)
    cube("arch_southwest_corner_solid_bowl_fill", (-79.0, -61.0, 8.8), (45.0, 42.0, 17.2), dark_concrete, bevel=0.035)
    flat_ring("arch_continuous_inner_concrete_terrace_lip", 54.0, 36.0, 62.0, 44.0, 4.0, 12.0, 2.05, concrete)
    flat_ring("arch_continuous_upper_concourse_lip", 75.0, 57.0, 88.0, 70.0, 25.0, 38.0, 12.2, concrete)

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
            cube(f"arch_corner_deep_foundation_block_{sx}_{sy}", (sx * 88.0, sy * 70.0, 7.2), (27.0, 27.0, 14.0), dark_concrete, bevel=0.035)
            cube(f"arch_corner_rear_facade_wrap_x_{sx}_{sy}_TEAM_ACCENT", (sx * 94.5, sy * 70.0, 12.5), (4.0, 30.0, 15.5), accent, bevel=0.025)
            cube(f"arch_corner_rear_facade_wrap_y_{sx}_{sy}_TEAM_ACCENT", (sx * 82.0, sy * 80.5, 12.5), (30.0, 4.0, 15.5), accent, bevel=0.025)
            cube(f"arch_corner_lower_concourse_slab_{sx}_{sy}", (sx * 76.5, sy * 59.0, 8.4), (39.0, 35.0, 0.85), concrete, bevel=0.018)
            cube(f"arch_corner_upper_concourse_slab_{sx}_{sy}", (sx * 86.5, sy * 69.5, 17.2), (34.0, 31.0, 0.85), concrete, bevel=0.018)
            cube(f"arch_corner_lower_seat_plate_TEAM_PRIMARY_{sx}_{sy}", (sx * 68.5, sy * 50.5, 7.9), (29.0, 23.0, 0.48), primary, (-0.13 * sy, 0.12 * sx, 0), bevel=0.015)
            cube(f"arch_corner_upper_seat_plate_TEAM_PRIMARY_{sx}_{sy}", (sx * 84.0, sy * 66.0, 17.9), (25.0, 23.0, 0.50), primary, (-0.18 * sy, 0.14 * sx, 0), bevel=0.015)
            cube(f"arch_corner_outer_wall_TEAM_ACCENT_{sx}_{sy}", (sx * 91.0, sy * 72.0, 12.0), (12.0, 1.0, 11.0), accent, bevel=0.02)
            cube(f"arch_corner_side_wall_TEAM_ACCENT_{sx}_{sy}", (sx * 96.0, sy * 62.0, 12.0), (1.0, 18.0, 11.0), accent, bevel=0.02)

    # Reference-style technical area: low dugouts and a restrained dressing-room tunnel.
    add_dugout("arch_home_dugout", -22.0, -35.05, "MALAGA CF", primary, secondary, black, metal, glass)
    add_dugout("arch_away_dugout", 22.0, -35.05, "MCF", primary, secondary, black, metal, glass)
    cube("arch_touchline_dark_asphalt_technical_lane", (0.0, -35.65, 0.075), (68.0, 3.7, 0.10), asphalt, bevel=0.01)
    cube("arch_low_blue_touchline_wall_TEAM_PRIMARY", (0, -33.90, 0.70), (112.0, 0.28, 1.02), primary, bevel=0.015)
    for idx, x in enumerate((-44, -25, -6, 13, 32, 51)):
        label = ("2J FOOTBALL INTELLIGENCE", "MALAGA CF", "PARTNER", "LA ROSALEDA", "SPONSOR", "MCF")[idx]
        cube(f"arch_pitchside_ad_board_{idx:02d}_{label.replace(' ', '_')}", (x, -33.70, 1.15), (14.6, 0.18, 1.02), led if idx % 2 == 0 else accent, bevel=0.01)
        bpy.ops.object.text_add(location=(x, -33.83, 1.20), rotation=(math.radians(82), 0, 0))
        ad = bpy.context.object
        ad.name = f"arch_pitchside_ad_text_{idx:02d}_{label.replace(' ', '_')}_TEAM_SECONDARY"
        ad.data.body = label
        ad.data.align_x = "CENTER"
        ad.data.align_y = "CENTER"
        ad.data.size = 0.70
        ad.data.extrude = 0.012
        ad.data.materials.append(secondary)
    cube("arch_players_tunnel_black_mouth", (0, -36.85, 1.55), (8.4, 0.56, 2.55), black, bevel=0.025)
    cube("arch_players_tunnel_left_jamb", (-4.85, -36.70, 1.75), (0.82, 1.10, 3.05), concrete, bevel=0.025)
    cube("arch_players_tunnel_right_jamb", (4.85, -36.70, 1.75), (0.82, 1.10, 3.05), concrete, bevel=0.025)
    cube("arch_players_tunnel_header_clean", (0, -36.70, 3.25), (10.4, 1.08, 0.72), concrete, bevel=0.025)
    cube("arch_players_tunnel_recess_glow", (0, -37.15, 1.52), (6.5, 0.08, 1.70), led, bevel=0.006)
    cube("arch_players_tunnel_clear_walkway", (0, -35.22, 0.22), (8.2, 2.85, 0.20), concrete, bevel=0.012)
    cube("arch_players_tunnel_blue_side_rail_l_TEAM_PRIMARY", (-4.75, -35.32, 0.82), (0.18, 2.75, 0.92), primary, bevel=0.01)
    cube("arch_players_tunnel_blue_side_rail_r_TEAM_PRIMARY", (4.75, -35.32, 0.82), (0.18, 2.75, 0.92), primary, bevel=0.01)
    cube("arch_tunnel_integrated_lower_stand_slab", (0, -43.4, 7.8), (54.0, 13.5, 0.72), concrete, (0.07, 0, 0), bevel=0.018)
    cube("arch_tunnel_integrated_lower_seats_TEAM_PRIMARY", (0, -43.2, 8.35), (50.0, 12.0, 0.42), primary, (0.07, 0, 0), bevel=0.012)
    cube("arch_tunnel_integrated_upper_stand_slab", (0, -55.0, 12.4), (92.0, 17.0, 0.72), concrete, (0.13, 0, 0), bevel=0.018)
    cube("arch_tunnel_overbuild_seat_deck_TEAM_PRIMARY", (0, -54.0, 12.95), (88.0, 15.6, 0.46), primary, (0.13, 0, 0), bevel=0.015)

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
    team_name = os.environ.get("PITCH3D_TEAM_NAME", "").strip()
    if team_name:
        for text, loc, size in (
            (team_name, (0, 51.2, 12.35), 7.2),
            (os.environ.get("PITCH3D_TEAM_CREST_TEXT", "MCF"), (-43.0, 51.0, 11.2), 5.6),
        ):
            bpy.ops.object.text_add(location=loc, rotation=(math.radians(72), 0, 0))
            obj = bpy.context.object
            obj.name = f"arch_seat_lettering_{text.replace(' ', '_')}_TEAM_SECONDARY"
            obj.data.body = text
            obj.data.align_x = "CENTER"
            obj.data.align_y = "CENTER"
            obj.data.size = size
            obj.data.extrude = 0.045
            obj.data.materials.append(secondary)


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
