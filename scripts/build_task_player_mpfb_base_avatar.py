import os
import sys
import math
import tempfile

import bpy
import bmesh


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MPFB_PARENT = os.path.expanduser('~/Library/Application Support/Blender/5.1/extensions/user_default')
MH_ASSET_ROOT = os.path.expanduser('~/Documents/MakeHuman/v1py3/official_assets/base')
OUT_PATH = os.path.join(tempfile.gettempdir(), 'player_mpfb_base.glb')
HUMANOID_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_humanoid.glb')
PREMIUM_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_premium_mpfb.glb')


def main():
    if MPFB_PARENT not in sys.path:
        sys.path.insert(0, MPFB_PARENT)

    original_extension_path_user = getattr(bpy.utils, 'extension_path_user', None)

    def extension_path_user(package):
        if package == 'mpfb':
            return os.path.join(bpy.utils.resource_path('USER'), 'mpfb')
        if original_extension_path_user:
            return original_extension_path_user(package)
        return os.path.join(bpy.utils.resource_path('USER'), str(package).split('.')[-1])

    bpy.utils.extension_path_user = extension_path_user

    import mpfb

    def get_preference(name):
        defaults = {
            'mpfb_user_data': os.path.join(bpy.utils.resource_path('USER'), 'mpfb'),
            'mpfb_second_root': MH_ASSET_ROOT,
            'mh_user_data': MH_ASSET_ROOT,
            'mh_auto_user_data': False,
            'mpfb_shelf_label': 'MPFB',
        }
        return defaults.get(name, '')

    mpfb.get_preference = get_preference
    mpfb.register()

    from mpfb.services.humanservice import HumanService

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    human_info = HumanService._create_default_human_info_dict()
    human_info.update({
        'name': 'task_player_mpfb_base',
        'rig': 'game_engine',
        'skin_mhmat': 'young_caucasian_male/young_caucasian_male.mhmat',
        'skin_material_type': 'GAMEENGINE',
        'eyes': '',
        'eyebrows': 'eyebrow011/eyebrow011.mhclo',
        'hair': 'short01/short01.mhclo',
        'teeth': '',
        'tongue': '',
        'eyelashes': '',
        'proxy': '',
        'clothes': [],
    })
    human_info['phenotype'].update({
        'age': 0.18,
        'gender': 0.96,
        'muscle': 0.72,
        'weight': 0.46,
        'height': 0.60,
        'proportions': 0.56,
    })

    settings = HumanService.get_default_deserialization_settings()
    settings.update({
        'mask_helpers': False,
        'detailed_helpers': False,
        'extra_vertex_groups': True,
        'load_clothes': False,
        'subdiv_levels': 0,
        'scale': 0.1,
        'override_rig': 'game_engine',
        'override_skin_model': 'GAMEENGINE',
        'material_instances': 'NEVER',
    })

    basemesh = HumanService.deserialize_from_dict(human_info, settings)

    skin_mat = bpy.data.materials.new('mpfb_player_skin')
    skin_mat.use_nodes = True
    skin_bsdf = skin_mat.node_tree.nodes.get('Principled BSDF')
    if skin_bsdf:
        skin_bsdf.inputs['Base Color'].default_value = (0.74, 0.56, 0.43, 1.0)
        skin_bsdf.inputs['Roughness'].default_value = 0.58

    hair_mat = bpy.data.materials.new('mpfb_player_dark_hair')
    hair_mat.use_nodes = True
    hair_bsdf = hair_mat.node_tree.nodes.get('Principled BSDF')
    if hair_bsdf:
        hair_bsdf.inputs['Base Color'].default_value = (0.05, 0.035, 0.025, 1.0)
        hair_bsdf.inputs['Roughness'].default_value = 0.76

    def delete_vertex_groups(obj, group_names):
        if not obj or obj.type != 'MESH':
            return
        target_indices = {
            group.index
            for group in obj.vertex_groups
            if group.name in group_names
        }
        if not target_indices:
            return
        mesh = obj.data
        delete_indices = {
            vert.index
            for vert in mesh.vertices
            if any(group.group in target_indices for group in vert.groups)
        }
        if not delete_indices:
            return
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        delete_verts = [vert for vert in bm.verts if vert.index in delete_indices]
        bmesh.ops.delete(bm, geom=delete_verts, context='VERTS')
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

    delete_vertex_groups(basemesh, {'HelperGeometry', 'JointCubes', 'genitals', 'nipple', 'nippleTip'})

    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            if 'hair' in obj.name.lower() or 'eyebrow' in obj.name.lower():
                obj.data.materials.clear()
                obj.data.materials.append(hair_mat)
            else:
                obj.data.materials.clear()
                obj.data.materials.append(skin_mat)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            try:
                bpy.ops.object.shade_smooth()
            except Exception:
                pass
            obj.select_set(False)

    eye_white = bpy.data.materials.new('mpfb_player_eye_white')
    eye_white.use_nodes = True
    eye_bsdf = eye_white.node_tree.nodes.get('Principled BSDF')
    if eye_bsdf:
        eye_bsdf.inputs['Base Color'].default_value = (0.94, 0.92, 0.88, 1.0)
        eye_bsdf.inputs['Roughness'].default_value = 0.42
    iris_mat = bpy.data.materials.new('mpfb_player_iris')
    iris_mat.use_nodes = True
    iris_bsdf = iris_mat.node_tree.nodes.get('Principled BSDF')
    if iris_bsdf:
        iris_bsdf.inputs['Base Color'].default_value = (0.08, 0.05, 0.025, 1.0)
        iris_bsdf.inputs['Roughness'].default_value = 0.35

    armature = next((obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE'), None)

    def bind_mesh_to_head(obj):
        if not obj or not armature or obj.type != 'MESH':
            return
        obj.parent = armature
        group = obj.vertex_groups.new(name='head')
        group.add([vert.index for vert in obj.data.vertices], 1.0, 'REPLACE')
        modifier = obj.modifiers.new('Armature', 'ARMATURE')
        modifier.object = armature

    for x in (-0.034, 0.034):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.017, location=(x, -0.098, 1.315))
        eye = bpy.context.object
        eye.name = 'mpfb_player_eye'
        eye.scale.y = 0.44
        eye.data.materials.append(eye_white)
        bind_mesh_to_head(eye)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.007, location=(x, -0.111, 1.315))
        iris = bpy.context.object
        iris.name = 'mpfb_player_iris'
        iris.scale.y = 0.16
        iris.data.materials.append(iris_mat)
        bind_mesh_to_head(iris)

    def create_action(name, frames):
        if not armature:
            return
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
            for bone_name in rotations:
                bone = armature.pose.bones.get(bone_name)
                if bone:
                    bone.keyframe_insert(data_path='rotation_euler', frame=frame)
        action.frame_range = (frames[0][0], frames[-1][0])
        armature.animation_data.action = None
        bpy.ops.object.mode_set(mode='OBJECT')

    neutral = {
        'upperarm_l': (0, 0, -10), 'lowerarm_l': (0, 0, -4), 'hand_l': (0, 0, -2),
        'upperarm_r': (0, 0, 10), 'lowerarm_r': (0, 0, 4), 'hand_r': (0, 0, 2),
        'spine_03': (1, 0, 0), 'neck_01': (-1, 0, 0),
    }
    run_a = dict(neutral, **{
        'spine_01': (3, 0, 0), 'spine_03': (7, 0, 3),
        'upperarm_l': (-8, 0, -16), 'lowerarm_l': (-12, 0, -8), 'hand_l': (-5, 0, -4),
        'upperarm_r': (10, 0, 15), 'lowerarm_r': (-12, 0, 8), 'hand_r': (-5, 0, 4),
        'thigh_l': (26, 0, 3), 'calf_l': (-34, 0, 0), 'foot_l': (12, 0, 0),
        'thigh_r': (-20, 0, -3), 'calf_r': (18, 0, 0), 'foot_r': (-9, 0, 0),
    })
    run_b = dict(neutral, **{
        'spine_01': (3, 0, 0), 'spine_03': (7, 0, -3),
        'upperarm_l': (10, 0, -15), 'lowerarm_l': (-12, 0, -8), 'hand_l': (-5, 0, -4),
        'upperarm_r': (-8, 0, 16), 'lowerarm_r': (-12, 0, 8), 'hand_r': (-5, 0, 4),
        'thigh_l': (-20, 0, 3), 'calf_l': (18, 0, 0), 'foot_l': (-9, 0, 0),
        'thigh_r': (26, 0, -3), 'calf_r': (-34, 0, 0), 'foot_r': (12, 0, 0),
    })
    pass_windup = dict(neutral, **{
        'spine_01': (2, 0, -3), 'spine_03': (5, 0, -5),
        'upperarm_l': (3, 0, -16), 'lowerarm_l': (-10, 0, -7),
        'upperarm_r': (-4, 0, 14), 'lowerarm_r': (-10, 0, 7),
        'thigh_l': (4, 0, 2), 'calf_l': (-10, 0, 0), 'foot_l': (4, 0, 0),
        'thigh_r': (-16, 0, -3), 'calf_r': (22, 0, 0), 'foot_r': (-10, 0, 0),
    })
    pass_pose = dict(neutral, **{
        'spine_01': (4, 0, 2), 'spine_03': (8, 0, 5),
        'upperarm_l': (-4, 0, -18), 'lowerarm_l': (-10, 0, -7),
        'upperarm_r': (5, 0, 16), 'lowerarm_r': (-12, 0, 7),
        'thigh_l': (-8, 0, 2), 'calf_l': (8, 0, 0), 'foot_l': (-4, 0, 0),
        'thigh_r': (24, 0, -4), 'calf_r': (-20, 0, 0), 'foot_r': (18, 0, 0),
    })
    cross_windup = dict(neutral, **{
        'spine_01': (3, 0, -4), 'spine_03': (6, 0, -8),
        'upperarm_l': (4, 0, -18), 'lowerarm_l': (-10, 0, -8),
        'upperarm_r': (-6, 0, 16), 'lowerarm_r': (-10, 0, 8),
        'thigh_l': (8, 0, 2), 'calf_l': (-12, 0, 0),
        'thigh_r': (-22, 0, -5), 'calf_r': (24, 0, 0), 'foot_r': (-12, 0, 0),
    })
    cross_pose = dict(neutral, **{
        'spine_01': (5, 0, 5), 'spine_03': (12, 0, 10),
        'upperarm_l': (-6, 0, -20), 'lowerarm_l': (-12, 0, -8),
        'upperarm_r': (8, 0, 18), 'lowerarm_r': (-14, 0, 8),
        'thigh_l': (-10, 0, 3), 'calf_l': (8, 0, 0), 'foot_l': (-4, 0, 0),
        'thigh_r': (34, 0, -6), 'calf_r': (-28, 0, 0), 'foot_r': (24, 0, 0),
    })
    shot_windup = dict(neutral, **{
        'spine_01': (4, 0, -5), 'spine_03': (8, 0, -10),
        'upperarm_l': (5, 0, -20), 'lowerarm_l': (-12, 0, -8),
        'upperarm_r': (-8, 0, 18), 'lowerarm_r': (-12, 0, 8),
        'thigh_l': (8, 0, 3), 'calf_l': (-14, 0, 0), 'foot_l': (5, 0, 0),
        'thigh_r': (-30, 0, -6), 'calf_r': (38, 0, 0), 'foot_r': (-16, 0, 0),
    })
    shot_pose = dict(neutral, **{
        'spine_01': (6, 0, 6), 'spine_03': (13, 0, 12),
        'upperarm_l': (-7, 0, -22), 'lowerarm_l': (-12, 0, -8),
        'upperarm_r': (10, 0, 20), 'lowerarm_r': (-14, 0, 8),
        'thigh_l': (-14, 0, 3), 'calf_l': (10, 0, 0), 'foot_l': (-6, 0, 0),
        'thigh_r': (42, 0, -8), 'calf_r': (-34, 0, 0), 'foot_r': (28, 0, 0),
    })
    press_pose = dict(neutral, **{
        'spine_01': (7, 0, 0), 'spine_03': (13, 0, 0), 'neck_01': (-5, 0, 0),
        'upperarm_l': (1, 0, -20), 'lowerarm_l': (-16, 0, -8),
        'upperarm_r': (1, 0, 20), 'lowerarm_r': (-16, 0, 8),
        'thigh_l': (20, 0, 5), 'calf_l': (-24, 0, 0), 'foot_l': (8, 0, 0),
        'thigh_r': (18, 0, -5), 'calf_r': (-22, 0, 0), 'foot_r': (8, 0, 0),
    })

    create_action('idle', [(1, neutral), (24, dict(neutral, **{'spine_03': (3, 0, 0)})), (48, neutral)])
    create_action('run', [(1, run_a), (12, neutral), (24, run_b), (36, neutral), (48, run_a)])
    create_action('pass', [(1, neutral), (10, pass_windup), (18, pass_pose), (30, neutral)])
    create_action('cross', [(1, neutral), (10, cross_windup), (20, cross_pose), (36, neutral)])
    create_action('shot', [(1, neutral), (10, shot_windup), (20, shot_pose), (34, neutral)])
    create_action('press', [(1, neutral), (12, press_pose), (24, neutral)])

    root_objs = [obj for obj in bpy.context.scene.objects if obj.parent is None]
    group = bpy.data.objects.new('task_player_mpfb_base_avatar', None)
    bpy.context.collection.objects.link(group)
    for obj in root_objs:
        if obj is not group:
            obj.parent = group

    bpy.ops.object.select_all(action='DESELECT')
    group.select_set(True)
    bpy.context.view_layer.objects.active = group
    group.rotation_euler[0] = 0

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT_PATH,
        export_format='GLB',
        export_yup=True,
        export_apply=False,
    )
    with open(OUT_PATH, 'rb') as src:
        data = src.read()
    for copy_path in (HUMANOID_PATH, PREMIUM_PATH):
        with open(copy_path, 'wb') as dst:
            dst.write(data)
    print(OUT_PATH)


if __name__ == '__main__':
    sys.exit(main())
