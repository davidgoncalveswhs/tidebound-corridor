"""Prepare a character model for the 3D battle: join, clean, shrink, stand on the floor, export a small .glb.

Run it from a terminal (Blender 3.6 or newer):

  blender --background --python tools/prepare_model.py -- INPUT.glb OUTPUT.glb [--tris 30000] [--height 2.35] [--tex 2048] [--jpeg] [--keep-rig]

  INPUT / OUTPUT   .glb, .gltf, .fbx, .obj or .vrm files (the output is always .glb)
  --tris N         target triangle count (default 30000)
  --height H       final height in game units (default 2.35, the size of the placeholder heroes)
  --tex N          shrink any texture larger than N pixels (default 2048)
  --jpeg           save textures as JPEG (much smaller files; a little lossy)
  --keep-rig       do not shrink the mesh at all (only clean, scale and export)

Rigged models are shrunk too; the bone weights are carried over by the Decimate modifier.
Animations are kept. If the model has one clip, name it in Blender or in the game manifest as you like.

On macOS the Blender program is usually /Applications/Blender.app/Contents/MacOS/Blender
"""
import sys, os, math
import bpy, bmesh
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(argv) < 2:
    print(__doc__); sys.exit(1)
src, dst = argv[0], argv[1]
def opt(name, default, cast=float):
    return cast(argv[argv.index(name) + 1]) if name in argv else default
TARGET_TRIS, HEIGHT, MAXTEX, KEEP_RIG = opt('--tris', 30000, int), opt('--height', 2.35), opt('--tex', 2048, int), '--keep-rig' in argv

# ---- start clean and import ----
bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(src)[1].lower()
if ext in ('.glb', '.gltf', '.vrm'): bpy.ops.import_scene.gltf(filepath=src)
elif ext == '.fbx': bpy.ops.import_scene.fbx(filepath=src)
elif ext == '.obj': bpy.ops.wm.obj_import(filepath=src)
else: sys.exit(f'Unsupported file type: {ext}')

meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not meshes: sys.exit('No meshes found in the file.')
rigged = any(o.find_armature() for o in meshes) or any(o.type == 'ARMATURE' for o in bpy.context.scene.objects)
print(f'Meshes: {len(meshes)}   rigged: {rigged}')

def tri_count(objs):
    return sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
def select_only(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

# ---- bake transforms so scale and rotation are 1 / 0 ----
if not rigged:
    select_only(meshes)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ---- clean up each mesh: merge duplicate points, drop loose bits ----
for o in meshes:
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00005)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(o.data); bm.free()
    for p in o.data.polygons: p.use_smooth = True

# ---- shrink to the target triangle budget ----
before = tri_count(meshes)
if KEEP_RIG:
    print('--keep-rig: skipping decimation.')
elif before > TARGET_TRIS:
    if len(meshes) > 1 and not rigged:
        select_only(meshes); bpy.ops.object.join(); meshes = [bpy.context.view_layer.objects.active]
    for o in meshes:
        share = tri_count([o]) / before
        mod = o.modifiers.new('Shrink', 'DECIMATE'); mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(0.01, min(1.0, TARGET_TRIS * share / max(1, tri_count([o])))); mod.use_collapse_triangulate = True
        select_only([o])
        if rigged:   # shrink the mesh itself, before the skeleton bends it, and keep the bone weights
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
        bpy.ops.object.modifier_apply(modifier=mod.name)
print(f'Triangles: {before} -> {tri_count([o for o in bpy.context.scene.objects if o.type == "MESH"])}')

# ---- shrink big textures ----
for img in bpy.data.images:
    if img.size[0] > MAXTEX or img.size[1] > MAXTEX:
        k = MAXTEX / max(img.size)
        img.scale(max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
        print(f'Texture {img.name}: shrunk to {img.size[0]}x{img.size[1]}')

# ---- scale to the game height and stand on the floor, centred ----
allobjs = [o for o in bpy.context.scene.objects if o.type in ('MESH', 'ARMATURE')]
def bounds():
    pts = [o.matrix_world @ Vector(c) for o in bpy.context.scene.objects if o.type == 'MESH' for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
lo, hi = bounds()
cur = hi.z - lo.z or 1.0
roots = [o for o in bpy.context.scene.objects if o.parent is None]
k = HEIGHT / cur
for r in roots: r.scale = r.scale * k
bpy.context.view_layer.update()
lo, hi = bounds()
shift = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z))
for r in roots: r.location += shift
bpy.context.view_layer.update()
if not rigged:
    select_only([o for o in bpy.context.scene.objects if o.type == 'MESH'])
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
lo, hi = bounds()
print(f'Final size: {hi.x - lo.x:.2f} x {hi.y - lo.y:.2f} x {hi.z - lo.z:.2f}  (Z is up in Blender; the game gets Y up)')

# ---- export: Y up, no compression, animations kept, textures packed ----
bpy.ops.export_scene.gltf(filepath=dst, export_format='GLB', export_yup=True, export_apply=True,
                          export_animations=True, export_skins=True, export_image_format='JPEG' if '--jpeg' in argv else 'AUTO', export_jpeg_quality=85)
print(f'Saved {dst}  ({os.path.getsize(dst) / 1e6:.1f} MB)')
print('Next: put it in 3d/models/ and add it to manifest.json. If it faces the wrong way, set "yaw": 3.14159 there.')
