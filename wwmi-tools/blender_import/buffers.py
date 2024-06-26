
import io
import re
import struct
import numpy
import collections
import textwrap

from mathutils import Matrix, Vector


class Fatal(Exception): pass


# TODO: Support more DXGI formats:
f32_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]32)+_FLOAT''')
f16_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]16)+_FLOAT''')
u32_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]32)+_UINT''')
u16_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]16)+_UINT''')
u8_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]8)+_UINT''')
s32_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]32)+_SINT''')
s16_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]16)+_SINT''')
s8_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]8)+_SINT''')
unorm16_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]16)+_UNORM''')
unorm8_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]8)+_UNORM''')
snorm16_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]16)+_SNORM''')
snorm8_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD]8)+_SNORM''')

misc_float_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD][0-9]+)+_(?:FLOAT|UNORM|SNORM)''')
misc_int_pattern = re.compile(r'''(?:DXGI_FORMAT_)?(?:[RGBAD][0-9]+)+_[SU]INT''')


def EncoderDecoder(fmt):
    if f32_pattern.match(fmt):
        return (lambda data: b''.join(struct.pack('<f', x) for x in data),
                lambda data: numpy.frombuffer(data, numpy.float32).tolist())
    if f16_pattern.match(fmt):
        return (lambda data: numpy.fromiter(data, numpy.float16).tobytes(),
                lambda data: numpy.frombuffer(data, numpy.float16).tolist())
    if u32_pattern.match(fmt):
        return (lambda data: numpy.fromiter(data, numpy.uint32).tobytes(),
                lambda data: numpy.frombuffer(data, numpy.uint32).tolist())
    if u16_pattern.match(fmt):
        return (lambda data: numpy.fromiter(data, numpy.uint16).tobytes(),
                lambda data: numpy.frombuffer(data, numpy.uint16).tolist())
    if u8_pattern.match(fmt):
        return (lambda data: numpy.fromiter(data, numpy.uint8).tobytes(),
                lambda data: numpy.frombuffer(data, numpy.uint8).tolist())
    if s32_pattern.match(fmt):
        return (lambda data: numpy.fromiter(data, numpy.int32).tobytes(),
                lambda data: numpy.frombuffer(data, numpy.int32).tolist())
    if s16_pattern.match(fmt):
        return (lambda data: numpy.fromiter(data, numpy.int16).tobytes(),
                lambda data: numpy.frombuffer(data, numpy.int16).tolist())
    if s8_pattern.match(fmt):
        return (lambda data: numpy.fromiter(data, numpy.int8).tobytes(),
                lambda data: numpy.frombuffer(data, numpy.int8).tolist())

    if unorm16_pattern.match(fmt):
        return (
            lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 65535.0)).astype(numpy.uint16).tobytes(),
            lambda data: (numpy.frombuffer(data, numpy.uint16) / 65535.0).tolist())
    if unorm8_pattern.match(fmt):
        return (lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 255.0)).astype(numpy.uint8).tobytes(),
                lambda data: (numpy.frombuffer(data, numpy.uint8) / 255.0).tolist())
    if snorm16_pattern.match(fmt):
        return (
            lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 32767.0)).astype(numpy.int16).tobytes(),
            lambda data: (numpy.frombuffer(data, numpy.int16) / 32767.0).tolist())
    if snorm8_pattern.match(fmt):
        return (lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 127.0)).astype(numpy.int8).tobytes(),
                lambda data: (numpy.frombuffer(data, numpy.int8) / 127.0).tolist())

    raise Fatal('File uses an unsupported DXGI Format: %s' % fmt)


components_pattern = re.compile(r'''(?<![0-9])[0-9]+(?![0-9])''')


def format_components(fmt):
    return len(components_pattern.findall(fmt))


def format_size(fmt):
    matches = components_pattern.findall(fmt)
    return sum(map(int, matches)) // 8


class InputLayoutElement(object):
    def __init__(self, arg):
        if isinstance(arg, io.IOBase):
            self.from_file(arg)
        else:
            self.from_dict(arg)

        self.encoder, self.decoder = EncoderDecoder(self.Format)

    def from_file(self, f):
        self.SemanticName = self.next_validate(f, 'SemanticName')
        self.SemanticIndex = int(self.next_validate(f, 'SemanticIndex'))
        self.Format = self.next_validate(f, 'Format')
        self.InputSlot = int(self.next_validate(f, 'InputSlot'))
        self.AlignedByteOffset = self.next_validate(f, 'AlignedByteOffset')
        if self.AlignedByteOffset == 'append':
            raise Fatal('Input layouts using "AlignedByteOffset=append" are not yet supported')
        self.AlignedByteOffset = int(self.AlignedByteOffset)
        self.InputSlotClass = self.next_validate(f, 'InputSlotClass')
        self.InstanceDataStepRate = int(self.next_validate(f, 'InstanceDataStepRate'))

    def to_dict(self):
        d = {}
        d['SemanticName'] = self.SemanticName
        d['SemanticIndex'] = self.SemanticIndex
        d['Format'] = self.Format
        d['InputSlot'] = self.InputSlot
        d['AlignedByteOffset'] = self.AlignedByteOffset
        d['InputSlotClass'] = self.InputSlotClass
        d['InstanceDataStepRate'] = self.InstanceDataStepRate
        return d

    def to_string(self, indent=2):
        return textwrap.indent(textwrap.dedent('''
            SemanticName: %s
            SemanticIndex: %i
            Format: %s
            InputSlot: %i
            AlignedByteOffset: %i
            InputSlotClass: %s
            InstanceDataStepRate: %i
        ''').lstrip() % (
            self.SemanticName,
            self.SemanticIndex,
            self.Format,
            self.InputSlot,
            self.AlignedByteOffset,
            self.InputSlotClass,
            self.InstanceDataStepRate,
        ), ' ' * indent)

    def from_dict(self, d):
        self.SemanticName = d['SemanticName']
        self.SemanticIndex = d['SemanticIndex']
        self.Format = d['Format']
        self.InputSlot = d['InputSlot']
        self.AlignedByteOffset = d['AlignedByteOffset']
        self.InputSlotClass = d['InputSlotClass']
        self.InstanceDataStepRate = d['InstanceDataStepRate']
        self.format_len = format_components(self.Format)

    @staticmethod
    def next_validate(f, field):
        line = next(f).strip()
        assert (line.startswith(field + ': '))
        return line[len(field) + 2:]

    @property
    def name(self):
        if self.SemanticIndex:
            return '%s%i' % (self.SemanticName, self.SemanticIndex)
        return self.SemanticName

    def pad(self, data, val):
        # padding = format_components(self.Format) - len(data)
        # assert (padding >= 0)
        # return data + [val] * padding
        padding = self.format_len - len(data)
        assert(padding >= 0)
        data.extend([val]*padding)
        return data

    def clip(self, data):
        return data[:format_components(self.Format)]

    def size(self):
        return format_size(self.Format)

    def is_float(self):
        return misc_float_pattern.match(self.Format)

    def is_int(self):
        return misc_int_pattern.match(self.Format)

    def encode(self, data):
        # print(self.Format, data)
        return self.encoder(data)

    def decode(self, data):
        return self.decoder(data)

    def __eq__(self, other):
        return \
                self.SemanticName == other.SemanticName and \
                self.SemanticIndex == other.SemanticIndex and \
                self.Format == other.format and \
                self.InputSlot == other.InputSlot and \
                self.AlignedByteOffset == other.AlignedByteOffset and \
                self.InputSlotClass == other.InputSlotClass and \
                self.InstanceDataStepRate == other.InstanceDataStepRate


class InputLayout(object):
    def __init__(self, custom_prop=[], stride=0):
        self.elems = collections.OrderedDict()
        self.stride = stride
        for item in custom_prop:
            elem = InputLayoutElement(item)
            self.elems[elem.name] = elem

    def serialise(self):
        return [x.to_dict() for x in self.elems.values()]

    def to_string(self):
        ret = ''
        for i, elem in enumerate(self.elems.values()):
            ret += 'element[%i]:\n' % i
            ret += elem.to_string()
        return ret

    def parse_element(self, f):
        elem = InputLayoutElement(f)
        self.elems[elem.name] = elem

    def __iter__(self):
        return iter(self.elems.values())

    def __getitem__(self, semantic):
        return self.elems[semantic]

    def encode(self, vertex):
        buf = bytearray(self.stride)

        for semantic, data in vertex.items():
            if semantic.startswith('~'):
                continue
            elem = self.elems[semantic]
            data = elem.encode(data)
            buf[elem.AlignedByteOffset:elem.AlignedByteOffset + len(data)] = data

        assert (len(buf) == self.stride)
        return buf

    def decode(self, buf):
        vertex = {}
        for elem in self.elems.values():
            data = buf[elem.AlignedByteOffset:elem.AlignedByteOffset + elem.size()]
            vertex[elem.name] = elem.decode(data)
        return vertex

    def __eq__(self, other):
        return self.elems == other.elems


class VertexBuffer(object):
    vb_elem_pattern = re.compile(r'''vb\d+\[\d*\]\+\d+ (?P<semantic>[^:]+): (?P<data>.*)$''')

    # Python gotcha - do not set layout=InputLayout() in the default function
    # parameters, as they would all share the *same* InputLayout since the
    # default values are only evaluated once on file load
    def __init__(self, f=None, layout=None, load_vertices=True):
        self.vertices = []
        self.layout = layout and layout or InputLayout()
        self.first = 0
        self.vertex_count = 0
        self.offset = 0
        self.topology = 'trianglelist'

        if f is not None:
            self.parse_vb_txt(f, load_vertices)

    def parse_vb_txt(self, f, load_vertices):
        for line in map(str.strip, f):
            # print(line)
            if line.startswith('byte offset:'):
                self.offset = int(line[13:])
            if line.startswith('first vertex:'):
                self.first = int(line[14:])
            if line.startswith('vertex count:'):
                self.vertex_count = int(line[14:])
            if line.startswith('stride:'):
                self.layout.stride = int(line[7:])
            if line.startswith('element['):
                self.layout.parse_element(f)
            if line.startswith('topology:'):
                self.topology = line[10:]
                if line != 'topology: trianglelist':
                    raise Fatal('"%s" is not yet supported' % line)
            if line.startswith('vertex-data:'):
                if not load_vertices:
                    return
                self.parse_vertex_data(f)
        assert (len(self.vertices) == self.vertex_count)

    def parse_vb_bin(self, f):
        f.seek(self.offset)
        # XXX: Should we respect the first/base vertex?
        # f.seek(self.first * self.layout.stride, whence=1)
        self.first = 0
        while True:
            vertex = f.read(self.layout.stride)
            if not vertex:
                break
            self.vertices.append(self.layout.decode(vertex))
        # We intentionally disregard the vertex count when loading from a
        # binary file, as we assume frame analysis might have only dumped a
        # partial buffer to the .txt files (e.g. if this was from a dump where
        # the draw call index count was overridden it may be cut short, or
        # where the .txt files contain only sub-meshes from each draw call and
        # we are loading the .buf file because it contains the entire mesh):
        self.vertex_count = len(self.vertices)

    def append(self, vertex):
        self.vertices.append(vertex)
        self.vertex_count += 1

    def parse_vertex_data(self, f):
        vertex = {}
        for line in map(str.strip, f):
            # print(line)
            if line.startswith('instance-data:'):
                break

            match = self.vb_elem_pattern.match(line)
            if match:
                vertex[match.group('semantic')] = self.parse_vertex_element(match)
            elif line == '' and vertex:
                self.vertices.append(vertex)
                vertex = {}
        if vertex:
            self.vertices.append(vertex)

    def parse_vertex_element(self, match):
        fields = match.group('data').split(',')

        if self.layout[match.group('semantic')].Format.endswith('INT'):
            return tuple(map(int, fields))

        return tuple(map(float, fields))

    def remap_blendindices(self, obj, mapping):
        def lookup_vgmap(x):
            vgname = obj.vertex_groups[x].name
            return mapping.get(vgname, mapping.get(x, x))

        for vertex in self.vertices:
            for semantic in list(vertex):
                if semantic.startswith('BLENDINDICES'):
                    vertex['~' + semantic] = vertex[semantic]
                    vertex[semantic] = tuple(lookup_vgmap(x) for x in vertex[semantic])

    def revert_blendindices_remap(self):
        # Significantly faster than doing a deep copy
        for vertex in self.vertices:
            for semantic in list(vertex):
                if semantic.startswith('BLENDINDICES'):
                    vertex[semantic] = vertex['~' + semantic]
                    del vertex['~' + semantic]

    def disable_blendweights(self):
        for vertex in self.vertices:
            for semantic in list(vertex):
                if semantic.startswith('BLENDINDICES'):
                    vertex[semantic] = (0, 0, 0, 0)

    def write(self, output, operator=None):
        for vertex in self.vertices:
            output.write(self.layout.encode(vertex))

        msg = 'Wrote %i vertices to %s' % (len(self), output.name)
        if operator:
            operator.report({'INFO'}, msg)
        else:
            print(msg)

    def encode(self, vb_id):
        result = bytearray()
        for vertex in self.vertices:
            result += self.layout.encode(vertex)
        print(f'Encoded {len(self)} vertices for {vb_id}')
        return result

    def __len__(self):
        return len(self.vertices)

    def merge(self, other):
        if self.layout != other.layout:
            raise Fatal(
                'Vertex buffers have different input layouts - ensure you are only trying to merge the same vertex buffer split across multiple draw calls')
        if self.first != other.first:
            # FIXME: Future 3DMigoto might automatically set first from the
            # index buffer and chop off unreferenced vertices to save space
            raise Fatal(
                'Cannot merge multiple vertex buffers - please check for updates of the 3DMigoto import script, or import each buffer separately')
        self.vertices.extend(other.vertices[self.vertex_count:])
        self.vertex_count = max(self.vertex_count, other.vertex_count)
        assert (len(self.vertices) == self.vertex_count)

    def wipe_semantic_for_testing(self, semantic, val=0):
        print('WARNING: WIPING %s FOR TESTING PURPOSES!!!' % semantic)
        semantic, _, components = semantic.partition('.')
        if components:
            components = [{'x': 0, 'y': 1, 'z': 2, 'w': 3}[c] for c in components]
        else:
            components = range(4)
        for vertex in self.vertices:
            for s in list(vertex):
                if s == semantic:
                    v = list(vertex[semantic])
                    for component in components:
                        if component < len(v):
                            v[component] = val
                    vertex[semantic] = v


class IndexBuffer(object):
    def __init__(self, *args, load_indices=True):
        self.faces = []
        self.first = 0
        self.index_count = 0
        self.format = 'DXGI_FORMAT_UNKNOWN'
        self.offset = 0
        self.topology = 'trianglelist'
        self.sha256 = None

        if isinstance(args[0], io.IOBase):
            assert (len(args) == 1)
            self.parse_ib_txt(args[0], load_indices)
        else:
            self.format, = args

        self.encoder, self.decoder = EncoderDecoder(self.format)

    def append(self, face):
        self.faces.append(face)
        self.index_count += len(face)

    def parse_ib_txt(self, f, load_indices):
        for line in map(str.strip, f):
            if line.startswith('byte offset:'):
                self.offset = int(line[13:])
            if line.startswith('first index:'):
                self.first = int(line[13:])
            elif line.startswith('index count:'):
                self.index_count = int(line[13:])
            elif line.startswith('topology:'):
                self.topology = line[10:]
                if line != 'topology: trianglelist':
                    raise Fatal('"%s" is not yet supported' % line)
            elif line.startswith('format:'):
                self.format = line[8:]
            elif line == '':
                if not load_indices:
                    return
                self.parse_index_data(f)
        assert (len(self.faces) * 3 == self.index_count)

    def parse_ib_bin(self, f):
        f.seek(self.offset)
        stride = format_size(self.format)
        # XXX: Should we respect the first index?
        # f.seek(self.first * stride, whence=1)
        self.first = 0

        face = []
        while True:
            index = f.read(stride)
            if not index:
                break
            face.append(*self.decoder(index))
            if len(face) == 3:
                self.faces.append(tuple(face))
                face = []
        assert (len(face) == 0)

        # We intentionally disregard the index count when loading from a
        # binary file, as we assume frame analysis might have only dumped a
        # partial buffer to the .txt files (e.g. if this was from a dump where
        # the draw call index count was overridden it may be cut short, or
        # where the .txt files contain only sub-meshes from each draw call and
        # we are loading the .buf file because it contains the entire mesh):
        self.index_count = len(self.faces) * 3

    def parse_index_data(self, f):
        for line in map(str.strip, f):
            face = tuple(map(int, line.split()))
            assert (len(face) == 3)
            self.faces.append(face)

    def merge(self, other):
        if self.format != other.format:
            raise Fatal(
                'Index buffers have different formats - ensure you are only trying to merge the same index buffer split across multiple draw calls')
        self.first = min(self.first, other.first)
        self.index_count += other.index_count
        self.faces.extend(other.faces)

    def write(self, output, operator=None):
        for face in self.faces:
            output.write(self.encoder(face))

        msg = 'Wrote %i indices to %s' % (len(self), output.name)
        if operator:
            operator.report({'INFO'}, msg)
        else:
            print(msg)

    def encode(self, ib_id):
        result = bytearray()
        for face in self.faces:
            result += self.encoder(face)
        print(f'Encoded {len(self)} indices for {ib_id}')
        return result

    def __len__(self):
        return len(self.faces) * 3


class ConstantBuffer(object):
    def __init__(self, f, start_idx, end_idx):
        self.entries = []
        entry = []
        i = 0
        for line in map(str.strip, f):
            if line.startswith('buf') or line.startswith('cb'):
                entry.append(float(line.split()[1]))
                if len(entry) == 4:
                    if i >= start_idx:
                        self.entries.append(entry)
                    else:
                        print('Skipping', entry)
                    entry = []
                    i += 1
                    if end_idx and i > end_idx:
                        break
        assert (entry == [])

    def as_3x4_matrices(self):
        return [Matrix(self.entries[i:i + 3]) for i in range(0, len(self.entries), 3)]



