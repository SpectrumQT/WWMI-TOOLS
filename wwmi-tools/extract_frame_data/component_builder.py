import logging
import copy

from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path

from ..migoto_io.buffers.byte_buffer import ByteBuffer, IndexBuffer, BufferElementLayout, BufferSemantic, AbstractSemantic, Semantic
from ..migoto_io.dump_parser.filename_parser import ResourceDescriptor

from .data_extractor import ShapeKeyData, PoseData, DrawData
from .shapekey_builder import ShapeKeys

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
logging.basicConfig(level=logging.DEBUG, format='%(message)s')


@dataclass()
class MeshComponent:
    ib_hash: str
    vb_hash: str
    sk_hash: str
    dispatch_x: int
    vertex_offset: int
    vertex_count: int
    index_offset: int
    index_count: int
    vg_offset: int
    vg_count: int
    index_buffer: IndexBuffer
    vertex_buffer: ByteBuffer
    skeleton_buffer: ByteBuffer
    textures: Dict[str, List[ResourceDescriptor]]


@dataclass()
class MeshComponentData:
    pose_data: PoseData
    draw_data: DrawData


@dataclass()
class MeshObject:
    ib_hash: str = None
    vb0_hash: str = None
    vb1_hash: str = None
    vertex_count: int = 0
    index_count: int = 0
    shapekey_hash: str = None
    components_data: List[MeshComponentData] = field(init=False)
    shapekey_data: ShapeKeys = field(init=False)
    components: List[MeshComponent] = field(init=False)
    
    def __post_init__(self):
        self.components_data = []
        self.components = []

    def verify(self):
        vb0_hashes = set([component.draw_data.vb_hash for component in self.components_data])
        if len(vb0_hashes) > 1:
            raise ValueError(f'components VB0 hash mismatch for object %s (hashes: %s)' % (
                self.vb0_hash, ', '.join(vb0_hashes)))
        self.vb0_hash = list(vb0_hashes)[0]

        vb1_hashes = set([component.pose_data.vb_hash for component in self.components_data])
        if len(vb1_hashes) > 1:
            raise ValueError(f'components VB1 hash mismatch for object %s (hashes: %s)' % (
                self.vb0_hash, ', '.join(vb1_hashes)))
        self.vb1_hash = list(vb1_hashes)[0]

        ib_hashes = set([component.draw_data.ib_hash for component in self.components_data])
        if len(ib_hashes) > 1:
            raise ValueError(f'components IB hash mismatch for object %s (hashes: %s)' % (
                self.vb0_hash, ', '.join(ib_hashes)))
        self.ib_hash = list(ib_hashes)[0]

    def import_component_data(self, pose_data: PoseData, draw_data: DrawData):
        self.components_data.append(MeshComponentData(
            pose_data=pose_data,
            draw_data=draw_data,
        ))
        
    def build_components(self, vb_layout: BufferElementLayout, shapekeys: Dict[str, ShapeKeys]):
        self.verify()
        self.components_data.sort(key=lambda data: data.draw_data.vertex_offset, reverse=False)
        self.import_shapekey_data(shapekeys)
        for component_data in self.components_data:
            component = self.build_component(component_data.pose_data, component_data.draw_data, vb_layout)
            self.vertex_count += component.vertex_count
            self.index_count += component.index_count
            self.components.append(component)
        self.merge_vertex_groups()

    def import_shapekey_data(self, shapekeys: Dict[str, ShapeKeys]):
        """
        Imports shapekeys data based on hash and ensures its uniqueness
        """
        for component_data in self.components_data:
            if component_data.pose_data.shapekey_hash is not None:
                if self.shapekey_hash is None:
                    self.shapekey_hash = component_data.pose_data.shapekey_hash
                elif self.shapekey_hash != component_data.pose_data.shapekey_hash:
                    raise ValueError(f'shapekeys data hash mismatch between components of object %s (%s != %s)' % (
                        self.vb0_hash, self.shapekey_hash, component_data.pose_data.shapekey_hash
                    ))
        self.shapekey_data = shapekeys.get(self.shapekey_hash, None)
        if self.shapekey_data is None:
            raise ValueError(f'no shapekey data %s found for object %s' % (self.shapekey_hash, self.vb0_hash))

    def build_component(self, pose_data: PoseData, draw_data: DrawData, vb_layout: BufferElementLayout):
        """
        Compiles component data from multiple sources into single export-optimized object
        """
        shapekey_buffer = None
        if self.shapekey_data is not None:
            # Fetch associated shapekeys data
            shapekey_buffer = self.shapekey_data.build_shapekey_buffer(draw_data.vertex_offset, draw_data.vertex_count)
            if shapekey_buffer is not None:
                # Copy VB layout and merge it with layout of shapekeys buffer
                vb_layout = copy.deepcopy(vb_layout)
                vb_layout.merge(shapekey_buffer.layout)

        vb = ByteBuffer(vb_layout)
        vb.extend(draw_data.vertex_count)

        vb.import_buffer(pose_data.position_buffer)
        vb.import_buffer(pose_data.blend_buffer)
        vb.import_buffer(pose_data.vector_buffer)
        if draw_data.color_buffer is not None:
            vb.import_buffer(draw_data.color_buffer)
        vb.import_buffer(draw_data.texcoord_buffer)

        if shapekey_buffer is not None:
            vb.import_buffer(shapekey_buffer)

        # Decrease vertex ids in IB by component offset to make them start from 0
        draw_data.index_buffer.faces = [
            tuple(vertex_index - draw_data.vertex_offset for vertex_index in face)
            for face in draw_data.index_buffer.faces
        ]

        textures = {}
        for texture in draw_data.textures:
            slot_hash = texture.get_slot_hash()
            textures[slot_hash] = texture

        return MeshComponent(
            ib_hash=draw_data.ib_hash,
            vb_hash=draw_data.vb_hash,
            sk_hash=pose_data.shapekey_hash,
            dispatch_x=pose_data.dispatch_x,
            vertex_offset=draw_data.vertex_offset,
            vertex_count=draw_data.vertex_count,
            index_offset=draw_data.index_offset,
            index_count=draw_data.index_count,
            index_buffer=draw_data.index_buffer,
            vg_offset=0,
            vg_count=0,
            vertex_buffer=vb,
            skeleton_buffer=pose_data.skeleton_data,
            textures=textures,
        )

    def merge_vertex_groups(self):
        """
        Concatenates VGs of components and remaps duplicate VGs based on bone values from skeleton buffers
        """
        vg_offset = 0
        vg_map = {}
        unique_bones = {}

        for component_id, component in enumerate(self.components):
            # Fetch joined list of all VG ids of all vertices of the component (4 VG ids per vertex)
            vertex_groups = component.vertex_buffer.get_values(AbstractSemantic(Semantic.Blendindices))
            # For remapping purposes, VG count is the highest used VG id among all vertices of the component
            # It allows to efficiently construct merged skeleton buffer in-game via vg_offset & vg_count of components
            component.vg_offset = vg_offset
            component.vg_count = max(vertex_groups) + 1
            # Ensure frame dump data integrity
            if component.skeleton_buffer.num_elements < component.vg_count:
                raise ValueError('skeleton of Component_%d has only %d bones, while there are %d VGs declared' % (
                    component_id, component.skeleton_buffer.num_elements, component.vg_count))
            # Build VG map
            for vg_id in range(component.vg_count):
                # Fetch data floats of bone which VG is linked to
                buffer_element = component.skeleton_buffer.get_element(vg_id)
                bone_data = tuple(buffer_element.get_value(AbstractSemantic(Semantic.RawData)))
                # Skip zero-valued bone (garbage data)
                if all(v == 0 for v in bone_data):
                    continue
                # Get desc object of already registered unique bone data
                unique_bone_data = unique_bones.get(bone_data, None)
                # Register VG in VG map
                if unique_bone_data is None or unique_bone_data['component_id'] == component_id:
                    # Handle new VG or duplicate VG within same component
                    shifted_vg_id = vg_offset + vg_id  # Remap VG to VG of merged skeleton
                    vg_map[vg_id] = shifted_vg_id  # Remap VG to VG of merged skeleton
                    unique_bones[bone_data] = {  # Register unique bone data
                        'component_id': component_id,
                        'vg_id': shifted_vg_id
                    }
                else:
                    # Handle duplicate VG across different components
                    vg_map[vg_id] = unique_bone_data['vg_id']  # Remap VG to VG of already registered bone
                    log.info(f'Remapped duplicate VG %d of Component_%d to VG %d of Component_%s' % (
                        vg_id, component_id, vg_map[vg_id], unique_bone_data["component_id"]))
            # Remap VG ids based on map we've constructed
            merged_vertex_groups = [vg_map[vg_id] for vg_id in vertex_groups]
            # Write edited data back to the byte buffer
            component.vertex_buffer.set_values(AbstractSemantic(Semantic.Blendindices), merged_vertex_groups)

            vg_offset += component.vg_count

        log.info(f'Merged {vg_offset} Vertex Groups')


@dataclass
class ComponentBuilder:
    # Input
    output_vb_layout: BufferElementLayout
    shader_hashes: Dict[str, str]
    shapekeys: Dict[str, ShapeKeys]
    pose_data: Dict[tuple, PoseData]
    draw_data: Dict[tuple, DrawData]
    # Output
    mesh_objects: Dict[str, MeshObject] = field(init=False)

    def __post_init__(self):

        self.mesh_objects = {}

        for (vertex_offset, vertex_count, vb1_hash), pose_data in self.pose_data.items():

            draw_guid = (vertex_offset, vertex_count, vb1_hash)
            draw_data = self.draw_data.get(draw_guid, None)

            if draw_data is None:
                raise ValueError(f'no draw data found for component {":".join(draw_guid)}')

            vb0_hash = draw_data.vb_hash

            if vb0_hash not in self.mesh_objects:
                self.mesh_objects[vb0_hash] = MeshObject()

            self.mesh_objects[vb0_hash].import_component_data(pose_data, draw_data)
            
        for mesh_object in self.mesh_objects.values():
            mesh_object.build_components(self.output_vb_layout, self.shapekeys)

        log.info(f'Collected components for {len(self.mesh_objects)} VB hashes: {", ".join(self.mesh_objects.keys())}')



    
    









