import math
import os
import shutil
import sys

import bpy
from mathutils import Vector


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_humanoid.glb')
COPY_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_premium_mpfb.glb')
DOWNLOAD_COPY = os.path.expanduser('~/Downloads/player_anatomical_footballer.glb')


def make_mat(name, color, roughness=0.65, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    return mat


def assign_mat(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def shade(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    obj.select_set(False)


def uv_sphere(name, loc, scale, mat, segments=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=1.0,
        location=loc,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    assign_mat(obj, mat)
    shade(obj)
    return obj


def cylinder(name, loc, radius, depth, mat, vertices=32, scale=(1, 1, 1), rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    assign_mat(obj, mat)
    shade(obj)
    return obj


def capsule_between(name, start, end, radius, mat, squash=(1.0, 1.0)):
    start = Vector(start)
    end = Vector(end)
    mid = (start + end) * 0.5
    direction = end - start
    length = direction.length
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=radius,
        depth=length,
        location=mid,
    )
    body = bpy.context.object
    body.name = f'{name}_body'
    body.scale.x *= squash[0]
    body.scale.y *= squash[1]
    body.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    assign_mat(body, mat)
    shade(body)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=12, radius=radius, location=start)
    a = bpy.context.object
    a.name = f'{name}_joint_a'
    a.scale.x *= squash[0]
    a.scale.y *= squash[1]
    assign_mat(a, mat)
    shade(a)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=12, radius=radius, location=end)
    b = bpy.context.object
    b.name = f'{name}_joint_b'
    b.scale.x *= squash[0]
    b.scale.y *= squash[1]
    assign_mat(b, mat)
    shade(b)

    return [body, a, b]


def add_textured_stripe(parent, name, x, width, mat):
    stripe = cylinder(
        name,
        (x, 0.003, 1.195),
        0.021,
        0.50,
        mat,
        vertices=16,
        scale=(width / 0.042, 0.20, 1.0),
        rotation=(math.pi / 2, 0, 0),
    )
    stripe.parent = parent
    return stripe


def build_armature():
    arm_data = bpy.data.armatures.new('footballer_action_rig_data')
    arm = bpy.data.objects.new('footballer_action_rig', arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    bones = {
        'hips': ((0, 0, 0.78), (0, 0, 0.98)),
        'spine': ((0, 0, 0.98), (0, 0, 1.30)),
        'neck': ((0, 0, 1.30), (0, 0, 1.43)),
        'head': ((0, 0, 1.43), (0, 0, 1.62)),
        'left_upper_arm': ((-0.21, 0, 1.27), (-0.44, 0.015, 1.08)),
        'left_forearm': ((-0.44, 0.015, 1.08), (-0.52, 0.03, 0.84)),
        'left_hand': ((-0.52, 0.03, 0.84), (-0.54, 0.04, 0.76)),
        'right_upper_arm': ((0.21, 0, 1.27), (0.44, 0.015, 1.08)),
        'right_forearm': ((0.44, 0.015, 1.08), (0.52, 0.03, 0.84)),
        'right_hand': ((0.52, 0.03, 0.84), (0.54, 0.04, 0.76)),
        'left_thigh': ((-0.115, 0, 0.80), (-0.135, 0.015, 0.46)),
        'left_shin': ((-0.135, 0.015, 0.46), (-0.125, 0.03, 0.13)),
        'left_foot': ((-0.125, 0.03, 0.13), (-0.125, 0.16, 0.04)),
        'right_thigh': ((0.115, 0, 0.80), (0.135, -0.015, 0.46)),
        'right_shin': ((0.135, -0.015, 0.46), (0.125, 0.03, 0.13)),
        'right_foot': ((0.125, 0.03, 0.13), (0.125, 0.16, 0.04)),
    }
    edit_bones = {}
    for name, (head, tail) in bones.items():
        bone = arm_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        edit_bones[name] = bone

    for child, parent in {
        'spine': 'hips',
        'neck': 'spine',
        'head': 'neck',
        'left_upper_arm': 'spine',
        'left_forearm': 'left_upper_arm',
        'left_hand': 'left_forearm',
        'right_upper_arm': 'spine',
        'right_forearm': 'right_upper_arm',
        'right_hand': 'right_forearm',
        'left_thigh': 'hips',
        'left_shin': 'left_thigh',
        'left_foot': 'left_shin',
        'right_thigh': 'hips',
        'right_shin': 'right_thigh',
        'right_foot': 'right_shin',
    }.items():
        edit_bones[child].parent = edit_bones[parent]

    bpy.ops.object.mode_set(mode='OBJECT')
    arm.hide_viewport = True
    arm.hide_render = True
    arm.select_set(False)
    return arm


def main():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    skin = make_mat('footballer_skin_warm', (0.66, 0.43, 0.27, 1), 0.54)
    skin_shadow = make_mat('footballer_skin_shadow', (0.45, 0.27, 0.17, 1), 0.66)
    jersey = make_mat('footballer_emerald_jersey', (0.0, 0.46, 0.29, 1), 0.55)
    jersey_dark = make_mat('footballer_deep_green_side_panels', (0.0, 0.28, 0.19, 1), 0.62)
    trim = make_mat('footballer_white_trim', (0.92, 0.95, 0.90, 1), 0.68)
    shorts = make_mat('footballer_navy_shorts', (0.015, 0.025, 0.052, 1), 0.70)
    socks = make_mat('footballer_white_socks', (0.88, 0.91, 0.86, 1), 0.72)
    boots = make_mat('footballer_black_boots', (0.008, 0.009, 0.012, 1), 0.52)
    studs = make_mat('footballer_boot_studs', (0.78, 0.82, 0.76, 1), 0.42)
    hair = make_mat('footballer_dark_hair', (0.025, 0.017, 0.012, 1), 0.76)
    eye = make_mat('footballer_eye_dark', (0.018, 0.014, 0.012, 1), 0.40)
    white = make_mat('footballer_eye_white', (0.88, 0.86, 0.80, 1), 0.50)

    rig = build_armature()
    group = bpy.data.objects.new('footballer_anatomical_player', None)
    bpy.context.collection.objects.link(group)

    parts = []

    # Anatomical body under the kit: visible neck, arms and face use a warmer skin tone.
    parts.append(uv_sphere('footballer_head_cranium', (0, 0.015, 1.58), (0.105, 0.085, 0.135), skin, 40, 20))
    parts.append(uv_sphere('footballer_jaw_chin', (0, 0.055, 1.505), (0.083, 0.070, 0.065), skin, 32, 12))
    parts.append(uv_sphere('footballer_neck', (0, 0.0, 1.365), (0.055, 0.050, 0.090), skin, 32, 12))
    parts.append(uv_sphere('footballer_nose', (0, 0.103, 1.575), (0.018, 0.027, 0.030), skin_shadow, 16, 8))
    for x in (-0.035, 0.035):
        parts.append(uv_sphere(f'footballer_eye_white_{x}', (x, 0.090, 1.615), (0.018, 0.007, 0.010), white, 16, 8))
        parts.append(uv_sphere(f'footballer_pupil_{x}', (x, 0.097, 1.615), (0.007, 0.003, 0.006), eye, 12, 6))
        parts.append(uv_sphere(f'footballer_ear_{x}', (x * 2.9, 0.01, 1.585), (0.018, 0.012, 0.034), skin, 16, 8))
    parts.append(uv_sphere('footballer_hair_cap', (0, -0.002, 1.678), (0.112, 0.088, 0.052), hair, 40, 10))
    parts.append(uv_sphere('footballer_hair_front', (0, 0.060, 1.660), (0.092, 0.030, 0.030), hair, 24, 8))

    # Kit with a real torso silhouette: shoulders, chest taper, waist and pelvis.
    torso = uv_sphere('footballer_torso_athletic_jersey', (0, 0.0, 1.130), (0.188, 0.094, 0.245), jersey, 48, 20)
    torso.parent = group
    parts.append(torso)
    parts.append(uv_sphere('footballer_chest_upper_mass', (0, 0.012, 1.245), (0.198, 0.088, 0.076), jersey, 40, 12))
    parts.append(uv_sphere('footballer_waist_taper', (0, 0.005, 0.940), (0.150, 0.080, 0.076), jersey_dark, 32, 10))
    parts.append(uv_sphere('footballer_pelvis_shorts', (0, 0.0, 0.785), (0.175, 0.087, 0.088), shorts, 40, 12))
    parts.append(cylinder('footballer_shirt_collar', (0, 0.002, 1.345), 0.072, 0.032, trim, vertices=32, scale=(1.15, 0.82, 1.0)))

    # Arms in a relaxed athletic stance.
    for side, sx in [('left', -1), ('right', 1)]:
        parts += capsule_between(f'footballer_{side}_upper_arm_sleeve', (sx * 0.190, 0.000, 1.225), (sx * 0.345, 0.035, 1.060), 0.045, jersey, (0.82, 1.00))
        parts += capsule_between(f'footballer_{side}_forearm_skin', (sx * 0.355, 0.035, 1.035), (sx * 0.445, 0.060, 0.825), 0.033, skin, (0.78, 0.90))
        parts.append(uv_sphere(f'footballer_{side}_hand', (sx * 0.455, 0.072, 0.760), (0.030, 0.023, 0.039), skin, 20, 10))
        for finger in range(4):
            parts.append(capsule_between(
                f'footballer_{side}_finger_{finger}',
                (sx * (0.452 + finger * 0.005), 0.090, 0.735),
                (sx * (0.458 + finger * 0.006), 0.112, 0.707),
                0.0045,
                skin,
                (0.85, 0.85),
            )[0])

    # Legs: shorts, exposed knee zone, socks and boots with recognisable foot volume.
    for side, sx in [('left', -1), ('right', 1)]:
        parts += capsule_between(f'footballer_{side}_thigh_shorts', (sx * 0.082, 0.000, 0.720), (sx * 0.112, 0.010, 0.505), 0.055, shorts, (0.82, 1.00))
        parts.append(uv_sphere(f'footballer_{side}_knee_skin', (sx * 0.114, 0.018, 0.455), (0.043, 0.036, 0.030), skin, 24, 10))
        parts += capsule_between(f'footballer_{side}_shin_sock', (sx * 0.114, 0.020, 0.405), (sx * 0.105, 0.040, 0.150), 0.034, socks, (0.78, 0.92))
        parts.append(cylinder(f'footballer_{side}_sock_top_band', (sx * 0.114, 0.020, 0.405), 0.039, 0.020, trim, vertices=24, scale=(0.90, 0.82, 1.0)))
        boot = uv_sphere(f'footballer_{side}_boot_foot', (sx * 0.105, 0.112, 0.052), (0.048, 0.105, 0.027), boots, 32, 10)
        parts.append(boot)
        parts.append(uv_sphere(f'footballer_{side}_boot_toe', (sx * 0.105, 0.185, 0.052), (0.044, 0.040, 0.024), boots, 24, 8))
        parts.append(cylinder(f'footballer_{side}_boot_white_laces', (sx * 0.105, 0.128, 0.085), 0.005, 0.070, trim, vertices=8, scale=(1, 1, 1), rotation=(math.pi / 2, 0, math.pi / 2)))
        for y in (0.070, 0.130, 0.185):
            parts.append(cylinder(f'footballer_{side}_stud_{y}', (sx * 0.115, y, 0.015), 0.007, 0.010, studs, vertices=10))

    for part in parts:
        if isinstance(part, list):
            continue
        if part.parent is None:
            part.parent = group

    # Merge visual meshes into one renderable object while preserving the hidden action rig.
    bpy.ops.object.select_all(action='DESELECT')
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    player = bpy.context.object
    player.name = 'footballer_anatomical_game_ready_mesh'
    player.data.name = 'footballer_anatomical_game_ready_mesh_data'
    world = player.matrix_world.copy()
    player.parent = None
    player.matrix_world = world

    # Add subtle beveling through weighted normals for less toy-like lighting.
    weighted = player.modifiers.new('footballer_weighted_normals', 'WEIGHTED_NORMAL')
    weighted.keep_sharp = True
    weighted.weight = 50
    bpy.context.view_layer.objects.active = player
    try:
        bpy.ops.object.modifier_apply(modifier=weighted.name)
    except Exception:
        pass

    # Bake Blender's Z-up modeling coordinates into the Y-up orientation used by
    # Three.js/the tactical pad. Without this, the preview sees the footballer
    # lying through the pitch and only the head reads correctly.
    player.rotation_euler[0] = -math.pi / 2
    rig.rotation_euler[0] = -math.pi / 2
    bpy.ops.object.select_all(action='DESELECT')
    player.select_set(True)
    bpy.context.view_layer.objects.active = player
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    min_y = min((player.matrix_world @ vertex.co).y for vertex in player.data.vertices)
    min_z = min((player.matrix_world @ vertex.co).z for vertex in player.data.vertices)
    for vertex in player.data.vertices:
        vertex.co.y -= min_y
        vertex.co.z -= min_z
    player.location = (0.0, 0.0, 0.0)
    rig.location = (0.0, 0.0, 0.0)

    bpy.ops.object.select_all(action='DESELECT')
    player.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = player

    bpy.ops.export_scene.gltf(
        filepath=OUT_PATH,
        export_format='GLB',
        export_yup=False,
        export_apply=False,
        export_animations=False,
    )
    shutil.copyfile(OUT_PATH, COPY_PATH)
    shutil.copyfile(OUT_PATH, DOWNLOAD_COPY)
    print(OUT_PATH)
    print(DOWNLOAD_COPY)


if __name__ == '__main__':
    sys.exit(main())
