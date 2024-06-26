
import os
import json

from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path

from ..migoto_io.buffers.dxgi_format import DXGIFormat
from ..migoto_io.dump_parser.filename_parser import ResourceDescriptor

from .shapekey_builder import ShapeKeys
from .component_builder import MeshObject


@dataclass
class TextureFilter:
    min_file_size: int
    exclude_extensions: List[str]
    exclude_same_slot_hash_textures: bool


@dataclass
class ComponentData:
    fmt: str
    vb: bytearray
    ib: bytearray
    textures: Dict[str, List[ResourceDescriptor]]


@dataclass
class ObjectData:
    metadata: dict
    components: List[ComponentData]


@dataclass
class OutputBuilder:
    # Input
    shapekeys: Dict[str, ShapeKeys]
    mesh_objects: Dict[str, MeshObject]
    texture_filter: TextureFilter
    # Output
    objects: Dict[str, ObjectData] = field(init=False)

    def __post_init__(self):
        self.objects = {}
        for vb_hash, mesh_object in self.mesh_objects.items():

            shapekeys = None
            for component in mesh_object.components:
                if component.sk_hash is not None:
                    shapekeys = self.shapekeys[component.sk_hash]

            self.filter_textures(mesh_object)

            self.objects[vb_hash] = ObjectData(
                metadata=self.build_metadata(mesh_object, shapekeys),
                components=[
                    ComponentData(
                        fmt=self.build_fmt(component.vertex_buffer, component.index_buffer),
                        vb=component.vertex_buffer.get_bytes(),
                        ib=component.index_buffer.get_bytes(),
                        textures=component.textures,
                    ) for component in mesh_object.components
                ]
            )

    def filter_textures(self, mesh_object):

        num_slot_hash_entries = {}

        for component in mesh_object.components:

            for texture in component.textures.values():
                slot_hash = texture.get_slot_hash()

                if slot_hash not in num_slot_hash_entries:
                    num_slot_hash_entries[slot_hash] = 0

                num_slot_hash_entries[slot_hash] += 1

        for component in mesh_object.components:

            textures = []

            for texture in component.textures.values():

                # Exclude texture with ignored extension
                if len(self.texture_filter.exclude_extensions) > 0:
                    if texture.ext in self.texture_filter.exclude_extensions:
                        continue
                    
                # Exclude texture below minimal file size 
                if self.texture_filter.min_file_size != 0:
                    file_size = Path(texture.path).stat().st_size
                    if file_size < self.texture_filter.min_file_size:
                        continue

                # Exclude texture if it has same slot+hash in all components
                if self.texture_filter.exclude_same_slot_hash_textures:
                    num_components = len(mesh_object.components)
                    if num_components > 1:
                        slot_hash = texture.get_slot_hash()
                        if num_slot_hash_entries[slot_hash] == num_components:
                            continue

                textures.append(texture)

            component.textures = textures


    @staticmethod
    def build_metadata(mesh_object, shapekeys):
        return {
            'ib_hash': mesh_object.ib_hash,
            'vb0_hash': mesh_object.vb0_hash,
            'vb1_hash': mesh_object.vb1_hash,
            'vertex_count': mesh_object.vertex_count,
            'index_count': mesh_object.index_count,
            'components': [
                {
                    'dispatch_x': component.dispatch_x,
                    'vertex_offset': component.vertex_offset,
                    'vertex_count': component.vertex_count,
                    'index_offset': component.index_offset,
                    'index_count': component.index_count,
                    'vg_offset': component.vg_offset,
                    'vg_count': component.vg_count,

                } for component in mesh_object.components
            ],
            'shapekeys': {
                'offsets_hash': shapekeys.offsets_hash,
                'scale_hash': shapekeys.scale_hash,
                'vertex_count': shapekeys.shapekey_offsets[-1] - 1,
                'dispatch_y': shapekeys.dispatch_y,
                'checksum': sum(shapekeys.shapekey_offsets[0:4]),
            } if shapekeys is not None else {}
        }

    @staticmethod
    def build_fmt(vb, ib):
        # Default 3dm blender import script expects 1-byte IB format DXGI_FORMAT_R16_UINT
        # Our IndexBuffer implementation uses 3-byte IB format DXGI_FORMAT_R16G16B16_UINT
        # So we'll have to override said format to be compatible
        ib_format = ib.get_format()
        if ib_format.find('16_UINT') != -1:
            ib_format = DXGIFormat.R16_UINT.get_format()
        elif ib_format.find('32_UINT') != -1:
            ib_format = DXGIFormat.R32_UINT.get_format()
        else:
            raise ValueError(f'unknown IB format {ib_format}')

        fmt = ''
        fmt += f'stride: {vb.layout.stride}\n'
        fmt += f'topology: trianglelist\n'
        fmt += f'format: {ib_format}\n'
        fmt += vb.layout.to_string()

        return fmt






