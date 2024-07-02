import re

from typing import List, Dict, Union
from dataclasses import dataclass, field
from enum import Enum

from ..migoto_io.blender_interface.collections import *
from ..migoto_io.blender_interface.objects import *

from ..migoto_io.blender_tools.modifiers import apply_modifiers_for_object_with_shape_keys

from ..extract_frame_data.metadata_format import ExtractedObject


class SkeletonType(Enum):
    Merged = 'Merged'
    PerComponent = 'Per-Component'


@dataclass
class TempObject:
    name: str
    object: bpy.types.Object
    vertex_count: int = 0
    index_count: int = 0
    index_offset: int = 0


@dataclass
class MergedObjectComponent:
    objects: List[TempObject]
    vertex_count: int = 0
    index_count: int = 0


@dataclass
class MergedObjectShapeKeys:
    vertex_count: int = 0


@dataclass
class MergedObject:
    object: bpy.types.Object
    mesh: bpy.types.Mesh
    components: List[MergedObjectComponent]
    shapekeys: MergedObjectShapeKeys
    skeleton_type: SkeletonType
    vertex_count: int = 0
    index_count: int = 0
    vg_count: int = 0


@dataclass
class ObjectMerger:
    # Input
    context: bpy.context
    extracted_object: ExtractedObject
    ignore_hidden: bool
    apply_modifiers: bool
    collection: str
    skeleton_type: SkeletonType
    # Output
    merged_object: MergedObject = field(init=False)

    def __post_init__(self):
        collection_was_hidden = collection_is_hidden(self.collection)
        unhide_collection(self.collection)

        self.initialize_components()
        self.import_objects_from_collection()
        self.prepare_temp_objects()
        self.build_merged_object()
        
        if collection_was_hidden:
            hide_collection(self.collection)

    def initialize_components(self):
        self.components = []
        for component_id, component in enumerate(self.extracted_object.components): 
            self.components.append(
                MergedObjectComponent(
                    objects=[],
                    index_count=0,
                )
            )

    def import_objects_from_collection(self):
        
        component_pattern = re.compile(r'.*(?:component|part)[_ -]*(\d+).*')

        for obj in get_collection_objects(self.collection):

            if self.ignore_hidden and object_is_hidden(obj):
                continue

            if obj.name.startswith('TEMP_'):
                continue
            
            match = component_pattern.findall(obj.name.lower())
            if len(match) == 0:
                continue
            component_id = int(match[0])

            temp_obj = copy_object(self.context, obj, name=f'TEMP_{obj.name}', collection=self.collection)

            self.components[component_id].objects.append(TempObject(
                name=obj.name,
                object=temp_obj,
            ))

    def prepare_temp_objects(self):

        index_offset = 0

        for component_id, component in enumerate(self.components):

            component.objects.sort(key=lambda x: x.name)

            for temp_object in component.objects:
                temp_obj = temp_object.object
                # Remove ignored or unexpected vertex groups
                if self.skeleton_type == SkeletonType.Merged:
                    total_vg_count = sum([component.vg_count for component in self.extracted_object.components])
                    ignore_list = [vg for vg in get_vertex_groups(temp_obj) if 'ignore' in vg.name.lower() or vg.index >= total_vg_count]
                elif self.skeleton_type == SkeletonType.PerComponent:
                    extracted_component = self.extracted_object.components[component_id]
                    total_vg_count = len(extracted_component.vg_map)
                    ignore_list = [vg for vg in get_vertex_groups(temp_obj) if 'ignore' in vg.name.lower() or vg.index >= total_vg_count]
                # Apply all modifiers to temporary object
                if self.apply_modifiers:
                    with OpenObject(self.context, temp_obj) as obj:
                        selected_modifiers = [modifier.name for modifier in get_modifiers(obj)]
                        apply_modifiers_for_object_with_shape_keys(self.context, selected_modifiers, None)
                # Triangulate temporary object, this step is crucial as export supports only triangles
                triangulate_object(self.context, temp_obj)
                remove_vertex_groups(temp_obj, ignore_list)
                # Calculate vertex count of temporary object
                temp_object.vertex_count = len(temp_obj.data.vertices)
                # Calculate index count of temporary object, IB stores 3 indices per triangle
                temp_object.index_count = len(temp_obj.data.polygons) * 3
                # Set index offset of temporary object to global index_offset
                temp_object.index_offset = index_offset
                # Update global index_offset
                index_offset += temp_object.index_count
                # Update vertex and index count of custom component
                component.vertex_count += temp_object.vertex_count
                component.index_count += temp_object.index_count

    def build_merged_object(self):

        merged_object = []
        vertex_count, index_count = 0, 0
        for component in self.components:
            for temp_object in component.objects:
                merged_object.append(temp_object.object)
            vertex_count += component.vertex_count
            index_count += component.index_count
            
        join_objects(self.context, merged_object)

        obj = merged_object[0]

        rename_object(obj, 'TEMP_EXPORT_OBJECT')

        # We'll skip Blender weight normalizer in favor of custom 8-bit friendly normalizer that is applied to weight data later
        # normalize_all_weights(self.context, obj)

        deselect_all_objects()
        select_object(obj)
        set_active_object(bpy.context, obj)

        mesh = obj.evaluated_get(self.context.evaluated_depsgraph_get()).to_mesh()
        
        mesh.calc_tangents()
        mesh.flip_normals()
        mesh.calc_tangents()

        self.merged_object = MergedObject(
            object=obj,
            mesh=mesh,
            components=self.components,
            vertex_count=len(obj.data.vertices),
            index_count=len(obj.data.polygons) * 3,
            vg_count=len(get_vertex_groups(obj)),
            shapekeys=MergedObjectShapeKeys(),
            skeleton_type=self.skeleton_type,
        )

        if vertex_count != self.merged_object.vertex_count:
            raise ValueError('vertex_count mismatch between merged object and its components')

        if index_count != self.merged_object.index_count:
            raise ValueError('index_count mismatch between merged object and its components')
