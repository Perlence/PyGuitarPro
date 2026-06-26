"""Reader for Guitar Pro 6 (``.gpx``) and Guitar Pro 7 (``.gp``) files.

Both formats wrap a ``score.gpif`` XML document inside a container:

* GP6 ``.gpx`` -- a ``BCFZ``-compressed ``BCFS`` virtual filesystem.  The
  ``BCFZ`` layer is a custom bitstream LZ scheme; the ``BCFS`` layer is a
  sector-based archive.  The decompression algorithm is based on code
  contributed by J. Jorgen von Bargen.
* GP7 ``.gp`` -- a plain ZIP archive with the score at
  ``Content/score.gpif``.

This module exposes :class:`GPXFile`, which mirrors the ``readSong``
interface of the binary readers and delegates the XML-to-:class:`Song`
mapping to :mod:`guitarpro.gpif`.
"""
import io
import struct
import zipfile

from .gpif import GPIFParser
from .models import GPException

__all__ = ('GPXFile', 'decompress', 'extractGPIF')

_HEADER_BCFS = b'BCFS'
_HEADER_BCFZ = b'BCFZ'
_SECTOR_SIZE = 0x1000


class _BitReader:
    """Reads individual bits from a byte string, most significant first."""

    def __init__(self, data):
        self.data = data
        self.byte = 0
        self.bit = 0

    def readBit(self):
        result = (self.data[self.byte] >> (7 - self.bit)) & 1
        self.bit += 1
        if self.bit == 8:
            self.bit = 0
            self.byte += 1
        return result

    def readBits(self, count):
        """Read *count* bits, most significant first."""
        result = 0
        for _ in range(count):
            result = (result << 1) | self.readBit()
        return result

    def readBitsReversed(self, count):
        """Read *count* bits, least significant first."""
        result = 0
        for i in range(count):
            result |= self.readBit() << i
        return result


def decompress(data):
    """Decompress a ``BCFZ`` payload.

    :param data: the bytes following the ``BCFZ`` magic, starting with the
        little-endian uncompressed length.
    """
    expectedLength, = struct.unpack_from('<i', data, 0)
    reader = _BitReader(data[4:])
    result = bytearray()
    while len(result) < expectedLength:
        flag = reader.readBit()
        if flag:
            # Back-reference into the already-decompressed output.
            wordSize = reader.readBits(4)
            offset = reader.readBitsReversed(wordSize)
            size = reader.readBitsReversed(wordSize)
            start = len(result) - offset
            toRead = min(offset, size)
            result += result[start:start + toRead]
        else:
            # Literal run; bytes flow through the bitstream, not byte-aligned.
            size = reader.readBitsReversed(2)
            for _ in range(size):
                result.append(reader.readBits(8))
    return bytes(result)


class GPXFileSystem:
    """Reads the ``BCFS`` sector archive into a name-to-bytes mapping."""

    def __init__(self, data):
        if data[:4] == _HEADER_BCFS:
            data = data[4:]
        self.data = data
        self.files = {}
        self._readBlocks()

    def _readBlocks(self):
        data = self.data
        offset = 0
        while offset + 3 < len(data):
            entryType, = struct.unpack_from('<i', data, offset)
            if entryType == 2:
                name = (data[offset + 0x04:offset + 0x04 + 127]
                        .split(b'\x00')[0].decode('ascii', 'replace'))
                size, = struct.unpack_from('<i', data, offset + 0x8C)
                blockOffset = offset + 0x94
                payload = bytearray()
                index = 0
                while True:
                    block, = struct.unpack_from('<i', data, blockOffset + 4 * index)
                    if block == 0:
                        break
                    start = block * _SECTOR_SIZE
                    payload += data[start:start + _SECTOR_SIZE]
                    index += 1
                self.files[name] = bytes(payload[:size])
            offset += _SECTOR_SIZE

    def read(self, name):
        return self.files[name]


def extractGPIF(data):
    """Return the ``score.gpif`` XML bytes from a ``.gpx`` or ``.gp`` blob."""
    if data[:2] == b'PK':
        # GP7: plain ZIP archive.
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in ('Content/score.gpif', 'score.gpif'):
                if name in archive.namelist():
                    return archive.read(name)
            raise GPException('no score.gpif found in GP7 archive')
    if data[:4] == _HEADER_BCFZ:
        data = decompress(data[4:])
    if data[:4] == _HEADER_BCFS:
        return GPXFileSystem(data).read('score.gpif')
    raise GPException('not a Guitar Pro 6/7 container')


class GPXFile:
    """Wraps a GP6/GP7 container and produces a :class:`Song`."""

    def __init__(self, fp, encoding=None, version=None, versionTuple=None):
        self.data = fp.read()
        self.encoding = encoding
        self.version = version
        self.versionTuple = versionTuple

    def readSong(self):
        gpif = extractGPIF(self.data)
        return GPIFParser(gpif, versionTuple=self.versionTuple).readSong()

    def close(self):
        pass
