import bpy
import math
from contextlib import nullcontext
from . import deps, utils
from .shapes import shape_enum_items, AlongCurveShape, SHAPE_MAP

_AXIS_LABELS = "XYZ"

_TRANSFORM_ROWS = (
    ("Base Offset:", "base_offset", "Base Offset"),
    ("Max Random Offset:", "max_random_offset", "Max Random Offset"),
    ("Base Rotation:", "base_rotation", "Base Rotation"),
    ("Max Random Rotation:", "max_random_rotation", "Max Random Rot"),
)

def _find_modifier_socket(modifier, name):
    if not modifier or not modifier.node_group:
        return None
    for item in modifier.node_group.interface.items_tree:
        if item.item_type != "SOCKET":
            continue
        if item.in_out == "INPUT" and item.name == name:
            return item
    return None

def _modifier_prop(layout, context, modifier, pages_object, name, label=None, **kwargs):
    socket = _find_modifier_socket(modifier, name)
    if not socket:
        return False
    pages = bpy.data.objects.get(pages_object) if pages_object else None
    override = (
        context.temp_override(object=pages, active_object=pages)
        if pages else nullcontext()
    )
    props = getattr(modifier, "properties", None)
    inputs = getattr(props, "inputs", None)
    with override:
        if inputs is None:
            layout.prop(modifier, f'["{socket.identifier}"]', text=label or name, **kwargs)
            return True
        entry = getattr(inputs, socket.identifier, None)
        if entry is None:
            return False
        layout.prop(entry, "value", text=label or name, **kwargs)
    return True

def _props_row(layout, context, props, names, labels, modifier=None, mod_names=None):
    row = layout.row(align=True)
    for name, label, mod_name in zip(names, labels, mod_names or names):
        if modifier and _modifier_prop(
                row, context, modifier, props.pages_object, mod_name, label=label):
            continue
        row.prop(props, name, text=label)

def _draw_source(box, props):
    box.prop(props, "mode", expand=True)
    match props.mode:
        case "PDF":
            box.prop(props, "pdf_path")
            box.prop(props, "cache_images")
            if not props.cache_images:
                return
            box.prop(props, "cache_path")
        case _:
            box.prop(props, "folder_path")

def _draw_curve_placement(col, context, props, mod):
    if not _modifier_prop(col, context, mod, props.pages_object, "Spacing", label="Spacing"):
        col.prop(props, "spacing")
    if not _modifier_prop(col, context, mod, props.pages_object, "Align to Curve"):
        col.prop(props, "align_to_curve")

def _draw_profile_placement(col, shape, props):
    col.label(text="Profile Size:")
    is_volume = shape and shape.distribution == "volume"
    labels = ("W", "L", "H") if is_volume else ("W", "H")
    names = ("profile_width", "profile_height", "profile_depth")[:len(labels)]
    row = col.row(align=True)
    for name, label in zip(names, labels):
        row.prop(props, name, text=label)

def _draw_placement(box, context, props, mod):
    box.prop(props, "placement_shape", text="Shape")
    shape = SHAPE_MAP.get(props.placement_shape)
    col = box.column(align=True)
    if isinstance(shape, AlongCurveShape):
        _draw_curve_placement(col, context, props, mod)
        return
    _draw_profile_placement(col, shape, props)

def _draw_transform(box, context, props, mod):
    for title, prop_prefix, mod_prefix in _TRANSFORM_ROWS:
        box.label(text=title)
        _props_row(box, context, props,
            [f"{prop_prefix}_{axis.lower()}" for axis in _AXIS_LABELS],
            list(_AXIS_LABELS),
            mod, [f"{mod_prefix} {axis}" for axis in _AXIS_LABELS])
        if title.startswith("Max Random Offset"):
            box.separator()

class PaperGeneratorProperties(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        items=[("PDF", "PDF", "Load from a PDF file"),
               ("FOLDER", "Image Folder", "Load from a folder of images")],
        default="PDF",
    )
    pdf_path: bpy.props.StringProperty(name="PDF File", subtype="FILE_PATH")
    cache_images: bpy.props.BoolProperty(name="Cache Images", default=False)
    cache_path: bpy.props.StringProperty(name="Cache Folder", subtype="DIR_PATH")
    folder_path: bpy.props.StringProperty(name="Image Folder", subtype="DIR_PATH")
    page_width: bpy.props.FloatProperty(name="Page Width", default=0.210, min=0.001, soft_max=2.0, unit="LENGTH")
    page_height: bpy.props.FloatProperty(name="Page Height", default=0.297, min=0.001, soft_max=2.0, unit="LENGTH")
    subdivisions: bpy.props.IntProperty(name="Subdivisions", default=0, min=0, max=6)
    paper_texture: bpy.props.EnumProperty(
        name="Paper Texture",
        items=[
            ("NONE", "None", "Page image only, no paper texture"),
            ("WRINKLED", "Wrinkled", "Wrinkled paper texture"),
            ("TEXTURED", "Textured", "Textured paper surface"),
            ("CUSTOM", "Custom", "Use your own image file"),
        ],
        default="NONE",
    )
    paper_texture_custom: bpy.props.StringProperty(name="Custom Texture", subtype="FILE_PATH")
    placement_shape: bpy.props.EnumProperty(
        name="Placement", items=lambda self, context: shape_enum_items())
    spacing: bpy.props.FloatProperty(name="Spacing", default=0.001, min=0.0, soft_max=0.05, unit="LENGTH")
    align_to_curve: bpy.props.BoolProperty(name="Align to Curve", default=True)
    profile_width: bpy.props.FloatProperty(name="Width", default=1.0, min=0.001, soft_max=5.0, unit="LENGTH")
    profile_height: bpy.props.FloatProperty(name="Length", default=1.0, min=0.001, soft_max=5.0, unit="LENGTH")
    profile_depth: bpy.props.FloatProperty(name="Height", default=1.0, min=0.001, soft_max=5.0, unit="LENGTH")
    base_offset_x: bpy.props.FloatProperty(name="X", default=0.0, unit="LENGTH")
    base_offset_y: bpy.props.FloatProperty(name="Y", default=0.0, unit="LENGTH")
    base_offset_z: bpy.props.FloatProperty(name="Z", default=0.0, unit="LENGTH")
    max_random_offset_x: bpy.props.FloatProperty(name="X", default=0.0, min=0.0, unit="LENGTH")
    max_random_offset_y: bpy.props.FloatProperty(name="Y", default=0.0, min=0.0, unit="LENGTH")
    max_random_offset_z: bpy.props.FloatProperty(name="Z", default=0.0, min=0.0, unit="LENGTH")
    base_rotation_x: bpy.props.FloatProperty(name="X", default=0.0, subtype="ANGLE")
    base_rotation_y: bpy.props.FloatProperty(name="Y", default=0.0, subtype="ANGLE")
    base_rotation_z: bpy.props.FloatProperty(name="Z", default=0.0, subtype="ANGLE")
    max_random_rotation_x: bpy.props.FloatProperty(name="X", default=0.0, min=0.0, max=math.pi, subtype="ANGLE")
    max_random_rotation_y: bpy.props.FloatProperty(name="Y", default=0.0, min=0.0, max=math.pi, subtype="ANGLE")
    max_random_rotation_z: bpy.props.FloatProperty(name="Z", default=0.0, min=0.0, max=math.pi, subtype="ANGLE")
    pages_object: bpy.props.StringProperty()
    pages_collection: bpy.props.StringProperty()
    pages_materials: bpy.props.StringProperty()

class PaperGeneratorMainPanel(bpy.types.Panel):
    bl_label = "Paper Generator"
    bl_idname = "PAPERGENERATOR_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Paper Generator"

    def draw(self, context):
        layout = self.layout
        props = context.scene.paper_generator_properties
        mod = utils.get_modifier(context)
        if not deps.is_pymupdf_available():
            layout.label(text="PyMuPDF not installed", icon="ERROR")
            layout.operator("paper_generator.install_deps", text="Install Dependencies")
            return
        layout.label(text="Source")
        _draw_source(layout.box(), props)
        layout.separator()
        layout.label(text="Page Setup")
        box = layout.box()
        col = box.column(align=True)
        col.prop(props, "page_width", text="Width")
        col.prop(props, "page_height", text="Height")
        col.prop(props, "subdivisions")
        layout.separator()
        layout.label(text="Placement")
        _draw_placement(layout.box(), context, props, mod)
        layout.separator()
        layout.label(text="Transform")
        _draw_transform(layout.box(), context, props, mod)
        layout.separator()
        layout.label(text="Generation")
        box = layout.box()
        box.prop(props, "paper_texture", text="Paper Texture")
        if props.paper_texture == "CUSTOM":
            box.prop(props, "paper_texture_custom", text="Image")
        layout.operator("paper_generator.generate", text="Generate Pages", icon="MESH_PLANE")
        layout.separator()
        layout.label(text="Finalize")
        ready = bool(props.pages_object)
        layout.label(text="Ready to finalize" if ready else "Run Generate first",
                     icon="CHECKMARK" if ready else "INFO")
        col = layout.column()
        col.enabled = ready
        col.operator("paper_generator.finalize", text="Finalize Pages", icon="CHECKMARK")

_classes = (PaperGeneratorProperties, PaperGeneratorMainPanel)

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.paper_generator_properties = bpy.props.PointerProperty(type=PaperGeneratorProperties)

def unregister():
    for cls in _classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.paper_generator_properties