import os
import bpy

_ADDON_DIR = os.path.dirname(os.path.realpath(__file__))
_PAPER_TEXTURE_DIR = os.path.join(_ADDON_DIR, "paper_textures")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

PRESET_NAMES = {
    "WRINKLED": "wrinkled",
    "TEXTURED": "textured",
}

def _find_image(base_name):
    for ext in IMAGE_EXTENSIONS:
        path = os.path.join(_PAPER_TEXTURE_DIR, base_name + ext)
        if os.path.isfile(path):
            return path
    if not os.path.isdir(_PAPER_TEXTURE_DIR):
        return None
    for file in os.listdir(_PAPER_TEXTURE_DIR):
        stem, ext = os.path.splitext(file)
        if ext.lower() not in IMAGE_EXTENSIONS:
            continue
        if stem.lower() != base_name.lower():
            continue
        return os.path.join(_PAPER_TEXTURE_DIR, file)
    return None

def _load_image(path):
    name = f"PaperGenerator_{os.path.basename(path)}"
    image = bpy.data.images.get(name)
    if not image:
        return bpy.data.images.load(path, check_existing=False)
    image.filepath = bpy.path.abspath(path)
    image.reload()
    return image

def resolve_paper_texture(mode, custom_path=""):
    match mode:
        case "NONE":
            return None
        case "CUSTOM":
            path = bpy.path.abspath(custom_path)
            return _load_image(path) if os.path.isfile(path) else None
        case preset_mode:
            preset = PRESET_NAMES.get(preset_mode)
            if not preset:
                return None
            path = _find_image(preset)
            return _load_image(path) if path else None

def preset_label(mode):
    match mode:
        case "CUSTOM":
            return "custom"
        case _:
            return PRESET_NAMES.get(mode, mode.lower())
