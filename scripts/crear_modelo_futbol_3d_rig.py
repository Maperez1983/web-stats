# Blender 4.x - Prototipo de escena 3D estilo tarea táctica de fútbol
# Uso:
#   /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/crear_modelo_futbol_3d_rig.py -- --export /tmp/tarea_futbol_3d.glb
# o abre en Blender > Scripting > Run Script.

import math
import os
import sys

import bpy


def parse_export_path(argv):
    if "--" not in argv:
        return None
    args = argv[argv.index("--") + 1 :]
    for i, arg in enumerate(args):
        if arg in {"--export", "--output", "--out"} and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--export="):
            return arg.split("=", 1)[1]
    return None


def mat(name, color):
    material = bpy.data.materials.new(name)
    material.use_nodes = False
    material.diffuse_color = color
    return material


def cube(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    return obj


def dashed_line(name, start, end, segments=18, width=0.22, material=None):
    sx, sy = start
    ex, ey = end
    dx = (ex - sx) / segments
    dy = (ey - sy) / segments
    length = (dx * dx + dy * dy) ** 0.5 * 0.6
    angle = math.atan2(dy, dx)
    for idx in range(segments):
        if idx % 2 != 0:
            continue
        cx = sx + dx * (idx + 0.5)
        cy = sy + dy * (idx + 0.5)
        o = cube(f"{name}_{idx}", (cx, cy, 0.09), (length, width, 0.05), material)
        o.rotation_euler[2] = angle


def create_player(name, loc, team_mat):
    x, y, z = loc
    parts = []

    body = cube(f"{name}_torso", (x, y, z + 1.15), (0.45, 0.28, 0.9), team_mat)
    parts.append(body)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.22, location=(x, y, z + 1.75))
    head = bpy.context.object
    head.name = f"{name}_cabeza"
    head.data.materials.append(skin_mat)
    parts.append(head)

    for side in (-1, 1):
        parts.append(cube(f"{name}_pierna{side}", (x + side * 0.12, y, z + 0.55), (0.16, 0.16, 0.75), black_mat))
        parts.append(cube(f"{name}_brazo{side}", (x + side * 0.33, y, z + 1.2), (0.14, 0.14, 0.72), team_mat))

    empty = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(empty)
    empty.location = (0, 0, 0)
    for part in parts:
        part.parent = empty

    bpy.ops.object.armature_add(enter_editmode=True, location=(x, y, z))
    arm = bpy.context.object
    arm.name = f"{name}_rig_humanoide_simple"
    eb = arm.data.edit_bones[0]
    eb.name = "hips"
    eb.head = (x, y, z + 0.8)
    eb.tail = (x, y, z + 1.25)

    spine = arm.data.edit_bones.new("spine")
    spine.head = eb.tail
    spine.tail = (x, y, z + 1.6)
    spine.parent = eb

    head_b = arm.data.edit_bones.new("head")
    head_b.head = spine.tail
    head_b.tail = (x, y, z + 1.95)
    head_b.parent = spine

    for side, label in ((-1, "L"), (1, "R")):
        leg = arm.data.edit_bones.new(f"{label}_leg")
        leg.head = (x + side * 0.12, y, z + 0.8)
        leg.tail = (x + side * 0.12, y, z + 0.15)
        leg.parent = eb

        arm_b = arm.data.edit_bones.new(f"{label}_arm")
        arm_b.head = (x + side * 0.25, y, z + 1.45)
        arm_b.tail = (x + side * 0.55, y, z + 0.95)
        arm_b.parent = spine

    bpy.ops.object.mode_set(mode="OBJECT")
    arm.parent = empty
    return empty


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

green_mat = mat("cesped_verde", (0.25, 0.55, 0.16, 1))
green2_mat = mat("franjas_cesped", (0.31, 0.63, 0.19, 1))
white_mat = mat("lineas_blancas", (1, 1, 1, 1))
yellow_mat = mat("zonas_amarillas", (1, 0.9, 0.05, 1))
dark_mat = mat("equipo_granate", (0.12, 0, 0.08, 1))
light_mat = mat("equipo_beige", (0.86, 0.67, 0.45, 1))
skin_mat = mat("piel", (0.78, 0.55, 0.38, 1))
black_mat = mat("negro", (0.02, 0.02, 0.02, 1))

field = cube("campo_3D_105x68", (0, 0, -0.02), (105, 68, 0.04), green_mat)
for i in range(10):
    x = -52.5 + i * 10.5 + 5.25
    cube("franja_cesped", (x, 0, 0.005), (5.25, 68, 0.01), green2_mat)

for name, x, y, sx, sy in (
    ("banda_sup", 0, 34, 105, 0.25),
    ("banda_inf", 0, -34, 105, 0.25),
    ("fondo_izq", -52.5, 0, 0.25, 68),
    ("fondo_der", 52.5, 0, 0.25, 68),
    ("medio", 0, 0, 0.22, 68),
):
    cube(name, (x, y, 0.04), (sx, sy, 0.05), white_mat)

for x in (-36, 36):
    cube("area_linea_fondo", (x, 0, 0.045), (0.2, 40, 0.05), white_mat)
    cube("area_linea_sup", (x / abs(x) * 44.25, 20, 0.045), (16.5, 0.2, 0.05), white_mat)
    cube("area_linea_inf", (x / abs(x) * 44.25, -20, 0.045), (16.5, 0.2, 0.05), white_mat)

x1, x2 = -38, 38
y1, y2 = -26, 26
for a, b in (((x1, y1), (x2, y1)), ((x1, y2), (x2, y2)), ((x1, y1), (x1, y2)), ((x2, y1), (x2, y2))):
    dashed_line("zona_punteada", a, b, 28, material=yellow_mat)
for x in (-25, -12.5, 0, 12.5, 25):
    dashed_line("division_vertical", (x, y1), (x, y2), 18, material=yellow_mat)
for y in (-8.5, 8.5):
    dashed_line("division_horizontal", (x1, y), (x2, y), 28, material=yellow_mat)

for name_idx, pos in enumerate(((-42, -12), (-30, -20), (-28, -5), (-25, 12), (-5, -8), (8, -12), (15, 8), (32, -15), (42, 20))):
    create_player(f"granate_{name_idx + 1}", (pos[0], pos[1], 0), dark_mat)

for name_idx, pos in enumerate(((-44, 12), (-18, -16), (-15, 5), (-6, 18), (5, 0), (22, 10), (24, -10), (38, 18), (45, -5))):
    create_player(f"beige_{name_idx + 1}", (pos[0], pos[1], 0), light_mat)

bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.35, location=(-20, -3, 0.35))
ball = bpy.context.object
ball.name = "balon"
ball.data.materials.append(white_mat)

bpy.ops.object.light_add(type="SUN", location=(0, -20, 30))
bpy.context.object.name = "sol_sombras_tacticas"
bpy.context.object.data.energy = 3

bpy.ops.object.camera_add(location=(0, -76, 58), rotation=(math.radians(58), 0, 0))
bpy.context.scene.camera = bpy.context.object
bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"

export_path = parse_export_path(sys.argv)
if not export_path:
    export_path = "/tmp/tarea_futbol_3d.glb"

os.makedirs(os.path.dirname(export_path), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=export_path, export_format="GLB")
print(f"PROTOTIPO CREADO: exportado a {export_path}")
