import bpy
import bmesh
import math

SEGMENTS = 32

class PlacementShape:
    label: str = ""
    distribution: str = "faces"

    def build_mesh(self, base_name, collection, width, length, height=1.0):
        raise NotImplementedError

class FaceShape(PlacementShape):
    distribution = "faces"

class VolumeShape(PlacementShape):
    distribution = "volume"

class AlongCurveShape(PlacementShape):
    label = "Along Curve"

    def build_mesh(self, *args, **kwargs):
        raise NotImplementedError

def _link_mesh(base_name, collection, bm):
    mesh = bpy.data.meshes.new(f"{base_name}_shape")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"{base_name}_shape", mesh)
    collection.objects.link(obj)
    return obj

def _face_from_verts(base_name, collection, verts):
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(v) for v in verts])
    return _link_mesh(base_name, collection, bm)

def _primitive(base_name, collection, scale, builder):
    bm = bmesh.new()
    builder(bm)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    return _link_mesh(base_name, collection, bm)

class TriangleShape(FaceShape):
    label = "Triangle"

    def build_mesh(self, base_name, collection, width, length, height=1.0):
        hw, hl = width * 0.5, length * 0.5
        return _face_from_verts(base_name, collection, [
            (0.0, hl, 0.0), (-hw, -hl, 0.0), (hw, -hl, 0.0),
        ])

class RectangleShape(FaceShape):
    label = "Rectangle"

    def build_mesh(self, base_name, collection, width, length, height=1.0):
        hw, hl = width * 0.5, length * 0.5
        return _face_from_verts(base_name, collection, [
            (-hw, -hl, 0.0), (hw, -hl, 0.0), (hw, hl, 0.0), (-hw, hl, 0.0),
        ])

class DiskShape(FaceShape):
    label = "Disk"

    def build_mesh(self, base_name, collection, width, length, height=1.0):
        bm = bmesh.new()
        hw, hl = width * 0.5, length * 0.5
        center = bm.verts.new((0.0, 0.0, 0.0))
        rim = [
            bm.verts.new((hw * math.cos(2 * math.pi * i / SEGMENTS),
                          hl * math.sin(2 * math.pi * i / SEGMENTS), 0.0))
            for i in range(SEGMENTS)
        ]
        for i in range(SEGMENTS):
            bm.faces.new([center, rim[i], rim[(i + 1) % SEGMENTS]])
        return _link_mesh(base_name, collection, bm)

class CubeShape(VolumeShape):
    label = "Cube"

    def build_mesh(self, base_name, collection, width, length, height=1.0):
        return _primitive(base_name, collection, (width, length, height),
            lambda bm: bmesh.ops.create_cube(bm, size=1.0))

class SphereShape(VolumeShape):
    label = "Sphere"

    def build_mesh(self, base_name, collection, width, length, height=1.0):
        return _primitive(base_name, collection, (width, length, height),
            lambda bm: bmesh.ops.create_uvsphere(
                bm, u_segments=SEGMENTS, v_segments=SEGMENTS // 2, radius=0.5))

class CylinderShape(VolumeShape):
    label = "Cylinder"

    def build_mesh(self, base_name, collection, width, length, height=1.0):
        return _primitive(base_name, collection, (width, length, height),
            lambda bm: bmesh.ops.create_cone(
                bm, cap_ends=True, cap_tris=False, segments=SEGMENTS,
                radius1=0.5, radius2=0.5, depth=1.0))

_ALL_SHAPES = (
    AlongCurveShape(),
    TriangleShape(),
    RectangleShape(),
    DiskShape(),
    CubeShape(),
    SphereShape(),
    CylinderShape(),
)

SHAPE_MAP = {shape.label.upper(): shape for shape in _ALL_SHAPES}

def shape_enum_items():
    return [(shape.label.upper(), shape.label, "") for shape in _ALL_SHAPES]
