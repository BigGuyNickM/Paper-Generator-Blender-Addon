import bpy
import os
from . import utils, geonodes, textures
from .shapes import SHAPE_MAP, AlongCurveShape

def generate(context):
    props = context.scene.paper_generator_properties
    images, base_name = _resolve_source(props)
    if images is None:
        return False, base_name
    if not images:
        return False, "No images found"
    shape = SHAPE_MAP.get(props.placement_shape)
    if shape is None:
        return False, f"Unknown placement shape: {props.placement_shape}"
    paper_image, paper_error = _resolve_paper_texture(props)
    if paper_error:
        return False, paper_error
    page_kw = _page_kwargs(props, len(images))
    collection = utils.create_collection(base_name)
    utils.create_materials(images, paper_image)
    props.pages_object = _build_placement(shape, props, base_name, collection, images, page_kw)
    props.pages_collection = collection.name
    props.pages_materials = ",".join(f"PaperPage_{i:04d}" for i in range(len(images)))
    return True, f"Generated {len(images)} pages"

def finalize(context):
    props = context.scene.paper_generator_properties
    pages, collection, materials, error = _resolve_state(props)
    if error:
        return False, error
    count = len(utils.finalize_pages(pages, materials, collection))
    props.pages_object = props.pages_collection = props.pages_materials = ""
    return True, f"Finalized {count} pages with materials assigned"

def _build_placement(shape, props, base_name, collection, images, page_kw):
    if isinstance(shape, AlongCurveShape):
        return _build_curve_placement(base_name, collection, images, props, page_kw)
    obj = shape.build_mesh(base_name, collection,
        props.profile_width, props.profile_height, props.profile_depth)
    builder = geonodes.SHAPE_BUILDERS.get(shape.distribution, geonodes.build_shape_faces)
    builder(obj, **page_kw)
    return obj.name

def _build_curve_placement(base_name, collection, images, props, page_kw):
    pages = utils.create_pages_object(base_name, collection)
    curve_length = max((len(images) - 1) * props.spacing, 0.001)
    curve = utils.create_curve(base_name, collection, curve_length=curve_length)
    geonodes.build_curve(pages, curve,
        spacing=props.spacing, align_to_curve=props.align_to_curve, **page_kw)
    return pages.name

def _resolve_paper_texture(props):
    match props.paper_texture:
        case "NONE":
            return None, None
        case mode:
            image = textures.resolve_paper_texture(mode, props.paper_texture_custom)
            if image:
                return image, None
            if mode == "CUSTOM":
                return None, "Custom paper texture file not found"
            name = textures.preset_label(mode)
            return None, f"Paper texture '{name}' not found in paper_textures/"

def _page_kwargs(props, page_count):
    return dict(
        page_count=page_count,
        page_width=props.page_width,
        page_height=props.page_height,
        subdivisions=props.subdivisions,
        base_offset=(props.base_offset_x, props.base_offset_y, props.base_offset_z),
        max_random_offset=(props.max_random_offset_x, props.max_random_offset_y, props.max_random_offset_z),
        base_rotation=(props.base_rotation_x, props.base_rotation_y, props.base_rotation_z),
        max_random_rotation=(props.max_random_rotation_x, props.max_random_rotation_y,
                             props.max_random_rotation_z),
    )

def _resolve_source(props):
    match props.mode:
        case "PDF":
            return _resolve_pdf(props)
        case _:
            return _resolve_folder(props)

def _resolve_pdf(props):
    pdf_path = bpy.path.abspath(props.pdf_path)
    if not os.path.isfile(pdf_path):
        return None, "PDF file not found"
    paths = utils.rasterize_pdf(pdf_path, utils.get_cache_path(pdf_path))
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    return utils.load_images_from_paths(paths), base_name

def _resolve_folder(props):
    folder = bpy.path.abspath(props.folder_path)
    if not os.path.isdir(folder):
        return None, "Folder not found"
    images = utils.load_images_from_folder(folder)
    name = os.path.basename(os.path.normpath(folder)).replace("_pages", "")
    return images, name

def _resolve_state(props):
    if not all((props.pages_object, props.pages_collection, props.pages_materials)):
        return None, None, None, "No generated paper found - run Generate first"
    pages = bpy.data.objects.get(props.pages_object)
    if not pages:
        return None, None, None, f"Pages object '{props.pages_object}' not found"
    collection = bpy.data.collections.get(props.pages_collection)
    materials = [bpy.data.materials.get(name) for name in props.pages_materials.split(",")]
    if None in materials:
        return None, None, None, "One or more page materials are missing"
    return pages, collection, materials, None

class PaperGeneratorGenerateOperator(bpy.types.Operator):
    bl_idname = "paper_generator.generate"
    bl_label = "Generate Paper"

    def execute(self, context):
        ok, msg = generate(context)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}

class PaperGeneratorFinalizeOperator(bpy.types.Operator):
    bl_idname = "paper_generator.finalize"
    bl_label = "Finalize Pages"

    def execute(self, context):
        ok, msg = finalize(context)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}

_classes = (PaperGeneratorGenerateOperator, PaperGeneratorFinalizeOperator)

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in _classes:
        bpy.utils.unregister_class(cls)
