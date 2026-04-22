"""Port of AlphaTab's GpxFileSystem + BitReader for Guitar Pro 6 (GPX)
container support. Output is required to be byte-identical to AlphaTab.

Upstream source (AlphaTab, MPL-2.0):
  * ``io/BitReader.ts``
  * ``io/ByteBuffer.ts`` (behavior mirrored in :class:`_ByteBuffer`)
  * ``importer/GpxFileSystem.ts``

Guitar Pro 6 files use either the compressed ``BCFZ`` variant (proprietary
Deflate-like LZ) or the uncompressed ``BCFS`` variant; both wrap the same
embedded filesystem whose ``score.gpif`` entry carries the GPIF XML that
GP6/GP7/GP8 share. Decompressing and walking the container produces the
same XML this module's caller hands to :mod:`guitarpro.gp7`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


class EndOfReader(Exception):
    """Raised when the :class:`_BitReader` source is exhausted. BCFZ's
    :meth:`GpxFileSystem.decompress` catches this as the normal termination
    signal of a stream (AT does the same via ``EndOfReaderError``)."""


class _ByteSource:
    """Minimal byte source exposing :meth:`read_byte` with AT's convention of
    returning ``-1`` at EOF (not raising)."""

    __slots__ = ("_data", "_pos")

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def read_byte(self) -> int:
        if self._pos >= len(self._data):
            return -1
        value = self._data[self._pos]
        self._pos += 1
        return value

    def read_all(self) -> bytes:
        tail = self._data[self._pos:]
        self._pos = len(self._data)
        return tail


class _BitReader:
    """Bitwise reader mirroring AT's ``BitReader`` semantics exactly.

    Default reads are MSB-first (high bit of the current byte consumed first);
    :meth:`read_bits_reversed` is the LSB-first counterpart used by BCFZ's
    back-reference offset/size encoding and literal-size field.
    """

    __slots__ = ("_source", "_current_byte", "_position")

    _BYTE_SIZE = 8

    def __init__(self, source: _ByteSource) -> None:
        self._source = source
        self._current_byte = 0
        self._position = self._BYTE_SIZE  # triggers fresh byte fetch on first bit

    def read_bit(self) -> int:
        if self._position >= self._BYTE_SIZE:
            b = self._source.read_byte()
            if b == -1:
                raise EndOfReader()
            self._current_byte = b
            self._position = 0
        value = (self._current_byte >> (self._BYTE_SIZE - self._position - 1)) & 0x01
        self._position += 1
        return value

    def read_bits(self, count: int) -> int:
        bits = 0
        i = count - 1
        while i >= 0:
            bits |= self.read_bit() << i
            i -= 1
        return bits

    def read_bits_reversed(self, count: int) -> int:
        bits = 0
        for i in range(count):
            bits |= self.read_bit() << i
        return bits

    def read_byte(self) -> int:
        return self.read_bits(8)

    def read_bytes(self, count: int) -> bytes:
        out = bytearray(count)
        for i in range(count):
            out[i] = self.read_byte() & 0xFF
        return bytes(out)

    def read_all(self) -> bytes:
        out = bytearray()
        try:
            while True:
                out.append(self.read_byte() & 0xFF)
        except EndOfReader:
            pass
        return bytes(out)


class _ByteBuffer:
    """Growable byte buffer whose :meth:`write` semantics match AT's
    ``ByteBuffer.write`` — including the **implicit zero-padding** when the
    source slice is shorter than the requested ``count``.

    AT achieves this by first allocating a zero-filled larger buffer through
    ``_ensureCapacity`` and then copying only the available source bytes via
    ``Uint8Array.set``; the trailing positions remain zero and are included
    in the advanced ``length``. We reproduce the same observable output.
    """

    __slots__ = ("_buf",)

    def __init__(self) -> None:
        self._buf = bytearray()

    @property
    def length(self) -> int:
        return len(self._buf)

    def get_buffer(self) -> bytes:
        return bytes(self._buf)

    def write_byte(self, value: int) -> None:
        self._buf.append(value & 0xFF)

    def write(self, source: bytes, offset: int, count: int) -> None:
        # Clamp offset to a non-negative region; `count - actual` bytes are
        # implicitly zero-padded at the end.
        start = max(0, offset)
        actual = max(0, min(count, len(source) - start))
        if actual > 0:
            self._buf.extend(source[start : start + actual])
        pad = count - actual
        if pad > 0:
            self._buf.extend(b"\x00" * pad)

    def to_array(self) -> bytes:
        return bytes(self._buf)


@dataclass
class GpxFile:
    """A single file entry within a :class:`GpxFileSystem` (name/size + raw
    bytes). ``data`` is ``None`` when the file was filtered out by
    :attr:`GpxFileSystem.file_filter`."""

    file_name: str = ""
    file_size: int = 0
    data: Optional[bytes] = None


class GpxFileSystem:
    """Port of AT's ``GpxFileSystem``. Loads a GPX/BCFS/BCFZ container and
    exposes the embedded files via :attr:`files`. Behavior is required to be
    byte-identical to AT on valid containers.

    Usage::

        fs = GpxFileSystem()
        fs.load(container_bytes)
        gpif_xml = next(f.data for f in fs.files if f.file_name == "score.gpif")
    """

    HEADER_BCFS = "BCFS"
    HEADER_BCFZ = "BCFZ"
    _SECTOR_SIZE = 0x1000

    def __init__(self) -> None:
        self.files: list[GpxFile] = []
        self.file_filter: Callable[[str], bool] = lambda _name: True

    def load(self, data: bytes) -> None:
        src = _BitReader(_ByteSource(data))
        self._read_block(src)

    def read_header(self, src: _BitReader) -> str:
        return self._get_string(src.read_bytes(4), 0, 4)

    def decompress(self, src: _BitReader, skip_header: bool = False) -> bytes:
        """Mirror of AT ``decompress``. Reads a little-endian expected-length
        prefix, then bit-level LZ-style decoding: flag=1 → back-reference
        (wordSize, offset, size), flag=0 → literal (size, raw bytes). End of
        stream (EndOfReader) terminates normally."""
        uncompressed = _ByteBuffer()
        header_bytes = src.read_bytes(4)
        expected_length = self._get_integer(header_bytes, 0)
        try:
            while uncompressed.length < expected_length:
                flag = src.read_bits(1)
                if flag == 1:
                    word_size = src.read_bits(4)
                    offset = src.read_bits_reversed(word_size)
                    size = src.read_bits_reversed(word_size)
                    source_position = uncompressed.length - offset
                    to_read = min(offset, size)
                    buffer = uncompressed.get_buffer()
                    uncompressed.write(buffer, source_position, to_read)
                else:
                    size = src.read_bits_reversed(2)
                    for _ in range(size):
                        uncompressed.write_byte(src.read_byte())
        except EndOfReader:
            pass

        buffer = uncompressed.get_buffer()
        result_offset = 4 if skip_header else 0
        result_size = uncompressed.length - result_offset
        return bytes(buffer[result_offset : result_offset + result_size])

    def _read_block(self, data: _BitReader) -> None:
        header = self.read_header(data)
        if header == self.HEADER_BCFZ:
            self._read_uncompressed_block(self.decompress(data, skip_header=True))
        elif header == self.HEADER_BCFS:
            self._read_uncompressed_block(data.read_all())
        else:
            raise ValueError(f"Unsupported GPX format: header={header!r}")

    def _read_uncompressed_block(self, data: bytes) -> None:
        sector_size = self._SECTOR_SIZE
        offset = sector_size  # first sector (0x1000) is empty (0xFF-filled)
        data_len = len(data)
        while offset + 3 < data_len:
            entry_type = self._get_integer(data, offset)
            if entry_type == 2:
                gpx_file = GpxFile()
                gpx_file.file_name = self._get_string(data, offset + 0x04, 127)
                gpx_file.file_size = self._get_integer(data, offset + 0x8C)
                store_file = bool(self.file_filter(gpx_file.file_name))
                if store_file:
                    self.files.append(gpx_file)

                data_pointer_offset = offset + 0x94
                sector_count = 0
                file_data = _ByteBuffer() if store_file else None
                while True:
                    sector = self._get_integer(data, data_pointer_offset + 4 * sector_count)
                    sector_count += 1
                    if sector != 0:
                        offset = sector * sector_size
                        if store_file:
                            assert file_data is not None  # guarded by store_file
                            file_data.write(data, offset, sector_size)
                    else:
                        break

                if store_file:
                    assert file_data is not None
                    trimmed = min(gpx_file.file_size, file_data.length)
                    raw = file_data.to_array()
                    gpx_file.data = bytes(raw[:trimmed])

            offset += sector_size

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _get_string(data: bytes, offset: int, length: int) -> str:
        end = min(offset + length, len(data))
        out = bytearray()
        for i in range(max(0, offset), end):
            code = data[i]
            if code == 0:
                break
            out.append(code)
        return out.decode("latin1")

    @staticmethod
    def _get_integer(data: bytes, offset: int) -> int:
        """Little-endian signed int32 matching AT's ``_getInteger``.

        AT uses bitwise-OR of byte shifts; in JS this coerces the result to a
        signed int32. Out-of-bounds reads in AT return ``undefined`` which
        coerces to ``0`` under ``<<``; we mirror that by treating missing
        bytes as ``0``.
        """
        data_len = len(data)
        b0 = data[offset] if 0 <= offset < data_len else 0
        b1 = data[offset + 1] if 0 <= offset + 1 < data_len else 0
        b2 = data[offset + 2] if 0 <= offset + 2 < data_len else 0
        b3 = data[offset + 3] if 0 <= offset + 3 < data_len else 0
        raw = (b3 << 24) | (b2 << 16) | (b1 << 8) | b0
        if raw & 0x80000000:
            raw -= 0x1_0000_0000
        return raw


class GpxArchive:
    """Thin adapter exposing the subset of :class:`zipfile.ZipFile` API that
    :mod:`guitarpro.gp7` consumes (:meth:`namelist`, :meth:`read`), backed by
    a :class:`GpxFileSystem`. This lets GP6 containers flow through the same
    GPIF-parsing code path as GP7/GP8 without a second copy of the dispatch.
    """

    def __init__(self, data: bytes) -> None:
        fs = GpxFileSystem()
        fs.load(data)
        self._by_name: dict[str, bytes] = {
            entry.file_name: (entry.data or b"") for entry in fs.files
        }

    def namelist(self) -> list[str]:
        return list(self._by_name.keys())

    def read(self, name: str) -> bytes:
        try:
            return self._by_name[name]
        except KeyError:
            raise KeyError(f"no file named {name!r} in GPX container") from None


__all__ = ["EndOfReader", "GpxFile", "GpxFileSystem", "GpxArchive"]
