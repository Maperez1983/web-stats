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
MOCAP_SOURCE_PATH = os.environ.get('TASK_PLAYER_MOCAP_SOURCE', '').strip()


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


def add_pose_frame(armature, frame, rotations, pelvis_y=0.0, animated_bones=None):
    bpy.context.scene.frame_set(frame)
    reset_pose(armature)
    pelvis = armature.pose.bones.get('pelvis')
    if pelvis:
        pelvis.location.y = pelvis_y
        pelvis.keyframe_insert(data_path='location', frame=frame)
    for name in sorted(animated_bones or rotations.keys()):
        values = rotations.get(name, (0.0, 0.0, 0.0))
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
    animated_bones = set()
    for _, rotations, _ in frames:
        animated_bones.update(rotations.keys())
    for frame, rotations, pelvis_y in frames:
        add_pose_frame(armature, frame, rotations, pelvis_y, animated_bones)
    action.frame_range = (frames[0][0], frames[-1][0])
    track = armature.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, int(frames[0][0]), action)
    strip.frame_end = frames[-1][0]
    strip.use_auto_blend = True
    action.use_fake_user = True
    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'BEZIER'
    return action


def create_football_actions(armature):
    # Pseudo-mocap clips: hand-keyed football biomechanics with anticipation,
    # contact, follow-through and recovery. These are still procedural, but the
    # timing is intentionally closer to human action than the compact fallback.
    create_action(armature, 'idle', [
        (1, {'spine_03': (2, 0, 0), 'spine_02': (1, 0, 0), 'neck_01': (-1, 0, 0), 'upperarm_l': (2, 6, -12), 'lowerarm_l': (-8, 0, -4), 'upperarm_r': (1, -6, 12), 'lowerarm_r': (-8, 0, 4), 'thigh_l': (1, 0, 1), 'thigh_r': (-1, 0, -1)}, 0.0),
        (18, {'spine_03': (0, 0, 1), 'spine_02': (0, 0, 0), 'neck_01': (0, 0, -1), 'upperarm_l': (1, 5, -10), 'lowerarm_l': (-7, 0, -3), 'upperarm_r': (2, -5, 10), 'lowerarm_r': (-7, 0, 3), 'thigh_l': (0, 0, 0), 'thigh_r': (0, 0, 0)}, 0.010),
        (36, {'spine_03': (2, 0, -1), 'spine_02': (1, 0, 0), 'neck_01': (-1, 0, 1), 'upperarm_l': (2, 6, -12), 'lowerarm_l': (-8, 0, -4), 'upperarm_r': (1, -6, 12), 'lowerarm_r': (-8, 0, 4), 'thigh_l': (1, 0, 1), 'thigh_r': (-1, 0, -1)}, 0.0),
    ])
    create_action(armature, 'run', [
        (1, {'spine_03': (10, 0, -5), 'spine_02': (3, 0, -2), 'neck_01': (-4, 0, 2), 'upperarm_l': (-44, 6, -24), 'lowerarm_l': (-48, 0, -14), 'hand_l': (6, 0, -4), 'upperarm_r': (36, -5, 22), 'lowerarm_r': (-62, 0, 16), 'hand_r': (5, 0, 4), 'thigh_l': (48, 0, 5), 'calf_l': (-78, 0, 0), 'foot_l': (22, 0, 0), 'thigh_r': (-36, 0, -5), 'calf_r': (34, 0, 0), 'foot_r': (-16, 0, 0)}, 0.032),
        (5, {'spine_03': (12, 0, -2), 'spine_02': (4, 0, -1), 'neck_01': (-4, 0, 1), 'upperarm_l': (-18, 6, -18), 'lowerarm_l': (-58, 0, -12), 'upperarm_r': (22, -5, 18), 'lowerarm_r': (-50, 0, 12), 'thigh_l': (18, 0, 4), 'calf_l': (-32, 0, 0), 'foot_l': (6, 0, 0), 'thigh_r': (-12, 0, -3), 'calf_r': (66, 0, 0), 'foot_r': (-18, 0, 0)}, 0.008),
        (9, {'spine_03': (9, 0, 4), 'spine_02': (3, 0, 2), 'neck_01': (-3, 0, -2), 'upperarm_l': (34, 5, -20), 'lowerarm_l': (-60, 0, -14), 'upperarm_r': (-38, -6, 22), 'lowerarm_r': (-46, 0, 14), 'thigh_l': (-28, 0, 4), 'calf_l': (46, 0, 0), 'foot_l': (-14, 0, 0), 'thigh_r': (36, 0, -5), 'calf_r': (-74, 0, 0), 'foot_r': (18, 0, 0)}, 0.040),
        (13, {'spine_03': (11, 0, 2), 'spine_02': (4, 0, 1), 'neck_01': (-4, 0, -1), 'upperarm_l': (18, 5, -18), 'lowerarm_l': (-52, 0, -12), 'upperarm_r': (-20, -6, 18), 'lowerarm_r': (-56, 0, 12), 'thigh_l': (-8, 0, 3), 'calf_l': (68, 0, 0), 'foot_l': (-18, 0, 0), 'thigh_r': (16, 0, -4), 'calf_r': (-28, 0, 0), 'foot_r': (8, 0, 0)}, 0.010),
        (17, {'spine_03': (10, 0, -5), 'spine_02': (3, 0, -2), 'neck_01': (-4, 0, 2), 'upperarm_l': (-44, 6, -24), 'lowerarm_l': (-48, 0, -14), 'hand_l': (6, 0, -4), 'upperarm_r': (36, -5, 22), 'lowerarm_r': (-62, 0, 16), 'hand_r': (5, 0, 4), 'thigh_l': (48, 0, 5), 'calf_l': (-78, 0, 0), 'foot_l': (22, 0, 0), 'thigh_r': (-36, 0, -5), 'calf_r': (34, 0, 0), 'foot_r': (-16, 0, 0)}, 0.032),
        (25, {'spine_03': (9, 0, 4), 'spine_02': (3, 0, 2), 'neck_01': (-3, 0, -2), 'upperarm_l': (34, 5, -20), 'lowerarm_l': (-60, 0, -14), 'upperarm_r': (-38, -6, 22), 'lowerarm_r': (-46, 0, 14), 'thigh_l': (-28, 0, 4), 'calf_l': (46, 0, 0), 'foot_l': (-14, 0, 0), 'thigh_r': (36, 0, -5), 'calf_r': (-74, 0, 0), 'foot_r': (18, 0, 0)}, 0.040),
        (33, {'spine_03': (10, 0, -5), 'spine_02': (3, 0, -2), 'neck_01': (-4, 0, 2), 'upperarm_l': (-44, 6, -24), 'lowerarm_l': (-48, 0, -14), 'hand_l': (6, 0, -4), 'upperarm_r': (36, -5, 22), 'lowerarm_r': (-62, 0, 16), 'hand_r': (5, 0, 4), 'thigh_l': (48, 0, 5), 'calf_l': (-78, 0, 0), 'foot_l': (22, 0, 0), 'thigh_r': (-36, 0, -5), 'calf_r': (34, 0, 0), 'foot_r': (-16, 0, 0)}, 0.032),
    ])
    create_action(armature, 'pass', [
        (1, {'spine_03': (3, 0, -4), 'neck_01': (-2, 0, 2), 'upperarm_l': (0, 8, -20), 'upperarm_r': (0, -10, 18), 'thigh_r': (-16, 0, -4), 'calf_r': (24, 0, 0), 'foot_r': (-10, 0, 0)}, 0.0),
        (8, {'spine_03': (7, 0, -7), 'spine_02': (2, 0, -2), 'upperarm_l': (0, 12, -30), 'upperarm_r': (0, -18, 28), 'thigh_r': (-36, 0, -5), 'calf_r': (58, 0, 0), 'foot_r': (-18, 0, 0), 'thigh_l': (8, 0, 3)}, 0.008),
        (14, {'spine_03': (10, 0, 6), 'spine_02': (4, 0, 2), 'neck_01': (-4, 0, -2), 'upperarm_l': (0, 16, -42), 'lowerarm_l': (-10, 0, -8), 'upperarm_r': (0, -24, 38), 'lowerarm_r': (-14, 0, 10), 'thigh_r': (38, 0, -5), 'calf_r': (-28, 0, 0), 'foot_r': (26, 0, 0), 'thigh_l': (-12, 0, 4)}, 0.024),
        (20, {'spine_03': (8, 0, 10), 'spine_02': (3, 0, 4), 'upperarm_l': (0, 12, -34), 'upperarm_r': (0, -18, 30), 'thigh_r': (20, 0, -3), 'calf_r': (-4, 0, 0), 'foot_r': (10, 0, 0)}, 0.012),
        (32, {'spine_03': (2, 0, 2), 'upperarm_l': (0, 7, -16), 'upperarm_r': (0, -7, 16), 'thigh_r': (-4, 0, 0), 'calf_r': (8, 0, 0)}, 0.0),
    ])
    create_action(armature, 'shot', [
        (1, {'spine_03': (5, 0, -8), 'spine_02': (2, 0, -3), 'neck_01': (-2, 0, 3), 'upperarm_l': (0, 12, -38), 'upperarm_r': (0, -16, 34), 'thigh_r': (-30, 0, -6), 'calf_r': (48, 0, 0), 'foot_r': (-14, 0, 0)}, 0.0),
        (8, {'spine_03': (10, 0, -14), 'spine_02': (4, 0, -6), 'upperarm_l': (0, 18, -56), 'upperarm_r': (0, -24, 50), 'thigh_r': (-55, 0, -8), 'calf_r': (86, 0, 0), 'foot_r': (-22, 0, 0), 'thigh_l': (16, 0, 4)}, 0.014),
        (14, {'spine_03': (17, 0, 10), 'spine_02': (6, 0, 4), 'neck_01': (-7, 0, -4), 'upperarm_l': (0, 24, -70), 'lowerarm_l': (-12, 0, -8), 'upperarm_r': (0, -34, 62), 'lowerarm_r': (-14, 0, 12), 'thigh_r': (66, 0, -5), 'calf_r': (-42, 0, 0), 'foot_r': (34, 0, 0), 'thigh_l': (-24, 0, 5), 'calf_l': (18, 0, 0)}, 0.034),
        (20, {'spine_03': (20, 0, 18), 'spine_02': (7, 0, 8), 'neck_01': (-8, 0, -5), 'upperarm_l': (0, 18, -62), 'upperarm_r': (0, -26, 54), 'thigh_r': (34, 0, -2), 'calf_r': (2, 0, 0), 'foot_r': (16, 0, 0), 'thigh_l': (-18, 0, 4)}, 0.018),
        (36, {'spine_03': (6, 0, 4), 'upperarm_l': (0, 8, -24), 'upperarm_r': (0, -10, 24), 'thigh_r': (8, 0, 0), 'calf_r': (10, 0, 0)}, 0.0),
    ])
    create_action(armature, 'cross', [
        (1, {'spine_03': (4, -5, -10), 'spine_02': (2, -2, -4), 'upperarm_l': (0, 10, -34), 'upperarm_r': (0, -12, 32), 'thigh_r': (-28, 0, -12), 'calf_r': (42, 0, 0)}, 0.0),
        (9, {'spine_03': (8, -8, -16), 'upperarm_l': (0, 16, -48), 'upperarm_r': (0, -20, 44), 'thigh_r': (-46, 0, -16), 'calf_r': (72, 0, 0), 'foot_r': (-20, 0, -6), 'thigh_l': (10, 0, 4)}, 0.010),
        (16, {'spine_03': (13, 8, 22), 'spine_02': (5, 4, 8), 'neck_01': (-5, -2, -6), 'upperarm_l': (0, 22, -64), 'upperarm_r': (0, -32, 58), 'thigh_r': (54, -8, 18), 'calf_r': (-24, 0, 0), 'foot_r': (28, 0, 14), 'thigh_l': (-18, 0, 6)}, 0.030),
        (24, {'spine_03': (9, 5, 16), 'upperarm_l': (0, 16, -48), 'upperarm_r': (0, -24, 42), 'thigh_r': (24, -4, 8), 'foot_r': (12, 0, 8)}, 0.014),
        (40, {'spine_03': (4, 0, 3), 'upperarm_l': (0, 8, -20), 'upperarm_r': (0, -8, 20), 'thigh_r': (6, 0, 0)}, 0.0),
    ])
    create_action(armature, 'press', [
        (1, {'spine_03': (14, 0, -6), 'spine_02': (5, 0, -2), 'neck_01': (-6, 0, 2), 'upperarm_l': (8, 8, -30), 'lowerarm_l': (-26, 0, -10), 'upperarm_r': (-8, -8, 30), 'lowerarm_r': (-26, 0, 10), 'thigh_l': (24, 0, 5), 'thigh_r': (-20, 0, -5), 'calf_r': (26, 0, 0)}, 0.014),
        (7, {'spine_03': (17, 0, 3), 'spine_02': (6, 0, 1), 'upperarm_l': (-14, 10, -38), 'upperarm_r': (14, -10, 38), 'thigh_l': (-18, 0, 4), 'calf_l': (28, 0, 0), 'thigh_r': (28, 0, -4)}, 0.0),
        (13, {'spine_03': (16, 0, 8), 'upperarm_l': (-24, 12, -44), 'lowerarm_l': (-34, 0, -12), 'upperarm_r': (24, -12, 44), 'lowerarm_r': (-34, 0, 12), 'thigh_l': (-28, 0, 3), 'calf_l': (42, 0, 0), 'thigh_r': (34, 0, -5), 'calf_r': (-34, 0, 0)}, 0.018),
        (20, {'spine_03': (14, 0, -6), 'spine_02': (5, 0, -2), 'neck_01': (-6, 0, 2), 'upperarm_l': (8, 8, -30), 'lowerarm_l': (-26, 0, -10), 'upperarm_r': (-8, -8, 30), 'lowerarm_r': (-26, 0, 10), 'thigh_l': (24, 0, 5), 'thigh_r': (-20, 0, -5), 'calf_r': (26, 0, 0)}, 0.014),
        (27, {'spine_03': (17, 0, 3), 'spine_02': (6, 0, 1), 'upperarm_l': (-14, 10, -38), 'upperarm_r': (14, -10, 38), 'thigh_l': (-18, 0, 4), 'calf_l': (28, 0, 0), 'thigh_r': (28, 0, -4)}, 0.0),
        (33, {'spine_03': (14, 0, -6), 'spine_02': (5, 0, -2), 'neck_01': (-6, 0, 2), 'upperarm_l': (8, 8, -30), 'lowerarm_l': (-26, 0, -10), 'upperarm_r': (-8, -8, 30), 'lowerarm_r': (-26, 0, 10), 'thigh_l': (24, 0, 5), 'thigh_r': (-20, 0, -5), 'calf_r': (26, 0, 0)}, 0.014),
    ])
    create_action(armature, 'control', [
        (1, {'spine_03': (3, 0, 0), 'neck_01': (-2, 0, 0), 'upperarm_l': (0, 9, -18), 'upperarm_r': (0, -9, 18), 'thigh_r': (8, 0, 0)}, 0.0),
        (8, {'spine_03': (6, 0, -4), 'spine_02': (2, 0, -2), 'upperarm_l': (0, 12, -26), 'upperarm_r': (0, -14, 26), 'thigh_r': (24, 8, -8), 'calf_r': (-36, 0, 0), 'foot_r': (22, 0, -10), 'thigh_l': (-6, 0, 4)}, 0.010),
        (15, {'spine_03': (7, 0, -7), 'neck_01': (-5, 0, 3), 'upperarm_l': (0, 14, -30), 'upperarm_r': (0, -18, 30), 'thigh_r': (36, 10, -10), 'calf_r': (-54, 0, 0), 'foot_r': (38, 0, -16), 'thigh_l': (-12, 0, 5)}, 0.016),
        (21, {'spine_03': (5, 0, 5), 'spine_02': (2, 0, 2), 'upperarm_l': (0, 10, -22), 'upperarm_r': (0, -12, 22), 'thigh_r': (18, -6, 10), 'calf_r': (-18, 0, 0), 'foot_r': (12, 0, 14), 'thigh_l': (-4, 0, -3)}, 0.006),
        (34, {'spine_03': (2, 0, 0), 'upperarm_l': (0, 7, -16), 'upperarm_r': (0, -7, 16), 'thigh_r': (4, 0, 0)}, 0.0),
    ])
    armature.animation_data.action = bpy.data.actions.get('idle')


def import_compatible_mocap_actions(armature):
    if not MOCAP_SOURCE_PATH or not os.path.exists(MOCAP_SOURCE_PATH):
        return []

    before_objects = set(bpy.data.objects)
    before_actions = set(bpy.data.actions)
    ext = os.path.splitext(MOCAP_SOURCE_PATH)[1].lower()
    if ext in {'.glb', '.gltf'}:
        bpy.ops.import_scene.gltf(filepath=MOCAP_SOURCE_PATH)
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=MOCAP_SOURCE_PATH)
    else:
        return []

    imported_actions = [action for action in bpy.data.actions if action not in before_actions]
    kept = []
    armature.animation_data_create()
    for action in imported_actions:
        if not action.fcurves:
            continue
        action.name = f'mocap_{action.name}'
        action.use_fake_user = True
        track = armature.animation_data.nla_tracks.new()
        track.name = action.name
        strip = track.strips.new(action.name, int(action.frame_range[0]), action)
        strip.frame_end = action.frame_range[1]
        strip.use_auto_blend = True
        kept.append(action.name)

    for obj in [obj for obj in bpy.data.objects if obj not in before_objects]:
        bpy.data.objects.remove(obj, do_unlink=True)
    return kept


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
        import_compatible_mocap_actions(armature)

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
