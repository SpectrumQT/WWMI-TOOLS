import json
import time
import shutil

from types import LambdaType
from typing import List, Dict, Union
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from ..migoto_io.blender_interface.utility import *
from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.objects import *
from ..migoto_io.blender_interface.mesh import *

from ..migoto_io.buffers.dxgi_format import DXGIFormat
from ..migoto_io.buffers.byte_buffer import ByteBuffer, BufferElementLayout, BufferSemantic, AbstractSemantic, Semantic

from ..extract_frame_data.metadata_format import read_metadata

from .object_merger import ObjectMerger, SkeletonType
from .metadata_collector import Version, ModInfo
from .texture_collector import Texture, get_textures
from .ini_maker import IniMaker, is_ini_edited


class Fatal(Exception): pass


def translate_vectors(dxgi_format, flip):
    if dxgi_format.get_format().endswith('_UNORM'):
        # Scale normal range -1:+1 to UNORM range 0:+1
        if flip:
            return lambda x: -x/2.0 + 0.5
        else:
            return lambda x: x/2.0 + 0.5
    if flip:
        return lambda x: -x
    else:
        return lambda x: x


def normalize_weights(weights):
    '''
    Noramlizes provided list of float weights in a 8-bit friendly way 
    Returns list of 8-bit integers (0-255) with sum of 255
    '''
    total = sum(weights)

    if total == 0:
        return weights

    precision_error = 255

    tickets = [0] * len(weights)

    for idx, weight in enumerate(weights):
        # Ignore zero weight
        if weight == 0:
            continue
        weight = weight / total * 255
        # Ignore weight below minimal precision (1/255)
        if weight < 1:
            weights[idx] = 0
            continue
        # Strip float part from the weight
        int_weight = int(weight)
        weights[idx] = int_weight
        # Reduce precision_error by the integer weight value
        precision_error -= int_weight
        # Calculate weight 'significance' index to prioritize lower weights with float loss
        tickets[idx] = 255 / weight * (weight - int_weight)

    while precision_error > 0:
        ticket = max(tickets)
        if ticket > 0:
            # Route `1` from precision_error to weights with non-zero ticket value first
            i = tickets.index(ticket)
            tickets[i] = 0
        else:
            # Route remaining precision_error to highest weight to reduce its impact
            i = weights.index(max(weights))
        # Distribute `1` from precision_error
        weights[i] += 1
        precision_error -= 1

    return weights


@dataclass
class DataMap:
    LoopDataConverters: OrderedDict[AbstractSemantic, Union[LambdaType, None]]
    VertexDataConverters: OrderedDict[AbstractSemantic, Union[LambdaType, None]]
    IndexBuffer: Dict[str, List[BufferSemantic]]
    VertexBuffers: Dict[str, List[BufferSemantic]]
    ShapeKeyBuffers: Dict[str, List[BufferSemantic]]


def get_default_data_map():
    return DataMap(
        LoopDataConverters=OrderedDict({
            AbstractSemantic(Semantic.VertexId): None,
            AbstractSemantic(Semantic.Tangent): lambda data: data + (1.0,),
            AbstractSemantic(Semantic.Normal): lambda data: data,
            AbstractSemantic(Semantic.Color, 0): None,
            AbstractSemantic(Semantic.TexCoord, 0): lambda uv: (uv[0], 1.0 - uv[1]),
            AbstractSemantic(Semantic.Color, 1): lambda data: data[0:2],
            AbstractSemantic(Semantic.TexCoord, 1): lambda uv: (uv[0], 1.0 - uv[1]),
            AbstractSemantic(Semantic.TexCoord, 2): lambda uv: (uv[0], 1.0 - uv[1]),
        }),
        VertexDataConverters=OrderedDict({
            AbstractSemantic(Semantic.Position): None,
            AbstractSemantic(Semantic.Blendindices): lambda data: data[0:4] + [0] * (4 - len(data)),
            AbstractSemantic(Semantic.Blendweight): lambda data: normalize_weights(data[0:4]) + [0] * (4 - len(data)),
        }),
        IndexBuffer={
            'Index': [
                BufferSemantic(AbstractSemantic(Semantic.Index), DXGIFormat.R32_UINT, stride=12)
            ]},
        VertexBuffers={
            'Position': [
                BufferSemantic(AbstractSemantic(Semantic.Position, 0), DXGIFormat.R32G32B32_FLOAT)
            ],
            'Blend': [
                BufferSemantic(AbstractSemantic(Semantic.Blendindices, 0), DXGIFormat.R8_UINT, stride=4),
                BufferSemantic(AbstractSemantic(Semantic.Blendweight, 0), DXGIFormat.R8_UINT, stride=4),
            ],
            'Vector': [
                BufferSemantic(AbstractSemantic(Semantic.Tangent, 0), DXGIFormat.R8G8B8A8_SNORM),
                BufferSemantic(AbstractSemantic(Semantic.Normal, 0), DXGIFormat.R8G8B8A8_SNORM),
            ],
            'Color': [
                BufferSemantic(AbstractSemantic(Semantic.Color, 0), DXGIFormat.R8G8B8A8_UNORM),
            ],
            'TexCoord': [
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 0), DXGIFormat.R16G16_FLOAT),
                BufferSemantic(AbstractSemantic(Semantic.Color, 1), DXGIFormat.R16G16_UNORM),
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 1), DXGIFormat.R16G16_FLOAT),
                BufferSemantic(AbstractSemantic(Semantic.TexCoord, 2), DXGIFormat.R16G16_FLOAT),
            ],
        },
        ShapeKeyBuffers={
            'ShapeKeyOffset': [
                BufferSemantic(AbstractSemantic(Semantic.RawData), DXGIFormat.R32G32B32A32_UINT),
            ],
            'ShapeKeyVertexId': [
                BufferSemantic(AbstractSemantic(Semantic.RawData), DXGIFormat.R32_UINT),
            ],
            'ShapeKeyVertexOffset': [
                BufferSemantic(AbstractSemantic(Semantic.RawData, 0), DXGIFormat.R16_FLOAT),
            ],
        },
    )


def extract_semantic_data(data_map, loop_data, vertex_data):

    loop_data_converters = list(data_map.LoopDataConverters.items())
    vertex_data_converters = list(data_map.VertexDataConverters.items())

    vertex_cache = {}
    for semantic in data_map.LoopDataConverters.keys():
        vertex_cache[semantic] = []
    for semantic in data_map.VertexDataConverters.keys():
        vertex_cache[semantic] = []

    handle_mesh_vertex_data = len(vertex_data) > 0

    for loop_vertex_data in loop_data:

        vertex_id = loop_vertex_data[0]

        for i in range(1, len(loop_data_converters)):
            semantic, data_converter = loop_data_converters[i]
            if data_converter is None:
                vertex_cache[semantic].extend(loop_vertex_data[i])
            else:
                vertex_cache[semantic].extend(data_converter(loop_vertex_data[i]))

        if handle_mesh_vertex_data:

            mesh_vertex_data = vertex_data[vertex_id]

            for i in range(len(vertex_data_converters)):
                semantic, data_converter = vertex_data_converters[i]
                if data_converter is None:
                    vertex_cache[semantic].extend(mesh_vertex_data[i])
                else:
                    vertex_cache[semantic].extend(data_converter(mesh_vertex_data[i]))

    return vertex_cache


def get_mesh_data(context, mesh, data_map, collection):
    loop_data_converters = data_map.LoopDataConverters.keys()

    partial_export = len(data_map.LoopDataConverters) == 0
    if partial_export:
        if collection != context.scene.wwmi_tools_settings.loop_data_cached_collection:
            context.scene.wwmi_tools_settings.loop_data_cache = ''
        if len(context.scene.wwmi_tools_settings.loop_data_cache) == 0:
            loop_data_converters = get_default_data_map().LoopDataConverters.keys()
    else:
        context.scene.wwmi_tools_settings.loop_data_cache = ''

    faces, loop_data, vertex_data = fetch_mesh_data(mesh, loop_data_converters, data_map.VertexDataConverters.keys())
    
    if partial_export:
        if len(context.scene.wwmi_tools_settings.loop_data_cache) == 0:
            context.scene.wwmi_tools_settings.loop_data_cache = json.dumps(loop_data)
            context.scene.wwmi_tools_settings.loop_data_cached_collection = collection
        elif len(loop_data) == 0:
            loop_data = json.loads(context.scene.wwmi_tools_settings.loop_data_cache)

    vertex_cache = extract_semantic_data(data_map, loop_data, vertex_data)
    
    return faces, loop_data, vertex_cache


def extract_shapekey_data(loop_data, shapekeys, shapekey_data):

    shapekey_cache = {shapekey_id: {} for shapekey_id, _ in shapekeys}

    for vb_position_id, loop_vertex_data in enumerate(loop_data):

        vertex_id = loop_vertex_data[0]

        vertex_shapekey_data = shapekey_data.get(vertex_id, None)
        if vertex_shapekey_data is not None:
            for shapekey_id, vertex_offsets in vertex_shapekey_data.items():
                shapekey_cache[shapekey_id][vb_position_id] = vertex_offsets

    shapekey_offsets = []
    shapekey_vertex_ids = []
    shapekey_vertex_offsets = []

    shapekey_verts_count = 0
    for group_id in range(128):

        shapekey = shapekey_cache.get(group_id, None)
        if shapekey is None or len(shapekey_cache[group_id]) == 0:
            shapekey_offsets.extend([shapekey_verts_count if shapekey_verts_count != 0 else 0])
            continue

        shapekey_offsets.extend([shapekey_verts_count])

        for vertex_id, vertex_offsets in shapekey.items():
            shapekey_vertex_ids.extend([vertex_id])
            shapekey_vertex_offsets.extend(vertex_offsets + [0, 0, 0])
            shapekey_verts_count += 1

    return shapekey_offsets, shapekey_vertex_ids, shapekey_vertex_offsets


def get_shapekey_data(obj, mesh, data_map, loop_data):    
    shapekey_offsets, shapekey_vertex_ids, shapekey_vertex_offsets = None, None, None

    if len(data_map.ShapeKeyBuffers) > 0 and obj.data.shape_keys is not None:
        shapekeys, shapekey_data = fetch_shapekey_data(obj, mesh)
        shapekey_offsets, shapekey_vertex_ids, shapekey_vertex_offsets = extract_shapekey_data(loop_data, shapekeys, shapekey_data)
   
    return shapekey_offsets, shapekey_vertex_ids, shapekey_vertex_offsets


def build_buffers(data_map, vertex_count, faces, vertex_cache, shapekey_offsets, shapekey_vertex_ids, shapekey_vertex_offsets):
    buffers = {}

    # Build Index Buffer
    if len(data_map.IndexBuffer) > 0:
        index_buffer = ByteBuffer(BufferElementLayout(data_map.IndexBuffer['Index']))
        index_buffer.extend(len(faces))
        index_buffer.set_values(AbstractSemantic(Semantic.Index), faces) 
        buffers['Index'] = index_buffer

    # Build Vertex Buffers
    for name, semantics in data_map.VertexBuffers.items():
        vertex_buffer = ByteBuffer(BufferElementLayout(semantics))
        vertex_buffer.extend(vertex_count)
        for semantic in vertex_buffer.layout.semantics:
            vertex_buffer.set_values(semantic.semantic, vertex_cache[semantic.semantic])
        buffers[name] = vertex_buffer

    # Build Shape Key Buffers
    if len(data_map.ShapeKeyBuffers) > 0 and shapekey_offsets is not None and len(shapekey_vertex_ids) > 0:
        shapekey_offset_buffer = ByteBuffer(BufferElementLayout(data_map.ShapeKeyBuffers['ShapeKeyOffset']))
        shapekey_offset_buffer.extend(128)
        shapekey_offset_buffer.set_values(AbstractSemantic(Semantic.RawData), shapekey_offsets)
        buffers['ShapeKeyOffset'] = shapekey_offset_buffer

        shapekey_vertex_id_buffer = ByteBuffer(BufferElementLayout(data_map.ShapeKeyBuffers['ShapeKeyVertexId']))
        shapekey_vertex_id_buffer.extend(len(shapekey_vertex_ids))
        shapekey_vertex_id_buffer.set_values(AbstractSemantic(Semantic.RawData), shapekey_vertex_ids)
        buffers['ShapeKeyVertexId'] = shapekey_vertex_id_buffer

        shapekey_vertex_offset_buffer = ByteBuffer(BufferElementLayout(data_map.ShapeKeyBuffers['ShapeKeyVertexOffset']))
        shapekey_vertex_offset_buffer.extend(len(shapekey_vertex_ids))
        shapekey_vertex_offset_buffer.set_values(AbstractSemantic(Semantic.RawData, 0), shapekey_vertex_offsets)
        buffers['ShapeKeyVertexOffset'] = shapekey_vertex_offset_buffer

    return buffers


def blender_export(operator, context, cfg, data_map):
        
    start_time = time.time()

    user_context = get_user_context(context)

    object_source_folder = resolve_path(cfg.object_source_folder)
    mod_output_folder = resolve_path(cfg.mod_output_folder)
    meshes_path = mod_output_folder / 'Meshes'
    meshes_path.mkdir(parents=True, exist_ok=True)
    textures_path = mod_output_folder / 'Textures'
    textures_path.mkdir(parents=True, exist_ok=True)
    local_mod_logo_path = textures_path / 'Logo.dds'

    extracted_object = read_metadata(object_source_folder / 'Metadata.json')

    # Prepare merged temp object

    object_merger = ObjectMerger(
        extracted_object=extracted_object,
        ignore_hidden_objects=cfg.ignore_hidden_objects,
        ignore_muted_shape_keys=cfg.ignore_muted_shape_keys,
        apply_modifiers=cfg.apply_all_modifiers,
        context=context,
        collection=cfg.component_collection,
        skeleton_type=SkeletonType.Merged if cfg.mod_skeleton_type == 'MERGED' else SkeletonType.PerComponent,
    )
    merged_object = object_merger.merged_object
    obj = merged_object.object
    mesh = merged_object.mesh

    # Collect merged temp object data
    faces, loop_data, vertex_data = get_mesh_data(context, mesh, data_map, cfg.component_collection)

    shapekey_offsets, shapekey_vertex_ids, shapekey_vertex_offsets = get_shapekey_data(obj, mesh, data_map, loop_data)
    merged_object.shapekeys.vertex_count = len(shapekey_vertex_ids) if shapekey_vertex_ids is not None else 0

    vertex_count = len(loop_data)

    buffers = build_buffers(data_map, vertex_count, faces, vertex_data, shapekey_offsets, shapekey_vertex_ids, shapekey_vertex_offsets)

    # Write output

    if not cfg.partial_export:
        mod_logo_path = resolve_path(cfg.mod_logo)
        if mod_logo_path.is_file():
            shutil.copy(mod_logo_path, local_mod_logo_path)
    
    if not cfg.partial_export:
        textures = get_textures(object_source_folder)

    if cfg.write_ini and not cfg.partial_export:

        ini_path = mod_output_folder / 'mod.ini'

        if ini_path.is_file() and is_ini_edited(ini_path):
            timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
            ini_path.rename(ini_path.with_name(f'{ini_path.name} {timestamp}.BAK'))

        ini_maker = IniMaker(
            mod_info=ModInfo(
                wwmi_tools_version=Version(cfg.wwmi_tools_version),
                required_wwmi_version=Version(cfg.required_wwmi_version),
                mod_name=cfg.mod_name,
                mod_author=cfg.mod_author,
                mod_desc=cfg.mod_desc,
                mod_link=cfg.mod_link,
                mod_logo=local_mod_logo_path,
            ),
            extracted_object=extracted_object,
            merged_object=merged_object,
            output_vertex_count=vertex_count,
            buffers=buffers,
            textures=textures,
            comment_code=cfg.comment_ini,
            skeleton_scale=cfg.skeleton_scale,
            unrestricted_custom_shape_keys=cfg.unrestricted_custom_shape_keys,
        )

        with open(ini_path, "w") as f:
            f.write(ini_maker.build())

    if cfg.copy_textures and not cfg.partial_export:
        for texture in textures:
            texture_path = textures_path / texture.filename
            if texture_path.is_file():
                continue
            shutil.copy(texture.path, texture_path)

    for buffer_name, buffer in buffers.items():
        with open(meshes_path / f'{buffer_name}.buf', "wb") as f:
            f.write(buffer.get_bytes())

    if cfg.remove_temp_object:
        remove_object(obj)
        
    set_user_context(context, user_context)

    print(f"Execution time: %f" % (time.time() - start_time))


