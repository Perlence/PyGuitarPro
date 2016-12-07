# -*- coding: utf-8 -*-
"""
Parts of the GPX manipulation are based on code contributed by J.Jørgen
von Bargen.
"""

import os
import struct
from binascii import unhexlify, hexlify
from collections import OrderedDict
from hashlib import md5
from io import BytesIO

from six import string_types

from .utils import bit_length


_HEADER_BCFS = b'BCFS'
_HEADER_BCFZ = b'BCFZ'


def decompress(stream):
    """Decompress the given stream using the GPX compression format."""
    if isinstance(stream, BitsIO):
        fp = stream
    elif hasattr(stream, 'read'):
        fp = BitsIO(stream)
    elif isinstance(stream, string_types):
        fp = BitsIO(BytesIO(stream))
    else:
        raise TypeError('given stream cannot be read')

    result = b''
    expected, = struct.unpack('<i', fp.read(4))
    while len(result) < expected:
        # Compression flag.
        flag = fp.readbit()
        if flag:
            # Get offset and size of the content we need to read. Compressed
            # does mean we already have read the data and need to copy it from
            # our result buffer to the end.
            wordsize = fp.readbits(4)  # word size: 0 .. 15
            offset = fp.readbits(wordsize, reversed_=True)
            size = fp.readbits(wordsize, reversed_=True)

            # The offset is relative to the end.
            position = len(result) - offset
            to_read = min(offset, size)

            # Get the subbuffer storing the data and add it again to the end.
            result += result[position:position + to_read]
        else:
            # On raw content we need to read the data from the source buffer.
            size = fp.readbits(2, reversed_=True)
            for _ in range(size):
                result += fp.read(1)
    return result


def compress(stream):
    """Compress the given stream using the GPX compression format."""
    bits = BitsIO(BytesIO())
    buffer = b''
    expected = len(stream)
    position = 0
    while position < expected:
        subbuffer = b''
        offset = -1
        for i in range(position, expected):
            subbuffer = stream[position:i + 1]
            try:
                offset = buffer.rindex(subbuffer, -32768)
            except ValueError:
                if offset > -1:
                    subbuffer = subbuffer[:-1]
                    position = i
                    break
                if len(subbuffer) > 2:
                    position = i + 1
                    break
        else:
            position = expected
        if offset < 0:
            bits.writebit(0)
            bits.writebits(len(subbuffer), length=2, reversed_=True)
            bits.write(subbuffer)
        else:
            reversed_offset = len(buffer) - offset
            length = len(subbuffer)
            wordsize = max(map(bit_length, (reversed_offset, length)))
            bits.writebit(1)
            bits.writebits(wordsize, length=4)
            bits.writebits(reversed_offset, length=wordsize, reversed_=True)
            bits.writebits(length, length=wordsize, reversed_=True)
        buffer += subbuffer

    bits.flush()
    bits.seek(0)
    return struct.pack('<i', expected) + bits.read()


class BitsIO(object):

    def __init__(self, stream):
        self._stream = stream
        self._current = None
        self._position = 0

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def seek(self, offset):
        self._current = None
        self._position = offset * 8
        self._stream.seek(offset)

    def read(self, size=-1):
        if size == -1:
            bits = self.readbits(-1, pad=True)
        else:
            bits = self.readbits(size * 8, pad=True)
        return self._int_to_bytes(bits)

    def _int_to_bytes(self, value):
        result = hex(value)[2:].rstrip('L').encode('ascii')
        if len(result) % 2:
            result = b'0' + result
        return unhexlify(result)

    def readbits(self, size=-1, reversed_=False, pad=False):
        if size == -1:
            bits = list(iter(self.readbit, None))
        else:
            bits = [self.readbit() for _ in range(size)]
        return self._bits_to_int(bits, reversed_, pad)

    def readbit(self):
        local_position = self._position % 8
        try:
            # Need a new byte?
            if local_position == 0:
                self._current, = struct.unpack('B', self._stream.read(1))
            # Shift the desired byte to the least significant bit and
            # get the value using masking.
            value = (self._current >> (7 - local_position)) & 0x01
            self._position += 1
            return value
        except struct.error:
            return

    def _bits_to_int(self, bits, reversed_, pad):
        if pad:
            padding = len(bits) % 8
            if padding:
                bits += [0] * padding
        if reversed_:
            bits = reversed(bits)
        strbits = [str(bit) for bit in bits if bit is not None]
        return int(''.join(strbits), 2)

    def write(self, string):
        return self.writebits(self._bytes_to_int(string), 8 * len(string))

    def _bytes_to_int(self, string):
        return int(hexlify(string), 16)

    def writebits(self, integer, length=None, reversed_=False):
        written = 0
        for bit in self._int_to_bits(integer, length, reversed_):
            written += self.writebit(bit)
        return written

    def _int_to_bits(self, integer, length, reversed_):
        binary = bin(integer)[2:].rstrip('L').encode('ascii')
        if length:
            binary = b'0' * (length - len(binary)) + binary
        result = list(map(int, binary))
        if not reversed_:
            return result
        else:
            return reversed(result)

    def writebit(self, bit):
        written = 0
        local_position = self._position % 8
        self._current = (self._current or 0) | bit << (7 - local_position)
        if local_position == 7:
            self._stream.write(struct.pack('B', self._current))
            self._current = None
            written = 1
        self._position += 1
        return written

    def flush(self):
        if self._current is not None:
            self._stream.write(struct.pack('B', self._current))
            self._position += 8 - self._position % 8
        self._stream.flush()


class GPXFileSystem(object):

    def __init__(self, stream, mode='r'):
        self.files = OrderedDict()
        self.mode = key = mode.replace('b', '')[0]
        if isinstance(stream, string_types):
            self._filePassed = 0
            self.filename = stream
            modeDict = {'r': 'rb', 'w': 'wb', 'a': 'r+b'}
            try:
                fp = open(stream, modeDict[mode])
            except IOError:
                if mode == 'a':
                    mode = key = 'w'
                    fp = open(stream, modeDict[mode])
                else:
                    raise
        else:
            self._filePassed = 1
            fp = stream
            self.filename = getattr(stream, 'name', None)

        self.fp = fp

        if key == 'r':
            self._readContents()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        """Close the file, and for mode "w" and "a" write the ending
        records."""
        self.fp.close()

    def namelist(self):
        """Return a list of file names in the archive."""
        return self.files.keys()

    def open(self, name, mode='r'):
        if mode not in ('r', 'U', 'rU'):
            raise RuntimeError('open() requires mode "r", "U", or "rU"')
        if not self.fp:
            raise RuntimeError(
                'Attempt to read ZIP archive that was already closed')
        return BytesIO(self.files[name].data)

    def extract(self, member, path=None):
        member = self.files[member]
        if path is None:
            path = os.getcwd()
        return self._extract_member(member, path)

    def extractall(self, path=None, members=None):
        """Extract all members from the archive to the current working
        directory. `path' specifies a different directory to extract to.
        `members' is optional and must be a subset of the list returned by
        namelist().
        """
        if members is None:
            members = self.namelist()

        for name in members:
            self.extract(name, path)

    def _extract_member(self, member, targetpath):
        """Extract the ZipInfo object 'member' to a physical file on the path
        targetpath."""
        # build the destination pathname, replacing
        # forward slashes to platform specific separators.
        # Strip trailing path separator, unless it represents the root.
        if (targetpath[-1:] in (os.path.sep, os.path.altsep)
                and len(os.path.splitdrive(targetpath)[1]) > 1):
            targetpath = targetpath[:-1]

        # don't include leading "/" from file name if present
        if member.filename[0] == '/':
            targetpath = os.path.join(targetpath, member.filename[1:])
        else:
            targetpath = os.path.join(targetpath, member.filename)

        targetpath = os.path.normpath(targetpath)

        # Create all upper directories if necessary.
        upperdirs = os.path.dirname(targetpath)
        if upperdirs and not os.path.exists(upperdirs):
            os.makedirs(upperdirs)

        if member.filename[-1] == '/':
            if not os.path.isdir(targetpath):
                os.mkdir(targetpath)
            return targetpath

        source = member.data
        with open(targetpath, "wb") as target:
            target.write(source)

        return targetpath

    def printdir(self):
        raise NotImplementedError

    def read(self, name):
        return self.files[name].data

    def write(self, filename, arcname=None):
        raise NotImplementedError

    def writestr(self, arcname, bytes_):
        raise NotImplementedError

    def _readContents(self):
        header = self.fp.read(4)
        if header == _HEADER_BCFZ:
            decompressed = decompress(self.fp)[4:]
        elif header == _HEADER_BCFS:
            decompressed = self.fp.read()
        else:
            pass
        self._readBlock(decompressed)

    def _readBlock(self, data):
        # The decompressed block contains a list of filesystem entries. As long
        # as we have data we will try to read more entries.

        # The first sector (0x1000 bytes) is empty (filled with 0xFF) so the
        # first sector starts at 0x1000 (we already skipped the 4 byte header
        # so we don't have to take care of this).
        sectorSize = 0x1000
        offset = sectorSize
        # We always need 4 bytes (+3 including offset) to read the type.
        while (offset + 3) < len(data):
            entryType = self._readInt(data, offset)
            if entryType == 2:  # is a file?
                # File structure:

                # ======  ======  =====  ====================================
                # offset  type     size  description
                # ======  ======  =====  ====================================
                #   0x04  string  127 B  FileName (zero terminated)
                #   0x83  ?         9 B  Unknown
                #   0x8c  int       4 B  FileSize
                #   0x90  ?         4 B  Unknown
                #   0x94  int[]   n*4 B  Indices of the sector containing the
                #                        data (end is marked with 0)
                # ======  ======  =====  ====================================

                # The sectors marked at 0x94 are absolutely positioned
                # (1*0x1000 is sector 1, 2*0x1000 is sector 2,...).
                fileName = (self._readString(data, offset + 0x04, 127)
                                .strip(b'\x00'))
                fileSize = self._readInt(data, offset + 0x8C)
                # We need to iterate the blocks because. We need to move after
                # the last datasector.
                dataPointerOffset = offset + 0x94
                # We're keeping count so we can calculate the offset of the
                # array item.
                sectorCount = 0
                # This var is storing the sector index.
                sector = self._readInt(data,
                                       (dataPointerOffset +
                                        (4 * (sectorCount))))
                # As long we have data blocks we need to iterate them.
                fileData = b''
                while sector != 0:
                    # The next file entry starts after the last data sector so
                    # we move the offset along.
                    offset = sector * sectorSize
                    fileData += data[offset:offset + sectorSize]
                    sectorCount += 1
                    sector = self._readInt(data,
                                           (dataPointerOffset +
                                            (4 * (sectorCount))))

                fileData = fileData.rstrip(b'\x00')
                try:
                    gpxFile = self.files[fileName]
                    gpxFile.data += fileData
                except KeyError:
                    gpxFile = GPXFile(fileName, fileSize, fileData)
                    self.files[fileName] = gpxFile
            # Let's move to the next sector.
            offset += sectorSize

    def _readInt(self, data, offset):
        return struct.unpack_from('<i', data, offset)[0]

    def _readString(self, data, offset, length):
        b = data[offset:offset + length]
        return b.decode('cp1252')


class GPXFile(object):

    def __init__(self, name, size, data):
        self.filename = name
        self.filesize = size
        self.data = data


def testBitsIO():
    fp = BytesIO()
    bf = BitsIO(fp)

    bf.write(b'12\x00')  # 00110001 00110010 00000000
    bf.flush()
    bf.seek(0)

    assert bf.read() == b'12\x00'

    fp = BytesIO()
    bf = BitsIO(fp)

    bf.writebit(0)
    bf.writebits(0b011, length=3)
    bf.writebits(0b01000, length=5, reversed_=True)
    bf.write(b'd')
    bf.flush()
    bf.seek(0)

    assert bf.tell() == 0
    assert bf.readbit() == 0
    assert bf.readbits(3) == 0b011
    assert bf.readbits(5, reversed_=True) == 0b01000
    assert bf.read(1) == b'd'  # 01100100
    assert bf.tell() == 3


def testCompression():
    streams = [
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        'ABCDABCDABCDABCDABCDABCDABCD',
        'Noooooooooooooooooooooooooooooooo',
        ':)',
        '\x00\x00\x00\x00',
        # And for something completely different.
        open('tests/Mastodon - Ghost of Karelia.gp5').read(),
    ]
    for stream in streams:
        compressed = compress(stream)
        decompressed = decompress(compressed)
        assert stream == decompressed


def testGPXFileSystem():
    filename = 'tests/Queens of the Stone Age - I Appear Missing.gpx'
    with open(filename, 'rb') as fp:
        gpxfp = GPXFileSystem(fp)
        gpxfp.extract('score.gpif')
        score = gpxfp.read('score.gpif')
        assert md5(score).hexdigest() == 'da09c7f29a11b19e34433747a0260f55'
