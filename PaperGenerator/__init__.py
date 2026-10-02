bl_info = {
    "name": "Paper Generator",
    "author": "Nick Morse",
    "version": (1, 0, 1),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Paper Generator",
    "description": "Generate paper meshes from PDFs or image folders",
    "category": "Object",
}

import bpy
from . import deps, ui, pipeline

def register():
    deps.register()
    ui.register()
    pipeline.register()

def unregister():
    pipeline.unregister()
    ui.unregister()
    deps.unregister()
