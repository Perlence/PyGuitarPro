import struct
from binascii import unhexlify

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
            return object.__getattribute__(self, 'stream').__getattribute__(name)

    def read(self, size=-1):
        if size == -1:
            bits =  self.readbits(-1)
        else:
            bits =  self.readbits(size * 8)
        result = hex(bits).lstrip('0x').rstrip('L').encode('ascii')
        if len(result) % 2:
            result = b'0' + result
        return unhexlify(result)

    def readbits(self, size=-1, reversed_=False):
        if size == -1:
            bits = list(iter(self.readbit, None))
        else:
            bits = [self.readbit() for __ in range(size)]
        return self._encodebits(bits, reversed_=reversed_)

    def readbit(self):
        try:
            # need a new byte?
            if self.position > 7:
                self.currentByte, = struct.unpack('B', self.stream.read(1))
                self.position = 0
            # shift the desired byte to the least significant bit and
            # get the value using masking
            value = (self.currentByte >> (7 - self.position)) & 0x01
            self.position += 1
            return value
        except struct.error:
            return

    def _encodebits(self, bits, reversed_=False):
        length = len(bits)
        result = 0
        if reversed_:
            bits = reversed(bits)
        for index, bit in enumerate(bits):
            if bit is None:
                continue
            exp = (length - index - 1) if not reversed_ else index
            result |= bit << exp
        return result


class GPXFileSystem(object):

    def __init__(self, file, mode='r'):
        self.filelist = []
        self.mode = key = mode.replace('b', '')[0]
        if isinstance(file, string_types):
            self._filePassed = 0
            self.filename = file
            modeDict = {'r': 'rb', 'w': 'wb', 'a': 'r+b'}
            try:
                fp = open(file, modeDict[mode])
            except IOError:
                if mode == 'a':
                    mode = key = 'w'
                    fp = open(file, modeDict[mode])
                else:
                    raise
        else:
            self._filePassed = 1
            fp = file
            self.filename = getattr(file, 'name', None)

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

    def namelist():
        """Return a list of file names in the archive."""
        result = []
        for data in self.filelist:
            result.append(data.fileName)
        return result

    def open(self, name, mode='r'):
        pass

    def extract(self, member, path=None):
        pass

    def extractall(self, path=None, members=None):
        pass

    def printdir(self):
        pass

    def read(self, name):
        pass

    def write(self, filename, arcname=None):
        pass

    def writestr(self, arcname, bytes_):
        pass

    def _readContents(self):
        header = self.fp.read(4)
        if header == _HEADER_BCFZ:
            self._readUncompressedBlock(self.decompress(skipHeader=True))
        elif header == _HEADER_BCFS:
            self._readUncompressedBlock(self.fp.read())
        else:
            pass

    def decompress(self, skipHeader=False):
        """Decompresses the given bitinput using the GPX compression format.

        Only use this method if you are sure the binary data is compressed
        using the GPX format. Otherwise unexpected behavior can occure.

        :param src: the bitInput to read the data from.
        :param skipHeader: true if the header should NOT be included in the
            result byteset, otherwise false.
        :return: the decompressed byte data. if skipHeader is set to false the
            BCFS header is included.

        """
        uncompressed = b''
        expectedLength, = struct.unpack('<i', self.fp.read(4))

        while len(uncompressed) < expectedLength:
            # compression flag
            flag = self.fp.readbit()

            if flag:  # compressed content
                # get offset and size of the content we need to read.
                # compressed does mean we already have read the data and need
                # to copy it from our uncompressed buffer to the end.
                wordSize = self.fp.readbits(4)
                offset = self.fp.readbits(wordSize, reversed_=True)
                size = self.fp.readbits(wordSize, reversed_=True)

                # the offset is relative to the end
                sourcePosition = len(uncompressed) - offset
                toRead = min(offset, size)

                # get the subbuffer storing the data and add it again to the
                # end
                subBuffer = uncompressed[sourcePosition:sourcePosition + toRead]
                uncompressed += subBuffer
            else:  # raw content
                # on raw content we need to read the data from the source
                # buffer
                size = self.fp.readbits(2, reversed_=True)
                for i in range(size):
                    uncompressed += self.fp.read(1)

        return uncompressed


    def _readUncompressedBlock(self, data):
        # the uncompressed block contains a list of filesystem entires as long
        # we have data we will try to read more entries

        # the first sector (0x1000 bytes) is empty (filled with 0xFF) so the
        # first sector starts at 0x1000 (we already skipped the 4 byte header
        # so we don't have to take care of this)

        sectorSize = 0x1000
        offset = sectorSize

        # we always need 4 bytes (+3 including offset) to read the type
        while (offset + 3) < len(data):
            entryType = self._readInt(data, offset);
            if entryType == 2:  # is a file?
                # file structure:
                #  ======  ======  =====  ====================================
                #  offset  type     size  description
                #  ======  ======  =====  ====================================
                #    0x04  string  127 B  FileName (zero terminated)
                #    0x83  ?         9 B  Unknown
                #    0x8c  int       4 B  FileSize
                #    0x90  ?         4 B  Unknown
                #    0x94  int[]   n*4 B  Indices of the sector containing the
                #                         data (end is marked with 0)
                #  ======  ======  =====  ====================================

                # The sectors marked at 0x94 are absolutely positioned
                # (1*0x1000 is sector 1, 2*0x1000 is sector 2,...)

                gpxFile = GPXFile()
                gpxFile.fileName = self._readString(data, offset + 0x04, 127)
                gpxFile.fileSize = self._readInt(data, offset + 0x8C)

                self.filelist.append(gpxFile)

                # we need to iterate the blocks because we need to move after
                # the last datasector

                dataPointerOffset = offset + 0x94
                # we're keeping count so we can calculate the offset of the
                # array item
                sectorCount = 1
                # this var is storing the sector index
                sector = self._readInt(data, (dataPointerOffset +
                                              (4 * (sectorCount))))

                # as long we have data blocks we need to iterate them,
                fileData = b''
                while sector != 0:
                    # the next file entry starts after the last data sector so
                    # we move the offset along
                    offset = sector * sectorSize;
                    fileData += data[offset:offset + sectorSize]
                    sectorCount += 1
                    sector = self._readInt(data, (dataPointerOffset +
                                                  (4 * (sectorCount))))

                gpxFile.data = fileData
                self.filelist.append(gpxFile)

            # let's move to the next sector
            offset += sectorSize

    def _readInt(self, data, offset):
        b = data[offset:offset + 4]
        return struct.unpack('<i', b)

    def _readInt32(self):
        b = self.fp.read(4)
        return struct.unpack('<i', b)

    def _readString(self, data, offset, length):
        b = data[offset:offset + length]
        return b


class GPXFile(object):

    def __init__(self, name, size, data):
        self.fileName = name
        self.fileSize = size
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
    assert bf.readbits(5, reversed_=True) == 0b00010
    assert bf.read(1) == b'd'
    assert bf.tell() == 2


def testGPXFileSystem():
    with open('../tests/Queens of the Stone Age - I Appear Missing.gpx', 'rb') as fp:
        gpxfp = GPXFileSystem(fp)
        import ipdb; ipdb.set_trace()
