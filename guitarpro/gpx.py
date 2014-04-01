import struct
from cStringIO import StringIO

from six import string_types


_HEADER_BCFS = b'BCFS'
_HEADER_BCFZ = b'BCFZ'


class GPXFileSystem(object):

    def __init__(self, file, mode='r'):
        self.filelist = []
        if isinstance(file, string_types):
            self._filePassed = 0
            self.filename = file
            modeDict = {'r': 'rb', 'w': 'wb', 'a': 'r+b'}
            try:
                self.fp = open(file, modeDict[mode])
            except IOError:
                if mode == 'a':
                    mode = key = 'w'
                    self.fp = open(file, modeDict[mode])
                else:
                    raise
        else:
            self._filePassed = 1
            self.fp = file
            self.filename = getattr(file, 'name', None)

        if key == 'r':
            self._readContents()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        pass

    def namelist():
        pass

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
        uncompressed = StringIO()
        expectedLength = struct.unpack('<i', self.fp.read(4))

        # as long we reach our expected length we try to decompress, a EOF
        # might occure.
        while uncompressed.tell() < expectedLength:
            # compression flag
            flag = self.fp.readBits(1)

            if flag:  # compressed content
                # get offset and size of the content we need to read.
                # compressed does mean we already have read the data and need
                # to copy it from our uncompressed buffer to the end.
                wordSize = self.fp.readBits(4)
                offset = self.fp.readBitsReversed(wordSize)
                size = self.fp.readBitsReversed(wordSize)

                # the offset is relative to the end
                sourcePosition = uncompressed.length - offset
                toRead = min(offset, size)

                # get the subbuffer storing the data and add it again to the
                # end
                subBuffer = uncompressed.sub(sourcePosition, toRead)
                uncompressed.addBytes(subBuffer)
            else:  # raw content
                # on raw content we need to read the data from the source
                # buffer
                size = self.fp.readBitsReversed(2)
                for i in range(size):
                    uncompressed.add(self.fp.readByte())

        return uncompressed.getBytes(4 if skipHeader else 0)


    def _readUncompressedBlock(self, data):
        # the uncompressed block contains a list of filesystem entires as long
        # we have data we will try to read more entries

        # the first sector (0x1000 bytes) is empty (filled with 0xFF) so the
        # first sector starts at 0x1000 (we already skipped the 4 byte header
        # so we don't have to take care of this)

        sectorSize = 0x1000
        offset = sectorSize

        # we always need 4 bytes (+3 including offset) to read the type
        while (offset + 3) < data.length:
            entryType = self._readInt(data, offset);

            if entryType == 2:  # is a file?
                # file structure:
                #   offset |   type   |   size   | what
                #  --------+----------+----------+------
                #    0x04  |  string  |  127byte | FileName (zero terminated)
                #    0x83  |    ?     |    9byte | Unknown
                #    0x8c  |   int    |    4byte | FileSize
                #    0x90  |    ?     |    4byte | Unknown
                #    0x94  |   int[]  |  n*4byte | Indices of the sector containing the data (end is marked with 0)

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
