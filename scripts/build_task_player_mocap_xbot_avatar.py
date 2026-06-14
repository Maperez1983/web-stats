import math
import os
import shutil
import sys
import tempfile

import bpy


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SOURCE_PATH = os.environ.get('TASK_PLAYER_XBOT_SOURCE') or os.path.expanduser('~/Downloads/Xbot_threejs.glb')
OUT_PATH = os.path.join(tempfile.gettempdir(), 'player_mocap_xbot.glb')
HUMANOID_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_humanoid.glb')
PREMIUM_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_premium_mpfb.glb')


def make_material(name, color, roughness=0.62):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
    mat.diffuse_color = color
    return mat


def main():
    if not os.path.exists(SOURCE_PATH):
        raise RuntimeError(f'Xbot source not found: {SOURCE_PATH}')

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=SOURCE_PATH)

    for obj in list(bpy.context.scene.objects):
        if obj.type in {'CAMERA', 'LIGHT'} or obj.name in {'Cube', 'Icosphere'}:
            bpy.data.objects.remove(obj, do_unlink=True)

    armature = next((obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE'), None)
    if not armature:
        raise RuntimeError('Xbot armature not found')
    armature.name = 'task_player_mocap_xbot'

    skin = make_material('xbot_skin_surface_footballer_green_jersey', (0.82, 0.56, 0.47, 1.0), 0.58)
    joint = make_material('xbot_skin_joints', (0.72, 0.45, 0.37, 1.0), 0.64)
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        low = obj.name.lower()
        obj.name = f'task_player_mocap_{obj.name}'
        obj.data.materials.clear()
        obj.data.materials.append(joint if 'joint' in low else skin)
        try:
            obj.show_name = False
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.shade_smooth()
            obj.select_set(False)
        except Exception:
            pass

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT_PATH, export_format='GLB', export_yup=True, export_apply=False)
    for copy_path in (HUMANOID_PATH, PREMIUM_PATH):
        shutil.copyfile(OUT_PATH, copy_path)
    print(OUT_PATH)
    return

    def create_action(name, frames):
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='POSE')
        action = bpy.data.actions.new(name)
        armature.animation_data_create()
        armature.animation_data.action = action
        for frame, rotations in frames:
            bpy.context.scene.frame_set(frame)
            for bone in armature.pose.bones:
                bone.rotation_mode = 'XYZ'
                bone.rotation_euler = (0.0, 0.0, 0.0)
            for bone_name, rot in rotations.items():
                bone = armature.pose.bones.get(bone_name)
                if not bone:
                    continue
                bone.rotation_mode = 'XYZ'
                bone.rotation_euler = tuple(math.radians(float(v)) for v in rot)
                bone.keyframe_insert(data_path='rotation_euler', frame=frame)
        action.frame_range = (frames[0][0], frames[-1][0])
        armature.animation_data.action = None
        bpy.ops.object.mode_set(mode='OBJECT')

    neutral = {
        'mixamorig:Spine': (3, 0, 0),
        'mixamorig:Spine1': (4, 0, 0),
        'mixamorig:Spine2': (4, 0, 0),
        'mixamorig:Neck': (-2, 0, 0),
        'mixamorig:LeftArm': (0, 0, -8),
        'mixamorig:LeftForeArm': (-12, 0, -4),
        'mixamorig:RightArm': (0, 0, 8),
        'mixamorig:RightForeArm': (-12, 0, 4),
    }
    pass_pose = dict(neutral, **{
        'mixamorig:Spine': (6, 0, 2),
        'mixamorig:Spine2': (12, 0, 7),
        'mixamorig:LeftArm': (-6, 0, -18),
        'mixamorig:RightArm': (8, 0, 16),
        'mixamorig:LeftUpLeg': (-10, 0, 2),
        'mixamorig:LeftLeg': (14, 0, 0),
        'mixamorig:RightUpLeg': (32, 0, -5),
        'mixamorig:RightLeg': (-22, 0, 0),
        'mixamorig:RightFoot': (16, 0, 0),
    })
    cross_pose = dict(pass_pose, **{
        'mixamorig:Spine2': (14, 0, 12),
        'mixamorig:RightUpLeg': (38, 0, -8),
        'mixamorig:RightLeg': (-26, 0, 0),
        'mixamorig:RightFoot': (22, 0, 0),
    })
    shot_pose = dict(pass_pose, **{
        'mixamorig:Spine2': (16, 0, 14),
        'mixamorig:RightUpLeg': (44, 0, -9),
        'mixamorig:RightLeg': (-32, 0, 0),
        'mixamorig:RightFoot': (28, 0, 0),
    })
    press_pose = dict(neutral, **{
        'mixamorig:Hips': (0, 0, 0),
        'mixamorig:Spine': (8, 0, 0),
        'mixamorig:Spine2': (15, 0, 0),
        'mixamorig:LeftArm': (4, 0, -20),
        'mixamorig:LeftForeArm': (-28, 0, -8),
        'mixamorig:RightArm': (4, 0, 20),
        'mixamorig:RightForeArm': (-28, 0, 8),
        'mixamorig:LeftUpLeg': (20, 0, 4),
        'mixamorig:LeftLeg': (-24, 0, 0),
        'mixamorig:RightUpLeg': (18, 0, -4),
        'mixamorig:RightLeg': (-22, 0, 0),
    })

    create_action('pass', [(1, neutral), (10, pass_pose), (24, neutral)])
    create_action('cross', [(1, neutral), (10, cross_pose), (28, neutral)])
    create_action('shot', [(1, neutral), (10, shot_pose), (28, neutral)])
    create_action('press', [(1, neutral), (10, press_pose), (24, neutral)])

    bpy.ops.object.select_all(action='SELECT')
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT_PATH, export_format='GLB', export_yup=True, export_apply=False)
    for copy_path in (HUMANOID_PATH, PREMIUM_PATH):
        shutil.copyfile(OUT_PATH, copy_path)
    print(OUT_PATH)


if __name__ == '__main__':
    sys.exit(main())
