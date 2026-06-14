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


def shade_smooth(obj):
    try:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
    except Exception:
        pass


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

    skin = make_material('xbot_skin_surface', (0.82, 0.56, 0.47, 1.0), 0.58)
    joint = make_material('xbot_skin_joints', (0.72, 0.45, 0.37, 1.0), 0.64)
    shirt_mat = make_material('footballer_green_jersey', (0.00, 0.47, 0.30, 1.0), 0.58)
    trim_mat = make_material('footballer_white_trim', (0.92, 0.96, 0.92, 1.0), 0.62)
    shorts_mat = make_material('footballer_dark_shorts', (0.02, 0.05, 0.10, 1.0), 0.70)
    socks_mat = make_material('footballer_white_socks', (0.93, 0.95, 0.90, 1.0), 0.66)
    boots_mat = make_material('footballer_black_boots', (0.01, 0.012, 0.016, 1.0), 0.54)
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        low = obj.name.lower()
        obj.name = f'task_player_mocap_{obj.name}'
        obj.data.materials.clear()
        obj.data.materials.append(joint if 'joint' in low else skin)
        obj.show_name = False
        shade_smooth(obj)

    def parent_to_bone(obj, bone_name):
        if not obj or not armature.pose.bones.get(bone_name):
            return
        world = obj.matrix_world.copy()
        obj.parent = armature
        obj.parent_type = 'BONE'
        obj.parent_bone = bone_name
        obj.matrix_world = world

    def add_cylinder(name, material, radius, depth, location, scale=(1, 1, 1), bone='mixamorig:Hips', vertices=32):
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        obj.data.materials.append(material)
        shade_smooth(obj)
        parent_to_bone(obj, bone)
        return obj

    def add_cube(name, material, location, scale, bone):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        obj.data.materials.append(material)
        shade_smooth(obj)
        parent_to_bone(obj, bone)
        return obj

    def add_sphere(name, material, radius, location, scale=(1, 1, 1), bone='mixamorig:Hips'):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        obj.data.materials.append(material)
        shade_smooth(obj)
        parent_to_bone(obj, bone)
        return obj

    def add_tapered_torso(name, material, location, bone='mixamorig:Spine2'):
        rings = [
            (-0.25, 0.220, 0.150),
            (-0.10, 0.238, 0.162),
            (0.10, 0.258, 0.170),
            (0.23, 0.278, 0.150),
        ]
        segments = 28
        verts = []
        faces = []
        for z, rx, ry in rings:
            for index in range(segments):
                angle = (index / segments) * math.tau
                verts.append((math.cos(angle) * rx, math.sin(angle) * ry, z))
        for ring in range(len(rings) - 1):
            base = ring * segments
            nxt = (ring + 1) * segments
            for index in range(segments):
                faces.append((base + index, base + ((index + 1) % segments), nxt + ((index + 1) % segments), nxt + index))
        faces.append(tuple(reversed(range(segments))))
        top_start = (len(rings) - 1) * segments
        faces.append(tuple(top_start + index for index in range(segments)))
        mesh = bpy.data.meshes.new(f'{name}_mesh')
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        obj.data.materials.append(material)
        shade_smooth(obj)
        parent_to_bone(obj, bone)
        return obj

    add_tapered_torso(
        'footballer_rigged_jersey_torso',
        shirt_mat,
        (0, -0.040, 1.16),
        'mixamorig:Spine2',
    )
    add_cube('footballer_rigged_jersey_stripe_l', trim_mat, (-0.055, -0.235, 1.17), (0.026, 0.010, 0.17), 'mixamorig:Spine2')
    add_cube('footballer_rigged_jersey_stripe_r', trim_mat, (0.055, -0.235, 1.17), (0.026, 0.010, 0.17), 'mixamorig:Spine2')
    add_cylinder(
        'footballer_rigged_shorts',
        shorts_mat,
        0.225,
        0.18,
        (0, 0.00, 0.84),
        (0.92, 0.62, 1.0),
        'mixamorig:Hips',
        vertices=28,
    )

    for side, x in [('left', 0.18), ('right', -0.18)]:
        up_arm = f'mixamorig:{"Left" if side == "left" else "Right"}Arm'
        leg = f'mixamorig:{"Left" if side == "left" else "Right"}Leg'
        foot = f'mixamorig:{"Left" if side == "left" else "Right"}Foot'
        add_sphere(f'footballer_rigged_{side}_sleeve', shirt_mat, 0.078, (x * 0.92, -0.01, 1.16), (1.0, 0.66, 0.62), up_arm)
        add_cylinder(f'footballer_rigged_{side}_sock', socks_mat, 0.042, 0.30, (x * 0.72, -0.005, 0.30), (0.82, 0.76, 1.0), leg, vertices=18)
        boot = add_cube(f'footballer_rigged_{side}_boot', boots_mat, (x * 0.72, -0.09, 0.055), (0.070, 0.135, 0.030), foot)
        boot.rotation_euler[0] = math.radians(-8)

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT_PATH, export_format='GLB', export_yup=True, export_apply=False)
    for copy_path in (HUMANOID_PATH, PREMIUM_PATH):
        shutil.copyfile(OUT_PATH, copy_path)
    print(OUT_PATH)


if __name__ == '__main__':
    sys.exit(main())
