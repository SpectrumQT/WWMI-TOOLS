import os
import json
import re

from types import LambdaType
from typing import List, Dict, Union
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import bpy


class Version:
    def __init__(self, version: str):
        self.version = version.split('.')

    def __str__(self) -> str:
        return f'{self.version[0]}.{self.version[1]}.{self.version[2]}'

    def as_float(self):
        return float(f'{self.version[0]}.{self.version[1]}{self.version[2]}')

    def as_ints(self):
        return [map(int, self.version)]
    

@dataclass
class TempObject:
    name: str
    index_count: int


@dataclass
class Component:
    name: str
    index_offset: int
    index_count: int
    vg_offset: int = None
    vg_count: int = None
    vertex_offset: int = None
    vertex_count: int = None
    obj: bpy.types.Object = None
    components: List['Component'] = None


@dataclass
class MeshComponent:
    dispatch_x: int
    stock_component: Component
    custom_component: Union[Component, None]


@dataclass
class ModInfo:
    wwmi_tools_version: Version
    required_wwmi_version: Version
    mod_name: str
    mod_author: str
    mod_desc: str
    mod_link: str
    mod_logo: Path


@dataclass
class MeshObject:
    custom_vertex_count: int
    custom_index_count: int
    original_index_count: int
    original_vertex_count: int
    ib_hash: str
    vb0_hash: str
    vb1_hash: str
    components: List[MeshComponent] = field(init=False)


@dataclass
class ShapeKeys:
    offsets_hash: str
    scale_hash: str
    custom_vertex_count: int
    dispatch_y: int
    checksum: int


@dataclass
class Texture:
    component_id: int
    slot_id: int
    hash: str
    path: Path
    filename: str



@dataclass
class MetadataCollector():
    # Input
    mod_info: ModInfo
    object_source_folder: Path
    merged_objects: Dict[int, List[TempObject]]
    custom_vertex_count: int
    custom_index_count: int
    custom_shapekey_vertex_count: int
    # Output
    source_metadata: dict = field(init=False)
    mesh_object: MeshObject = field(init=False)
    shapekeys: ShapeKeys = field(init=False)
    textures: List[Texture] = field(init=False)

    def __post_init__(self):
        self.read_source_metadata()
        self.colect_object()
        self.colect_components()
        self.collect_shapekeys()
        self.colect_textures()

    def read_source_metadata(self):
        with open(self.object_source_folder / 'Metadata.json') as f:
            self.source_metadata = json.load(f)
  
    def colect_textures(self):
        textures = {}
        for texture_filename in os.listdir(self.object_source_folder):
            if texture_filename.endswith(".dds") or texture_filename.endswith(".jpg"): 
                data_pattern = re.compile(r'^Component_(\d+)-ps-t(\d+)-([a-f0-9]+).*')
                result = data_pattern.findall(texture_filename)
                if len(result) != 1:
                    continue
                result = result[0]
                if len(result) != 3:
                    continue
                component_id = result[0]
                slot_id = result[1]
                texture_hash = result[2]
                source_path = self.object_source_folder / texture_filename
                textures[texture_hash] = Texture(
                    component_id=component_id,
                    slot_id=slot_id,
                    hash=texture_hash,
                    path=source_path,
                    filename=f'{texture_hash}{source_path.suffix}',
                )
        self.textures = list(textures.values())

    def colect_object(self):
        self.mesh_object = MeshObject(
            ib_hash=self.source_metadata['ib_hash'],
            vb0_hash=self.source_metadata['vb0_hash'],
            vb1_hash=self.source_metadata['vb1_hash'],
            custom_vertex_count=self.custom_vertex_count,
            custom_index_count=self.custom_index_count,
            original_index_count=self.source_metadata['index_count'],
            original_vertex_count=self.source_metadata['vertex_count'],
        )

    def colect_components(self):
        self.mesh_object.components = []

        index_offset = 0

        for component_id, source_component in enumerate(self.source_metadata['components']):

            merged_objects = self.merged_objects.get(component_id, None)

            if merged_objects is not None:

                custom_component = Component(
                    name=f'Component_{component_id}',
                    index_offset=index_offset,
                    index_count=0,
                    components=[],
                )
                
                for obj in merged_objects:

                    sub_component = Component(
                        name=obj.name,
                        index_offset=index_offset,
                        index_count=obj.index_count,
                    )

                    index_offset += sub_component.index_count

                    custom_component.index_count += sub_component.index_count
                    custom_component.components.append(sub_component)

            else:
                custom_component = None

            component = MeshComponent(
                dispatch_x=source_component['dispatch_x'],
                stock_component=Component(
                    name=f'Component_{component_id}',
                    index_offset=source_component['index_offset'],
                    index_count=source_component['index_count'],
                    vertex_offset=source_component['vertex_offset'],
                    vertex_count=source_component['vertex_count'],
                    vg_offset=source_component['vg_offset'],
                    vg_count=source_component['vg_count'],
                ),
                custom_component=custom_component,
            )

            self.mesh_object.components.append(component)

    def collect_shapekeys(self):
        shapekeys = ShapeKeys(
            offsets_hash=self.source_metadata['shapekeys']['offsets_hash'],
            scale_hash=self.source_metadata['shapekeys']['scale_hash'],
            custom_vertex_count=self.custom_shapekey_vertex_count,
            dispatch_y=self.source_metadata['shapekeys']['dispatch_y'],
            checksum=self.source_metadata['shapekeys']['checksum'],
        )
        self.shapekeys = shapekeys