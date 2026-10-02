import bpy

MODIFIER_NAME = "PaperGenerator"
SCATTER_OVERSHOOT = 1.1
VOLUME_OVERSHOOT = 2.0
VOLUME_VOXEL_AMOUNT = 48

_MENU_LABELS = {
    "COUNT": "Count",
    "VOXEL_AMOUNT": "Amount",
    "DENSITY_RANDOM": "Random",
    "ALL": "All",
    "RANDOM": "Random",
    "POINT": "Point",
    "FACE": "Face",
    "FLOAT": "Float",
}

def _socket(iface, name, socket_type, in_out="INPUT", default=None, min_val=None):
    s = iface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    if default is not None:
        s.default_value = default
    if min_val is not None and hasattr(s, "min_value"):
        s.min_value = min_val
    return s

def _set_prop(node, attr, value):
    if hasattr(node, attr):
        setattr(node, attr, value)
        return
    sock = node.inputs.get(attr.replace("_", " ").title())
    label = _MENU_LABELS.get(value)
    if sock is not None and label is not None:
        try:
            sock.default_value = label
            return
        except (TypeError, ValueError):
            pass
    print(f"Paper Generator: could not set {attr}={value} on {node.bl_idname}, using the node default")

def _set_input(modifier, identifier, value):
    props = getattr(modifier, "properties", None)
    inputs = getattr(props, "inputs", None)
    if inputs is None:
        modifier[identifier] = value
        return
    entry = getattr(inputs, identifier, None)
    if entry is None:
        bpy.context.view_layer.update()
        entry = getattr(modifier.properties.inputs, identifier, None)
    if entry is None:
        print(f"Paper Generator: modifier input {identifier} not found")
        return
    entry.value = value

def _node(nodes, nm, key, node_type, location, **props):
    n = nodes.new(node_type)
    n.location = location
    for attr, val in props.items():
        _set_prop(n, attr, val)
    nm[key] = n
    return n

def _math(nodes, nm, key, loc, op, val_b=None):
    n = _node(nodes, nm, key, "ShaderNodeMath", loc, operation=op)
    if val_b is not None:
        n.inputs[1].default_value = val_b
    return n

def _page_socket_specs(page_count, page_width, page_height,
        base_offset, max_random_offset, base_rotation, max_random_rotation):
    return (
        ("page_count", "Page Count", "NodeSocketInt", page_count),
        ("page_width", "Page Width", "NodeSocketFloat", page_width),
        ("page_height", "Page Height", "NodeSocketFloat", page_height),
        ("base_offset_x", "Base Offset X", "NodeSocketFloat", base_offset[0]),
        ("base_offset_y", "Base Offset Y", "NodeSocketFloat", base_offset[1]),
        ("base_offset_z", "Base Offset Z", "NodeSocketFloat", base_offset[2]),
        ("max_rand_offset_x", "Max Random Offset X", "NodeSocketFloat", max_random_offset[0], 0.0),
        ("max_rand_offset_y", "Max Random Offset Y", "NodeSocketFloat", max_random_offset[1], 0.0),
        ("max_rand_offset_z", "Max Random Offset Z", "NodeSocketFloat", max_random_offset[2], 0.0),
        ("base_rotation_x", "Base Rotation X", "NodeSocketFloat", base_rotation[0]),
        ("base_rotation_y", "Base Rotation Y", "NodeSocketFloat", base_rotation[1]),
        ("base_rotation_z", "Base Rotation Z", "NodeSocketFloat", base_rotation[2]),
        ("max_rand_rot_x", "Max Random Rot X", "NodeSocketFloat", max_random_rotation[0], 0.0),
        ("max_rand_rot_y", "Max Random Rot Y", "NodeSocketFloat", max_random_rotation[1], 0.0),
        ("max_rand_rot_z", "Max Random Rot Z", "NodeSocketFloat", max_random_rotation[2], 0.0),
    )

def _page_sockets(iface, page_count, page_width, page_height,
        base_offset, max_random_offset, base_rotation, max_random_rotation):
    s = {}
    for spec in _page_socket_specs(page_count, page_width, page_height,
            base_offset, max_random_offset, base_rotation, max_random_rotation):
        key, label, socket_type, default = spec[:4]
        min_val = spec[4] if len(spec) > 4 else None
        s[key] = _socket(iface, label, socket_type, default=default, min_val=min_val)
    return s

def _apply_page_sockets(modifier, s, page_count, page_width, page_height,
        base_offset, max_random_offset, base_rotation, max_random_rotation):
    for spec in _page_socket_specs(page_count, page_width, page_height,
            base_offset, max_random_offset, base_rotation, max_random_rotation):
        key, val = spec[0], spec[3]
        _set_input(modifier, s[key].identifier, val)

def _new_tree(obj, *, with_input=False):
    mod = obj.modifiers.new(name=MODIFIER_NAME, type="NODES")
    tree = bpy.data.node_groups.new(f"{MODIFIER_NAME}_{obj.name}", "GeometryNodeTree")
    mod.node_group = tree
    iface = tree.interface
    _socket(iface, "Geometry", "NodeSocketGeometry", in_out="OUTPUT")
    if with_input:
        _socket(iface, "Geometry", "NodeSocketGeometry", in_out="INPUT")
    nodes, links, nm = tree.nodes, tree.links, {}
    inp = _node(nodes, nm, "input", "NodeGroupInput", (-800, 0))
    out = _node(nodes, nm, "output", "NodeGroupOutput", (1000, 0))
    return mod, iface, nodes, links, nm, inp, out

def _subsurf(obj, levels):
    if levels <= 0:
        return
    sub = obj.modifiers.new(name="Subdivision", type="SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels = sub.render_levels = levels

def _transform_labels(kind):
    match kind:
        case "offset":
            return "Base Offset", "Max Random Offset"
        case _:
            return "Base Rotation", "Max Random Rot"

def _axis_random(nodes, nm, links, inp, axis, prefix, x, y, seed):
    neg = _math(nodes, nm, f"neg_{prefix}_{axis}", (x, y), "MULTIPLY", -1.0)
    rnd = _node(nodes, nm, f"rnd_{prefix}_{axis}", "FunctionNodeRandomValue",
        (x + 180, y), data_type="FLOAT")
    rnd.inputs["Seed"].default_value = seed
    axis_label = axis.upper()
    links.new(inp.outputs[f"{prefix} {axis_label}"], neg.inputs[0])
    links.new(neg.outputs["Value"], rnd.inputs["Min"])
    links.new(inp.outputs[f"{prefix} {axis_label}"], rnd.inputs["Max"])
    return rnd.outputs["Value"]

def _combine_transform(nodes, nm, links, inp, kind, x, y, seed_base):
    base_label, rand_label = _transform_labels(kind)
    rnd_xyz = _node(nodes, nm, f"rnd_{kind}", "ShaderNodeCombineXYZ", (x + 360, y - 70))
    base_xyz = _node(nodes, nm, f"base_{kind}", "ShaderNodeCombineXYZ", (x + 360, y - 240))
    for i, axis in enumerate("XYZ"):
        links.new(_axis_random(nodes, nm, links, inp, axis, rand_label, x, y - i * 140, seed_base + i),
                  rnd_xyz.inputs[axis])
        links.new(inp.outputs[f"{base_label} {axis}"], base_xyz.inputs[axis])
    combine = _node(nodes, nm, f"{kind}", "ShaderNodeVectorMath", (x + 540, y - 140), operation="ADD")
    links.new(base_xyz.outputs["Vector"], combine.inputs[0])
    links.new(rnd_xyz.outputs["Vector"], combine.inputs[1])
    return combine.outputs["Vector"]

def _transform(nodes, nm, links, inp, x=300, y=500):
    return (
        _combine_transform(nodes, nm, links, inp, "offset", x, y, 0),
        _combine_transform(nodes, nm, links, inp, "rotation", x, y - 460, 10),
    )

def _instance_pages(nodes, nm, links, inp, out, points, offset, rotation):
    grid = _node(nodes, nm, "grid", "GeometryNodeMeshGrid", (100, -300))
    grid.inputs["Vertices X"].default_value = 2
    grid.inputs["Vertices Y"].default_value = 2
    links.new(inp.outputs["Page Width"], grid.inputs["Size X"])
    links.new(inp.outputs["Page Height"], grid.inputs["Size Y"])
    _node(nodes, nm, "instance", "GeometryNodeInstanceOnPoints", (900, 200))
    _node(nodes, nm, "translate", "GeometryNodeTranslateInstances", (950, 200))
    _node(nodes, nm, "realize", "GeometryNodeRealizeInstances", (980, 200))
    links.new(points, nm["instance"].inputs["Points"])
    links.new(grid.outputs["Mesh"], nm["instance"].inputs["Instance"])
    links.new(rotation, nm["instance"].inputs["Rotation"])
    links.new(nm["instance"].outputs["Instances"], nm["translate"].inputs["Instances"])
    links.new(offset, nm["translate"].inputs["Translation"])
    links.new(nm["translate"].outputs["Instances"], nm["realize"].inputs["Geometry"])
    links.new(nm["realize"].outputs["Geometry"], out.inputs["Geometry"])

def _trim_to_count(nodes, nm, links, inp, points):
    idx = _node(nodes, nm, "index", "GeometryNodeInputIndex", (-250, 0))
    rnd = _node(nodes, nm, "rnd", "FunctionNodeRandomValue", (-250, -150), data_type="FLOAT")
    srt = _node(nodes, nm, "sort", "GeometryNodeSortElements", (-150, 200))
    _set_prop(srt, "domain", "POINT")
    inv = _math(nodes, nm, "invert", (100, 0), "SUBTRACT", None)
    inv.inputs[0].default_value = 1.0
    delete = _node(nodes, nm, "delete", "GeometryNodeDeleteGeometry", (100, 200))
    _set_prop(delete, "domain", "POINT")
    _set_prop(delete, "mode", "ALL")
    less = _math(nodes, nm, "less_than", (-50, 0), "LESS_THAN")
    links.new(points, srt.inputs["Geometry"])
    links.new(idx.outputs["Index"], rnd.inputs["ID"])
    links.new(rnd.outputs["Value"], srt.inputs["Sort Weight"])
    links.new(srt.outputs["Geometry"], delete.inputs["Geometry"])
    links.new(idx.outputs["Index"], less.inputs[0])
    links.new(inp.outputs["Page Count"], less.inputs[1])
    links.new(less.outputs["Value"], inv.inputs[1])
    links.new(inv.outputs["Value"], delete.inputs["Selection"])
    return delete.outputs["Geometry"]

def _point_count(nodes, nm, links, points, x=-520):
    one = _node(nodes, nm, "one", "ShaderNodeValue", (x, -50))
    one.outputs[0].default_value = 1.0
    stat = _node(nodes, nm, "count_stat", "GeometryNodeAttributeStatistic", (x, 50))
    _set_prop(stat, "data_type", "FLOAT")
    _set_prop(stat, "domain", "POINT")
    links.new(points, stat.inputs["Geometry"])
    links.new(one.outputs[0], stat.inputs["Attribute"])
    return stat.outputs["Sum"]

def _density_from_count(nodes, nm, links, inp, count_sock, overshoot, x=-360):
    mul = _math(nodes, nm, "overshoot", (x - 160, 200), "MULTIPLY", overshoot)
    div = _math(nodes, nm, "density", (x, 200), "DIVIDE")
    floor = _math(nodes, nm, "count_floor", (x, 50), "MAXIMUM", 1.0)
    links.new(inp.outputs["Page Count"], mul.inputs[0])
    links.new(count_sock, floor.inputs[0])
    links.new(mul.outputs["Value"], div.inputs[0])
    links.new(floor.outputs["Value"], div.inputs[1])
    return div.outputs["Value"]

def _scatter_faces(nodes, nm, links, inp, mesh_sock):
    area = _node(nodes, nm, "face_area", "GeometryNodeInputMeshFaceArea", (-900, 200))
    stat = _node(nodes, nm, "area_stat", "GeometryNodeAttributeStatistic", (-900, 50))
    _set_prop(stat, "data_type", "FLOAT")
    _set_prop(stat, "domain", "FACE")
    links.new(mesh_sock, stat.inputs["Geometry"])
    links.new(area.outputs["Area"], stat.inputs["Attribute"])
    density = _density_from_count(nodes, nm, links, inp, stat.outputs["Sum"], SCATTER_OVERSHOOT)
    dist = _node(nodes, nm, "distribute", "GeometryNodeDistributePointsOnFaces", (-500, 200))
    _set_prop(dist, "distribute_method", "RANDOM")
    links.new(density, dist.inputs["Density"])
    links.new(mesh_sock, dist.inputs["Mesh"])
    return dist.outputs["Points"]

def _mesh_to_volume(nodes, nm, links, mesh_sock):
    m2v = _node(nodes, nm, "mesh_to_vol", "GeometryNodeMeshToVolume", (-900, 200))
    _set_prop(m2v, "resolution_mode", "VOXEL_AMOUNT")
    m2v.inputs["Voxel Amount"].default_value = VOLUME_VOXEL_AMOUNT
    links.new(mesh_sock, m2v.inputs["Mesh"])
    return m2v.outputs["Volume"]

def _scatter_volume(nodes, nm, links, inp, mesh_sock):
    volume = _mesh_to_volume(nodes, nm, links, mesh_sock)
    probe = _node(nodes, nm, "dist_probe", "GeometryNodeDistributePointsInVolume", (-700, 200))
    _set_prop(probe, "mode", "DENSITY_RANDOM")
    probe.inputs["Density"].default_value = 1.0
    links.new(volume, probe.inputs["Volume"])
    count = _point_count(nodes, nm, links, probe.outputs["Points"])
    density = _density_from_count(nodes, nm, links, inp, count, VOLUME_OVERSHOOT)
    dist = _node(nodes, nm, "distribute", "GeometryNodeDistributePointsInVolume", (-200, 200))
    _set_prop(dist, "mode", "DENSITY_RANDOM")
    links.new(density, dist.inputs["Density"])
    links.new(volume, dist.inputs["Volume"])
    return dist.outputs["Points"]

def _scatter_fn(distribution):
    return _scatter_volume if distribution == "volume" else _scatter_faces

def _build_shape(obj, distribution, page_count, page_width, page_height, subdivisions,
        base_offset, max_random_offset, base_rotation, max_random_rotation):
    mod, iface, nodes, links, nm, inp, out = _new_tree(obj, with_input=True)
    s = _page_sockets(iface, page_count, page_width, page_height,
        base_offset, max_random_offset, base_rotation, max_random_rotation)
    scatter = _scatter_fn(distribution)
    points = _trim_to_count(nodes, nm, links, inp,
        scatter(nodes, nm, links, inp, inp.outputs["Geometry"]))
    offset, rotation = _transform(nodes, nm, links, inp)
    _instance_pages(nodes, nm, links, inp, out, points, offset, rotation)
    _apply_page_sockets(mod, s, page_count, page_width, page_height,
        base_offset, max_random_offset, base_rotation, max_random_rotation)
    _subsurf(obj, subdivisions)
    return mod

def build_shape_faces(obj, **kw):
    return _build_shape(obj, "faces", **kw)

def build_shape_volume(obj, **kw):
    return _build_shape(obj, "volume", **kw)

SHAPE_BUILDERS = {"faces": build_shape_faces, "volume": build_shape_volume}

def build_curve(pages_object, curve_object, page_count, page_width, page_height,
        spacing, subdivisions, align_to_curve,
        base_offset, max_random_offset, base_rotation, max_random_rotation):
    mod, iface, nodes, links, nm, inp, out = _new_tree(pages_object)
    s = {
        "curve_object": _socket(iface, "Curve Object", "NodeSocketObject"),
        "spacing": _socket(iface, "Spacing", "NodeSocketFloat", default=spacing),
        "align_to_curve": _socket(iface, "Align to Curve", "NodeSocketBool", default=align_to_curve),
    }
    s.update(_page_sockets(iface, page_count, page_width, page_height,
        base_offset, max_random_offset, base_rotation, max_random_rotation))
    _node(nodes, nm, "obj_info", "GeometryNodeObjectInfo", (-900, 200), transform_space="RELATIVE")
    _node(nodes, nm, "resample", "GeometryNodeResampleCurve", (-600, 200), mode="COUNT")
    _node(nodes, nm, "crv_pts", "GeometryNodeCurveToPoints", (-300, 200), mode="EVALUATED")
    sw = _node(nodes, nm, "sw_rot", "GeometryNodeSwitch", (-300, 400), input_type="VECTOR")
    rot_add = _node(nodes, nm, "rot_add", "ShaderNodeVectorMath", (750, 350), operation="ADD")
    offset, rotation = _transform(nodes, nm, links, inp, x=100, y=500)
    links.new(inp.outputs["Curve Object"], nm["obj_info"].inputs["Object"])
    links.new(nm["obj_info"].outputs["Geometry"], nm["resample"].inputs["Curve"])
    links.new(inp.outputs["Page Count"], nm["resample"].inputs["Count"])
    links.new(nm["resample"].outputs["Curve"], nm["crv_pts"].inputs["Curve"])
    links.new(inp.outputs["Align to Curve"], sw.inputs["Switch"])
    links.new(nm["crv_pts"].outputs["Rotation"], sw.inputs["True"])
    links.new(sw.outputs["Output"], rot_add.inputs[0])
    links.new(rotation, rot_add.inputs[1])
    _instance_pages(nodes, nm, links, inp, out,
        nm["crv_pts"].outputs["Points"], offset, rot_add.outputs["Vector"])
    _set_input(mod, s["curve_object"].identifier, curve_object)
    _set_input(mod, s["spacing"].identifier, spacing)
    _set_input(mod, s["align_to_curve"].identifier, align_to_curve)
    _apply_page_sockets(mod, s, page_count, page_width, page_height,
        base_offset, max_random_offset, base_rotation, max_random_rotation)
    _subsurf(pages_object, subdivisions)
    return mod