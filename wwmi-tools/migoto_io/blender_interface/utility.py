
import bpy


def get_workdir():
    return bpy.path.abspath("//")


def get_blend_file_path():
    return bpy.data.filepath

