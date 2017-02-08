from six import string_types

from .base import GPFileBase, GPException
from .gp3 import GP3File
from .gp4 import GP4File
from .gp5 import GP5File

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


def parse(stream, encoding=None):
    """Open a GP file and read its contents.

    :param stream: path to a GP file or file-like object.
    :param encoding: decode strings in tablature using this charset. Given
        encoding must be an 8-bit charset.

    """
    gpfile = _open(None, stream, 'rb', encoding=encoding)
    song = gpfile.readSong()
    gpfile.close()
    return song


def write(song, stream, version=None, encoding=None):
    """Write a song into GP file.

    :param song: a :class:`guitarpro.base.GPFileBase` instance.
    :param stream: path to save GP file or file-like object.
    :param version: explicitly set version of saved GP file, e.g.
        ``(5, 1, 0)``.
    :type version: tuple
    :param encoding: encode strings into given 8-bit charset.

    """
    gpfile = _open(song, stream, 'wb', version=version, encoding=encoding)
    gpfile.writeSong(song)
    gpfile.close()


def _open(song, stream, mode='rb', version=None, encoding=None):
    """Open a GP file path for reading or writing.

    :param stream: filename or file-like object.
    :param mode: should be either "rb" or "wb".
    :param version: should be version of Guitar Pro, e.g. ``(5, 1, 0)``.
        If no explicit version given, attempt guess what it might be.
    :param encoding: treat strings found in tablature as encoded in given 8-bit
        encoding.

    """
    if mode not in ('rb', 'wb'):
        raise ValueError(
            "cannot read or write unless in binary mode, not '%s'" % mode)

    if isinstance(stream, string_types):
        fp = open(stream, mode)
    else:
        fp = stream

    if mode == 'rb':
        gpfilebase = GPFileBase(fp, encoding=encoding)
        versionString = gpfilebase.readVersion()
    elif mode == 'wb':
        isClipboard = song.clipboard is not None
        if version is None:
            version = song.versionTuple
        versionString = _VERSIONS[(version, isClipboard)]

    version, GPFile = getVersionAndGPFile(versionString)
    gpfile = GPFile(fp, version=versionString, versionTuple=version,
                    encoding=encoding)
    return gpfile


def getVersionAndGPFile(versionString):
    try:
        return _GPFILES[versionString]
    except KeyError:
        raise GPException("unsupported version '%s'" % versionString)
