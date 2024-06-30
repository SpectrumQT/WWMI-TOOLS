
import io
import copy
import textwrap
import math

from typing import Union, List
from dataclasses import dataclass
from enum import Enum

from .dxgi_format import *


class Semantic(Enum):
    VertexId = 'VERTEXID'
    Index = 'INDEX'
    Tangent = 'TANGENT'
    Normal = 'NORMAL'
    TexCoord = 'TEXCOORD'
    Color = 'COLOR'
    Position = 'POSITION'
    Blendindices = 'BLENDINDICES'
    Blendweight = 'BLENDWEIGHT'
    ShapeKey = 'SHAPEKEY'
    RawData = 'RAWDATA'

    def __str__(self):
        return f'{self.value}'

    def __repr__(self):
        return f'{self.value}'


@dataclass
class AbstractSemantic:
    semantic: Semantic
    index: int = 0

    def __init__(self, semantic, semantic_index=0):
        self.semantic = semantic
        self.index = semantic_index

    def __hash__(self):
        return hash((self.semantic, self.index))

    def __str__(self):
        return f'{self.semantic}_{self.index}'

    def __repr__(self):
        return f'{self.semantic}_{self.index}'
    
    def get_name(self):
        name = self.semantic.value
        if self.index > 0:
            name += str(self.index)
        if self.semantic == Semantic.TexCoord:
            name += '.xy'
        return name


@dataclass
class BufferSemantic:
    semantic: AbstractSemantic
    format: DXGIFormat
    stride: int = 0
    offset: int = 0

    def __post_init__(self):
        # Calculate byte stride
        if self.stride == 0:
            self.stride = self.format.byte_width

    def __hash__(self):
        return hash((self.semantic, self.format.format, self.stride, self.offset))

    def __repr__(self):
        return f'{self.semantic} ({self.format.format} size={self.stride} offset={self.offset})'

    def to_string(self, indent=2):
        return textwrap.indent(textwrap.dedent(f'''
            SemanticName: {self.semantic.semantic}
            SemanticIndex: {self.semantic.index}
            Format: {self.format.format}
            InputSlot: 0
            AlignedByteOffset: {self.offset}
            InputSlotClass: per-vertex
            InstanceDataStepRate: 0
        ''').lstrip(), ' ' * indent)

    def get_format(self):
        return self.format.get_format()

@dataclass
class BufferElementLayout:
    semantics: List[BufferSemantic]
    stride: int = 0
    force_stride: bool = False

    def __post_init__(self):
        # Autofill byte Stride and Offsets
        if self.stride == 0:
            # Calculate byte stride
            for element in self.semantics:
                self.stride += element.stride
            # Calculate byte offsets
            offset = 0
            for element in self.semantics:
                element.offset = offset
                offset += element.stride
        # Autofill Semantic Index
        groups = {}
        for semantic in self.semantics:
            if semantic not in groups:
                groups[semantic] = 0
                continue
            if semantic.semantic.index == 0:
                groups[semantic] += 1
                semantic.semantic.index = groups[semantic]

    def get_element(self, semantic):
        for element in self.semantics:
            if semantic == element.semantic:
                return element

    def add_element(self, semantic):
        semantic = copy.deepcopy(semantic)
        semantic.offset = self.stride
        self.semantics.append(semantic)
        self.stride += semantic.stride

    def merge(self, layout):

        for semantic in layout.semantics:
            if not self.get_element(semantic):
                self.add_element(semantic)

    def to_string(self):
        ret = ''
        for i, semantic in enumerate(self.semantics):
            ret += 'element[%i]:\n' % i
            ret += semantic.to_string()
        return ret


class BufferElement:
    def __init__(self, buffer, index):
        self.buffer = buffer
        self.index = index
        self.layout = self.buffer.layout

    def get_bytes(self, semantic, return_buffer_semantic=False):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        byte_offset = self.index * semantic.stride
        data_bytes = self.buffer.data[semantic][byte_offset : byte_offset + semantic.stride]
        if not return_buffer_semantic:
            return data_bytes
        else:
            return data_bytes, semantic

    def set_bytes(self, semantic, data_bytes):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        byte_offset = self.index * semantic.stride
        self.buffer.data[semantic][byte_offset: byte_offset + semantic.stride] = data_bytes

    def get_value(self, semantic):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        data_bytes = self.get_bytes(semantic)
        return semantic.format.decoder(data_bytes)

    def set_value(self, semantic, value):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        self.set_bytes(semantic, semantic.format.encoder(value))

    def get_all_bytes(self):
        data_bytes = bytearray()
        for semantic in self.layout.semantics:
            data_bytes.extend(self.get_bytes(semantic))
        return data_bytes


class ByteBuffer:
    def __init__(self, layout, data_bytes=None):
        self.layout = None
        self.data = {}
        self.num_elements = 0

        self.update_layout(layout)

        if data_bytes is not None:
            self.from_bytes(data_bytes)

    def validate(self):
        num_elements = {}
        for semantic in self.layout.semantics:
            num_elements[semantic] = len(self.data[semantic]) / semantic.stride
        if min(num_elements.values()) != max(num_elements.values()):
            num_elements = ', '.join([f'{k.semantic}: {v}' for k, v in num_elements.items()])
            raise ValueError(f'elements count mismatch in buffers: {num_elements}')
        if len(self.layout.semantics) != len(self.data):
            raise ValueError(f'data structure must match buffer layout!')
        self.num_elements = int(min(num_elements.values()))

    def update_layout(self, layout):
        self.layout = layout
        if len(self.data) != 0:
            self.validate()

    def from_bytes(self, data_bytes):
        if self.layout.force_stride:
            data_bytes.extend(bytearray((math.ceil(len(data_bytes) / self.layout.stride)) * self.layout.stride - len(data_bytes)))



        num_elements = len(data_bytes) / self.layout.stride
        if num_elements % 1 != 0:
            raise ValueError(f'buffer stride {self.layout.stride} must be multiplier of bytes len {len(data_bytes)}')
        num_elements = int(num_elements)

        self.data = {}
        for semantic in self.layout.semantics:
            self.data[semantic] = bytearray()

        byte_offset = 0
        for element_id in range(num_elements):
            for semantic in self.layout.semantics:
                self.data[semantic].extend(data_bytes[byte_offset:byte_offset+semantic.stride])
                byte_offset += semantic.stride

        if byte_offset != len(data_bytes):
            raise ValueError(f'layout mismatch: input ended at {byte_offset} instead of {len(data_bytes)}')

        self.validate()

    def get_element(self, index):
        return BufferElement(self, index)

    def extend(self, num_elements):
        if num_elements <= 0:
            raise ValueError(f'cannot extend buffer by {num_elements} elements')
        for semantic in self.layout.semantics:
            if semantic in self.data:
                self.data[semantic].extend(bytearray(num_elements * semantic.stride))
            else:
                self.data[semantic] = bytearray(num_elements * semantic.stride)
        self.validate()

    def get_fragment(self, offset, element_count):
        fragment = ByteBuffer(self.layout)
        for semantic in self.layout.semantics:
            byte_offset = offset * semantic.stride
            byte_count = element_count * semantic.stride
            fragment.data[semantic] = self.data[semantic][byte_offset:byte_offset+byte_count]
        fragment.validate()
        return fragment

    def import_buffer(self, src_byte_buffer, semantic_map=None, skip_missing=False):
        """
        Imports elements from source buffer based on their semantics
        Without 'semantic_map' provided creates new 'semantic_map' containing all source semantics
        Errors if any of 'semantic_map' elements is not found in src or dst buffers and 'skip_missing' is False
        """
        # Ensure equal number of elements in both buffers
        if src_byte_buffer.num_elements != self.num_elements:
            raise ValueError('source buffer len %d differs from destination buffer len %d' % (
                    src_byte_buffer.num_elements, self.num_elements))
        
        # Calculate semantic map
        semantic_map = self.map_semantics(src_byte_buffer, self, semantic_map=semantic_map, skip_missing=skip_missing)

        # Import data bytes
        for src_semantic, dst_semantic in semantic_map.items():
            if src_semantic.format == dst_semantic.format:
                self.data[dst_semantic] = src_byte_buffer.data[src_semantic]
            else:
                src_values = src_semantic.format.decoder(src_byte_buffer.data[src_semantic])
                self.data[dst_semantic] = dst_semantic.format.encoder(src_values)

        self.validate()

    def get_bytes(self, semantic=None):
        if semantic is None:
            data_bytes = bytearray()
            for element_id in range(self.num_elements):
                data_bytes.extend(self.get_element(element_id).get_all_bytes())
            return data_bytes
        else:
            if isinstance(semantic, AbstractSemantic):
                semantic = self.layout.get_element(semantic)
            return self.data[semantic]

    def get_values(self, semantic):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        data_bytes = self.get_bytes(semantic)
        return semantic.format.decoder(data_bytes)

    def set_bytes(self, semantic, data_bytes):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        self.data[semantic] = data_bytes
        self.validate()

    def set_values(self, semantic, values):
        if isinstance(semantic, AbstractSemantic):
            semantic = self.layout.get_element(semantic)
        self.set_bytes(semantic, semantic.format.encoder(values))

    @staticmethod
    def map_semantics(src_byte_buffer, dst_byte_buffer, semantic_map=None, skip_missing=False):
        """
        
        """
        verified_semantic_map = {}
        if semantic_map is not None:
            # Semantic map may consist of AbstractSemantic instead of BufferSemantic, we need to convert it in this case
            # AbstractSemantic is independent of buffer specifics and contains only SemanticName and SemanticIndex
            # BufferSemantic wraps AbstractSemantic and describes where AbstractSemantic is located in given buffer
            for src_semantic, dst_semantic in semantic_map.items():
                # Ensure source semantic location in source buffer
                src_semantic = src_semantic
                if isinstance(src_semantic, AbstractSemantic):
                    src_semantic = src_byte_buffer.layout.get_element(src_semantic)
                if src_semantic not in src_byte_buffer.layout.semantics:
                    if not skip_missing:
                        raise ValueError(f'source buffer has no {src_semantic.semantic} semantic')
                    continue
                # Ensure destination semantic location in destination buffer
                dst_semantic = src_semantic
                if isinstance(src_semantic, AbstractSemantic):
                    dst_semantic = dst_byte_buffer.layout.get_element(dst_semantic)
                if dst_semantic not in dst_byte_buffer.layout.semantics:
                    if not skip_missing:
                        raise ValueError(f'destination buffer has no {dst_semantic.semantic} semantic')
                    continue
                # Add semantic to verified map
                verified_semantic_map[src_semantic] = dst_semantic
        else:
            # If there is no semantics map provided, map everything by default
            for src_semantic in src_byte_buffer.layout.semantics:
                # Locate matching semantic in destination buffer
                dst_semantic = dst_byte_buffer.layout.get_element(src_semantic.semantic)
                if dst_semantic is None:
                    if not skip_missing:
                        raise ValueError(f'destination buffer has no {src_semantic.semantic} semantic')
                    continue
                verified_semantic_map[src_semantic] = dst_semantic

        return verified_semantic_map


class IndexBuffer(ByteBuffer):
    def __init__(self, layout, data, load_indices=True):
        self.offset = None
        self.first_index = None
        self.index_count = None
        self.topology = None
        self.format = None
        self.faces = None

        if isinstance(data, io.IOBase):
            self.parse_format(data)
            if load_indices:
                self.parse_faces(data)
            super().__init__(layout)
        elif isinstance(data, bytearray):
            super().__init__(layout, data)
            self.bytes_to_faces()
        else:
            raise ValueError(f'unknown IB data format {data}')

    def parse_format(self, f):
        for line in map(str.strip, f):
            if line.startswith('byte offset:'):
                self.offset = int(line[13:])
            elif line.startswith('first index:'):
                self.first_index = int(line[13:])
            elif line.startswith('index count:'):
                self.index_count = int(line[13:])
            elif line.startswith('topology:'):
                self.topology = line[10:]
                if line != 'topology: trianglelist':
                    raise ValueError('"%s" is not yet supported' % line)
            elif line.startswith('format:'):
                dxgi_format = line[8:].replace('DXGI_FORMAT_', '')
                self.format = dxgi_format
            elif line == '':
                if any(x is None for x in [self.offset, self.first_index, self.index_count, self.topology, self.format]):
                    raise ValueError('failed to parse IB format')
                break

    def parse_faces(self, f):
        self.faces = []
        for line in map(str.strip, f):
            face = tuple(map(int, line.split()))
            assert (len(face) == 3)
            self.faces.append(face)
        assert (len(self.faces) * 3 == self.index_count)

    def faces_to_bytes(self):
        indices = []
        for face in self.faces:
            assert (len(face) == 3)
            indices.extend(list(face))
        assert (len(indices) == self.index_count)
        data_bytes = self.layout.semantics[0].format.encoder(indices)
        self.from_bytes(data_bytes)
        assert (self.num_elements * 3 == self.index_count)

    def bytes_to_faces(self):
        self.faces = []
        for element_id in range(self.num_elements):
            face = self.get_element(element_id).get_value(self.layout.semantics[0])
            self.faces.append(tuple(face))

    def get_bytes(self, semantic=None):
        if self.num_elements * 3 != self.index_count:
            self.faces_to_bytes()
        assert (self.num_elements * 3 == self.index_count)
        return super().get_bytes(semantic)

    def get_format(self):
        return self.layout.get_element(AbstractSemantic(Semantic.Index)).get_format()