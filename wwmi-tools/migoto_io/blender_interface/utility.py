from pathlib import Path

import bpy


def get_workdir() -> Path:
    return Path(bpy.path.abspath("//"))


def get_blend_file_path() -> Path:
    return Path(bpy.data.filepath)


def resolve_path(path) -> Path:
    return Path(bpy.path.abspath(path)).resolve()