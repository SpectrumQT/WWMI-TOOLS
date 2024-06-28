import json

from typing import List, Dict, Union
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class ExtractedObjectComponent:
    dispatch_x: int
    vertex_offset: int
    vertex_count: int
    index_offset: int
    index_count: int
    vg_offset: int
    vg_count: int


@dataclass
class ExtractedObjectShapeKeys:
    offsets_hash: str = ''
    scale_hash: str = ''
    vertex_count: int = 0
    dispatch_y: int = 0
    checksum: int = 0


@dataclass
class ExtractedObject:
    ib_hash: str
    vb0_hash: str
    vb1_hash: str
    vertex_count: int
    index_count: int
    components: List[ExtractedObjectComponent]
    shapekeys: ExtractedObjectShapeKeys

    def __post_init__(self):
        if isinstance(self.shapekeys, dict):
            self.components = [ExtractedObjectComponent(**component) for component in self.components]
            self.shapekeys = ExtractedObjectShapeKeys(**self.shapekeys)

    def as_json(self):
        return json.dumps(asdict(self), indent=4)


def read_metadata(metadata_path: Path) -> ExtractedObject:
    with open(metadata_path) as f:
        return ExtractedObject(**json.load(f))

