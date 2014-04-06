import os
import struct
from binascii import unhexlify
from collections import OrderedDict
from hashlib import md5

from six import string_types
from six.moves import cStringIO as StringIO


_HEADER_BCFS = b'BCFS'
_HEADER_BCFZ = b'BCFZ'


class BitFile(object):
    def __init__(self, stream):
        self.stream = stream
        self.currentByte = None
        self.position = 8  # to ensure a byte is read on beginning

    def __getattr__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return (object.__getattribute__(self, 'stream')
                          .__getattribute__(name))

    def read(self, size=-1):
        if size == -1:
            bits = self.readbits(-1)
        else:
            bits = self.readbits(size * 8)
        return self._int_to_bytes(bits)

    def _int_to_bytes(self, value):
        result = hex(value)[2:].rstrip('L').encode('ascii')
        if len(result) % 2:
            result = b'0' + result
        return unhexlify(result)

    def readbits(self, size=-1, reversed_=False):
        if size == -1:
            bits = list(iter(self.readbit, None))
        else:
            bits = [self.readbit() for _ in range(size)]
        return self._bits_to_int(bits, reversed_=reversed_)

    def readbit(self):
        try:
            # Need a new byte?
            if self.position > 7:
                self.currentByte, = struct.unpack('B', self.stream.read(1))
                self.position = 0
            # Shift the desired byte to the least significant bit and
            # get the value using masking.
            value = (self.currentByte >> (7 - self.position)) & 0x01
            self.position += 1
            return value
        except struct.error:
            return

    def _bits_to_int(self, bits, reversed_=False):
        if reversed_:
            bits = reversed(bits)
        strbits = [str(bit) for bit in bits if bit is not None]
        return int(''.join(strbits), 2)


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

        self.fp = BitFile(fp)

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
        return StringIO(self.files[name].data)

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
            self._readUncompressedBlock(self._decompress())
        elif header == _HEADER_BCFS:
            self._readUncompressedBlock(self.fp.read())
        else:
            pass

    def _decompress(self):
        """Decompresses the given bitinput using the GPX compression format.

        Only use this method if you are sure the binary data is compressed
        using the GPX format. Otherwise unexpected behavior can occur.

        """
        uncompressed = b''
        expectedLength, = struct.unpack('<i', self.fp.read(4))
        while len(uncompressed) < expectedLength:
            # Compression flag.
            flag = self.fp.readbit()
            if flag:
                # Get offset and size of the content we need to read.
                # Compressed does mean we already have read the data and need
                # to copy it from our uncompressed buffer to the end.
                wordSize = self.fp.readbits(4)  # word size: 0 .. 16
                offset = self.fp.readbits(wordSize, reversed_=True)  # offset: 0 .. 65536
                size = self.fp.readbits(wordSize, reversed_=True)

                # The offset is relative to the end.
                position = len(uncompressed) - offset
                toRead = min(offset, size)

                # Get the subbuffer storing the data and add it again to the
                # end.
                subBuffer = uncompressed[position:position + toRead]
                uncompressed += subBuffer
            else:
                # On raw content we need to read the data from the source
                # buffer.
                size = self.fp.readbits(2, reversed_=True)
                for _ in range(size):
                    uncompressed += self.fp.read(1)
        return uncompressed[4:]

    def _readUncompressedBlock(self, data):
        # The uncompressed block contains a list of filesystem entries. As long
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


def testBitFileReading():
    fp = StringIO('12')
    bf = BitFile(fp)
    assert bf.read() == b'12'

    fp = StringIO('12')  # 00110001 00110010
    bf = BitFile(fp)
    assert bf.tell() == 0
    assert bf.readbit() == 0
    assert bf.readbits(3) == 0b011
    assert bf.readbits(5, reversed_=True) == 0b01000
    assert bf.read(1) == b'2'
    assert bf.tell() == 2


def testGPXFileSystem():
    filename = '../tests/Queens of the Stone Age - I Appear Missing.gpx'
    with open(filename, 'rb') as fp:
        gpxfp = GPXFileSystem(fp)
        assert (md5(gpxfp.read('score.gpif')).hexdigest() ==
                'da09c7f29a11b19e34433747a0260f55')
