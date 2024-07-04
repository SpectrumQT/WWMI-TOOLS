
from pathlib import Path


bl_info = {
    "name": "WWMI Tools",
    "version": (0, 8, 5),
    "wwmi_version": (0, 6, 1),
    "blender": (2, 80, 0),
    "author": "SpectrumQT, DarkStarSword",
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Wuthering Waves modding toolkit",
    "category": "Object",
    "tracker_url": "https://github.com/SpectrumQT/WWMI-Tools",
}


def reload_package(module_dict_main):
    def reload_package_recursive(current_dir, module_dict):
        for path in current_dir.iterdir():
            if "__init__" in str(path) or path.stem not in module_dict:
                continue
            if path.is_file() and path.suffix == ".py":
                importlib.reload(module_dict[path.stem])
            elif path.is_dir():
                reload_package_recursive(path, module_dict[path.stem].__dict__)
    reload_package_recursive(Path(__file__).parent, module_dict_main)


import bpy
if "bpy" in locals():
    import importlib
    reload_package(locals())


from . import wwmi_tools


classes = [
    wwmi_tools.WWMI_Settings,
    wwmi_tools.WWMI_Import,
    wwmi_tools.WWMI_Export,
    wwmi_tools.WWMI_ExtractFrameData,
    wwmi_tools.WWMI_FillGapsInVertexGroups,
    wwmi_tools.WWMI_RemoveUnusedVertexGroups,
    wwmi_tools.WWMI_RemoveAllVertexGroups,
    wwmi_tools.WWMI_ApplyModifierForObjectWithShapeKeysOperator,
    wwmi_tools.WWMI_TOOLS_PT_UI_PANEL,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.wwmi_tools_settings = bpy.props.PointerProperty(type=wwmi_tools.WWMI_Settings)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.wwmi_tools_settings


if __name__ == '__main__':
    register()

