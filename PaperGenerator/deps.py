import bpy
import importlib
import subprocess
import sys

_pymupdf_installed = False

def _libs_dir():
    return bpy.utils.user_resource("SCRIPTS", path="modules", create=True)

def _ensure_on_path():
    libs = _libs_dir()
    if libs not in sys.path:
        sys.path.append(libs)

def is_pymupdf_available():
    return _pymupdf_installed

def check_dependencies():
    global _pymupdf_installed
    _ensure_on_path()
    importlib.invalidate_caches()
    try:
        importlib.import_module("fitz")
        _pymupdf_installed = True
    except ImportError:
        _pymupdf_installed = False
    return _pymupdf_installed

def install_dependencies():
    _ensure_on_path()
    python = sys.executable
    subprocess.run([python, "-m", "ensurepip", "--upgrade"],
                   capture_output=True, text=True)
    try:
        subprocess.run(
            [python, "-m", "pip", "install", "--upgrade",
             "--only-binary=:all:", "--target", _libs_dir(), "pymupdf"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        print("Paper Generator: dependency install failed")
        print(e.stdout)
        print(e.stderr)
        return False
    return check_dependencies()

class PaperGeneratorInstallDepsOperator(bpy.types.Operator):
    bl_idname = "paper_generator.install_deps"
    bl_label = "Install Dependencies"

    def execute(self, context):
        ok = install_dependencies()
        self.report(
            {"INFO"} if ok else {"ERROR"},
            "PyMuPDF installed" if ok
            else "Installation failed, check the system console",
        )
        return {"FINISHED"}

_classes = (PaperGeneratorInstallDepsOperator,)

def register():
    check_dependencies()
    for cls in _classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in _classes:
        bpy.utils.unregister_class(cls)