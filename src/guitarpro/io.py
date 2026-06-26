import io
import os

from .iobase import GPFileBase
from .gp3 import GP3File
from .gp4 import GP4File
from .gp5 import GP5File
from .gpx import GPXFile
from .models import GPException, Song

__all__ = ('parse', 'write')

_GPFILES = {
    'FICHIER GUITAR PRO v3.00': ((3, 0, 0), GP3File),

    'FICHIER GUITAR PRO v4.00': ((4, 0, 0), GP4File),
    'FICHIER GUITAR PRO v4.06': ((4, 0, 6), GP4File),
    'FICHIER GUITAR PRO L4.06': ((4, 0, 6), GP4File),
    'CLIPBOARD GUITAR PRO 4.0 [c6]': ((4, 0, 6), GP4File),

    'FICHIER GUITAR PRO v5.00': ((5, 0, 0), GP5File),
    'FICHIER GUITAR PRO v5.10': ((5, 1, 0), GP5File),
    'CLIPBOARD GP 5.0': ((5, 0, 0), GP5File),
    'CLIPBOARD GP 5.1': ((5, 1, 0), GP5File),
    'CLIPBOARD GP 5.2': ((5, 2, 0), GP5File),
}

_VERSIONS = {
    # (versionTuple, isClipboard): versionString,
    ((3, 0, 0), False): 'FICHIER GUITAR PRO v3.00',

    ((4, 0, 0), False): 'FICHIER GUITAR PRO v4.00',
    ((4, 0, 6), False): 'FICHIER GUITAR PRO v4.06',
    ((4, 0, 6), True): 'CLIPBOARD GUITAR PRO 4.0 [c6]',

    ((5, 0, 0), False): 'FICHIER GUITAR PRO v5.00',
    ((5, 1, 0), False): 'FICHIER GUITAR PRO v5.10',
    ((5, 2, 0), False): 'FICHIER GUITAR PRO v5.10',  # sic
    ((5, 0, 0), True): 'CLIPBOARD GP 5.0',
    ((5, 1, 0), True): 'CLIPBOARD GP 5.1',
    ((5, 2, 0), True): 'CLIPBOARD GP 5.2',
}

_EXT_VERSIONS = {
    'gp3': (3, 0, 0),
    'gp4': (4, 0, 6),
    'gp5': (5, 1, 0),
    'tmp': (5, 2, 0),
}

#: Magic numbers of the GP6 (``.gpx``) and GP7 (``.gp``) container formats.
_GPX_MAGICS = (b'BCFZ', b'BCFS', b'PK\x03\x04')


def parse(stream, encoding='cp1252') -> Song:
    """Open a GP file and read its contents.

    :param stream: path to a GP file or file-like object.
    :param encoding: decode strings in tablature using this charset.
        Given encoding must be an 8-bit charset.
    """
    gpfile, shouldClose = _open(None, stream, 'rb', encoding=encoding)
    try:
        return gpfile.readSong()
    finally:
        if shouldClose:
            gpfile.close()


def write(song: Song, stream, version: tuple | None = None, encoding='cp1252'):
    """Write a song into GP file.

    :param song: a song to write.
    :param stream: path to save GP file or file-like object.
    :param version: explicitly set version of GP file to save, e.g.
        ``(5, 1, 0)``.
    :param encoding: encode strings into given 8-bit charset.
    """
    gpfile, shouldClose = _open(song, stream, 'wb', version=version, encoding=encoding)
    try:
        gpfile.writeSong(song)
    finally:
        if shouldClose:
            gpfile.close()


def _open(song, stream, mode='rb', version=None, encoding=None):
    """Open a GP file path for reading or writing."""
    if mode not in ('rb', 'wb'):
        raise ValueError(f"cannot read or write unless in binary mode, not '{mode}'")

    shouldClose = False
    if isinstance(stream, (str, bytes, os.PathLike)):
        fp = open(stream, mode)
        shouldClose = True
        filename = stream
    else:
        fp = stream
        filename = getattr(fp, 'name', '<file>')

    if mode == 'rb':
        if not (hasattr(fp, 'seekable') and fp.seekable()):
            # The magic peek below needs to rewind; buffer non-seekable streams.
            fp = io.BytesIO(fp.read())
        magic = fp.read(4)
        fp.seek(0)
        if magic in _GPX_MAGICS:
            gpfile = GPXFile(fp, encoding)
            return gpfile, shouldClose
        gpfilebase = GPFileBase(fp, encoding)
        versionString = gpfilebase.readVersion()
    elif mode == 'wb':
        gpxFormat = _gpxFormat(version, filename)
        if gpxFormat is not None:
            gpfile = GPXFile(fp, encoding, version=gpxFormat)
            return gpfile, shouldClose
        isClipboard = song.clipboard is not None
        if version is None:
            version = song.versionTuple
        if version is None:
            version = guessVersionByExtension(filename)
        versionString = _VERSIONS[(version, isClipboard)]

    version, GPFile = getVersionAndGPFile(versionString)
    gpfile = GPFile(fp, encoding, version=versionString, versionTuple=version)
    return gpfile, shouldClose


def getVersionAndGPFile(versionString):
    try:
        return _GPFILES[versionString]
    except KeyError:
        raise GPException(f"unsupported version '{versionString}'")


def _gpxFormat(version, filename):
    """Return ``'gpx'``/``'gp'`` if *version* or *filename* targets GP6/GP7."""
    if version is not None:
        return {(6, 0, 0): 'gpx', (7, 0, 0): 'gp'}.get(tuple(version))
    __, ext = os.path.splitext(filename)
    ext = ext.lstrip('.').lower()
    if ext in ('gpx', 'gp'):
        return ext
    return None


def guessVersionByExtension(filename):
    __, ext = os.path.splitext(filename)
    ext = ext.lstrip('.')
    version = _EXT_VERSIONS.get(ext)
    if version is None:
        version = _EXT_VERSIONS['gp5']
    return version
