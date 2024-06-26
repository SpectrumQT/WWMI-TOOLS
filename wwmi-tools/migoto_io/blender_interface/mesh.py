import collections
import re

from typing import List

import bmesh

from ..buffers.byte_buffer import AbstractSemantic, Semantic


def mesh_triangulate(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()


loop_data_getters_template = {
    Semantic.VertexId: lambda semantic: lambda loop, color, texcoord: loop.vertex_index,
    Semantic.Tangent: lambda semantic: lambda loop, color, texcoord: tuple(loop.tangent),
    Semantic.Normal: lambda semantic: lambda loop, color, texcoord: tuple(loop.normal) + (loop.bitangent_sign,),
    Semantic.Color: lambda semantic: lambda loop, color, texcoord: tuple(color[semantic.get_name()].color),
    Semantic.TexCoord: lambda semantic: lambda loop, color, texcoord: tuple(texcoord[semantic.get_name()]),
}


vertex_data_getters_template = {
    Semantic.Position: lambda semantic: lambda vertex, vertex_groups: vertex.undeformed_co,
    Semantic.Blendindices: lambda semantic: lambda vertex, vertex_groups: [vg.group for vg in vertex_groups],
    Semantic.Blendweight: lambda semantic: lambda vertex, vertex_groups: [vg.weight for vg in vertex_groups],
}


def get_data_getters(semantics: List[AbstractSemantic], data_getters_template):
    data_getters = []
    for semantic in semantics:
        data_getter = data_getters_template.get(semantic.semantic, None)
        if data_getter is None:
            continue
        data_getters.append(data_getter(semantic))
    return data_getters


def fetch_mesh_data(mesh, loop_semantics: List[AbstractSemantic], vertex_semantics: List[AbstractSemantic]):
    # Mesh Vertex is object that defines spatial parameters of point in the point cloud of a model, such as:
    #   1. Coordinates in 3-dimensional space (Position)
    #   2. Position Misplacement (Weights and Shapekeys)
    # Mesh Polygon is object that defines faces that form the surface of a model:
    #   1. Face consists of corners (Loops) 
    # Mesh Loop is object that defines point properties that are specific for given face, such as:
    #   1. Link to Mesh Vertex (Mesh Vertex Id)
    #   2. Color attributes (Vertex Color, UV coords)
    #   3. Vector attributes (Normal, Tangent)
    #
    # In terms of export, VB vertex is a point with unique set of attributes (position, normal, texcoord, etc)
    # With data structure mentioned above, we should use 2 data sources:
    #   1. Loops (mesh.polygons): each unique set of Loop attributes would define new VB vertex
    #   2. Vertices (mesh.vertices): it's gonna be a shared pool of VB vertex position data

    faces = []
    loop_data = collections.OrderedDict()
    loop_data_getters = get_data_getters(loop_semantics, loop_data_getters_template)

    if len(loop_data_getters) > 1:
        for face in mesh.polygons:

            for loop in mesh.loops[face.loop_start:face.loop_start+face.loop_total]:

                texcoords = {}
                for uv_layer in mesh.uv_layers:
                    texcoords[uv_layer.name] = uv_layer.data[loop.index].uv

                colors = {}
                for color in mesh.vertex_colors:
                    colors[color.name] = color.data[loop.index]

                # Fetch requested loop attributes
                data = [data_getter(loop, colors, texcoords) for data_getter in loop_data_getters]

                # Insert loop data to dict and get its index
                # If loop data is NOT found in dict, it'll return index of new entry via len(loop_data)
                # If loop data is found in dict, it'll return its index
                vb_vertex_index = loop_data.setdefault(tuple(data), len(loop_data))

                # Register VB index as face corner in faces cache, for triangles we'll append 3 indices per face
                faces.append(vb_vertex_index)

    loop_data = list(loop_data.keys())

    vertex_data = []
    vertex_data_getters = get_data_getters(vertex_semantics, vertex_data_getters_template)

    if len(vertex_data_getters) > 0:
        for vertex in mesh.vertices:

            vertex_groups = sorted(vertex.groups, key=lambda x: x.weight, reverse=True)

            # Fetch requested vertex attributes
            data = []
            for data_getter in vertex_data_getters:
                data.append(data_getter(vertex, vertex_groups))

            # Insert vertex data to list, its indices will be equal to Mesh Vertex Ids
            vertex_data.append(data)

    return faces, loop_data, vertex_data


def fetch_shapekey_data(obj, mesh):
    base_data = obj.data.shape_keys.key_blocks['Basis'].data
    shapekey_pattern = re.compile(r'.*(?:deform|custom)[_ -]*(\d+).*')

    shapekeys = []
    for shapekey in obj.data.shape_keys.key_blocks:
        match = shapekey_pattern.findall(shapekey.name.lower())
        if len(match) == 0:
            continue
        shapekey_id = int(match[0])
        shapekeys.append((shapekey_id, shapekey))

    shapekey_data = {}
    for vertex_id in range(len(mesh.vertices)):
        base_vertex_coords = base_data[vertex_id].co
        shapekey_data[vertex_id] = {}
        for (shapekey_id, shapekey) in shapekeys:
            shapekey_vertex_coords = shapekey.data[vertex_id].co
            vertex_offset = shapekey_vertex_coords - base_vertex_coords
            if vertex_offset.length < 0.00000001:
                continue
            shapekey_data[vertex_id][shapekey_id] = list(vertex_offset)

    return shapekeys, shapekey_data
