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

    add(cube(f"{name}_continuous_podium", tr(0, 6.5, 0.45), (length + 4, 20.5, 0.9), mat_concrete, (0, 0, rot)))
    add(cube(f"{name}_pitch_fascia_TEAM_ACCENT", tr(0, -2.8, 1.05), (length + 1.5, 0.42, 1.15), mat_team, (0, 0, rot)))

    row_counts = (18, 13, 8)
    row_origins = ((-0.6, 0.86), (10.2, 5.72), (16.9, 9.25))
    row_widths = (1.00, 0.88, 0.78)
    for tier, rows in enumerate(row_counts):
        base_y, base_z = row_origins[tier]
        width_factor = row_widths[tier]
        if tier:
            add(cube(f"{name}_concourse_{tier}", tr(0, base_y - 0.55, base_z - 0.20), (length * (width_factor + 0.04), 1.35, 0.42), mat_concrete, (0, 0, rot)))
            add(cube(f"{name}_glass_rail_{tier}", tr(0, base_y - 1.25, base_z + 0.28), (length * width_factor, 0.13, 0.34), mat_glass, (0, 0, rot)))
        for r in range(rows):
            py = base_y + r * 0.70
            pz = base_z + r * 0.36
            add(cube(f"{name}_riser_{tier}_{r:02d}", tr(0, py, pz), (length * width_factor, 0.52, 0.20), mat_concrete, (-0.055, 0, rot)))
            add(cube(f"{name}_seat_band_TEAM_PRIMARY_{tier}_{r:02d}", tr(0, py - 0.08, pz + 0.16), (length * (width_factor - 0.04), 0.34, 0.16), mat_team, (-0.09, 0, rot)))

    for ratio in (-0.40, -0.24, 0.0, 0.24, 0.40):
        px = ratio * length
        add(cube(f"{name}_stair_TEAM_SECONDARY_{ratio:.2f}", tr(px, 4.2, 2.9), (1.1, 10.8, 0.18), mat_secondary, (-0.055, 0, rot)))
        add(cube(f"{name}_vomitory_{ratio:.2f}", tr(px, 0.18, 2.25), (3.25, 0.34, 1.85), mat_dark, (0, 0, rot)))
        add(cube(f"{name}_upper_vomitory_{ratio:.2f}", tr(px, 13.3, 7.1), (3.25, 0.34, 1.45), mat_dark, (0, 0, rot)))

    add(cube(f"{name}_continuous_roof_TEAM_SECONDARY", tr(0, 22.0, 14.5), (length + 10, 9.4, 0.36), mat_roof, (-0.015, 0, rot)))
    add(cube(f"{name}_light_bar", tr(0, 17.7, 12.95), (length * 0.86, 0.20, 0.14), mat_light, (0, 0, rot)))
    for i in range(-6, 7):
        px = i * (length / 12)
        add(cube(f"{name}_roof_rib_{i}", tr(px, 20.8, 13.72), (0.14, 8.8, 0.16), mat_metal, (0, 0, rot)))
        if i % 2 == 0:
            add(cube(f"{name}_rear_mast_{i}", tr(px, 24.3, 9.7), (0.26, 0.26, 8.1), mat_concrete, (0, 0, rot)))
            add(cube(f"{name}_cantilever_brace_{i}", tr(px, 21.6, 11.6), (0.16, 6.1, 0.18), mat_metal, (0.55, 0, rot)))


def add_corner(name, x, y, rot, mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats

    def tr(px, py, pz):
        ca = math.cos(rot)
        sa = math.sin(rot)
        return (x + px * ca - py * sa, y + px * sa + py * ca, pz)

    add = lambda obj: obj
    add(cube(f"{name}_corner_podium", tr(0, 6.3, 0.45), (25, 20, 0.9), mat_concrete, (0, 0, rot)))
    add(cube(f"{name}_corner_fascia_TEAM_ACCENT", tr(0, -2.6, 1.05), (24, 0.42, 1.15), mat_team, (0, 0, rot)))
    for r in range(18):
        py = -0.65 + r * 0.72
        pz = 0.86 + r * 0.36
        width = 22 - r * 0.32
        add(cube(f"{name}_corner_riser_{r:02d}", tr(0, py, pz), (width, 0.50, 0.20), mat_concrete, (-0.055, 0, rot)))
        add(cube(f"{name}_corner_seats_TEAM_PRIMARY_{r:02d}", tr(0, py - 0.08, pz + 0.16), (max(5, width - 1.4), 0.32, 0.15), mat_team, (-0.09, 0, rot)))
    add(cube(f"{name}_corner_roof_TEAM_SECONDARY", tr(0, 21.2, 14.5), (29, 8.8, 0.36), mat_roof, (-0.015, 0, rot)))
    add(cube(f"{name}_corner_light_bar", tr(0, 17.2, 12.95), (17.5, 0.20, 0.14), mat_light, (0, 0, rot)))
    for ratio in (-0.35, 0.35):
        add(cube(f"{name}_corner_rear_mast_{ratio}", tr(ratio * 22, 23.2, 9.7), (0.26, 0.26, 8.1), mat_concrete, (0, 0, rot)))


def add_tunnel_and_benches(mats):
    mat_team, mat_secondary, mat_concrete, mat_dark, mat_glass, mat_metal, mat_roof, mat_light = mats
    y = -41
    cube("integrated_players_tunnel_frame", (0, y, 1.45), (9.2, 0.55, 2.35), mat_concrete)
    cube("integrated_players_tunnel_opening", (0, y - 0.34, 1.25), (6.4, 0.12, 1.62), mat_dark)
    cube("integrated_players_tunnel_roof_TEAM_SECONDARY", (0, y + 1.8, 2.62), (9.4, 5.8, 0.34), mat_roof, (-0.04, 0, 0))
    cube("integrated_players_tunnel_header_TEAM_ACCENT", (0, y - 0.68, 2.38), (9.6, 0.28, 0.88), mat_team)
    for x in (-8.0, 8.0):
        cube(f"premium_dugout_platform_{x}", (x, y + 2.6, 0.18), (11.2, 2.3, 0.20), mat_dark)
        cube(f"premium_dugout_glass_{x}", (x, y + 1.62, 1.18), (10.8, 0.12, 1.20), mat_glass)
        cube(f"premium_dugout_roof_{x}", (x, y + 2.45, 2.20), (11.4, 2.0, 0.12), mat_glass, (-0.18, 0, 0))
        for seat in range(8):
            sx = x - 4.1 + seat * 1.18
            cube(f"premium_dugout_seat_TEAM_PRIMARY_{x}_{seat}", (sx, y + 2.72, 0.68), (0.72, 0.58, 0.22), mat_team)


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
    mat_light = mat("STADIUM_LIGHTS", (0.90, 0.96, 1.0, 1), 0.12, 0.0, 1.0, (0.70, 0.88, 1.0, 1), 1.2)

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

    # Continuous roof links make the stadium read as one closed object.
    cube("roof_link_north_TEAM_SECONDARY", (0, 67.8, 14.65), (125, 4.2, 0.30), mat_secondary, (-0.015, 0, 0))
    cube("roof_link_south_TEAM_SECONDARY", (0, -67.8, 14.65), (125, 4.2, 0.30), mat_secondary, (0.015, 0, 0))
    cube("roof_link_east_TEAM_SECONDARY", (87.4, 0, 14.65), (4.2, 105, 0.30), mat_secondary)
    cube("roof_link_west_TEAM_SECONDARY", (-87.4, 0, 14.65), (4.2, 105, 0.30), mat_secondary)

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
