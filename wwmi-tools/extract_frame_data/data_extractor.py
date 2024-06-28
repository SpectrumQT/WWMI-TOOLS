
from dataclasses import dataclass, field
from typing import Union, List, Dict
from enum import Enum

from ..migoto_io.buffers.byte_buffer import ByteBuffer, IndexBuffer, BufferElementLayout, BufferSemantic, AbstractSemantic, Semantic
from ..migoto_io.dump_parser.log_parser import CallParameters
from ..migoto_io.dump_parser.filename_parser import ResourceDescriptor
from ..migoto_io.dump_parser.resource_collector import ShaderCallBranch


class PoseConstantBufferFormat(Enum):
    static = 1
    animated = 2


@dataclass(frozen=True)
class ShapeKeyData:
    shapekey_hash: str
    shapekey_scale_hash: str
    dispatch_y: int
    shapekey_offset_buffer: ByteBuffer
    shapekey_vertex_id_buffer: ByteBuffer
    shapekey_vertex_offset_buffer: ByteBuffer


@dataclass
class PoseData:
    vb_hash: str
    shapekey_hash: Union[str, None]
    cb_format: PoseConstantBufferFormat
    total_vertex_count: int
    dispatch_x: int
    position_buffer: ByteBuffer
    blend_buffer: ByteBuffer
    vector_buffer: ByteBuffer
    skeleton_data: ByteBuffer


@dataclass
class DrawData:
    ib_hash: str
    vb_hash: str
    vertex_offset: int
    vertex_count: int
    index_offset: int
    index_count: int
    index_buffer: IndexBuffer
    textures: List[ResourceDescriptor]
    color_buffer: ByteBuffer
    texcoord_buffer: ByteBuffer


@dataclass
class DataExtractor:
    # Input
    call_branches: Dict[str, ShaderCallBranch]
    # Output
    shader_hashes: Dict[str, str] = field(init=False)
    shape_key_data: Dict[str, ShapeKeyData] = field(init=False)
    pose_data: Dict[tuple, PoseData] = field(init=False)
    draw_data: Dict[tuple, DrawData] = field(init=False)

    def __post_init__(self):
        self.shader_hashes = {}
        self.shape_key_data = {}
        self.pose_data = {}
        self.draw_data = {}

        self.handle_shapekey_cs_0(list(self.call_branches.values()))
        self.handle_static_pose_cs(list(self.call_branches.values()))

    def handle_shapekey_cs_0(self, call_branches):
        for call_branch in call_branches:
            if call_branch.shader_id != 'SHAPEKEY_CS_0':
                continue
            for branch_call in call_branch.calls:
                self.verify_shader_hash(branch_call.call, call_branch.shader_id, 1)
            # We don't need any data from this call, lets go deeper
            self.handle_shapekey_cs_1(call_branch.nested_branches)

    def handle_shapekey_cs_1(self, call_branches):
        for call_branch in call_branches:
            if call_branch.shader_id != 'SHAPEKEY_CS_1':
                continue

            for branch_call in call_branch.calls:

                self.verify_shader_hash(branch_call.call, call_branch.shader_id, 1)

                shape_key_data = ShapeKeyData(
                    shapekey_hash=branch_call.resources['SHAPEKEY_OUTPUT'].hash,
                    shapekey_scale_hash=branch_call.resources['SHAPEKEY_SCALE_OUTPUT'].hash,
                    dispatch_y=branch_call.call.parameters[CallParameters.Dispatch].ThreadGroupCountY,
                    shapekey_offset_buffer=branch_call.resources['SHAPEKEY_OFFSET_BUFFER'],
                    shapekey_vertex_id_buffer=branch_call.resources['SHAPEKEY_VERTEX_ID_BUFFER'],
                    shapekey_vertex_offset_buffer=branch_call.resources['SHAPEKEY_VERTEX_OFFSET_BUFFER'],
                )

                cached_shape_key_data = self.shape_key_data.get(shape_key_data.shapekey_hash, None)

                if cached_shape_key_data is None:
                    self.shape_key_data[shape_key_data.shapekey_hash] = shape_key_data
                else:
                    if shape_key_data.dispatch_y != cached_shape_key_data.dispatch_y:
                        raise ValueError(f'dispatch params mismatch for SHAPEKEY_CS_1')

            self.handle_shapekey_cs_2(call_branch.nested_branches)

    def handle_shapekey_cs_2(self, call_branches):
        for call_branch in call_branches:
            if call_branch.shader_id != 'SHAPEKEY_CS_2':
                continue
            for branch_call in call_branch.calls:
                self.verify_shader_hash(branch_call.call, call_branch.shader_id, 1)
            # We don't need any data from this call as well, lets go deeper
            self.handle_animated_pose_cs(call_branch.nested_branches)

    def handle_animated_pose_cs(self, call_branches):
        for call_branch in call_branches:
            if call_branch.shader_id == 'ANIMATED_POSE_CS':
                self.handle_pose_cs_branch(call_branch)

    def handle_static_pose_cs(self, call_branches):
        for call_branch in call_branches:
            if call_branch.shader_id == 'STATIC_POSE_CS':
                self.handle_pose_cs_branch(call_branch)

    def handle_pose_cs_branch(self, call_branch):
        for branch_call in call_branch.calls:

            cb_format, vertex_offset, vertex_count = self.read_pose_cs_cb(branch_call.resources['POSE_CB'])

            if call_branch.shader_id == 'ANIMATED_POSE_CS':
                pose_cs_cb_format = PoseConstantBufferFormat.animated
                shapekey_hash = branch_call.resources['SHAPEKEY_INPUT'].hash
            else:
                pose_cs_cb_format = PoseConstantBufferFormat.static
                shapekey_hash = None

            # Skip ANIMATED_POSE_CS calls that were misidentified as STATIC_POSE_CS calls due to same IO pattern
            if pose_cs_cb_format == PoseConstantBufferFormat.static and cb_format == PoseConstantBufferFormat.animated:
                continue

            # Skip STATIC_POSE_CS calls that were misidentified as ANIMATED_POSE_CS calls due to same IO pattern
            # if pose_cs_cb_format == PoseConstantBufferFormat.animated and cb_format == PoseConstantBufferFormat.static:
            #     continue

            if cb_format != pose_cs_cb_format:
                raise ValueError(f'CB format mismatch for {call_branch.shader_id} call {branch_call}')

            self.verify_shader_hash(branch_call.call, call_branch.shader_id, 1)

            position_buffer = branch_call.resources['POSITION_BUFFER']
            blend_buffer = branch_call.resources['BLEND_BUFFER']
            vector_buffer = branch_call.resources['VECTOR_BUFFER']

            if blend_buffer.num_elements != position_buffer.num_elements:
                raise ValueError(f'BLEND_BUFFER size must match POSITION_BUFFER!')
            if vector_buffer.num_elements != position_buffer.num_elements:
                raise ValueError(f'VECTOR_BUFFER size must match POSITION_BUFFER!')

            pose_data = PoseData(
                cb_format=cb_format,
                total_vertex_count=position_buffer.num_elements,
                vb_hash=branch_call.resources['POSE_OUTPUT'].hash,
                shapekey_hash=shapekey_hash,
                dispatch_x=branch_call.call.parameters[CallParameters.Dispatch].ThreadGroupCountX,
                position_buffer=position_buffer.get_fragment(vertex_offset, vertex_count),
                blend_buffer=blend_buffer.get_fragment(vertex_offset, vertex_count),
                vector_buffer=vector_buffer.get_fragment(vertex_offset, vertex_count),
                skeleton_data=branch_call.resources['SKELETON_DATA'],
            )

            draw_guid = (vertex_offset, vertex_count, pose_data.vb_hash)

            cached_pose_data = self.pose_data.get(draw_guid, None)

            if cached_pose_data is None:
                self.pose_data[draw_guid] = pose_data
            else:
                if pose_data.dispatch_x != cached_pose_data.dispatch_x:
                    raise ValueError(f'dispatch params mismatch for ANIMATED_POSE_CS')
                # else:
                #     print('duplicate')

        self.handle_draw_vs(call_branch.nested_branches)

    def handle_draw_vs(self, call_branches):
        for call_branch in call_branches:

            if call_branch.shader_id != 'DRAW_VS':
                continue

            for branch_call in call_branch.calls:

                index_buffer = branch_call.resources['IB_BUFFER_TXT']
                vb_hash = branch_call.resources['POSE_INPUT_1'].hash

                vertex_indices = [x for y in index_buffer.faces for x in y]
                vertex_offset = min(vertex_indices)
                vertex_count = max(vertex_indices) - vertex_offset + 1

                draw_guid = (vertex_offset, vertex_count, vb_hash)

                cached_pose_data = self.pose_data.get(draw_guid, None)

                if cached_pose_data is None:
                    continue

                color_buffer = branch_call.resources['COLOR_BUFFER']
                if color_buffer.num_elements == cached_pose_data.total_vertex_count:
                    color_buffer = color_buffer.get_fragment(vertex_offset, vertex_count)
                else:
                    color_buffer = None

                texcoord_buffer = branch_call.resources['TEXCOORD_BUFFER']
                if texcoord_buffer.num_elements == cached_pose_data.total_vertex_count:
                    texcoord_buffer = texcoord_buffer.get_fragment(vertex_offset, vertex_count)
                else:
                    texcoord_buffer = None

                textures = []
                for texture_id in range(16):
                    texture = branch_call.resources.get(f'TEXTURE_{texture_id}', None)
                    if texture is not None:
                        textures.append(texture)

                draw_data = DrawData(
                    ib_hash=branch_call.resources['IB_BUFFER'].hash,
                    vb_hash=branch_call.resources['POSE_INPUT_0'].hash,
                    vertex_offset=vertex_offset,
                    vertex_count=vertex_count,
                    index_offset=branch_call.call.parameters[CallParameters.DrawIndexed].StartIndexLocation,
                    index_count=branch_call.call.parameters[CallParameters.DrawIndexed].IndexCount,
                    index_buffer=index_buffer,
                    color_buffer=color_buffer,
                    texcoord_buffer=texcoord_buffer,
                    textures=textures,
                )

                cached_draw_data = self.draw_data.get(draw_guid, None)

                if cached_draw_data is None:
                    self.draw_data[draw_guid] = draw_data
                else:
                    if index_buffer.num_elements != cached_draw_data.index_buffer.num_elements:
                        raise ValueError(f'index data mismatch for DRAW_VS')

                    if color_buffer is not None:
                        cached_draw_data.color_buffer = color_buffer

                    if texcoord_buffer is not None:
                        cached_draw_data.texcoord_buffer = texcoord_buffer

                    cached_draw_data.textures.extend(textures)

    def verify_shader_hash(self, call, shader_id, max_call_shaders):
        if len(call.shaders) != max_call_shaders:
            raise ValueError(f'number of associated shaders for {shader_id} call should be equal to {max_call_shaders}!')
        cached_shader_hash = self.shader_hashes.get(shader_id, None)
        call_shader_hash = next(iter(call.shaders.values())).hash
        if cached_shader_hash is None:
            self.shader_hashes[shader_id] = call_shader_hash
        elif cached_shader_hash != call_shader_hash:
            raise ValueError(f'inconsistent shader hash {cached_shader_hash} for {shader_id}')

    @staticmethod
    def read_pose_cs_cb(cb):
        cb_0 = cb.get_element(0).get_value(AbstractSemantic(Semantic.RawData, 0))
        cb_1 = cb.get_element(1).get_value(AbstractSemantic(Semantic.RawData, 0))

        offset = cb_0[2]

        # For all pose shaders following must be true:
        #  1. cb[0].y == cb[0].z
        if offset != cb_0[1]:
            raise ValueError(f'Unknown cb format!')

        doubled_offset = offset * 2
        # For Pose CS without ShapeKey cb following must be true:
        #  1. cb[0].y * 2 == cb[1].x
        if doubled_offset == cb_1[0]:
            vertex_count = cb_0[3]
            cb_format = PoseConstantBufferFormat.static
        # For Pose CS with ShapeKey cb following must be true:
        #  1. cb[0].y * 2 == cb[1].y
        elif doubled_offset == cb_1[1]:
            vertex_count = cb_1[0]
            cb_format = PoseConstantBufferFormat.animated
        # Exit if failed to detect format
        else:
            raise ValueError(f'Unknown cb format!')

        return cb_format, offset, vertex_count
