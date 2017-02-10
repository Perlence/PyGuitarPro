import struct

import attr


@attr.s
class GPFileBase(object):
    bendPosition = 60
    bendSemitone = 25

    _supportedVersions = []

    data = attr.ib()
    encoding = attr.ib()
    version = attr.ib(default=None)
    versionTuple = attr.ib(default=None)

    def close(self):
        self.data.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    # Reading
    # =======

    def skip(self, count):
        return self.data.read(count)

    def read(self, fmt, count, default=None):
        try:
            data = self.data.read(count)
            result = struct.unpack(fmt, data)
            return result[0]
        except struct.error:
            if default is not None:
                return default
            else:
                raise

    def readByte(self, count=1, default=None):
        """Read 1 byte *count* times."""
        args = ('B', 1)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readSignedByte(self, count=1, default=None):
        """Read 1 signed byte *count* times."""
        args = ('b', 1)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readBool(self, count=1, default=None):
        """Read 1 byte *count* times as a boolean."""
        args = ('?', 1)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readShort(self, count=1, default=None):
        """Read 2 little-endian bytes *count* times as a short integer."""
        args = ('<h', 2)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readInt(self, count=1, default=None):
        """Read 4 little-endian bytes *count* times as an integer."""
        args = ('<i', 4)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readFloat(self, count=1, default=None):
        """Read 4 little-endian bytes *count* times as a float."""
        args = ('<f', 4)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readDouble(self, count=1, default=None):
        """Read 8 little-endian bytes *count* times as a double."""
        args = ('<d', 8)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readString(self, size, length=None):
        if length is None:
            length = size
        count = size if size > 0 else length
        s = self.data.read(count)
        ss = s[:(length if length >= 0 else size)]
        return ss.decode(self.encoding)

    def readByteSizeString(self, size):
        """Read length of the string stored in 1 byte and followed by character
        bytes."""
        return self.readString(size, self.readByte())

    def readIntSizeString(self):
        """Read length of the string stored in 1 integer and followed by
        character bytes."""
        return self.readString(self.readInt())

    def readIntByteSizeString(self):
        """Read length of the string increased by 1 and stored in 1 integer
        followed by length of the string in 1 byte and finally followed by
        character bytes.
        """
        d = self.readInt() - 1
        return self.readByteSizeString(d)

    def readVersion(self):
        if self.version is None:
            self.version = self.readByteSizeString(30)
        return self.version

    # Writing
    # =======

    def placeholder(self, count, byte=b'\x00'):
        self.data.write(byte * count)

    def writeByte(self, data):
        packed = struct.pack('B', int(data))
        self.data.write(packed)

    def writeSignedByte(self, data):
        packed = struct.pack('b', int(data))
        self.data.write(packed)

    def writeBool(self, data):
        packed = struct.pack('?', bool(data))
        self.data.write(packed)

    def writeShort(self, data):
        packed = struct.pack('<h', int(data))
        self.data.write(packed)

    def writeInt(self, data):
        packed = struct.pack('<i', int(data))
        self.data.write(packed)

    def writeFloat(self, data):
        packed = struct.pack('<f', float(data))
        self.data.write(packed)

    def writeDouble(self, data):
        packed = struct.pack('<d', float(data))
        self.data.write(packed)

    def writeString(self, data, size=None):
        if size is None:
            size = len(data)
        self.data.write(data.encode(self.encoding))
        self.placeholder(size - len(data))

    def writeByteSizeString(self, data, size=None):
        if size is None:
            size = len(data)
        self.writeByte(len(data))
        return self.writeString(data, size)

    def writeIntSizeString(self, data):
        self.writeInt(len(data))
        return self.writeString(data)

    def writeIntByteSizeString(self, data):
        self.writeInt(len(data) + 1)
        return self.writeByteSizeString(data)

    def writeVersion(self):
        self.writeByteSizeString(self.version, 30)
