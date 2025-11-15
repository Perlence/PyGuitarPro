import struct
import logging
from contextlib import contextmanager

import attr

from . import models as gp


logger = logging.getLogger(__name__)


@attr.s
class GPFileBase:
    data = attr.ib()
    encoding = attr.ib()
    version = attr.ib(default=None)
    versionTuple = attr.ib(default=None)

    bendPosition = 60
    bendSemitone = 25

    _supportedVersions = []

    _currentTrack = None
    _currentMeasureNumber = None
    _currentVoiceNumber = None
    _currentBeatNumber = None

    def close(self):
        self.data.close()

    def __enter__(self):
        return self

    def __exit__(self, *excInfo):
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

    def readByteSizeString(self, count: int):
        """Read the string length (1 byte) followed by *count* character bytes.

        Returns the decoded string sliced to the length specified by the first
        byte.
        """
        if count > 255:
            raise ValueError("count must be less than or equal to 255")
        size = self.readByte()
        s = self.data.read(count)[:size]
        return s.decode(self.encoding)

    def readIntSizeString(self):
        """Read the string length (1 integer) followed by the character bytes."""
        count = self.readInt()
        s = self.data.read(count)
        return s.decode(self.encoding)

    def readIntByteSizeString(self):
        """Read the byte count (1 integer) followed by a byte-size string."""
        count = self.readInt()
        return self.readByteSizeString(count-1)

    def readVersion(self):
        if self.version is None:
            self.version = self.readByteSizeString(30)
        return self.version

    @contextmanager
    def annotateErrors(self, action):
        self._currentTrack = None
        self._currentMeasureNumber = None
        self._currentVoiceNumber = None
        self._currentBeatNumber = None
        try:
            yield
        except Exception as err:
            location = self.getCurrentLocation()
            if not location:
                raise
            raise gp.GPException(f"{action} {', '.join(location)}, "
                                 f"got {err.__class__.__name__}: {err}") from err
        finally:
            self._currentTrack = None
            self._currentMeasureNumber = None
            self._currentVoiceNumber = None
            self._currentBeatNumber = None

    def getEnumValue(self, enum):
        if enum.name == 'unknown':
            location = self.getCurrentLocation()
            logger.warning(f"{enum.value!r} is an unknown {enum.__class__.__name__} in {', '.join(location)}")
        return enum.value

    def getCurrentLocation(self):
        location = []
        if self._currentTrack is not None:
            location.append(f"track {self._currentTrack.number}")
        if self._currentMeasureNumber is not None:
            location.append(f"measure {self._currentMeasureNumber}")
        if self._currentVoiceNumber is not None:
            location.append(f"voice {self._currentVoiceNumber}")
        if self._currentBeatNumber is not None:
            location.append(f"beat {self._currentBeatNumber}")
        return location

    # Writing
    # =======

    def placeholder(self, count):
        self.data.write(b'\x00' * count)

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

    def writeByteSizeString(self, data: str, count: int):
        if count > 255:
            raise ValueError("count must be less than or equal to 255")
        encoded = data.encode(self.encoding)[:count]
        self.writeByte(len(encoded))
        self.data.write(encoded.ljust(count, b'\x00'))

    def writeIntSizeString(self, data: str):
        encoded = data.encode(self.encoding)[:0x7FFFFFFF]
        self.writeInt(len(encoded))
        self.data.write(encoded)

    def writeIntByteSizeString(self, data: str):
        encoded = data.encode(self.encoding)[:0xFF]
        self.writeInt(len(encoded) + 1)
        self.writeByte(len(encoded))
        self.data.write(encoded)

    def writeVersion(self):
        self.writeByteSizeString(self.version, 30)
