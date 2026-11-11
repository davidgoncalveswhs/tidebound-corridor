"""Shrink a rigged model and put the animation clips of one or more other rigged files onto it.

  blender --background --python tools/merge_anims.py -- MODEL.glb OUTPUT.glb [--clips A.glb B.glb ...] [--tris 30000] [--tex 2048]

The first file keeps its own animation (for example a walk). Each --clips file donates its animations
(for example a kick). All files must use the same bone names.
"""
import sys, os, bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
model, out = a[0], a[1]
clips = []
if '--clips' in a:
    for x in a[a.index('--clips') + 1:]:
        if x.startswith('--'): break
        clips.append(x)
def opt(n, d, c=float): return c(a[a.index(n) + 1]) if n in a else d
TRIS, MAXTEX, HEIGHT = opt('--tris', 30000, int), opt('--tex', 2048, int), opt('--height', 2.35)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=model)
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
walk = arm.animation_data.action if arm.animation_data else None
actions = {}
if walk: actions[walk.name] = walk
# shrink the mesh before the skeleton bends it, keeping the bone weights
tris = sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons)
for o in meshes:
    share = sum(len(p.vertices) - 2 for p in o.data.polygons) / tris
    m = o.modifiers.new('Shrink', 'DECIMATE'); m.ratio = max(0.01, min(1, TRIS * share / max(1, sum(len(p.vertices) - 2 for p in o.data.polygons)))); m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = o; bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0); bpy.ops.object.modifier_apply(modifier=m.name)
print('triangles', tris, '->', sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons))
for img in bpy.data.images:
    if img.size[0] > MAXTEX or img.size[1] > MAXTEX:
        k = MAXTEX / max(img.size); img.scale(max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
# collect the other clips
for path in clips:
    before = set(bpy.context.scene.objects); acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new_acts = [x for x in bpy.data.actions if x not in acts_before]
    for ac in new_acts: ac.use_fake_user = True; actions[ac.name] = ac
    for o in [o for o in bpy.context.scene.objects if o not in before]: bpy.data.objects.remove(o, do_unlink=True)
print('clips', list(actions))
# every clip on its own NLA track of the model's armature
arm.animation_data_create(); arm.animation_data.action = None
for name, ac in actions.items():
    tr = arm.animation_data.nla_tracks.new(); tr.name = name; st = tr.strips.new(name, 0, ac); st.name = name
# size and stand it like the other models
def bounds():
    pts = [o.matrix_world @ Vector(c) for o in bpy.context.scene.objects if o.type == 'MESH' for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
lo, hi = bounds(); k = HEIGHT / ((hi.z - lo.z) or 1)
roots = [o for o in bpy.context.scene.objects if o.parent is None]
for r in roots: r.scale = r.scale * k
bpy.context.view_layer.update(); lo, hi = bounds()
for r in roots: r.location += Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
bpy.context.view_layer.update()
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_yup=True, export_apply=True, export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True, export_image_format='JPEG', export_jpeg_quality=85)
print('Saved', out, round(os.path.getsize(out) / 1e6, 1), 'MB')
