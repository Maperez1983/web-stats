import os
import sys

import bpy
import bmesh


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MPFB_PARENT = os.path.expanduser('~/Library/Application Support/Blender/5.1/extensions/user_default')
MH_ASSET_ROOT = os.path.expanduser('~/Documents/MakeHuman/v1py3/official_assets/base')
OUT_PATH = os.path.join(ROOT, 'football/static/football/models/avatar/player_mpfb_base.glb')
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

    for x in (-0.034, 0.034):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.017, location=(x, -0.098, 1.315))
        eye = bpy.context.object
        eye.name = 'mpfb_player_eye'
        eye.scale.y = 0.44
        eye.data.materials.append(eye_white)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.007, location=(x, -0.111, 1.315))
        iris = bpy.context.object
        iris.name = 'mpfb_player_iris'
        iris.scale.y = 0.16
        iris.data.materials.append(iris_mat)

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
