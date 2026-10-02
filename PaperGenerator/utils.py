import bpy
import os
from .textures import IMAGE_EXTENSIONS

def get_cache_path(pdf_path):
    directory = os.path.dirname(pdf_path)
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    return os.path.join(directory, f"{name}_pages")

def rasterize_pdf(pdf_path, cache_path, dpi=150):
    import fitz
    os.makedirs(cache_path, exist_ok=True)
    document = fitz.open(pdf_path)
    image_paths = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for index, page in enumerate(document):
        pixmap = page.get_pixmap(matrix=matrix)
        out_path = os.path.join(cache_path, f"page_{index:04d}.jpg")
        pixmap.save(out_path)
        image_paths.append(out_path)
    document.close()
    return image_paths

def load_images_from_folder(folder_path):
    extensions = {ext.lower() for ext in IMAGE_EXTENSIONS}
    files = sorted(
        f for f in os.listdir(folder_path)
        if os.path.splitext(f)[1].lower() in extensions
    )
    return load_images_from_paths([os.path.join(folder_path, f) for f in files])

def load_images_from_paths(image_paths):
    images = []
    for path in image_paths:
        name = os.path.basename(path)
        image = bpy.data.images.get(name) or bpy.data.images.load(path)
        images.append(image)
    return images

def create_materials(images, paper_image=None):
    return [_create_material(image, i, paper_image) for i, image in enumerate(images)]

def _create_material(image, index, paper_image=None):
    material_name = f"PaperPage_{index:04d}"
    existing = bpy.data.materials.get(material_name)
    if existing:
        bpy.data.materials.remove(existing)
    material = bpy.data.materials.new(name=material_name)
    if bpy.app.version < (5, 0, 0):
        material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Roughness"].default_value = 1.0
    principled.inputs["Specular IOR Level"].default_value = 0.0
    texcoord = nodes.new("ShaderNodeTexCoord")
    page_tex = nodes.new("ShaderNodeTexImage")
    page_tex.image = image
    page_tex.location = (-500, 100)
    color = _page_color_output(links, nodes, texcoord, page_tex, paper_image)
    links.new(color, principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    texcoord.location = (-700, 0)
    principled.location = (100, 0)
    output.location = (300, 0)
    return material

def _page_color_output(links, nodes, texcoord, page_tex, paper_image):
    links.new(texcoord.outputs["UV"], page_tex.inputs["Vector"])
    if not paper_image:
        return page_tex.outputs["Color"]
    paper_tex = nodes.new("ShaderNodeTexImage")
    paper_tex.image = paper_image
    paper_tex.location = (-500, -100)
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.location = (-200, 0)
    links.new(texcoord.outputs["UV"], paper_tex.inputs["Vector"])
    links.new(page_tex.outputs["Color"], mix.inputs["A"])
    links.new(paper_tex.outputs["Color"], mix.inputs["B"])
    return mix.outputs["Result"]

def create_collection(base_name):
    collection = bpy.data.collections.new(base_name)
    bpy.context.scene.collection.children.link(collection)
    return collection

def create_curve(base_name, collection, curve_length=1.0):
    curve_data = bpy.data.curves.new(f"{base_name}_curve", type="CURVE")
    curve_data.dimensions = "3D"
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(1)
    handle_length = curve_length * 0.25
    start, end = spline.bezier_points[0], spline.bezier_points[1]
    start.co = (0, 0, 0)
    start.handle_left = (0, 0, -handle_length)
    start.handle_right = (0, 0, handle_length)
    end.co = (0, 0, curve_length)
    end.handle_left = (0, 0, curve_length - handle_length)
    end.handle_right = (0, 0, curve_length + handle_length)
    for point in (start, end):
        point.handle_left_type = point.handle_right_type = "FREE"
    curve_object = bpy.data.objects.new(f"{base_name}_curve", curve_data)
    collection.objects.link(curve_object)
    return curve_object

def create_pages_object(base_name, collection):
    mesh = bpy.data.meshes.new(f"{base_name}_mesh")
    pages_object = bpy.data.objects.new(f"{base_name}_mesh", mesh)
    collection.objects.link(pages_object)
    return pages_object

def get_modifier(context):
    properties = context.scene.paper_generator_properties
    if not properties.pages_object:
        return None
    scene_object = bpy.data.objects.get(properties.pages_object)
    if not scene_object:
        return None
    return scene_object.modifiers.get("PaperGenerator")

def finalize_pages(pages_object, materials, collection):
    context = bpy.context
    _select_active(pages_object)
    is_curve_mode = any(obj.type == "CURVE" for obj in collection.objects)
    bpy.ops.object.modifier_apply(modifier="PaperGenerator")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    page_objects = _sorted_page_objects(collection, is_curve_mode)
    if is_curve_mode:
        _remove_curve_objects(collection)
    base_name = pages_object.name.replace("_mesh", "").replace("_shape", "")
    for index, page_object in enumerate(page_objects):
        _finalize_single_page(context, page_object, index, materials, base_name)
    return page_objects

def _select_active(obj):
    context = bpy.context
    context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)

def _sorted_page_objects(collection, is_curve_mode):
    mesh_objects = [obj for obj in collection.objects if obj.type == "MESH"]
    if is_curve_mode:
        return sorted(mesh_objects, key=lambda obj: obj.location.z, reverse=True)
    return sorted(mesh_objects, key=lambda obj: obj.name)

def _remove_curve_objects(collection):
    curves = [obj for obj in collection.objects if obj.type == "CURVE"]
    for obj in curves:
        bpy.data.objects.remove(obj, do_unlink=True)

def _finalize_single_page(context, page_object, index, materials, base_name):
    _select_active(page_object)
    if not page_object.data.uv_layers:
        page_object.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.reset()
    bpy.ops.object.mode_set(mode="OBJECT")
    page_object.data.materials.clear()
    if index < len(materials):
        # reversed so page 0 ends up on top when stacked
        page_object.data.materials.append(materials[len(materials) - 1 - index])
    if "Subdivision" in page_object.modifiers:
        bpy.ops.object.modifier_apply(modifier="Subdivision")
    page_object.name = f"{base_name}_page_{index:04d}"
    page_object.data.name = f"{base_name}_page_{index:04d}_mesh"
