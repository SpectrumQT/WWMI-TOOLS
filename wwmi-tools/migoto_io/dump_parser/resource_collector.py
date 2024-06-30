import time

from typing import Union, List, Dict
from dataclasses import dataclass

from ..buffers.byte_buffer import ByteBuffer, BufferElementLayout, IndexBuffer

from .filename_parser import SlotType, ShaderType, SlotId, ResourceDescriptor

from .calls_collector import ShaderMap, Slot, CallsCollector, ShaderCallBranch


@dataclass
class Source:
    shader_id: str
    shader_type: ShaderType
    slot_type: SlotType
    slot_id: SlotId = None
    file_ext: str = None
    ignore_missing: bool = False


@dataclass
class DataMap:
    sources: List[Source]
    layout: BufferElementLayout = None


@dataclass
class ResourceCollector:
    shader_resources: Dict[str, DataMap]
    call_branches: Dict[str, ShaderCallBranch] = None
    cache: Dict[str, Union[ByteBuffer, IndexBuffer]] = None

    def __post_init__(self):
        self.cache = {}
        for shader_id, shader_call_branch in self.call_branches.items():
            self.collect_branch_data(shader_id, shader_call_branch)

    def collect_branch_data(self, shader_id, shader_call_branch):
        for branch_call in shader_call_branch.calls:
            for resource_tag, data_map in self.shader_resources.items():
                for source in data_map.sources:
                    if source.shader_id == shader_id:
                        self.collect_branch_call_resource(branch_call, resource_tag, source, data_map.layout)
        for nested_branch in shader_call_branch.nested_branches:
            self.collect_branch_data(nested_branch.shader_id, nested_branch)

    def collect_branch_call_resource(self, branch_call, resource_tag, source, layout):

        filter_attributes = {
            'slot_type': source.slot_type,
        }
        if source.slot_id is not None:
            filter_attributes['slot_id'] = source.slot_id
        if source.shader_type != ShaderType.Empty:
            filter_attributes['slot_shader_type'] = source.shader_type

        resource = branch_call.call.get_filtered_resource(filter_attributes)

        if resource is None:
            if source.ignore_missing:
                layout = None
            else:
                raise ValueError(f'Failed to locate required resource {resource_tag} at {source} in call {branch_call.call}!')

        if layout is not None:

            # Contents of .buf IB isn't always accurate, so it can make sense to use .txt instead
            if source.slot_type == SlotType.IndexBuffer and source.file_ext == 'txt':
                txt_path = resource.path.replace('.buf', '.txt')
                resource = ResourceDescriptor(txt_path)

            resource_hash = resource.get_sha256()

            cached_resource = self.cache.get(resource_hash, None)

            if cached_resource is None:
                if source.slot_type == SlotType.IndexBuffer and source.file_ext == 'txt':
                    with open(resource.path, 'r') as f:
                        resource = IndexBuffer(layout, f)
                else:
                    resource = ByteBuffer(layout, resource.get_bytes())

                self.cache[resource_hash] = resource
            else:
                resource = cached_resource

        if branch_call.resources is None:
            branch_call.resources = {}

        branch_call.resources[resource_tag] = resource

    # def run(self):
    #     shapekey_resources = self.get_shapekey_resources()
    #     self.resources = CollectedResources(
    #         ShapeKey=shapekey_resources,
    #         Pose=self.get_pose_resources(shapekey_resources),
    #         Draw=self.get_draw_resources(),
    #     )
    #
    # def get_shapekey_resources(self):
    #     call = self.calls.ShapeKey
    #     return ShapeKeyResources(
    #         Config=call.get_filtered_resource({
    #             'slot_shader_type': ShaderType.Compute,
    #             'slot_type': SlotType.ConstantBuffer,
    #             'slot_id': SlotId(0),
    #         }),
    #         Output=call.get_filtered_resource({
    #             'slot_type': SlotType.UAV,
    #             'slot_id': SlotId(0),
    #         }),
    #         VertexIds=call.get_filtered_resource({
    #             'slot_shader_type': ShaderType.Compute,
    #             'slot_type': SlotType.Texture,
    #             'slot_id': SlotId(0),
    #         }),
    #         VertexOffsets=call.get_filtered_resource({
    #             'slot_shader_type': ShaderType.Compute,
    #             'slot_type': SlotType.Texture,
    #             'slot_id': SlotId(1),
    #         }),
    #     )
    #
    # def get_pose_resources(self, shapekey_resources):
    #     pose_resources = []
    #     for call in self.calls.Pose.values():
    #         if len(call.shaders) != 1:
    #             raise ValueError(f'Failed to process Pose CS call: expected 1 linked shader, got {len(call.shaders)}')
    #         shader_hash = next(iter(call.shaders))
    #
    #         shapekey_input = call.get_filtered_resource({
    #             'hash': shapekey_resources.Output.hash,
    #         })
    #         shapekey_slot_id_offset = 0 if shapekey_input is None else 1
    #
    #         pose_resources.append(PoseResources(
    #             Config=call.get_filtered_resource({
    #                 'slot_shader_type': ShaderType.Compute,
    #                 'slot_type': SlotType.ConstantBuffer,
    #                 'slot_id': SlotId(0),
    #             }),
    #             VB=call.get_filtered_resource({
    #                 'slot_type': SlotType.UAV,
    #                 'slot_id': SlotId(1),
    #             }),
    #             Blends=call.get_filtered_resource({
    #                 'slot_shader_type': ShaderType.Compute,
    #                 'slot_type': SlotType.Texture,
    #                 'slot_id': SlotId(3 + shapekey_slot_id_offset),
    #             }),
    #             Normals=call.get_filtered_resource({
    #                 'slot_shader_type': ShaderType.Compute,
    #                 'slot_type': SlotType.Texture,
    #                 'slot_id': SlotId(4 + shapekey_slot_id_offset),
    #             }),
    #             Positions=call.get_filtered_resource({
    #                 'slot_shader_type': ShaderType.Compute,
    #                 'slot_type': SlotType.Texture,
    #                 'slot_id': SlotId(5 + shapekey_slot_id_offset),
    #             }),
    #         ))
    #
    #     return pose_resources
    #
    # def get_draw_resources(self):
    #     draw_resources = []
    #
    #     for call in self.calls.Draw.values():
    #         textures = []
    #         for i in range(16):
    #             textures.append(call.get_filtered_resource({
    #                 'slot_shader_type': ShaderType.Pixel,
    #                 'slot_type': SlotType.Texture,
    #                 'slot_id': SlotId(i),
    #             }))
    #
    #         hash_ib = call.get_filtered_resource({
    #             'ext': 'buf',
    #             'slot_type': SlotType.IndexBuffer,
    #         })
    #
    #         txt_ib_path = hash_ib.path.replace('.buf', '.txt')
    #         if os.path.exists(txt_ib_path):
    #             data_ib = ResourceDescriptor(txt_ib_path)
    #         else:
    #             raise ValueError(f'Failed to find .txt version of IB: {txt_ib_path}')
    #
    #         draw_resources.append(DrawResources(
    #             VB=call.get_filtered_resource({
    #                 'slot_type': SlotType.VertexBuffer,
    #                 'slot_id': SlotId(0),
    #             }),
    #             HashIB=hash_ib,
    #             DataIB=data_ib,
    #             Texcoords=call.get_filtered_resource({
    #                 'ext': 'buf',
    #                 'slot_shader_type': ShaderType.Vertex,
    #                 'slot_type': SlotType.Texture,
    #                 'slot_id': SlotId(0),
    #             }),
    #             Colors=call.get_filtered_resource({
    #                 'ext': 'buf',
    #                 'slot_shader_type': ShaderType.Vertex,
    #                 'slot_type': SlotType.Texture,
    #                 'slot_id': SlotId(2),
    #             }),
    #             Textures=textures,
    #         ))
    #
    #     return draw_resources

