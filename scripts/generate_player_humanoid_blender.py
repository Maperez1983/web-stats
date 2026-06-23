import math
import os

import bpy
import bmesh


OUT_PATH = "/Volumes/Mac Satecchi/Mac/Web-stats/football/static/football/models/avatar/player_humanoid.glb"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_name in ("meshes", "materials", "images", "lights", "cameras"):
        block = getattr(bpy.data, block_name)
        for item in list(block):
            try:
                block.remove(item)
            except Exception:
                pass


def make_material(name, rgba, roughness=0.7, metallic=0.02):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    output.location = (240, 0)
    bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def new_empty(name, parent=None, location=(0, 0, 0), rotation=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.location = location
    obj.rotation_euler = rotation
    bpy.context.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def apply_parent(obj, parent):
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()


def smooth(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def add_tapered_cylinder(
    name,
    radius_top,
    radius_bottom,
    depth,
    location,
    vertices=6,
    rotation=(0, 0, 0),
    parent=None,
    material=None,
    scale=(1, 1, 1),
):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=1.0,
        depth=depth,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    z_half = depth / 2.0
    for vert in bm.verts:
        factor = radius_top if vert.co.z > 0 else radius_bottom
        vert.co.x *= factor
        vert.co.y *= factor
    bm.to_mesh(mesh)
    bm.free()
    if material:
        mesh.materials.append(material)
    if parent:
        apply_parent(obj, parent)
    smooth(obj)
    return obj


def add_box(name, scale, location, rotation=(0, 0, 0), parent=None, material=None):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if material:
        obj.data.materials.append(material)
    if parent:
        apply_parent(obj, parent)
    smooth(obj)
    return obj


def add_ico(name, radius, location, parent=None, material=None, subdivisions=1, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=radius, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    if material:
        obj.data.materials.append(material)
    if parent:
        apply_parent(obj, parent)
    smooth(obj)
    return obj


def bevel(obj, width=0.02, segments=2):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.select_set(False)


def build_player():
    clear_scene()

    skin = make_material("Skin", (0.94, 0.79, 0.63, 1.0), roughness=0.86)
    kit_primary = make_material("KitPrimary", (0.87, 0.12, 0.12, 1.0), roughness=0.72)
    kit_secondary = make_material("KitLight", (0.10, 0.64, 0.54, 1.0), roughness=0.74)
    shorts = make_material("Shorts", (0.15, 0.28, 0.88, 1.0), roughness=0.68)
    socks = make_material("Socks", (0.13, 0.58, 0.90, 1.0), roughness=0.75)
    boots = make_material("Boots", (0.09, 0.10, 0.12, 1.0), roughness=0.6)
    hair = make_material("Hair", (0.18, 0.11, 0.06, 1.0), roughness=0.88)

    root = new_empty("PlayerRoot", location=(0, 0, 0))
    torso_pivot = new_empty("TorsoPivot", parent=root, location=(0, 0, 1.05))
    left_arm_pivot = new_empty("LeftArmPivot", parent=torso_pivot, location=(-0.36, 0, 0.34), rotation=(0, 0, math.radians(8)))
    right_arm_pivot = new_empty("RightArmPivot", parent=torso_pivot, location=(0.36, 0, 0.34), rotation=(0, 0, math.radians(-8)))
    left_leg_pivot = new_empty("LeftLegPivot", parent=root, location=(-0.13, 0, 0.9))
    right_leg_pivot = new_empty("RightLegPivot", parent=root, location=(0.13, 0, 0.9))

    torso = add_tapered_cylinder(
        "PlayerBody",
        radius_top=0.34,
        radius_bottom=0.24,
        depth=0.82,
        location=(0, 0, 0.38),
        vertices=6,
        parent=torso_pivot,
        material=kit_primary,
        scale=(1.0, 0.72, 1.0),
    )
    bevel(torso, width=0.016)

    chest_band = add_box(
        "ChestBand",
        scale=(0.24, 0.11, 0.06),
        location=(0, 0.01, 0.20),
        parent=torso_pivot,
        material=kit_secondary,
    )
    stripe_left = add_box(
        "StripeLeft",
        scale=(0.05, 0.12, 0.34),
        location=(-0.10, 0.02, 0.30),
        parent=torso_pivot,
        material=kit_secondary,
    )
    stripe_mid = add_box(
        "StripeMid",
        scale=(0.045, 0.12, 0.36),
        location=(0.0, 0.02, 0.30),
        parent=torso_pivot,
        material=kit_secondary,
    )
    stripe_right = add_box(
        "StripeRight",
        scale=(0.05, 0.12, 0.34),
        location=(0.10, 0.02, 0.30),
        parent=torso_pivot,
        material=kit_secondary,
    )
    neck = add_box("Neck", (0.07, 0.06, 0.07), (0, 0, 0.82), parent=torso_pivot, material=skin)

    shorts_body = add_tapered_cylinder(
        "ShortsBody",
        radius_top=0.26,
        radius_bottom=0.22,
        depth=0.28,
        location=(0, 0, -0.10),
        vertices=6,
        parent=torso_pivot,
        material=shorts,
        scale=(1.0, 0.74, 1.0),
    )
    bevel(shorts_body, width=0.012)

    left_arm = add_tapered_cylinder(
        "LeftArm",
        radius_top=0.085,
        radius_bottom=0.072,
        depth=0.58,
        location=(0, 0, -0.21),
        vertices=6,
        parent=left_arm_pivot,
        material=kit_primary,
        scale=(0.95, 0.95, 1.0),
    )
    left_forearm = add_tapered_cylinder(
        "LeftForearm",
        radius_top=0.07,
        radius_bottom=0.06,
        depth=0.42,
        location=(0, 0, -0.57),
        vertices=6,
        parent=left_arm_pivot,
        material=skin,
        scale=(0.92, 0.92, 1.0),
    )
    left_hand = add_box("LeftHand", (0.05, 0.04, 0.08), (0, 0, -0.82), parent=left_arm_pivot, material=skin)

    right_arm = add_tapered_cylinder(
        "RightArm",
        radius_top=0.085,
        radius_bottom=0.072,
        depth=0.58,
        location=(0, 0, -0.21),
        vertices=6,
        parent=right_arm_pivot,
        material=kit_primary,
        scale=(0.95, 0.95, 1.0),
    )
    right_forearm = add_tapered_cylinder(
        "RightForearm",
        radius_top=0.07,
        radius_bottom=0.06,
        depth=0.42,
        location=(0, 0, -0.57),
        vertices=6,
        parent=right_arm_pivot,
        material=skin,
        scale=(0.92, 0.92, 1.0),
    )
    right_hand = add_box("RightHand", (0.05, 0.04, 0.08), (0, 0, -0.82), parent=right_arm_pivot, material=skin)

    for obj in (left_arm, left_forearm, left_hand, right_arm, right_forearm, right_hand, neck, chest_band, stripe_left, stripe_mid, stripe_right):
        bevel(obj, width=0.012)

    left_thigh = add_tapered_cylinder(
        "LeftThigh",
        radius_top=0.11,
        radius_bottom=0.095,
        depth=0.48,
        location=(0, 0, -0.22),
        vertices=6,
        parent=left_leg_pivot,
        material=skin,
        scale=(0.88, 0.96, 1.0),
    )
    left_sock = add_tapered_cylinder(
        "LeftSock",
        radius_top=0.09,
        radius_bottom=0.08,
        depth=0.50,
        location=(0, 0, -0.72),
        vertices=6,
        parent=left_leg_pivot,
        material=socks,
        scale=(0.82, 0.90, 1.0),
    )
    left_boot = add_box(
        "LeftBoot",
        scale=(0.08, 0.18, 0.055),
        location=(0.0, 0.075, -1.02),
        rotation=(math.radians(8), 0, 0),
        parent=left_leg_pivot,
        material=boots,
    )

    right_thigh = add_tapered_cylinder(
        "RightThigh",
        radius_top=0.11,
        radius_bottom=0.095,
        depth=0.48,
        location=(0, 0, -0.22),
        vertices=6,
        parent=right_leg_pivot,
        material=skin,
        scale=(0.88, 0.96, 1.0),
    )
    right_sock = add_tapered_cylinder(
        "RightSock",
        radius_top=0.09,
        radius_bottom=0.08,
        depth=0.50,
        location=(0, 0, -0.72),
        vertices=6,
        parent=right_leg_pivot,
        material=socks,
        scale=(0.82, 0.90, 1.0),
    )
    right_boot = add_box(
        "RightBoot",
        scale=(0.08, 0.18, 0.055),
        location=(0.0, 0.075, -1.02),
        rotation=(math.radians(8), 0, 0),
        parent=right_leg_pivot,
        material=boots,
    )
    for obj in (left_thigh, left_sock, left_boot, right_thigh, right_sock, right_boot):
        bevel(obj, width=0.012)

    head = add_ico(
        "Head",
        radius=0.18,
        location=(0, 0, 1.03),
        parent=torso_pivot,
        material=skin,
        subdivisions=1,
        scale=(0.95, 0.9, 1.05),
    )
    hair_cap = add_tapered_cylinder(
        "HairCap",
        radius_top=0.19,
        radius_bottom=0.16,
        depth=0.20,
        location=(0, 0, 1.10),
        vertices=6,
        parent=torso_pivot,
        material=hair,
        scale=(1.0, 0.9, 0.6),
    )
    fringe = add_box(
        "HairFringe",
        scale=(0.13, 0.06, 0.10),
        location=(0, 0.10, 1.07),
        rotation=(math.radians(10), 0, 0),
        parent=torso_pivot,
        material=hair,
    )
    hair_left = add_box(
        "HairLeft",
        scale=(0.045, 0.05, 0.18),
        location=(-0.12, 0.02, 0.93),
        rotation=(0, math.radians(8), 0),
        parent=torso_pivot,
        material=hair,
    )
    hair_right = add_box(
        "HairRight",
        scale=(0.045, 0.05, 0.18),
        location=(0.12, 0.02, 0.93),
        rotation=(0, math.radians(-8), 0),
        parent=torso_pivot,
        material=hair,
    )
    for obj in (head, hair_cap, fringe, hair_left, hair_right):
        bevel(obj, width=0.01)

    bpy.ops.object.camera_add(location=(0, -7, 2.5), rotation=(math.radians(78), 0, 0))
    bpy.context.scene.camera = bpy.context.active_object

    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 24

    keys = [
        (1, 0.34, -0.34, -0.52, 0.52, -0.18),
        (7, -0.10, 0.10, 0.18, -0.18, 0.06),
        (13, -0.34, 0.34, 0.52, -0.52, 0.18),
        (19, 0.10, -0.10, -0.18, 0.18, -0.06),
        (24, 0.34, -0.34, -0.52, 0.52, -0.18),
    ]

    for frame, l_arm_x, r_arm_x, l_leg_x, r_leg_x, torso_x in keys:
        scene.frame_set(frame)
        left_arm_pivot.rotation_euler = (l_arm_x, 0, math.radians(8))
        right_arm_pivot.rotation_euler = (r_arm_x, 0, math.radians(-8))
        left_leg_pivot.rotation_euler = (l_leg_x, 0, 0)
        right_leg_pivot.rotation_euler = (r_leg_x, 0, 0)
        torso_pivot.rotation_euler = (torso_x, 0, 0)
        root.location = (0, 0, 0.02 * math.sin((frame / 24.0) * math.pi * 2))
        left_arm_pivot.keyframe_insert(data_path="rotation_euler")
        right_arm_pivot.keyframe_insert(data_path="rotation_euler")
        left_leg_pivot.keyframe_insert(data_path="rotation_euler")
        right_leg_pivot.keyframe_insert(data_path="rotation_euler")
        torso_pivot.keyframe_insert(data_path="rotation_euler")
        root.keyframe_insert(data_path="location")

    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for child in root.children_recursive:
        child.select_set(True)
    bpy.context.view_layer.objects.active = root

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT_PATH,
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_animations=True,
        export_frame_range=True,
        export_nla_strips=False,
        export_force_sampling=True,
    )


if __name__ == "__main__":
    build_player()
