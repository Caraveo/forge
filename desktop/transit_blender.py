import bpy, os, sys

src, out_fbx, work_dir = sys.argv[-3:]
os.makedirs(work_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

# Make the imported scene self-contained and preserve its material graph.
for image in list(bpy.data.images):
    if image.type == 'GENERATED':
        continue
    stem = os.path.splitext(os.path.basename(image.filepath or image.name))[0]
    path = os.path.join(work_dir, stem + '.png')
    try:
        # On the second pass, Transit has already replaced this file with the
        # upscaled version; keep that version instead of overwriting it.
        if not os.path.exists(path):
            image.save_render(path)
        replacement = bpy.data.images.load(path, check_existing=False)
        for material in bpy.data.materials:
            if not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if hasattr(node, 'image') and node.image == image:
                    node.image = replacement
        image['transit_texture'] = path
    except Exception as exc:
        print(f'TRANSIT_TEXTURE_WARNING {image.name}: {exc}')

# Apply transforms without changing the model's visible size.
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.select_set(False)

os.makedirs(os.path.dirname(out_fbx), exist_ok=True)
bpy.ops.export_scene.fbx(
    filepath=out_fbx,
    use_selection=False,
    object_types={'MESH', 'ARMATURE', 'EMPTY'},
    apply_unit_scale=True,
    bake_space_transform=False,
    path_mode='COPY',
    embed_textures=True,
    use_mesh_modifiers=True,
    add_leaf_bones=False,
    bake_anim=True,
    bake_anim_use_all_bones=True,
    bake_anim_use_nla_strips=False,
    bake_anim_use_all_actions=True,
)
print(f'TRANSIT_OUTPUT={out_fbx}')
