"""Put a NEW unrigged mesh onto an EXISTING rigged model's skeleton (and its animations).

  blender --background --python tools/rerig_model.py -- OLD_RIGGED.glb NEW_UNRIGGED.glb OUTPUT.glb [--tris 30000] [--height 2.35] [--tex 2048]

The new mesh is shrunk, sized and positioned to match the old one, then takes its skin weights from the nearest
surface of the old mesh. Works best when both are in a similar pose (for example, both in an A-pose or T-pose).
"""
import sys, os, bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
if len(a) < 3: print(__doc__); sys.exit(1)
old_path, new_path, out = a[:3]
def opt(n, d, c=float): return c(a[a.index(n) + 1]) if n in a else d
TRIS, MAXTEX = opt('--tris', 30000, int), opt('--tex', 2048, int)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=old_path)
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
old_meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(old_meshes) > 1:
    bpy.ops.object.select_all(action='DESELECT')
    for o in old_meshes: o.select_set(True)
    bpy.context.view_layer.objects.active = old_meshes[0]; bpy.ops.object.join(); old_meshes = [bpy.context.view_layer.objects.active]
src = old_meshes[0]
def bounds(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
slo, shi = bounds(src); print('old mesh size', tuple(round(v, 2) for v in (shi - slo)))

before = set(bpy.context.scene.objects)
bpy.ops.import_scene.gltf(filepath=new_path)
added = [o for o in bpy.context.scene.objects if o not in before]
meshes = [o for o in added if o.type == 'MESH']
new = max(meshes, key=lambda o: len(o.data.vertices))
for o in added:
    if o is not new: bpy.data.objects.remove(o, do_unlink=True)
new.parent = None
bpy.context.view_layer.objects.active = new; bpy.ops.object.select_all(action='DESELECT'); new.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
# shrink
tris = sum(len(p.vertices) - 2 for p in new.data.polygons)
if tris > TRIS:
    m = new.modifiers.new('Shrink', 'DECIMATE'); m.ratio = TRIS / tris; m.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=m.name)
print('new triangles', tris, '->', sum(len(p.vertices) - 2 for p in new.data.polygons))
# match the old mesh: same height, centred, feet on the same floor
nlo, nhi = bounds(new); k = (shi.z - slo.z) / (nhi.z - nlo.z); new.scale = (k, k, k); bpy.ops.object.transform_apply(scale=True)
nlo, nhi = bounds(new); new.location += Vector(((slo.x + shi.x) / 2 - (nlo.x + nhi.x) / 2, (slo.y + shi.y) / 2 - (nlo.y + nhi.y) / 2, slo.z - nlo.z)); bpy.ops.object.transform_apply(location=True)
nlo, nhi = bounds(new); print('new mesh size', tuple(round(v, 2) for v in (nhi - nlo)))
# skin weights from the old mesh
for vg in src.vertex_groups: new.vertex_groups.new(name=vg.name)
dt = new.modifiers.new('xfer', 'DATA_TRANSFER'); dt.object = src; dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
try: dt.layers_vgroup_select_src = 'ALL'; dt.layers_vgroup_select_dst = 'NAME'
except Exception as e: print('layer select', e)
bpy.context.view_layer.objects.active = new; bpy.ops.object.modifier_apply(modifier=dt.name)
bpy.ops.object.vertex_group_limit_total(limit=4); bpy.ops.object.vertex_group_normalize_all(lock_active=False)
am = new.modifiers.new('Armature', 'ARMATURE'); am.object = arm; new.parent = arm; new.matrix_parent_inverse = arm.matrix_world.inverted()
bpy.data.objects.remove(src, do_unlink=True)
for img in bpy.data.images:
    if img.size[0] > MAXTEX or img.size[1] > MAXTEX:
        k2 = MAXTEX / max(img.size); img.scale(max(1, int(img.size[0] * k2)), max(1, int(img.size[1] * k2)))
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_yup=True, export_apply=True, export_animations=True, export_skins=True, export_image_format='JPEG', export_jpeg_quality=85)
print('Saved', out, round(os.path.getsize(out) / 1e6, 1), 'MB')
