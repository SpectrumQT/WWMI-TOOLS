import os
from pathlib import Path
from collections import OrderedDict

import bpy
from bpy.props import BoolProperty, StringProperty, PointerProperty, IntProperty, CollectionProperty


from .migoto_io.blender_interface.objects import *
from .migoto_io.blender_interface.collections import *
from .migoto_io.blender_interface.utility import *
from .migoto_io.buffers.byte_buffer import AbstractSemantic, Semantic
from .migoto_io.blender_tools.vertex_groups import *
from .migoto_io.blender_tools.modifiers import *


from .blender_import.blender_import import blender_import
from .blender_export.blender_export import blender_export, get_default_data_map, DataMap
from .extract_frame_data.extract_frame_data import extract_frame_data


from . import bl_info


class WWMI_Settings(bpy.types.PropertyGroup):
    # project_builder = ProjectBuilder()

    wwmi_tools_version: bpy.props.StringProperty(
        name = "WWMI Tools Version",
        default = '.'.join(map(str, bl_info["version"]))
    ) # type: ignore

    required_wwmi_version: bpy.props.StringProperty(
        name = "Required WWMI Version",
        default = '.'.join(map(str, bl_info["wwmi_version"]))
    ) # type: ignore

    loop_data_cache: bpy.props.StringProperty(
        name = "Loop Data Cache",
        default = ""
    ) # type: ignore
    
    loop_data_cached_collection: PointerProperty(
        name="Loop Data Cached Components",
        type=bpy.types.Collection,
    ) # type: ignore

    tool_mode: bpy.props.EnumProperty(
        name="Mode",
        description="Defines list of available actions",
        items=[
            ('EXPORT_MOD', 'Export Mod', 'Export selected collection as WWMI mod'),
            ('IMPORT_OBJECT', 'Import Object', 'Import .ib ad .vb files from selected directory'),
            ('EXTRACT_FRAME_DATA', 'Extract Objects From Dump', 'Extract components of all WWMI-compatible objects from the selected frame dump directory'),
            ('TOOLS_MODE', 'Toolbox', 'Bunch of useful object actions'),
        ],
        default=0,
    ) # type: ignore

    ########################################
    # Extract Frame Data
    ########################################

    frame_dump_folder: StringProperty(
        name="Frame Dump",
        description="Frame dump files directory",
        default='',
        subtype="DIR_PATH",
    ) # type: ignore

    skip_small_textures: BoolProperty(
        name="Textures Filtering: Skip Small",
        description="Skip texture smaller than specified size",
        default=True,
    ) # type: ignore

    skip_small_textures_size: IntProperty(
        name="Min Size (KB)",
        description="Minimal texture size in KB. Default is 256KB",
        default=256,
    ) # type: ignore

    skip_jpg_textures: BoolProperty(
        name="Textures Filtering: Skip .jpg",
        description="Skip texture with .jpg extension. These textures are mostly gradients and other masks",
        default=True,
    ) # type: ignore

    skip_same_slot_hash_textures: BoolProperty(
        name="Textures Filtering: Skip Same Slot-Hash",
        description="Skip texture if its hash is found in same slot of all components. May filter out useful textures!",
        default=False,
    ) # type: ignore

    extract_output_folder: StringProperty(
        name="Output Folder",
        description="Extracted WWMI objects export directory",
        default='',
        subtype="DIR_PATH",
    ) # type: ignore

    ########################################
    # Object Import
    ########################################

    object_source_folder: StringProperty(
        name="Object Sources",
        description="Directory with components and textures of WWMI object",
        default='',
        subtype="DIR_PATH",
    ) # type: ignore

    import_skeleton_type: bpy.props.EnumProperty(
        name="Skeleton",
        description="Controls the way of Vertex Groups handling",
        items=[
            ('MERGED', 'Merged', 'Imported mesh will have unified list of Vertex Groups, allowing to weight any vertex of any component to any bone. Mod Upsides: easy to weight, advanced weighting support (i.e. long hair to cape). Mod Downsides: model will be updated with 1 frame delay, mod will pause while there are more than one of same modded object on screen. Suggested usage: new modders, character or echo mods with complex weights.'),
            ('COMPONENT', 'Per-Component', 'Imported mesh will have its Vertex Groups split into per component lists, restricting weighting of any vertex only to its parent component. Mod Upsides: no 1-frame delay for model updates, minor performance gain. Mod downsides: hard to weight, very limited weighting options. Suggested usage: weapon mods and simple retextures.'),
        ],
        default=0,
    ) # type: ignore

    mirror_mesh: BoolProperty(
        name="Mirror Mesh",
        description="Automatically mirror mesh to match actual in-game left-right",
        default=True,
    ) # type: ignore

    ########################################
    # Mod Export
    ########################################

    component_collection: PointerProperty(
        name="Components",
        description="Collection with WWMI object's components named like `Component 0` or `Component_1 RedHat` or `Dat Gas cOmPoNENT- 3 OMG` (lookup RegEx: r'.*component[_ -]*(\d+).*')",
        type=bpy.types.Collection,
        # default=False
    ) # type: ignore
    
    ignore_hidden: BoolProperty(
        name="Ignore Hidden Objects",
        description="If enabled, hidden objects inside Components collection won't be exported",
        default=False,
    ) # type: ignore

    mod_output_folder: StringProperty(
        name="Mod Folder",
        description="Mod export directory to place mod.ini and Meshes&Textures folders into",
        default='',
        subtype="DIR_PATH",
    ) # type: ignore
    
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply all modifiers to temporary copy of the merged object",
        default=False,
    ) # type: ignore

    mod_name: StringProperty(
        name="Mod Name",
        description="Name of mod to be displayed in user notifications and mod managers",
        default='Unnamed Mod',
    ) # type: ignore

    mod_author: StringProperty(
        name="Author Name",
        description="Name of mod author to be displayed in user notifications and mod managers",
        default='Unknown Author',
    ) # type: ignore

    mod_desc: StringProperty(
        name="Mod Description",
        description="Short mod description to be displayed in user notifications and mod managers",
        default='',
    ) # type: ignore

    mod_link: StringProperty(
        name="Mod Link",
        description="Link to mod web page to be displayed in user notifications and mod managers",
        default='',
    ) # type: ignore

    mod_logo: StringProperty(
        name="Mod Logo",
        description="Texture with 512x512 size and .dds extension (BC7 SRGB) to be displayed in user notifications and mod managers, will be placed to /Textures/Logo.dds",
        default='',
        subtype="FILE_PATH",
    ) # type: ignore

    mod_skeleton_type: bpy.props.EnumProperty(
        name="Skeleton",
        description="Select the same skeleton type that was used for import! Defines logic of exported mod.ini.",
        items=[
            ('MERGED', 'Merged', 'Mesh with this skeleton should have unified list of Vertex Groups'),
            ('COMPONENT', 'Per-Component', 'Mesh with this skeleton should have its Vertex Groups split into per-component lists.'),
        ],
        default=0,
    ) # type: ignore

    partial_export: BoolProperty(
        name="Partial Export",
        description="For advanced usage only. Allows to export only selected buffers. Speeds up export when you're sure that there were no changes to certain data since previous export. Disables INI generation and assets copying",
        default=False,
    ) # type: ignore

    export_index: BoolProperty(
        name="Export Index Buffer",
        description="Contains data that associates vertices with faces",
        default=True,
    ) # type: ignore

    export_positions: BoolProperty(
        name="Export Position Buffer",
        description="Contains coordinates of each vertex",
        default=True,
    ) # type: ignore

    export_blends: BoolProperty(
        name="Export Blend Buffer",
        description="Contains VG ids and weights of each vertex",
        default=True,
    ) # type: ignore

    export_vectors: BoolProperty(
        name="Export Vector Buffer",
        description="Contains normals and tangents",
        default=True,
    ) # type: ignore

    export_colors: BoolProperty(
        name="Export Color Buffer",
        description="Contains vertex color atribute named COLOR",
        default=True,
    ) # type: ignore

    export_texcoords: BoolProperty(
        name="Export TexCoord Buffer",
        description="Contains UVs and vertex color atribute named COLOR1",
        default=True,
    ) # type: ignore

    export_shapekeys: BoolProperty(
        name="Export Shape Keys Buffers",
        description="Contains shape keys data",
        default=True,
    ) # type: ignore

    apply_all_modifiers: BoolProperty(
        name="Apply All Modifiers",
        description="Automatically apply all existing modifiers to temporary copies of each object",
        default=False,
    ) # type: ignore

    copy_textures: BoolProperty(
        name="Copy Textures",
        description="Copy texture files to export folder",
        default=True,
    ) # type: ignore

    write_ini: BoolProperty(
        name="Write Mod INI",
        description="Write new .ini to export folder",
        default=True,
    ) # type: ignore

    comment_ini: BoolProperty(
        name="Comment INI code",
        description="Add comments to INI code, useful if you want to get better idea how it works",
        default=False,
    ) # type: ignore

    remove_temp_object: BoolProperty(
        name="Remove Temp Object",
        description="Remove temporary object built from merged components after export. May be useful to uncheck for debug purposes",
        default=True,
    ) # type: ignore


# @orientation_helper(axis_forward='-Z', axis_up='Y')
class WWMI_Import(bpy.types.Operator):
    """
    Import object extracted from frame dump data with WWMI
    """
    bl_idname = "wwmi_tools.import_object"
    bl_label = "Import Object"
    bl_description = "Import object extracted from frame dump data with WWMI"

    bl_options = {'UNDO'}

    def execute(self, context):
        try:
            cfg = context.scene.wwmi_tools_settings
            cfg.mod_skeleton_type = cfg.import_skeleton_type
            blender_import(self, context, cfg)

        except ValueError as e:
            self.report({'ERROR'}, str(e))
        
        return {'FINISHED'}


class WWMI_Export(bpy.types.Operator):
    """
    Export object as WWMI mod
    """
    bl_idname = "wwmi_tools.export_mod"
    bl_label = "Export Mod"
    bl_description = "Export object as WWMI mod"

    def get_data_map(self, context):
        """
        Calculates list of exported buffers and processed semantics based on partial export settings
        Speeds up export of single buffer up to 5 times compared to full export
        """
        cfg = context.scene.wwmi_tools_settings

        default_data_map = get_default_data_map()

        if cfg.partial_export:
            
            data_map = DataMap(
                LoopDataConverters=OrderedDict({}),
                VertexDataConverters=OrderedDict({}),
                IndexBuffer={},
                VertexBuffers={},
                ShapeKeyBuffers={},
            )

            # Loop data is used to create list of exported vertices, so there are only two options for partial export:
            # 1. Recalculate each time whenever Index / Vector / Color / TexCoord buffers is selected
            # 2. Load from cache if there is no Index / Vector / Color / TexCoord buffers selected
            # If LoopDataConverters is empty, export module will handle caching automatically
            if not all([not x for x in [cfg.export_index, cfg.export_vectors, cfg.export_colors, cfg.export_texcoords]]):
                data_map.LoopDataConverters=default_data_map.LoopDataConverters

            # Vertex data processing can be skipped entirely if no Position / Blend buffers selected
            for semantic, converter in default_data_map.VertexDataConverters.items():
                if not cfg.export_positions:
                    if semantic == AbstractSemantic(Semantic.Position):
                        continue
                if not cfg.export_blends:
                    if semantic == AbstractSemantic(Semantic.Blendindices):
                        continue
                    if semantic == AbstractSemantic(Semantic.Blendweight):
                        continue
                data_map.VertexDataConverters[semantic] = converter

            # Skip building unselected Index buffer
            for name, semantics in default_data_map.IndexBuffer.items():
                if not cfg.export_index and name == 'Index':
                    continue
                data_map.IndexBuffer[name] = semantics

            # Skip building unselected Position/Blend/Vector/Vector/TexCoord buffer
            for name, semantics in default_data_map.VertexBuffers.items():
                if not cfg.export_positions and name == 'Position':
                    continue
                if not cfg.export_blends and name == 'Blend':
                    continue
                if not cfg.export_vectors and name == 'Vector':
                    continue
                if not cfg.export_colors and name == 'Color':
                    continue
                if not cfg.export_texcoords and name == 'TexCoord':
                    continue
                data_map.VertexBuffers[name] = semantics

            # Skip building unselected Shape Keys buffers stack
            for name, semantics in default_data_map.ShapeKeyBuffers.items():
                if not cfg.export_shapekeys:
                    continue
                data_map.ShapeKeyBuffers[name] = semantics
                
            return data_map
    
        else:

            return default_data_map

    def verify_collection(self, context):
        cfg = context.scene.wwmi_tools_settings
        if not cfg.component_collection.name in get_scene_collections():
            raise ValueError(f'Collection "{cfg.component_collection.name}" must be a member of "Scene Collection"!')

    def execute(self, context):
        try:
            cfg = context.scene.wwmi_tools_settings
            self.verify_collection(context)

            data_map = self.get_data_map(context)

            blender_export(self, context, cfg, data_map)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}


class WWMI_ExtractFrameData(bpy.types.Operator):
    """
    Extract objects from frame dump
    """
    bl_idname = "wwmi_tools.extract_frame_data"
    bl_label = "Extract Objects From Dump"
    bl_description = "Extract objects from frame dump"

    def execute(self, context):
        try:
            cfg = context.scene.wwmi_tools_settings

            extract_frame_data(cfg)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_FillGapsInVertexGroups(bpy.types.Operator):
    """
    Fills in missing vertex groups for a model so there are no gaps, and sorts to make sure everything is in order
    Works on the currently selected object
    e.g. if the selected model has groups 0 1 4 5 7 2 it adds an empty group for 3 and 6 and sorts to make it 0 1 2 3 4 5 6 7
    Very useful to make sure there are no gaps or out-of-order vertex groups
    """
    bl_idname = "wwmi_tools.fill_gaps_in_vertex_groups"
    bl_label = "Fill Gaps In Vertex Groups"
    bl_description = "Adds missing vertex groups and sorts the VG lists of selected objects (i.e. if object had 0,4,2 groups, it'll add missing 1,3 and sort the list to 0,1,2,3,4). Sourced by SilentNightSound#7430"

    def execute(self, context):
        try:
            for obj in get_selected_objects(context):
                fill_gaps_in_vertex_groups(context, obj)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_RemoveUnusedVertexGroups(bpy.types.Operator):
    """
    Remove all vertex groups from selected objects
    """
    bl_idname = "wwmi_tools.remove_unused_vertex_groups"
    bl_label = "Remove Unused Vertex Groups"
    bl_description = "Remove vertex groups with zero weights from selected objects. Sourced by Ave"

    def execute(self, context):
        try:
            for obj in get_selected_objects(context):
                remove_unused_vertex_groups(context, obj)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}
    

class WWMI_RemoveAllVertexGroups(bpy.types.Operator):
    """
    Remove all vertex groups from selected objects
    """
    bl_idname = "wwmi_tools.remove_all_vertex_groups"
    bl_label = "Remove All Vertex Groups"
    bl_description = "Remove all vertex groups from selected objects"

    def execute(self, context):
        try:
            for obj in get_selected_objects(context):
                remove_all_vertex_groups(context, obj)
            
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            
        return {'FINISHED'}


class PropertyCollectionModifierItem(bpy.types.PropertyGroup):
    checked: BoolProperty(
        name="", 
        default=False
    ) # type: ignore
bpy.utils.register_class(PropertyCollectionModifierItem)


class WWMI_ApplyModifierForObjectWithShapeKeysOperator(bpy.types.Operator):
    bl_idname = "wwmi_tools.apply_modifier_for_object_with_shape_keys"
    bl_label = "Apply Modifiers For Object With Shape Keys"
    bl_description = "Apply selected modifiers and remove from the stack for object with shape keys (Solves 'Modifier cannot be applied to a mesh with shape keys' error when pushing 'Apply' button in 'Object modifiers'). Sourced by Przemysław Bągard"
 
    def item_list(self, context):
        return [(modifier.name, modifier.name, modifier.name) for modifier in bpy.context.object.modifiers]
    
    my_collection: CollectionProperty(
        type=PropertyCollectionModifierItem
    ) # type: ignore
    
    disable_armatures: BoolProperty(
        name="Don't include armature deformations",
        default=True,
    ) # type: ignore
 
    def execute(self, context):
        ob = bpy.context.object
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = ob
        ob.select_set(True)
        
        selectedModifiers = [o.name for o in self.my_collection if o.checked]
        
        if not selectedModifiers:
            self.report({'ERROR'}, 'No modifier selected!')
            return {'FINISHED'}
        
        success, errorInfo = apply_modifiers_for_object_with_shape_keys(context, selectedModifiers, self.disable_armatures)
        
        if not success:
            self.report({'ERROR'}, errorInfo)
        
        return {'FINISHED'}
        
    def draw(self, context):
        if context.object.data.shape_keys and context.object.data.shape_keys.animation_data:
            self.layout.separator()
            self.layout.label(text="Warning:")
            self.layout.label(text="              Object contains animation data")
            self.layout.label(text="              (like drivers, keyframes etc.)")
            self.layout.label(text="              assigned to shape keys.")
            self.layout.label(text="              Those data will be lost!")
            self.layout.separator()
        #self.layout.prop(self, "my_enum")
        box = self.layout.box()
        for prop in self.my_collection:
            box.prop(prop, "checked", text=prop["name"])
        #box.prop(self, "my_collection")
        self.layout.prop(self, "disable_armatures")
 
    def invoke(self, context, event):
        self.my_collection.clear()
        for i in range(len(bpy.context.object.modifiers)):
            item = self.my_collection.add()
            item.name = bpy.context.object.modifiers[i].name
            item.checked = False
        return context.window_manager.invoke_props_dialog(self)


class WWMI_TOOLS_PT_UI_PANEL(bpy.types.Panel):
    """
    Wuthering Waves modding toolkit
    """

    bl_idname = "WWMI_TOOLS_PT_UI_PANEL"
    bl_label = "WWMI Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    # @classmethod
    # def poll(cls, context):
    #     return (context.object is not None)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw_menu_tools_mode(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout

        layout.row().operator(WWMI_ApplyModifierForObjectWithShapeKeysOperator.bl_idname)
        layout.row().operator(WWMI_FillGapsInVertexGroups.bl_idname)
        layout.row().operator(WWMI_RemoveUnusedVertexGroups.bl_idname)
        layout.row().operator(WWMI_RemoveAllVertexGroups.bl_idname)

    def draw_menu_export_mod(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.row()
        
        layout.row().prop(cfg, 'component_collection')
        layout.row().prop(cfg, 'ignore_hidden')
        layout.row().prop(cfg, 'object_source_folder')
        layout.row().prop(cfg, 'mod_output_folder')
        layout.row().prop(cfg, 'mod_skeleton_type')

        layout.row()

        layout.row().prop(cfg, 'partial_export')

        if cfg.partial_export:
            layout.row().prop(cfg, 'export_index')
            layout.row().prop(cfg, 'export_positions')
            layout.row().prop(cfg, 'export_blends')
            layout.row().prop(cfg, 'export_vectors')
            layout.row().prop(cfg, 'export_colors')
            layout.row().prop(cfg, 'export_texcoords')
            layout.row().prop(cfg, 'export_shapekeys')
        else:
            layout.row()
            
            layout.row().prop(cfg, 'apply_all_modifiers')
            layout.row().prop(cfg, 'copy_textures')

            col = layout.column(align=True)
            grid = col.grid_flow(columns=2, align=True)
            grid.alignment = 'LEFT'
            grid.prop(cfg, 'write_ini')
            if cfg.write_ini:
                grid.prop(cfg, 'comment_ini')
                
                layout.row()
                layout.row().prop(cfg, 'mod_name')
                layout.row().prop(cfg, 'mod_author')
                layout.row().prop(cfg, 'mod_desc')
                layout.row().prop(cfg, 'mod_link')
                layout.row().prop(cfg, 'mod_logo')
        
        layout.row()

        layout.row().prop(cfg, 'remove_temp_object')
        
        layout.row()

        layout.row().operator(WWMI_Export.bl_idname)

    def draw_menu_import_object(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.row()

        layout.row().prop(cfg, 'object_source_folder')
        layout.row().prop(cfg, 'import_skeleton_type')
        layout.row().prop(cfg, 'mirror_mesh')

        layout.row()

        layout.row().operator(WWMI_Import.bl_idname)

    def draw_menu_extract_frame_data(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout
        
        layout.row()

        layout.row().prop(cfg, 'frame_dump_folder')
        layout.row().prop(cfg, 'extract_output_folder')

        layout.row()

        col = layout.column(align=True)
        grid = col.grid_flow(columns=2, align=True)
        grid.alignment = 'LEFT'
        grid.prop(cfg, 'skip_small_textures')
        if cfg.skip_small_textures:
            grid.prop(cfg, 'skip_small_textures_size')

        layout.row().prop(cfg, 'skip_jpg_textures')
        layout.row().prop(cfg, 'skip_same_slot_hash_textures')

        layout.row()

        layout.row().operator(WWMI_ExtractFrameData.bl_idname)

    def draw(self, context):
        cfg = context.scene.wwmi_tools_settings
        layout = self.layout

        layout.row().prop(cfg, 'tool_mode')

        if cfg.tool_mode == 'TOOLS_MODE':
            self.draw_menu_tools_mode(context)

        if cfg.tool_mode == 'EXPORT_MOD':
            self.draw_menu_export_mod(context)

        elif cfg.tool_mode == 'IMPORT_OBJECT':
            self.draw_menu_import_object(context)

        elif cfg.tool_mode == 'EXTRACT_FRAME_DATA':
            self.draw_menu_extract_frame_data(context)
