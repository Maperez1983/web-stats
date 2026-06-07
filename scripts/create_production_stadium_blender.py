import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import create_hyperrealistic_stadium_blender as base


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "football" / "static" / "football" / "models" / "stadium"
IMG_DIR = ROOT / "football" / "static" / "football" / "images" / "stadium"
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

OUT_BLEND = OUT_DIR / "benagalbon-production-stadium.blend"
OUT_GLB = OUT_DIR / "benagalbon-production-stadium.glb"
OUT_RENDER = IMG_DIR / "benagalbon-production-stadium-final.png"
OUT_DETAIL = IMG_DIR / "benagalbon-production-stadium-detail.png"
OUT_CLOSEUP = IMG_DIR / "benagalbon-production-stadium-closeup.png"


def tune_render():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 256
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = -0.14
    scene.view_settings.gamma = 1.0
    scene.world.color = (0.66, 0.82, 1.0)
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.66, 0.82, 1.0, 1.0)
        bg.inputs["Strength"].default_value = 0.96


def tune_production_materials():
    base.M["broadcast_mow_dark"] = base.material("broadcast_mow_dark_green", (0.070, 0.34, 0.095), 0.92)
    base.M["broadcast_mow_light"] = base.material("broadcast_mow_light_green", (0.20, 0.47, 0.145), 0.90)
    overrides = {
        "green": ((0.015, 0.39, 0.17, 1.0), 0.60),
        "green_dark": ((0.018, 0.18, 0.115, 1.0), 0.70),
        "seat_white": ((1.0, 1.0, 0.965, 1.0), 0.42),
        "concrete": ((0.68, 0.71, 0.70, 1.0), 0.86),
        "concrete_dark": ((0.44, 0.49, 0.50, 1.0), 0.90),
        "roof": ((0.12, 0.17, 0.19, 1.0), 0.44),
        "grass_a": ((0.070, 0.32, 0.080, 1.0), 0.91),
        "grass_b": ((0.20, 0.46, 0.13, 1.0), 0.89),
        "grass_detail_dark": ((0.050, 0.24, 0.070, 1.0), 0.94),
        "grass_detail_light": ((0.18, 0.42, 0.12, 1.0), 0.92),
    }
    for key, (color, roughness) in overrides.items():
        mat = base.M.get(key)
        if not mat:
            continue
        mat.diffuse_color = color
        bsdf = next((node for node in mat.node_tree.nodes if getattr(node, "type", "") == "BSDF_PRINCIPLED"), None) if mat.use_nodes else None
        if bsdf:
            if "Base Color" in bsdf.inputs:
                bsdf.inputs["Base Color"].default_value = color
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = roughness


def add_hair_grass():
    for obj in bpy.context.scene.objects:
        if not obj.name.startswith("grass_stripe_"):
            continue
        ps = obj.modifiers.new(f"{obj.name}_production_grass", "PARTICLE_SYSTEM")
        settings = ps.particle_system.settings
        settings.count = 1400
        settings.type = "HAIR"
        settings.hair_length = 0.18
        settings.use_advanced_hair = True
        settings.rendered_child_count = 5
        settings.child_type = "INTERPOLATED"
        settings.child_length = 0.72
        settings.roughness_1_size = 0.08
        settings.roughness_1 = 0.025
        settings.roughness_2 = 0.018
        settings.display_percentage = 10
        settings.use_modifier_stack = True


def add_close_grass_blade_clusters():
    dark, light = [], []
    for i in range(1400):
        x = -base.HALF_X + (i * 7.31 % (base.PITCH_X - 2)) + 1
        y = -base.HALF_Y + (i * 11.17 % (base.PITCH_Y - 2)) + 1
        if i % 5 == 0:
            y *= 0.55
        h = 0.07 + ((i * 13) % 11) * 0.012
        blade = ((x, y, 0.17 + h / 2), (0.018, 0.10 + (i % 4) * 0.025, h))
        (light if i % 4 == 0 else dark).append(blade)
    base.mesh_boxes("production_close_pitch_dark_blades", dark, "grass_detail_dark")
    base.mesh_boxes("production_close_pitch_light_blades", light, "grass_detail_light")


def remove_main_stand_seat_noise():
    prefixes = (
        "south_main_stand_green_seats",
        "south_main_stand_white_seats",
        "south_main_stand_green_seat_backs",
        "south_main_stand_white_seat_backs",
        "south_main_stand_upper_white_seats",
        "south_main_stand_top_white_seats",
        "production_crisp_main_",
        "production_clean_readable_",
    )
    fragments = (
        "molded_seat_pan_",
        "molded_seat_back_",
        "molded_seat_left_ear_",
        "molded_seat_right_ear_",
    )
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(prefixes) or obj.name.startswith(fragments):
            bpy.data.objects.remove(obj, do_unlink=True)


def add_reference_main_stand_mosaic():
    # Single seat layer for the reference look: green bowl with one clean white name.
    sign = 1
    base_y = sign * (base.HALF_Y + 8)
    rows = 30
    cols = 172
    green_boxes, white_boxes, white_backs, green_backs = [], [], [], []
    for row in range(1, 26):
        y = base_y + sign * (row * 0.77)
        z = 1.36 + row * 0.48
        width = base.PITCH_X + 28 - row * 0.32
        for col in range(5, cols - 5):
            nx = col / (cols - 1) - 0.5
            if abs(nx) < 0.020 or abs(nx - 0.23) < 0.014 or abs(nx + 0.23) < 0.014 or abs(nx - 0.39) < 0.014 or abs(nx + 0.39) < 0.014:
                continue
            x = nx * (width - 3.4)
            white = base.seat_text_mask("BENAGALBON CD", col, row, cols, rows, start_col=12, end_col=160)
            pans = white_boxes if white else green_boxes
            backs = white_backs if white else green_backs
            pans.append(((x, y - sign * 0.065, z + 0.18), (0.38, 0.32, 0.085)))
            backs.append(((x, y + sign * 0.105, z + 0.49), (0.38, 0.08, 0.40)))
    base.mesh_boxes("production_reference_main_green_seat_pans", green_boxes, "green")
    base.mesh_boxes("production_reference_main_green_seat_backs", green_backs, "green")
    base.mesh_boxes("production_reference_main_white_name_pans", white_boxes, "seat_white")
    base.mesh_boxes("production_reference_main_white_name_backs", white_backs, "seat_white")


def add_reference_pitch_striping():
    stripe_w = base.PITCH_X / 12
    for i in range(12):
        x = -base.HALF_X + stripe_w * (i + 0.5)
        mat = "broadcast_mow_light" if i % 2 == 0 else "broadcast_mow_dark"
        base.cube(f"production_broadcast_mow_band_{i:02d}", (x, 0, 0.121 + i * 0.0001), (stripe_w - 0.08, base.PITCH_Y - 0.25, 0.014), mat, 0.0)


def add_reference_roof_and_scoreboard():
    sign = 1
    base_y = sign * (base.HALF_Y + 8)
    base.cube("production_main_stand_front_shadow_band", (0, base_y + sign * 15.6, 18.9), (base.PITCH_X + 42, 1.05, 1.35), "roof", 0.02)
    for i in range(17):
        x = -base.PITCH_X / 2 - 9 + i * ((base.PITCH_X + 18) / 16)
        base.cube(f"production_reference_light_bar_main_{i}", (x, base_y + sign * 16.6, 20.15), (3.2, 0.22, 0.22), "light", 0.012)
    base.cube("production_reference_scoreboard_body", (41.5, base.HALF_Y + 6.4, 9.1), (9.5, 0.36, 5.1), "screen", 0.035)
    base.cube("production_reference_scoreboard_green_face", (41.5, base.HALF_Y + 6.16, 9.1), (8.6, 0.08, 4.25), "green_dark", 0.018)
    base.add_text("production_reference_scoreboard_cdb", "CDB", (41.5, base.HALF_Y + 6.08, 9.1), 1.15, "white", rot=(math.radians(90), 0, 0), extrude=0.012)


def add_upper_bowl_mass_and_vomitories():
    for sign, prefix in [(1, "north"), (-1, "south")]:
        base_y = sign * (base.HALF_Y + 8)
        base.cube(f"production_{prefix}_rear_upper_concrete_bowl", (0, base_y + sign * 31.0, 14.4), (base.PITCH_X + 53, 5.2, 11.0), "concrete", 0.025)
        base.cube(f"production_{prefix}_upper_dark_shadow_gap", (0, base_y + sign * 25.0, 12.9), (base.PITCH_X + 47, 1.1, 2.0), "concrete_dark", 0.018)
        for x in [-45, -25, 0, 25, 45]:
            base.cube(f"production_{prefix}_vomitory_shadow_{x}", (x, base_y + sign * 11.8, 6.6), (4.2, 1.0, 3.0), "concrete_dark", 0.018)
            base.cube(f"production_{prefix}_vomitory_lintel_{x}", (x, base_y + sign * 11.2, 8.4), (5.2, 0.65, 0.45), "concrete", 0.012)
            for side in [-1, 1]:
                base.cube(f"production_{prefix}_vomitory_jamb_{x}_{side}", (x + side * 2.3, base_y + sign * 11.2, 6.8), (0.42, 0.65, 2.9), "concrete", 0.012)


def add_production_seat_depth():
    # Add a subtle front lip on key visible seating tiers so rows read as individual chairs.
    for sign, prefix in [(1, "south"), (-1, "north")]:
        base_y = sign * (base.HALF_Y + 8)
        for row in range(0, 28, 2):
            y = base_y + sign * (row * 0.78 - 0.21)
            z = 1.45 + row * 0.48
            width = base.PITCH_X + 22 - row * 0.35
            base.cube(f"production_{prefix}_seat_row_shadow_{row}", (0, y, z), (width, 0.08, 0.08), "concrete_dark", 0.012)
    for sign, prefix in [(1, "east"), (-1, "west")]:
        base_x = sign * (base.HALF_X + 8)
        for row in range(0, 20, 2):
            x = base_x + sign * (row * 0.78 - 0.21)
            z = 1.38 + row * 0.45
            depth = base.PITCH_Y + 21 - row * 0.45
            base.cube(f"production_{prefix}_seat_row_shadow_{row}", (x, 0, z), (0.08, depth, 0.08), "concrete_dark", 0.012)


def add_molded_seat_patches():
    sign = 1
    base_y = sign * (base.HALF_Y + 8)
    rows = 28
    for row in range(3, 18):
        y = base_y + sign * (row * 0.78)
        z = 1.25 + row * 0.48
        width = base.PITCH_X + 26 - row * 0.35
        for col in range(8, 141, 3):
            nx = col / 147 - 0.5
            if abs(nx) < 0.018 or abs(nx - 0.23) < 0.014 or abs(nx + 0.23) < 0.014 or abs(nx - 0.39) < 0.014 or abs(nx + 0.39) < 0.014:
                continue
            x = nx * (width - 3)
            mat = "seat_white" if base.seat_text_mask("BENAGALBON CD", col, row, 148, rows, start_col=8, end_col=140) else "green"
            base.cube(f"molded_seat_pan_{row}_{col}", (x, y - sign * 0.06, z + 0.17), (0.46, 0.34, 0.08), mat, 0.035)
            back = base.cube(f"molded_seat_back_{row}_{col}", (x, y + sign * 0.13, z + 0.45), (0.46, 0.08, 0.44), mat, 0.035)
            back.rotation_euler.x = math.radians(-7 * sign)
            base.cube(f"molded_seat_left_ear_{row}_{col}", (x - 0.25, y + sign * 0.04, z + 0.30), (0.055, 0.20, 0.22), mat, 0.02)
            base.cube(f"molded_seat_right_ear_{row}_{col}", (x + 0.25, y + sign * 0.04, z + 0.30), (0.055, 0.20, 0.22), mat, 0.02)


def remove_non_realistic_overlays():
    for obj in list(bpy.context.scene.objects):
        if obj.name.endswith("_seat_name_overlay") or "seat_name_overlay" in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)


def add_stair_handrails():
    for sign, prefix in [(1, "south"), (-1, "north")]:
        base_y = sign * (base.HALF_Y + 8)
        for nx in [-0.39, -0.23, 0.0, 0.23, 0.39]:
            x = nx * (base.PITCH_X + 18)
            for offset in [-0.42, 0.42]:
                base.cylinder_between(
                    f"production_{prefix}_stair_handrail_{nx}_{offset}",
                    (x + offset, base_y + sign * 1.6, 2.0),
                    (x + offset, base_y + sign * 20.4, 14.4),
                    0.035,
                    "steel",
                    10,
                )
            for row in range(3, 25, 4):
                y = base_y + sign * (row * 0.78)
                z = 1.35 + row * 0.48
                base.cylinder_between(
                    f"production_{prefix}_stair_post_{nx}_{row}",
                    (x, y, z),
                    (x, y, z + 0.86),
                    0.028,
                    "steel",
                    8,
                )


def add_production_roof_detail():
    for sign, name in [(1, "south"), (-1, "north")]:
        base_y = sign * (base.HALF_Y + 8)
        for i in range(22):
            x = -base.PITCH_X / 2 - 13 + i * ((base.PITCH_X + 26) / 21)
            base.cylinder_between(
                f"production_{name}_thin_roof_purlin_{i}",
                (x, base_y + sign * 17.4, 21.0),
                (x, base_y + sign * 40.5, 22.4),
                0.035,
                "steel",
                8,
            )
        for j in range(5):
            y = base_y + sign * (19.0 + j * 4.4)
            base.cylinder_between(
                f"production_{name}_long_roof_runner_{j}",
                (-base.PITCH_X / 2 - 18, y, 21.5),
                (base.PITCH_X / 2 + 18, y, 21.5),
                0.045,
                "steel",
                10,
            )
        for i in range(14):
            x0 = -base.PITCH_X / 2 - 18 + i * ((base.PITCH_X + 36) / 13)
            x1 = x0 + ((base.PITCH_X + 36) / 26)
            base.cylinder_between(
                f"production_{name}_roof_x_lattice_a_{i}",
                (x0, base_y + sign * 18.2, 19.6),
                (x1, base_y + sign * 38.5, 22.9),
                0.030,
                "steel",
                8,
            )
            base.cylinder_between(
                f"production_{name}_roof_x_lattice_b_{i}",
                (x1, base_y + sign * 18.2, 19.8),
                (x0, base_y + sign * 38.5, 22.7),
                0.030,
                "steel",
                8,
            )
        for j in range(4):
            y = base_y + sign * (21.5 + j * 4.8)
            panel = base.cube(f"production_{name}_translucent_roof_panel_{j}", (0, y, 22.08 + j * 0.04), (base.PITCH_X + 42, 2.8, 0.08), "glass", 0.012)
            panel.rotation_euler.x = math.radians(2.5 * sign)


def add_modeled_floodlights():
    for sign, prefix in [(1, "south"), (-1, "north")]:
        base_y = sign * (base.HALF_Y + 8)
        for i in range(11):
            x = -base.PITCH_X / 2 - 3 + i * ((base.PITCH_X + 6) / 10)
            y = base_y + sign * 16.8
            z = 20.0
            base.cube(f"production_{prefix}_floodlight_housing_{i}", (x, y, z), (2.6, 0.34, 0.36), "roof", 0.025)
            base.cube(f"production_{prefix}_floodlight_glass_{i}", (x, y - sign * 0.20, z - 0.01), (2.35, 0.045, 0.24), "light", 0.012)
            for j in [-0.9, 0.0, 0.9]:
                base.cylinder_between(
                    f"production_{prefix}_floodlight_bracket_{i}_{j}",
                    (x + j, y + sign * 0.18, z - 0.2),
                    (x + j, y + sign * 1.4, z + 0.75),
                    0.025,
                    "steel",
                    8,
                )


def add_facade_paneling():
    for sign, prefix in [(1, "south"), (-1, "north")]:
        y = sign * (base.HALF_Y + 49.7)
        base.cube(f"production_{prefix}_dark_back_of_house", (0, y, 10.2), (base.PITCH_X + 72, 0.42, 13.4), "concrete_dark", 0.02)
        for x in range(-64, 65, 8):
            base.cube(f"production_{prefix}_facade_light_panel_{x}", (x, y - sign * 0.24, 10.4), (5.2, 0.18, 10.8), "concrete", 0.018)
            base.cube(f"production_{prefix}_facade_reveal_{x}", (x + 3.1, y - sign * 0.35, 10.4), (0.12, 0.16, 10.9), "concrete_dark", 0.006)


def add_matchday_micro_architecture():
    # Adds close-range stadium cues that read well in the interactive Three.js camera.
    for sign, prefix in [(1, "south"), (-1, "north")]:
        outer_y = sign * (base.HALF_Y + 55.3)
        inner_y = sign * (base.HALF_Y + 2.7)
        base.cube(f"production_{prefix}_outer_concourse_slab", (0, outer_y, 0.11), (base.PITCH_X + 80, 8.0, 0.22), "asphalt", 0.012)
        base.cube(f"production_{prefix}_ticketing_glass_wall", (-38, outer_y - sign * 1.8, 3.2), (18.0, 0.28, 5.6), "glass", 0.018)
        base.cube(f"production_{prefix}_club_shop_glass_wall", (36, outer_y - sign * 1.8, 3.0), (20.0, 0.28, 5.2), "glass", 0.018)
        base.add_text(
            f"production_{prefix}_ticketing_sign",
            "TAQUILLAS",
            (-38, outer_y - sign * 2.02, 6.45),
            0.72,
            "white",
            rot=(math.radians(90), 0, 0),
            extrude=0.01,
        )
        base.add_text(
            f"production_{prefix}_shop_sign",
            "BENAGALBON CD",
            (36, outer_y - sign * 2.02, 6.25),
            0.66,
            "white",
            rot=(math.radians(90), 0, 0),
            extrude=0.01,
        )
        for i, x in enumerate(range(-58, 59, 8)):
            base.cube(f"production_{prefix}_turnstile_plinth_{i}", (x, outer_y - sign * 5.2, 0.62), (2.2, 0.42, 1.0), "concrete_dark", 0.02)
            base.cylinder_between(
                f"production_{prefix}_turnstile_bar_a_{i}",
                (x - 0.68, outer_y - sign * 5.4, 1.25),
                (x + 0.68, outer_y - sign * 5.4, 1.25),
                0.022,
                "steel",
                8,
            )
            base.cylinder_between(
                f"production_{prefix}_turnstile_bar_b_{i}",
                (x, outer_y - sign * 5.95, 0.72),
                (x, outer_y - sign * 4.85, 1.78),
                0.018,
                "steel",
                8,
            )
        for x in range(-64, 65, 16):
            base.cylinder_between(f"production_{prefix}_concourse_light_post_{x}", (x, outer_y - sign * 6.7, 0.1), (x, outer_y - sign * 6.7, 7.2), 0.055, "steel", 10)
            base.cube(f"production_{prefix}_concourse_light_head_{x}", (x, outer_y - sign * 6.95, 7.35), (1.6, 0.34, 0.28), "light", 0.02)
        for x in range(-52, 53, 13):
            base.cube(f"production_{prefix}_pitch_camera_box_{x}", (x, inner_y, 2.85), (1.2, 0.34, 0.72), "screen", 0.02)
            base.cylinder_between(
                f"production_{prefix}_pitch_camera_lens_{x}",
                (x, inner_y - sign * 0.22, 2.85),
                (x, inner_y - sign * 0.54, 2.85),
                0.18,
                "rubber",
                16,
            )
            base.cylinder_between(f"production_{prefix}_camera_tripod_{x}_a", (x, inner_y, 2.48), (x - 0.42, inner_y + sign * 0.38, 0.28), 0.025, "steel", 8)
            base.cylinder_between(f"production_{prefix}_camera_tripod_{x}_b", (x, inner_y, 2.48), (x + 0.42, inner_y + sign * 0.38, 0.28), 0.025, "steel", 8)
            base.cylinder_between(f"production_{prefix}_camera_tripod_{x}_c", (x, inner_y, 2.48), (x, inner_y - sign * 0.55, 0.28), 0.025, "steel", 8)

    for sign, prefix in [(1, "east"), (-1, "west")]:
        outer_x = sign * (base.HALF_X + 42.0)
        base.cube(f"production_{prefix}_service_road", (outer_x, 0, 0.08), (7.5, base.PITCH_Y + 76, 0.16), "asphalt", 0.006)
        for y in range(-56, 57, 14):
            base.cube(f"production_{prefix}_wayfinding_totem_{y}", (outer_x - sign * 2.7, y, 2.05), (0.62, 1.8, 3.8), "green_dark", 0.018)
            base.add_text(
                f"production_{prefix}_wayfinding_label_{y}",
                "ACCESO",
                (outer_x - sign * 3.04, y, 2.75),
                0.34,
                "white",
                rot=(math.radians(90), 0, math.radians(90)),
                extrude=0.008,
            )


def add_sponsor_and_identity_layer():
    sponsors = ["SEGUNDA JUGADA", "MODERNIA", "INVERSURE", "FINCAS VELAZQUEZ"]
    for sign, prefix in [(1, "north"), (-1, "south")]:
        y = sign * (base.HALF_Y + 4.95)
        for i, label in enumerate(sponsors):
            x = -45 + i * 30
            base.cube(f"production_{prefix}_sponsor_panel_{i}", (x, y, 1.2), (21.0, 0.16, 1.6), "green_dark", 0.018)
            base.add_text(
                f"production_{prefix}_sponsor_text_{i}",
                label,
                (x, y - sign * 0.12, 1.25),
                0.42,
                "white",
                rot=(math.radians(90), 0, 0),
                extrude=0.008,
            )
    for sign, prefix in [(1, "east"), (-1, "west")]:
        x = sign * (base.HALF_X + 4.95)
        for i, label in enumerate(reversed(sponsors)):
            y = -35 + i * 23
            base.cube(f"production_{prefix}_goal_sponsor_panel_{i}", (x, y, 1.18), (0.16, 16.2, 1.5), "green_dark", 0.018)
            base.add_text(
                f"production_{prefix}_goal_sponsor_text_{i}",
                label,
                (x - sign * 0.12, y, 1.22),
                0.36,
                "white",
                rot=(math.radians(90), 0, math.radians(90)),
                extrude=0.008,
            )


def add_realistic_pitch_wear_and_service_marks():
    worn = []
    dark = []
    for i in range(80):
        x = -base.HALF_X + 4 + (i * 9.7 % (base.PITCH_X - 8))
        y = -base.HALF_Y + 5 + (i * 14.3 % (base.PITCH_Y - 10))
        if abs(x) < 10 and abs(y) < 12:
            continue
        worn.append(((x, y, 0.153), (1.2 + (i % 4) * 0.38, 0.20 + (i % 5) * 0.08, 0.016)))
    for i in range(46):
        x = -base.HALF_X + 2 + (i * 17.1 % (base.PITCH_X - 4))
        y = -base.HALF_Y + 2 + (i * 6.9 % (base.PITCH_Y - 4))
        dark.append(((x, y, 0.156), (0.62 + (i % 3) * 0.24, 0.10 + (i % 4) * 0.05, 0.012)))
    base.mesh_boxes("production_pitch_boot_wear_soft_patches", worn, "grass_wear")
    base.mesh_boxes("production_pitch_darker_repair_grain", dark, "grass_shadow")


def add_concrete_joint_lines():
    for sign, prefix in [(1, "south"), (-1, "north")]:
        y = sign * (base.HALF_Y + 34.0)
        for x in range(-60, 61, 10):
            base.cube(f"production_{prefix}_facade_joint_{x}", (x, y, 10.8), (0.10, 0.18, 11.0), "concrete_dark", 0.006)
    for sign, prefix in [(1, "east"), (-1, "west")]:
        x = sign * (base.HALF_X + 24.5)
        for y in range(-42, 43, 10):
            base.cube(f"production_{prefix}_facade_joint_{y}", (x, y, 8.4), (0.18, 0.10, 8.5), "concrete_dark", 0.006)


def add_pitchside_realism():
    for sign, prefix in [(1, "north"), (-1, "south")]:
        y = sign * (base.HALF_Y + 4.1)
        base.cube(f"production_{prefix}_photo_pit_dark_channel", (0, y, 0.18), (base.PITCH_X + 14, 1.35, 0.18), "asphalt", 0.008)
        for x in range(-52, 53, 8):
            base.cylinder_between(f"production_{prefix}_front_fence_post_{x}", (x, y, 0.18), (x, y, 2.25), 0.022, "steel", 8)
        for z in [0.8, 1.45, 2.05]:
            base.cylinder_between(f"production_{prefix}_front_fence_rail_{z}", (-base.HALF_X - 7, y, z), (base.HALF_X + 7, y, z), 0.024, "steel", 8)
    for x, name in [(-28, "left"), (28, "right")]:
        base.cube(f"production_pitchside_dugout_shadow_{name}", (x, -base.HALF_Y - 7.1, 0.42), (15.0, 2.4, 0.16), "asphalt", 0.02)
        for i in range(7):
            base.cube(f"production_dugout_seat_highback_{name}_{i}", (x - 4.5 + i * 1.5, -base.HALF_Y - 7.6, 1.45), (0.82, 0.20, 0.92), "green", 0.025)


def add_better_environment():
    # Replace procedural blob clouds with flatter background clouds and a richer distant skyline.
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith("soft_cloud_"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for i in range(8):
        x = -150 + i * 26
        y = 168 + math.sin(i * 1.4) * 8
        z = 54 + (i % 3) * 2
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=10, radius=1, location=(x, y, z))
        cloud = bpy.context.object
        cloud.name = f"production_flat_cloud_{i:02d}"
        cloud.scale = (10 + (i % 4) * 2.5, 1.9, 0.62)
        cloud.data.materials.append(base.M["cloud"])
        cloud.visible_shadow = False
    for i in range(14):
        h = 11 + (i % 6) * 3
        x = -125 + i * 15
        y = 155 + (i % 5) * 3
        base.cube(f"production_skyline_tower_{i:02d}", (x, y, h / 2), (7.0, 5.0, h), "city", 0.02)


def set_camera(name, location, target, lens):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.name = name
    direction = Vector(target) - Vector(cam.location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (Vector(target) - Vector(location)).length
    cam.data.dof.aperture_fstop = 9.0
    bpy.context.scene.camera = cam
    return cam


def render_to(path, resolution=(2400, 1350)):
    scene = bpy.context.scene
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def build_scene():
    print("BUILD=reset")
    base.reset_scene()
    base.init_materials()
    tune_render()
    tune_production_materials()
    print("BUILD=pitch")
    base.add_pitch()
    base.add_pitch_professional_detail()
    base.add_low_grass_geometry()
    print("BUILD=stands")
    base.add_long_stand("south_main_stand", 1)
    base.add_long_stand("north_stand", -1)
    base.add_end_stand("east_goal_stand", 1)
    base.add_end_stand("west_goal_stand", -1)
    base.add_corner_stands()
    print("BUILD=details")
    base.add_boards()
    base.add_goals_and_benches()
    base.add_players_tunnel_and_technical_area()
    base.add_inner_bowl_finishing_details()
    base.add_architectural_quality_pass()
    base.add_broadcast_and_matchday_details()
    base.add_outer_facade_and_pitch_details()
    base.add_screen_and_crest()
    base.add_environment()
    remove_non_realistic_overlays()
    add_hair_grass()
    add_close_grass_blade_clusters()
    add_reference_pitch_striping()
    add_production_seat_depth()
    remove_main_stand_seat_noise()
    add_reference_main_stand_mosaic()
    print("BUILD=production architecture")
    add_upper_bowl_mass_and_vomitories()
    add_stair_handrails()
    add_production_roof_detail()
    add_modeled_floodlights()
    add_reference_roof_and_scoreboard()
    add_pitchside_realism()
    add_concrete_joint_lines()
    add_facade_paneling()
    add_matchday_micro_architecture()
    add_sponsor_and_identity_layer()
    add_realistic_pitch_wear_and_service_marks()
    add_better_environment()
    base.add_lighting_and_camera()
    sun = bpy.data.objects.get("production_extra_sun")
    if not sun:
        bpy.ops.object.light_add(type="SUN", location=(-90, -115, 135))
        sun = bpy.context.object
        sun.name = "production_extra_sun"
    sun.data.energy = 1.05
    sun.rotation_euler = (math.radians(42), 0, math.radians(-33))

    set_camera("production_broadcast_camera", (-76, -63, 27), (0, 4, 6.0), 28)
    print("BUILD=save")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    print("BUILD=export_glb")
    bpy.ops.export_scene.gltf(filepath=str(OUT_GLB), export_format="GLB", export_yup=True)
    print("BUILD=render_final")
    render_to(OUT_RENDER)
    set_camera("production_detail_camera", (-48, -49, 20), (-4, 1, 4), 34)
    print("BUILD=render_detail")
    render_to(OUT_DETAIL, (1800, 1200))
    set_camera("production_closeup_camera", (-30, -39, 12.5), (-4, 18, 7.2), 45)
    print("BUILD=render_closeup")
    render_to(OUT_CLOSEUP, (1800, 1200))
    print(f"BLEND={OUT_BLEND}")
    print(f"GLB={OUT_GLB}")
    print(f"RENDER={OUT_RENDER}")
    print(f"DETAIL={OUT_DETAIL}")
    print(f"CLOSEUP={OUT_CLOSEUP}")


if __name__ == "__main__":
    build_scene()
