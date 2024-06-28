import os
import math
import struct
import itertools
import time
from pathlib import Path

from array import array

import bpy
from bpy_extras.io_utils import unpack_list, axis_conversion

from ..migoto_io.blender_interface.utility import *
from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.objects import *

from .buffers import VertexBuffer, IndexBuffer


class Fatal(Exception): pass


if bpy.app.version >= (2, 80):
    vertex_color_layer_channels = 4
else:
    vertex_color_layer_channels = 3


def load_3dmigoto_mesh_bin(operator, vb_paths, ib_paths, pose_path):
    if len(vb_paths) != 1 or len(ib_paths) > 1:
        raise Fatal('Cannot merge meshes loaded from binary files')

    # Loading from binary files, but still need to use the .txt files as a
    # reference for the format:
    vb_bin_path, vb_txt_path = vb_paths[0]
    ib_bin_path, ib_txt_path = ib_paths[0]

    vb = VertexBuffer(open(vb_txt_path, 'r'), load_vertices=False)
    vb.parse_vb_bin(open(vb_bin_path, 'rb'))

    ib = None
    if ib_paths:
        ib = IndexBuffer(open(ib_txt_path, 'r'), load_indices=False)
        ib.parse_ib_bin(open(ib_bin_path, 'rb'))

    return vb, ib, os.path.basename(vb_bin_path), pose_path


def load_3dmigoto_mesh(operator, paths):
    vb_paths, ib_paths, use_bin, pose_path = zip(*paths)
    pose_path = pose_path[0]

    if use_bin[0]:
        return load_3dmigoto_mesh_bin(operator, vb_paths, ib_paths, pose_path)

    vb = VertexBuffer(open(vb_paths[0], 'r'))
    # Merge additional vertex buffers for meshes split over multiple draw calls:
    for vb_path in vb_paths[1:]:
        tmp = VertexBuffer(open(vb_path, 'r'))
        vb.merge(tmp)

    # For quickly testing how importent any unsupported semantics may be:
    # vb.wipe_semantic_for_testing('POSITION.w', 1.0)
    # vb.wipe_semantic_for_testing('TEXCOORD.w', 0.0)
    # vb.wipe_semantic_for_testing('TEXCOORD5', 0)
    # vb.wipe_semantic_for_testing('BINORMAL')
    # vb.wipe_semantic_for_testing('TANGENT')
    # vb.write(open(os.path.join(os.path.dirname(vb_paths[0]), 'TEST.vb'), 'wb'), operator=operator)

    ib = None
    if ib_paths:
        ib = IndexBuffer(open(ib_paths[0], 'r'))
        # Merge additional vertex buffers for meshes split over multiple draw calls:
        for ib_path in ib_paths[1:]:
            tmp = IndexBuffer(open(ib_path, 'r'))
            ib.merge(tmp)

    return vb, ib, os.path.basename(vb_paths[0]), pose_path


def import_normals_step1(mesh, data, vertex_layers, translate_normal):
    # Ensure normals are 3-dimensional:
    # XXX: Assertion triggers in DOA6
    # if len(data[0]) == 4:
    #     if [x[3] for x in data] != [0.0]*len(data):
    #         #raise Fatal('Normals are 4D')
    #         # operator.report({'WARNING'}, 'Normals are 4D, storing W coordinate in NORMAL.w vertex layer. Beware that some types of edits on this mesh may be problematic.')
    #         vertex_layers['NORMAL.w'] = [[x[3]] for x in data]
    normals = [tuple(map(translate_normal, (x[0], x[1], x[2]))) for x in data]

    # To make sure the normals don't get lost by Blender's edit mode,
    # or mesh.update() we need to set custom normals in the loops, not
    # vertices.
    #
    # For testing, to make sure our normals are preserved let's use
    # garbage ones:
    #import random
    #normals = [(random.random() * 2 - 1,random.random() * 2 - 1,random.random() * 2 - 1) for x in normals]
    #
    # Comment from other import scripts:
    # Note: we store 'temp' normals in loops, since validate() may alter final mesh,
    #       we can only set custom lnors *after* calling it.
    mesh.create_normals_split()
    for l in mesh.loops:
        l.normal[:] = normals[l.vertex_index]


def import_normals_step2(mesh):
    # Taken from import_obj/import_fbx
    clnors = array('f', [0.0] * (len(mesh.loops) * 3))
    mesh.loops.foreach_get("normal", clnors)

    # Not sure this is still required with use_auto_smooth, but the other
    # importers do it, and at the very least it shouldn't hurt...
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))

    mesh.normals_split_custom_set(tuple(zip(*(iter(clnors),) * 3)))
    mesh.use_auto_smooth = True  # This has a double meaning, one of which is to use the custom normals
    # XXX CHECKME: show_edge_sharp moved in 2.80, but I can't actually
    # recall what it does and have a feeling it was unimportant:
    # mesh.show_edge_sharp = True


def import_vertex_groups(mesh, obj, blend_indices, blend_weights):
    assert (len(blend_indices) == len(blend_weights))
    if blend_indices:
        # We will need to make sure we re-export the same blend indices later -
        # that they haven't been renumbered. Not positive whether it is better
        # to use the vertex group index, vertex group name or attach some extra
        # data. Make sure the indices and names match:
        num_vertex_groups = max(itertools.chain(*itertools.chain(*blend_indices.values()))) + 1
        for i in range(num_vertex_groups):
            obj.vertex_groups.new(name=str(i))
        for vertex in mesh.vertices:
            for semantic_index in sorted(blend_indices.keys()):
                for i, w in zip(blend_indices[semantic_index][vertex.index],
                                blend_weights[semantic_index][vertex.index]):
                    if w == 0.0:
                        continue
                    obj.vertex_groups[i].add((vertex.index,), w, 'REPLACE')


def import_shapekeys(mesh, obj, shapekeys):
    if len(shapekeys.keys()) == 0:
        return
    
    # Add basis shapekey
    basis_shapekey = obj.shape_key_add(name='Basis')
    basis_shapekey.interpolation = 'KEY_LINEAR'

    # Set shapekeys to relative 'cause WuWa uses this type
    obj.data.shape_keys.use_relative = True

    # Import shapekeys
    for shapekey_id in shapekeys.keys():
        # Add new shapekey
        shapekey = obj.shape_key_add(name=f'Deform {shapekey_id}')
        shapekey.interpolation = 'KEY_LINEAR'

        # Apply shapekey vertex position offsets to each indexed vertex
        shapekey_data = shapekeys[shapekey_id]
        for vertex_id in range(len(obj.data.vertices)):
            position_offset = shapekey_data[vertex_id]
            shapekey.data[vertex_id].co.x += position_offset[0]
            shapekey.data[vertex_id].co.y += position_offset[1]
            shapekey.data[vertex_id].co.z += position_offset[2]


def import_uv_layers(mesh, obj, texcoords, flip_texcoord_v):
    for (texcoord, data) in sorted(texcoords.items()):
        # TEXCOORDS can have up to four components, but UVs can only have two
        # dimensions. Not positive of the best way to handle this in general,
        # but for now I'm thinking that splitting the TEXCOORD into two sets of
        # UV coordinates might work:
        dim = len(data[0])
        if dim == 4:
            components_list = ('xy', 'zw')
        elif dim == 2:
            components_list = ('xy',)
        else:
            raise Fatal('Unhandled TEXCOORD dimension: %i' % dim)
        cmap = {'x': 0, 'y': 1, 'z': 2, 'w': 3}

        for components in components_list:
            uv_name = 'TEXCOORD%s.%s' % (texcoord and texcoord or '', components)
            if hasattr(mesh, 'uv_textures'):  # 2.79
                mesh.uv_textures.new(uv_name)
            else:  # 2.80
                mesh.uv_layers.new(name=uv_name)
            blender_uvs = mesh.uv_layers[uv_name]

            # This will assign a texture to the UV layer, which works fine but
            # working out which texture maps to which UV layer is guesswork
            # before the import and the artist may as well just assign it
            # themselves in the UV editor pane when they can see the unwrapped
            # mesh to compare it with the dumped textures:
            #
            # path = textures.get(uv_layer, None)
            # if path is not None:
            #    image = load_image(path)
            #    for i in range(len(mesh.polygons)):
            #        mesh.uv_textures[uv_layer].data[i].image = image

            # Can't find an easy way to flip the display of V in Blender, so
            # add an option to flip it on import & export:
            if flip_texcoord_v:
                flip_uv = lambda uv: (uv[0], 1.0 - uv[1])
                # Record that V was flipped so we know to undo it when exporting:
                # obj['3DMigoto:' + uv_name] = {'flip_v': True}
            else:
                flip_uv = lambda uv: uv

            uvs = [[d[cmap[c]] for c in components] for d in data]
            for l in mesh.loops:
                blender_uvs.data[l.index].uv = flip_uv(uvs[l.vertex_index])


# This loads unknown data from the vertex buffers as vertex layers
def import_vertex_layers(mesh, obj, vertex_layers):
    for (element_name, data) in sorted(vertex_layers.items()):
        dim = len(data[0])
        cmap = {0: 'x', 1: 'y', 2: 'z', 3: 'w'}
        for component in range(dim):

            if dim != 1 or element_name.find('.') == -1:
                layer_name = '%s.%s' % (element_name, cmap[component])
            else:
                layer_name = element_name

            if type(data[0][0]) == int:
                mesh.vertex_layers_int.new(name=layer_name)
                layer = mesh.vertex_layers_int[layer_name]
                for v in mesh.vertices:
                    val = data[v.index][component]
                    # Blender integer layers are 32bit signed and will throw an
                    # exception if we are assigning an unsigned value that
                    # can't fit in that range. Reinterpret as signed if necessary:
                    if val < 0x80000000:
                        layer.data[v.index].value = val
                    else:
                        layer.data[v.index].value = struct.unpack('i', struct.pack('I', val))[0]
            elif type(data[0][0]) == float:
                mesh.vertex_layers_float.new(name=layer_name)
                layer = mesh.vertex_layers_float[layer_name]
                for v in mesh.vertices:
                    layer.data[v.index].value = data[v.index][component]
            else:
                raise Fatal('BUG: Bad layer type %s' % type(data[0][0]))


def import_faces_from_ib(mesh, ib):
    mesh.loops.add(len(ib.faces) * 3)
    mesh.polygons.add(len(ib.faces))
    mesh.loops.foreach_set('vertex_index', unpack_list(ib.faces))
    mesh.polygons.foreach_set('loop_start', [x * 3 for x in range(len(ib.faces))])
    mesh.polygons.foreach_set('loop_total', [3] * len(ib.faces))


def import_faces_from_vb(mesh, vb):
    # Only lightly tested
    num_faces = len(vb.vertices) // 3
    mesh.loops.add(num_faces * 3)
    mesh.polygons.add(num_faces)
    mesh.loops.foreach_set('vertex_index', [x for x in range(num_faces * 3)])
    mesh.polygons.foreach_set('loop_start', [x * 3 for x in range(num_faces)])
    mesh.polygons.foreach_set('loop_total', [3] * num_faces)


def normal_import_translation(elem, flip):
    unorm = elem.Format.endswith('_UNORM')
    if unorm:
        # Scale UNORM range 0:+1 to normal range -1:+1
        if flip:
            return lambda x: -(x*2.0 - 1.0)
        else:
            return lambda x: x*2.0 - 1.0
    if flip:
        return lambda x: -x
    else:
        return lambda x: x


def import_vertices(mesh, vb, flip_normal=False):
    mesh.vertices.add(len(vb.vertices))

    seen_offsets = set()
    blend_indices = {}
    blend_weights = {}
    texcoords = {}
    vertex_layers = {}
    use_normals = False
    shapekeys = {}

    for elem in vb.layout:
        if elem.InputSlotClass != 'per-vertex':
            continue

        # TODO: Allow poorly named semantics to map to other meanings to be
        # properly interpreted. This still needs to be added to the GUI, and
        # mapped back on export. Alternatively, you can alter the input
        # assembler layout format in the vb*.txt / *.fmt files prior to import.
        semantic_translations = {
            # 'ATTRIBUTE': 'POSITION', # UE4
        }
        translated_elem_name = semantic_translations.get(elem.name, elem.name)

        # Discard elements that reuse offsets in the vertex buffer, e.g. COLOR
        # and some TEXCOORDs may be aliases of POSITION:
        if (elem.InputSlot, elem.AlignedByteOffset) in seen_offsets:
            assert (translated_elem_name != 'POSITION')
            continue
        seen_offsets.add((elem.InputSlot, elem.AlignedByteOffset))

        data = tuple(x[elem.name] for x in vb.vertices)
        if translated_elem_name == 'POSITION':
            # Ensure positions are 3-dimensional:
            if len(data[0]) == 4:
                if ([x[3] for x in data] != [1.0] * len(data)):
                    # XXX: Leaving this fatal error in for now, as the meshes
                    # it triggers on in DOA6 (skirts) lie about almost every
                    # semantic and we cannot import them with this version of
                    # the script regardless. Comment it out if you want to try
                    # importing anyway and preserving the W coordinate in a
                    # vertex group. It might also be possible to project this
                    # back into 3D if we assume the coordinates are homogeneous
                    # (i.e. divide XYZ by W), but that might be assuming too
                    # much for a generic script.
                    raise Fatal('Positions are 4D')
                    # Occurs in some meshes in DOA6, such as skirts.
                    # W coordinate must be preserved in these cases.
                    print('Positions are 4D, storing W coordinate in POSITION.w vertex layer')
                    vertex_layers['POSITION.w'] = [[x[3]] for x in data]
            positions = [(x[0], x[1], x[2]) for x in data]
            mesh.vertices.foreach_set('co', unpack_list(positions))
        elif translated_elem_name.startswith('COLOR'):
            if len(data[0]) <= 3 or vertex_color_layer_channels == 4:
                # Either a monochrome/RGB layer, or Blender 2.80 which uses 4
                # channel layers
                mesh.vertex_colors.new(name=elem.name)
                color_layer = mesh.vertex_colors[elem.name].data
                c = vertex_color_layer_channels
                for l in mesh.loops:
                    color_layer[l.index].color = list(data[l.vertex_index]) + [0] * (c - len(data[l.vertex_index]))
            else:
                mesh.vertex_colors.new(name=elem.name + '.RGB')
                mesh.vertex_colors.new(name=elem.name + '.A')
                color_layer = mesh.vertex_colors[elem.name + '.RGB'].data
                alpha_layer = mesh.vertex_colors[elem.name + '.A'].data
                for l in mesh.loops:
                    color_layer[l.index].color = data[l.vertex_index][:3]
                    alpha_layer[l.index].color = [data[l.vertex_index][3], 0, 0]
        elif translated_elem_name == 'NORMAL':
            use_normals = True
            translate_normal = normal_import_translation(elem, flip_normal)
            import_normals_step1(mesh, data, vertex_layers, translate_normal)
        elif translated_elem_name in ('TANGENT', 'BINORMAL'):
            #    # XXX: loops.tangent is read only. Not positive how to handle
            #    # this, or if we should just calculate it when re-exporting.
            #    for l in mesh.loops:
            #        assert(data[l.vertex_index][3] in (1.0, -1.0))
            #        l.tangent[:] = data[l.vertex_index][0:3]
            # print('NOTICE: Skipping import of %s in favour of recalculating on export' % elem.name)
            pass
        elif translated_elem_name.startswith('BLENDINDICES'):
            # data = [[y & 255 for y in x] for x in data]
            blend_indices[elem.SemanticIndex] = data
        elif translated_elem_name.startswith('BLENDWEIGHT'):
            blend_weights[elem.SemanticIndex] = data
        elif translated_elem_name.startswith('TEXCOORD') and elem.is_float():
            texcoords[elem.SemanticIndex] = data
        elif translated_elem_name.startswith('SHAPEKEY') and elem.is_float():
            # if elem.SemanticIndex not in shapekeys:
            #     shapekeys[elem.SemanticIndex] = {}
            shapekeys[elem.SemanticIndex] = data

        else:
            print('NOTICE: Storing unhandled semantic %s %s as vertex layer' % (elem.name, elem.Format))
            vertex_layers[elem.name] = data

    return (blend_indices, blend_weights, texcoords, vertex_layers, use_normals, shapekeys)


def import_3dmigoto_vb_ib(operator, context, cfg, paths, flip_texcoord_v=True, axis_forward='-Y', axis_up='Z'):
    vb, ib, name, pose_path = load_3dmigoto_mesh(operator, paths)

    name = name.split('.')[0]

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(mesh.name, mesh)

    global_matrix = axis_conversion(from_forward=axis_forward, from_up=axis_up).to_4x4()
    obj.matrix_world = global_matrix

    # Attach the vertex buffer layout to the object for later exporting. Can't
    # seem to retrieve this if attached to the mesh - to_mesh() doesn't copy it:
    # obj['3DMigoto:VBLayout'] = vb.layout.serialise()
    # obj['3DMigoto:VBStride'] = vb.layout.stride  # FIXME: Strides of multiple vertex buffers
    # obj['3DMigoto:FirstVertex'] = vb.first

    if ib is not None:
        import_faces_from_ib(mesh, ib)
        # Attach the index buffer layout to the object for later exporting.
        # if ib.format == "DXGI_FORMAT_R16_UINT":
        #     obj['3DMigoto:IBFormat'] = "DXGI_FORMAT_R32_UINT"
        # else:
        #     obj['3DMigoto:IBFormat'] = ib.format
        # obj['3DMigoto:FirstIndex'] = ib.first
    else:
        import_faces_from_vb(mesh, vb)

    (blend_indices, blend_weights, texcoords, vertex_layers, use_normals, shapekeys) = import_vertices(mesh, vb, flip_normal=False)

    mesh.flip_normals()

    import_uv_layers(mesh, obj, texcoords, flip_texcoord_v)

    import_vertex_layers(mesh, obj, vertex_layers)

    import_vertex_groups(mesh, obj, blend_indices, blend_weights)

    import_shapekeys(mesh, obj, shapekeys)

    # Validate closes the loops so they don't disappear after edit mode and probably other important things:
    mesh.validate(verbose=False, clean_customdata=False)  # *Very* important to not remove lnors here!
    # Not actually sure update is necessary. It seems to update the vertex normals, not sure what else:
    mesh.update()

    # Must be done after validate step:
    if use_normals:
        import_normals_step2(mesh)
    else:
        mesh.calc_normals()

    return obj


def blender_import(operator, context, cfg):
    
    object_source_folder = resolve_path(cfg.object_source_folder)

    col = new_collection(object_source_folder.stem)

    for filename in os.listdir(object_source_folder):
        if not filename.endswith('fmt'):
            continue

        fmt_path = object_source_folder / filename
        ib_path = fmt_path.with_suffix('.ib')
        vb_path = fmt_path.with_suffix('.vb')

        obj = import_3dmigoto_vb_ib(operator, context, cfg, [((vb_path, fmt_path), (ib_path, fmt_path), True, None)])

        link_object_to_collection(obj, col)
    
        with OpenObject(context, obj, 'OBJECT'):

            # obj.rotation_euler[0] = math.radians(0)
            # obj.rotation_euler[2] = math.radians(180)

            if cfg.mirror_mesh:
                obj.scale = -0.01, 0.01, 0.01
            else:
                obj.scale = 0.01, 0.01, 0.01
