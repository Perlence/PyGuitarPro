import __builtin__
import os

from base import *
from gp3 import GP3File
from gp4 import GP4File

GPFILES = {
    'FICHIER GUITAR PRO v3.00': GP3File,
    'FICHIER GUITAR PRO v4.00': GP4File,
    'FICHIER GUITAR PRO v4.06': GP4File,
    'FICHIER GUITAR PRO L4.06': GP4File,
    # 'FICHIER GUITAR PRO v5.00': GP5File,
    # 'FICHIER GUITAR PRO v5.10': GP5File
}

VERSIONS = {
    'gp3': 'FICHIER GUITAR PRO v3.00',
    'gp4': 'FICHIER GUITAR PRO v4.06',
    'gp5': 'FICHIER GUITAR PRO v5.10'
}

def findFormatExtFile(path):
    '''Guess format from filepath
    '''
    root, ext = os.path.splitext(path)
    ext = ext.lstrip('.')
    if ext in ('gp3', 'gp4', 'gp5'):
        return ext
    else:
        return 'gp3'

def open(filename, mode='rb', format=None):
    '''Open a GP file path for reading or writing.

    For writing to a GP file, `mode` should be "wb".
    Format may be one of ['gp3', 'gp4', 'gp5']
    '''
    if mode not in ('rb', 'wb'):
        raise GuitarProException("cannot read or write unless in binary mode, not '%s'" % mode)
    
    fp = __builtin__.open(filename, mode)
    if mode == 'rb':
        gpfilebase = GPFileBase(fp)
        if format is None:
            gpfilebase.readVersion()
            gpfilebase.data.seek(0)
            version = gpfilebase.version
        else:
            version = VERSIONS[format]
    elif mode == 'wb':
        if format is None:
            format = findFormatExtFile(filename)
            version = VERSIONS[format]
        else:
            version = VERSIONS[format]
    try:
        GPFile = GPFILES[version]
    except KeyError:
        raise base.GuitarProException("unsupported version '%s'" % gpfilebase.version)
    gpfile = GPFile(fp)
    if mode == 'wb':
        gpfile.version = version
    return GPFile(fp)

def parse(filename, format=None):
    '''Open a GP file and read its contents
    '''
    gpfile = open(filename, 'rb', format)
    song = gpfile.readSong()
    gpfile.close()
    return song

def write(song, filename, format=None):
    '''Write a song into GP file
    '''
    gpfile = open(filename, 'wb', format)
    song = gpfile.writeSong(song)
    gpfile.close()