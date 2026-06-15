import os
import sys
import math

import bpy


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SOURCE_PATH = os.path.expanduser(
    '~/Downloads/Universal_Base_Characters_Standard_extracted/'
    'Universal Base Characters[Standard]/Base Characters/Godot - UE/'
    'Superhero_Male_FullBody.gltf'
)
IN_PATH = SOURCE_PATH if os.path.exists(SOURCE_PATH) else os.path.join(
    ROOT, 'football/static/football/models/avatar/player_humanoid.glb'
)
OUT_PATH = IN_PATH
if os.path.abspath(IN_PATH) == os.path.abspath(SOURCE_PATH):
    OUT_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_humanoid.glb')
COPY_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_premium_mpfb.glb')


def make_mat(name, color, roughness=0.68):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = 0.0
    return mat


def poly_center(mesh, poly):
    x = y = z = 0.0
    for idx in poly.vertices:
        co = mesh.vertices[idx].co
        x += co.x
        y += co.y
        z += co.z
    n = max(1, len(poly.vertices))
    return x / n, y / n, z / n


def assign_skin_material(obj):
    mesh = obj.data
    skin = make_mat('footballer_skin', (0.72, 0.50, 0.34, 1.0), 0.58)
    hair = make_mat('footballer_dark_hair', (0.035, 0.025, 0.018, 1.0), 0.76)
    jersey = make_mat('footballer_green_jersey_base', (0.00, 0.46, 0.29, 1.0), 0.60)
    shorts = make_mat('footballer_dark_shorts_base', (0.02, 0.05, 0.10, 1.0), 0.70)
    socks = make_mat('footballer_white_socks_base', (0.93, 0.95, 0.90, 1.0), 0.66)
    boots = make_mat('footballer_black_boots_base', (0.01, 0.012, 0.016, 1.0), 0.54)
    mesh.materials.clear()
    for mat in (skin, hair, jersey, shorts, socks, boots):
        mesh.materials.append(mat)
    for poly in mesh.polygons:
        x, depth, y = poly_center(mesh, poly)
        mat_index = 0
        if y > 1.62 and (depth > 0.035 or y > 1.72):
            mat_index = 1
        elif 0.90 <= y <= 1.50 and abs(x) <= 0.52:
            mat_index = 2
        elif 1.03 <= y <= 1.32 and 0.30 <= abs(x) <= 0.66:
            mat_index = 2
        elif 0.50 <= y < 0.91 and abs(x) <= 0.33:
            mat_index = 3
        elif 0.13 <= y < 0.45 and 0.055 <= abs(x) <= 0.22:
            mat_index = 4
        elif y < 0.13 and 0.045 <= abs(x) <= 0.24:
            mat_index = 5
        poly.material_index = mat_index


def pose_armature(armature):
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')

    def rotate(name, x=0.0, y=0.0, z=0.0):
        bone = armature.pose.bones.get(name)
        if not bone:
            return
        bone.rotation_mode = 'XYZ'
        bone.rotation_euler.rotate_axis('X', x)
        bone.rotation_euler.rotate_axis('Y', y)
        bone.rotation_euler.rotate_axis('Z', z)

    rotate('upperarm_l', z=-1.12, y=0.10)
    rotate('lowerarm_l', z=-0.24, y=-0.08)
    rotate('hand_l', x=0.10, z=-0.08)
    rotate('upperarm_r', z=1.12, y=-0.10)
    rotate('lowerarm_r', z=0.24, y=0.08)
    rotate('hand_r', x=0.10, z=0.08)
    rotate('thigh_l', x=-0.05, y=0.03, z=0.04)
    rotate('thigh_r', x=0.05, y=-0.03, z=-0.04)
    rotate('calf_l', x=0.08)
    rotate('calf_r', x=0.05)
    rotate('spine_03', x=0.04, y=-0.04)

    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def reset_pose(armature):
    for bone in armature.pose.bones:
        bone.rotation_mode = 'XYZ'
        bone.rotation_euler = (0.0, 0.0, 0.0)
        bone.location = (0.0, 0.0, 0.0)


def add_pose_frame(armature, frame, rotations, pelvis_y=0.0):
    bpy.context.scene.frame_set(frame)
    reset_pose(armature)
    pelvis = armature.pose.bones.get('pelvis')
    if pelvis:
        pelvis.location.y = pelvis_y
        pelvis.keyframe_insert(data_path='location', frame=frame)
    for name, values in rotations.items():
        bone = armature.pose.bones.get(name)
        if not bone:
            continue
        bone.rotation_mode = 'XYZ'
        bone.rotation_euler = tuple(math.radians(value) for value in values)
        bone.keyframe_insert(data_path='rotation_euler', frame=frame)


def create_action(armature, name, frames):
    action = bpy.data.actions.new(name)
    armature.animation_data_create()
    armature.animation_data.action = action
    for frame, rotations, pelvis_y in frames:
        add_pose_frame(armature, frame, rotations, pelvis_y)
    action.frame_range = (frames[0][0], frames[-1][0])
    track = armature.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, int(frames[0][0]), action)
    strip.frame_end = frames[-1][0]
    strip.use_auto_blend = True
    action.use_fake_user = True
    return action


def create_football_actions(armature):
    # Compact procedural clips. They are not mocap, but they give the task
    # viewer named football actions on the rigged human mesh while retargeting
    # from a mocap library is prepared.
    create_action(armature, 'idle', [
        (1, {'spine_03': (1, 0, 0), 'upperarm_l': (0, 6, -10), 'upperarm_r': (0, -6, 10)}, 0.0),
        (24, {'spine_03': (-1, 0, 1), 'upperarm_l': (0, 5, -8), 'upperarm_r': (0, -5, 8)}, 0.012),
        (48, {'spine_03': (1, 0, 0), 'upperarm_l': (0, 6, -10), 'upperarm_r': (0, -6, 10)}, 0.0),
    ])
    run_a = {
        'spine_03': (7, 0, -4),
        'upperarm_l': (-42, 4, -18), 'lowerarm_l': (-38, 0, -10),
        'upperarm_r': (35, -4, 18), 'lowerarm_r': (-55, 0, 12),
        'thigh_l': (42, 0, 4), 'calf_l': (-72, 0, 0), 'foot_l': (18, 0, 0),
        'thigh_r': (-34, 0, -4), 'calf_r': (38, 0, 0), 'foot_r': (-12, 0, 0),
    }
    run_b = {
        'spine_03': (7, 0, 4),
        'upperarm_l': (35, 4, -18), 'lowerarm_l': (-55, 0, -12),
        'upperarm_r': (-42, -4, 18), 'lowerarm_r': (-38, 0, 10),
        'thigh_l': (-34, 0, 4), 'calf_l': (38, 0, 0), 'foot_l': (-12, 0, 0),
        'thigh_r': (42, 0, -4), 'calf_r': (-72, 0, 0), 'foot_r': (18, 0, 0),
    }
    create_action(armature, 'run', [(1, run_a, 0.035), (8, run_b, 0.0), (16, run_a, 0.035)])
    create_action(armature, 'pass', [
        (1, {'spine_03': (4, 0, -5), 'upperarm_l': (0, 8, -24), 'upperarm_r': (0, -12, 20), 'thigh_r': (-22, 0, -5), 'calf_r': (34, 0, 0)}, 0.0),
        (12, {'spine_03': (9, 0, 8), 'upperarm_l': (0, 14, -36), 'upperarm_r': (0, -20, 32), 'thigh_r': (36, 0, -4), 'calf_r': (-20, 0, 0), 'foot_r': (18, 0, 0), 'thigh_l': (-8, 0, 4)}, 0.015),
        (24, {'spine_03': (3, 0, 2), 'upperarm_l': (0, 8, -18), 'upperarm_r': (0, -8, 18), 'thigh_r': (-8, 0, 0), 'calf_r': (10, 0, 0)}, 0.0),
    ])
    create_action(armature, 'shot', [
        (1, {'spine_03': (6, 0, -8), 'upperarm_l': (0, 12, -42), 'upperarm_r': (0, -18, 36), 'thigh_r': (-38, 0, -6), 'calf_r': (64, 0, 0)}, 0.0),
        (10, {'spine_03': (14, 0, 12), 'upperarm_l': (0, 18, -58), 'upperarm_r': (0, -26, 50), 'thigh_r': (58, 0, -4), 'calf_r': (-32, 0, 0), 'foot_r': (26, 0, 0), 'thigh_l': (-16, 0, 5)}, 0.025),
        (24, {'spine_03': (8, 0, 5), 'upperarm_l': (0, 10, -28), 'upperarm_r': (0, -12, 28), 'thigh_r': (12, 0, 0), 'calf_r': (12, 0, 0)}, 0.0),
    ])
    create_action(armature, 'cross', [
        (1, {'spine_03': (5, -4, -10), 'upperarm_l': (0, 10, -38), 'upperarm_r': (0, -12, 34), 'thigh_r': (-30, 0, -10), 'calf_r': (44, 0, 0)}, 0.0),
        (12, {'spine_03': (10, 5, 18), 'upperarm_l': (0, 18, -52), 'upperarm_r': (0, -24, 48), 'thigh_r': (46, -6, 14), 'calf_r': (-18, 0, 0), 'foot_r': (20, 0, 10)}, 0.02),
        (26, {'spine_03': (4, 0, 4), 'upperarm_l': (0, 10, -24), 'upperarm_r': (0, -10, 24), 'thigh_r': (8, 0, 0)}, 0.0),
    ])
    create_action(armature, 'press', [
        (1, {'spine_03': (12, 0, -6), 'upperarm_l': (8, 6, -28), 'upperarm_r': (-8, -6, 28), 'thigh_l': (20, 0, 4), 'thigh_r': (-18, 0, -4), 'calf_r': (24, 0, 0)}, 0.012),
        (10, {'spine_03': (14, 0, 6), 'upperarm_l': (-10, 8, -34), 'upperarm_r': (10, -8, 34), 'thigh_l': (-18, 0, 4), 'calf_l': (22, 0, 0), 'thigh_r': (22, 0, -4)}, 0.0),
        (20, {'spine_03': (12, 0, -6), 'upperarm_l': (8, 6, -28), 'upperarm_r': (-8, -6, 28), 'thigh_l': (20, 0, 4), 'thigh_r': (-18, 0, -4), 'calf_r': (24, 0, 0)}, 0.012),
    ])
    create_action(armature, 'control', [
        (1, {'spine_03': (3, 0, 0), 'upperarm_l': (0, 10, -20), 'upperarm_r': (0, -10, 20), 'thigh_r': (8, 0, 0)}, 0.0),
        (14, {'spine_03': (5, 0, -5), 'upperarm_l': (0, 12, -26), 'upperarm_r': (0, -14, 26), 'thigh_r': (32, 8, -8), 'calf_r': (-46, 0, 0), 'foot_r': (34, 0, -12), 'thigh_l': (-8, 0, 4)}, 0.012),
        (28, {'spine_03': (2, 0, 0), 'upperarm_l': (0, 8, -18), 'upperarm_r': (0, -8, 18), 'thigh_r': (4, 0, 0)}, 0.0),
    ])
    armature.animation_data.action = bpy.data.actions.get('idle')


def main():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=IN_PATH)

    armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            armature = obj
        if obj.type == 'MESH' and any('Superhero_Male' in slot.material.name for slot in obj.material_slots if slot.material):
            assign_skin_material(obj)

    if armature:
        pose_armature(armature)
        create_football_actions(armature)

    bpy.ops.export_scene.gltf(
        filepath=OUT_PATH,
        export_format='GLB',
        export_yup=True,
        export_apply=False,
        export_animations=True,
    )

    with open(OUT_PATH, 'rb') as src, open(COPY_PATH, 'wb') as dst:
        dst.write(src.read())


if __name__ == '__main__':
    sys.exit(main())
