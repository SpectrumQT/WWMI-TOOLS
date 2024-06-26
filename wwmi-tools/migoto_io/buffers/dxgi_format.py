import numpy
import struct

from enum import Enum
from typing import Tuple


class DXGIEncoderDecoder(Enum):
    FLOAT32 = (lambda data: b''.join(struct.pack('<f', x) for x in data),
               lambda data: numpy.frombuffer(data, numpy.float32).tolist())
    FLOAT16 = (lambda data: numpy.fromiter(data, numpy.float16).tobytes(),
               lambda data: numpy.frombuffer(data, numpy.float16).tolist())
    UINT32 = (lambda data: numpy.fromiter(data, numpy.uint32).tobytes(),
              lambda data: numpy.frombuffer(data, numpy.uint32).tolist())
    UINT16 = (lambda data: numpy.fromiter(data, numpy.uint16).tobytes(),
              lambda data: numpy.frombuffer(data, numpy.uint16).tolist())
    UINT8 = (lambda data: numpy.fromiter(data, numpy.uint8).tobytes(),
             lambda data: numpy.frombuffer(data, numpy.uint8).tolist())
    SINT32 = (lambda data: numpy.fromiter(data, numpy.int32).tobytes(),
              lambda data: numpy.frombuffer(data, numpy.int32).tolist())
    SINT16 = (lambda data: numpy.fromiter(data, numpy.int16).tobytes(),
              lambda data: numpy.frombuffer(data, numpy.int16).tolist())
    SINT8 = (lambda data: numpy.fromiter(data, numpy.int8).tobytes(),
             lambda data: numpy.frombuffer(data, numpy.int8).tolist())
    UNORM16 = (
        lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 65535.0)).astype(numpy.uint16).tobytes(),
        lambda data: (numpy.frombuffer(data, numpy.uint16) / 65535.0).tolist())
    UNORM8 = (lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 255.0)).astype(numpy.uint8).tobytes(),
              lambda data: (numpy.frombuffer(data, numpy.uint8) / 255.0).tolist())
    SNORM16 = (lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 32767.0)).astype(numpy.int16).tobytes(),
               lambda data: (numpy.frombuffer(data, numpy.int16) / 32767.0).tolist())
    SNORM8 = (lambda data: numpy.around((numpy.fromiter(data, numpy.float32) * 127.0)).astype(numpy.int8).tobytes(),
              lambda data: (numpy.frombuffer(data, numpy.int8) / 127.0).tolist())


class DXGIFormat(Enum):
    def __new__(cls, fmt, encoder_decoder, byte_width):
        obj = object.__new__(cls)
        obj._value_ = fmt
        obj.format = fmt
        obj.encoder = encoder_decoder.value[0]
        obj.decoder = encoder_decoder.value[1]
        obj.byte_width = byte_width
        return obj

    def get_format(self):
        return 'DXGI_FORMAT_' + self.format

    # Float 32
    R32G32B32A32_FLOAT = 'R32G32B32A32_FLOAT', DXGIEncoderDecoder.FLOAT32, 16
    R32G32B32_FLOAT = 'R32G32B32_FLOAT', DXGIEncoderDecoder.FLOAT32, 12
    R32G32_FLOAT = 'R32G32_FLOAT', DXGIEncoderDecoder.FLOAT32, 8
    R32_FLOAT = 'R32_FLOAT', DXGIEncoderDecoder.FLOAT32, 4
    # Float 16
    R16G16B16A16_FLOAT = 'R16G16B16A16_FLOAT', DXGIEncoderDecoder.FLOAT16, 8
    R16G16B16_FLOAT = 'R16G16B16_FLOAT', DXGIEncoderDecoder.FLOAT16, 6
    R16G16_FLOAT = 'R16G16_FLOAT', DXGIEncoderDecoder.FLOAT16, 4
    R16_FLOAT = 'R16_FLOAT', DXGIEncoderDecoder.FLOAT16, 2
    # UINT 32
    R32G32B32A32_UINT = 'R32G32B32A32_UINT', DXGIEncoderDecoder.UINT32, 16
    R32G32B32_UINT = 'R32G32B32_UINT', DXGIEncoderDecoder.UINT32, 12
    R32G32_UINT = 'R32G32_UINT', DXGIEncoderDecoder.UINT32, 8
    R32_UINT = 'R32_UINT', DXGIEncoderDecoder.UINT32, 4
    # UINT 16
    R16G16B16A16_UINT = 'R16G16B16A16_UINT', DXGIEncoderDecoder.UINT16, 8
    R16G16B16_UINT = 'R16G16B16_UINT', DXGIEncoderDecoder.UINT16, 6
    R16G16_UINT = 'R16G16_UINT', DXGIEncoderDecoder.UINT16, 4
    R16_UINT = 'R16_UINT', DXGIEncoderDecoder.UINT16, 2
    # UINT 8
    R8G8B8A8_UINT = 'R8G8B8A8_UINT', DXGIEncoderDecoder.UINT8, 4
    R8G8B8_UINT = 'R8G8B8_UINT', DXGIEncoderDecoder.UINT8, 3
    R8G8_UINT = 'R8G8_UINT', DXGIEncoderDecoder.UINT8, 2
    R8_UINT = 'R8_UINT', DXGIEncoderDecoder.UINT8, 1
    # SINT 32
    R32G32B32A32_SINT = 'R32G32B32A32_SINT', DXGIEncoderDecoder.SINT32, 16
    R32G32B32_SINT = 'R32G32B32_SINT', DXGIEncoderDecoder.SINT32, 12
    R32G32_SINT = 'R32G32_SINT', DXGIEncoderDecoder.SINT32, 8
    R32_SINT = 'R32_SINT', DXGIEncoderDecoder.SINT32, 4
    # SINT 16
    R16G16B16A16_SINT = 'R16G16B16A16_SINT', DXGIEncoderDecoder.SINT16, 8
    R16G16B16_SINT = 'R16G16B16_SINT', DXGIEncoderDecoder.SINT16, 6
    R16G16_SINT = 'R16G16_SINT', DXGIEncoderDecoder.SINT16, 4
    R16_SINT = 'R16_SINT', DXGIEncoderDecoder.SINT16, 2
    # SINT 8
    R8G8B8A8_SINT = 'R8G8B8A8_SINT', DXGIEncoderDecoder.SINT8, 4
    R8G8B8_SINT = 'R8G8B8_SINT', DXGIEncoderDecoder.SINT8, 3
    R8G8_SINT = 'R8G8_SINT', DXGIEncoderDecoder.SINT8, 2
    R8_SINT = 'R8_SINT', DXGIEncoderDecoder.SINT8, 1
    # UNORM 16
    R16G16B16A16_UNORM = 'R16G16B16A16_UNORM', DXGIEncoderDecoder.UNORM16, 8
    R16G16B16_UNORM = 'R16G16B16_UNORM', DXGIEncoderDecoder.UNORM16, 6
    R16G16_UNORM = 'R16G16_UNORM', DXGIEncoderDecoder.UNORM16, 4
    R16_UNORM = 'R16_UNORM', DXGIEncoderDecoder.UNORM16, 2
    # UNORM 8
    R8G8B8A8_UNORM = 'R8G8B8A8_UNORM', DXGIEncoderDecoder.UNORM8, 4
    R8G8B8_UNORM = 'R8G8B8_UNORM', DXGIEncoderDecoder.UNORM8, 3
    R8G8_UNORM = 'R8G8_UNORM', DXGIEncoderDecoder.UNORM8, 2
    R8_UNORM = 'R8_UNORM', DXGIEncoderDecoder.UNORM8, 1
    # SNORM 16
    R16G16B16A16_SNORM = 'R16G16B16A16_SNORM', DXGIEncoderDecoder.SNORM16, 8
    R16G16B16_SNORM = 'R16G16B16_SNORM', DXGIEncoderDecoder.SNORM16, 6
    R16G16_SNORM = 'R16G16_SNORM', DXGIEncoderDecoder.SNORM16, 4
    R16_SNORM = 'R16_SNORM', DXGIEncoderDecoder.SNORM16, 2
    # SNORM 8
    R8G8B8A8_SNORM = 'R8G8B8A8_SNORM', DXGIEncoderDecoder.SNORM8, 4
    R8G8B8_SNORM = 'R8G8B8_SNORM', DXGIEncoderDecoder.SNORM8, 3
    R8G8_SNORM = 'R8G8_SNORM', DXGIEncoderDecoder.SNORM8, 2
    R8_SNORM = 'R8_SNORM', DXGIEncoderDecoder.SNORM8, 1
