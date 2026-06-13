import math
import os
import sys

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


def assign_football_kit(obj):
    mesh = obj.data
    skin = make_mat('footballer_skin', (0.72, 0.50, 0.34, 1.0), 0.58)
    shirt = make_mat('footballer_green_jersey', (0.0, 0.48, 0.30, 1.0), 0.62)
    trim = make_mat('footballer_white_trim', (0.92, 0.96, 0.94, 1.0), 0.66)
    shorts = make_mat('footballer_dark_shorts', (0.015, 0.025, 0.045, 1.0), 0.72)
    socks = make_mat('footballer_white_socks', (0.92, 0.94, 0.90, 1.0), 0.72)
    boots = make_mat('footballer_black_boots', (0.01, 0.012, 0.016, 1.0), 0.52)

    mesh.materials.clear()
    for mat in (skin, shirt, trim, shorts, socks, boots):
        mesh.materials.append(mat)

    for poly in mesh.polygons:
        x, depth, y = poly_center(mesh, poly)
        ax = abs(x)
        mat_index = 0
        if 0.78 <= y <= 1.28 and ax <= 0.58:
            mat_index = 1
        if 0.58 <= y < 0.88 and ax <= 0.34:
            mat_index = 3
        if 0.14 <= y < 0.48 and 0.05 <= ax <= 0.23:
            mat_index = 4
        if y < 0.12 and 0.04 <= ax <= 0.25:
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


def main():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=IN_PATH)

    armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            armature = obj
        if obj.type == 'MESH' and any('Superhero_Male' in slot.material.name for slot in obj.material_slots if slot.material):
            assign_football_kit(obj)

    if armature:
        pose_armature(armature)

    bpy.ops.export_scene.gltf(
        filepath=OUT_PATH,
        export_format='GLB',
        export_yup=True,
        export_apply=False,
    )

    with open(OUT_PATH, 'rb') as src, open(COPY_PATH, 'wb') as dst:
        dst.write(src.read())


if __name__ == '__main__':
    sys.exit(main())
