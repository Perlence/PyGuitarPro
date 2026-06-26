"""Reader for Guitar Pro 6 (``.gpx``) and Guitar Pro 7 (``.gp``) files.

Both formats wrap a ``score.gpif`` XML document inside a container:

* GP6 ``.gpx`` -- a ``BCFZ``-compressed ``BCFS`` virtual filesystem.  The
  ``BCFZ`` layer is a custom bitstream LZ scheme; the ``BCFS`` layer is a
  sector-based archive.  The decompression algorithm is based on code
  contributed by J. Jorgen von Bargen.
* GP7 ``.gp`` -- a plain ZIP archive with the score at
  ``Content/score.gpif``.

This module exposes :class:`GPXFile`, which mirrors the ``readSong`` and
``writeSong`` interface of the binary readers and delegates the
XML-to-:class:`Song` mapping to :mod:`guitarpro.gpif`.

GP6 files can be written as well as read; the container is rebuilt as a
``BCFZ``-compressed ``BCFS`` archive holding a single ``score.gpif``.  GP7
files are written as a ZIP archive.
"""
import io
import struct
import zipfile

from .gpif import GPIFParser, GPIFWriter
from .models import GPException

__all__ = ('GPXFile', 'decompress', 'compress', 'extractGPIF', 'buildGPX', 'buildGP')

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
        # The final byte of the payload is zero-padded; past the end we
        # keep yielding padding bits so the last token can be decoded.
        if self.byte >= len(self.data):
            return 0
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


class _BitWriter:
    """Writes individual bits to a byte string, most significant first."""

    def __init__(self):
        self.out = bytearray()
        self.current = 0
        self.count = 0

    def writeBit(self, bit):
        self.current = (self.current << 1) | (bit & 1)
        self.count += 1
        if self.count == 8:
            self.out.append(self.current)
            self.current = 0
            self.count = 0

    def writeBits(self, value, count):
        """Write *count* bits of *value*, most significant first."""
        for i in range(count - 1, -1, -1):
            self.writeBit((value >> i) & 1)

    def writeBitsReversed(self, value, count):
        """Write *count* bits of *value*, least significant first."""
        for i in range(count):
            self.writeBit((value >> i) & 1)

    def writeBytes(self, data):
        for byte in data:
            self.writeBits(byte, 8)

    def getvalue(self):
        if self.count:
            # Flush the partial final byte, padding the low bits with zeros.
            self.out.append(self.current << (8 - self.count))
            self.current = 0
            self.count = 0
        return bytes(self.out)


def compress(data):
    """Compress *data* into a ``BCFZ`` payload (length prefix + bitstream).

    The BCFZ scheme allows back-references, but a stream of plain literal
    runs is equally valid and decodes identically.  Emitting literals only
    keeps the encoder linear and simple; the modest size overhead (a 3-bit
    header per three bytes) is acceptable for written files.
    """
    writer = _BitWriter()
    for offset in range(0, len(data), 3):
        chunk = data[offset:offset + 3]
        writer.writeBit(0)
        writer.writeBitsReversed(len(chunk), 2)
        writer.writeBytes(chunk)
    return struct.pack('<i', len(data)) + writer.getvalue()


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


def buildBCFS(files):
    """Build a ``BCFS`` image from a name-to-bytes mapping.

    Layout (in coordinates after the 4-byte ``BCFS`` magic, which is how the
    reader indexes the image): sector 0 is reserved, one entry sector per file
    follows, then the file data sectors.  Entry sectors are tagged with type
    ``2`` and list the absolute indices of their data sectors.
    """
    names = list(files)
    sectors = [bytearray(_SECTOR_SIZE)]  # reserved header sector

    # Assign contiguous data sectors to each file.
    dataStart = 1 + len(names)
    cursor = dataStart
    blockMap = {}
    dataSectors = []
    for name in names:
        payload = files[name]
        sectorCount = max(1, -(-len(payload) // _SECTOR_SIZE))
        blockMap[name] = list(range(cursor, cursor + sectorCount))
        for k in range(sectorCount):
            chunk = payload[k * _SECTOR_SIZE:(k + 1) * _SECTOR_SIZE]
            dataSectors.append(chunk + b'\x00' * (_SECTOR_SIZE - len(chunk)))
        cursor += sectorCount

    # Entry sectors.
    for name in names:
        entry = bytearray(_SECTOR_SIZE)
        struct.pack_into('<i', entry, 0x00, 2)
        encoded = name.encode('cp1252')[:127]
        entry[0x04:0x04 + len(encoded)] = encoded
        struct.pack_into('<i', entry, 0x8C, len(files[name]))
        for index, block in enumerate(blockMap[name]):
            struct.pack_into('<i', entry, 0x94 + 4 * index, block)
        sectors.append(entry)

    sectors.extend(bytearray(s) for s in dataSectors)
    return _HEADER_BCFS + b''.join(bytes(s) for s in sectors)


def buildGPX(song):
    """Serialize *song* into GP6 (``.gpx``) container bytes."""
    gpif = GPIFWriter(song).write()
    image = buildBCFS({'score.gpif': gpif})
    return _HEADER_BCFZ + compress(image)


def buildGP(song):
    """Serialize *song* into GP7 (``.gp``) ZIP container bytes."""
    gpif = GPIFWriter(song).write()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('VERSION', '7.0')
        archive.writestr('Content/score.gpif', gpif)
    return buffer.getvalue()


class GPXFile:
    """Wraps a GP6/GP7 container, reading or writing a :class:`Song`."""

    def __init__(self, fp, encoding=None, version=None, versionTuple=None):
        self.fp = fp
        self.encoding = encoding
        self.version = version
        self.versionTuple = versionTuple

    def readSong(self):
        gpif = extractGPIF(self.fp.read())
        return GPIFParser(gpif, versionTuple=self.versionTuple).readSong()

    def writeSong(self, song):
        if self.version == 'gp':
            self.fp.write(buildGP(song))
        else:
            self.fp.write(buildGPX(song))

    def close(self):
        pass
