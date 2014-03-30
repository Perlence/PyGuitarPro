import os

from six import string_types

from .base import GPFileBase, GPException
from .gp3 import GP3File
from .gp4 import GP4File
from .gp5 import GP5File

__version__ = '0.2.1'
__all__ = ('parse', 'write')

_GPFILES = {
    'FICHIER GUITAR PRO v3.00': GP3File,
    'FICHIER GUITAR PRO v4.00': GP4File,
    'FICHIER GUITAR PRO v4.06': GP4File,
    'FICHIER GUITAR PRO L4.06': GP4File,
    'FICHIER GUITAR PRO v5.00': GP5File,
    'FICHIER GUITAR PRO v5.10': GP5File,
}

_VERSIONS = {
    'gp3':  'FICHIER GUITAR PRO v3.00',
    'gp4':  'FICHIER GUITAR PRO v4.06',
    'gp5':  'FICHIER GUITAR PRO v5.10',
    'gp50': 'FICHIER GUITAR PRO v5.00',
    'gp51': 'FICHIER GUITAR PRO v5.10',
}


def findFormatExtFile(path):
    """Guess format from filepath."""
    __, ext = os.path.splitext(path)
    ext = ext.lstrip('.')
    if ext in ('gp3', 'gp4', 'gp5'):
        return ext
    else:
        return 'gp5'


def _open(stream, mode='rb', format=None, encoding=None):
    """Open a GP file path for reading or writing.

    :param stream: filename or file-like object.
    :param mode: should be either "rb" or "wb".
    :param format: may be one of the supported formats, e.g. "gp5". If no
        explicit format given, guess what it might be.
    :param encoding: treat strings found in tablature as encoded in given 8-bit
        encoding.

    """
    if mode not in ('rb', 'wb'):
        raise ValueError(
            "cannot read or write unless in binary mode, not '%s'" % mode)

    if isinstance(stream, string_types):
        fp = open(stream, mode)
        filename = stream
    else:
        fp = stream
        filename = getattr(fp, 'name', '<file>')

    if mode == 'rb':
        gpfilebase = GPFileBase(fp, encoding=encoding)
        if format is None:
            gpfilebase.readVersion()
            version = gpfilebase.version
        else:
            version = _VERSIONS[format]
    elif mode == 'wb':
        if format is None:
            format = findFormatExtFile(filename)
            version = _VERSIONS[format]
        else:
            version = _VERSIONS[format]

    try:
        GPFile = _GPFILES[version]
    except KeyError:
        raise GPException("unsupported version '%r'" % gpfilebase.version)
    gpfile = GPFile(fp, encoding=encoding)
    gpfile.version = version
    return gpfile


def parse(stream, format=None, encoding=None):
    """Open a GP file and read its contents.

    :param stream: path to a GP file or file-like object.
    :param format: explicitly set format of GP file.
    :param encoding: decode strings in tablature using this charset. Given
        encoding must be an 8-bit charset.

    """
    gpfile = _open(stream, 'rb', format=format, encoding=encoding)
    song = gpfile.readSong()
    gpfile.close()
    return song


def write(song, stream, format=None, encoding=None):
    """Write a song into GP file.

    :param song: a :class:`guitarpro.base.GPFileBase` instance.
    :param stream: path to save GP file or file-like object.
    :param format: explicitly set format of saved GP file.
    :param encoding: encode strings into given 8-bit charset.

    """
    gpfile = _open(stream, 'wb', format=format, encoding=encoding)
    song = gpfile.writeSong(song)
    gpfile.close()
