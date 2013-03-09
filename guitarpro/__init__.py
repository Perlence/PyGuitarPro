from base import *
import base
import gp3

def parse(filename, version=None):
    gpfilebase = GPFileBase()
    gpfilebase.open(filename, 'rb')
    if version == None:
        gpfilebase.readVersion()
        gpfilebase.data.seek(0)
        version_suffix = gpfilebase.version[-5:]
    else:
        version_suffix = version
    
    if version_suffix == 'v3.00':
        gpfile = gp3.GP3File()
        gpfile.openFileLike(gpfilebase.data)
    elif version_suffix in ('v4.00', 'v4.06', 'L4.06'):
        gpfile = gp4.GP4File()
        gpfile.openFileLike(gpfilebase.data)
    elif version_suffix in ('v5.00', 'v5.10'):
        gpfile = gp5.GP5File()
        gpfile.openFileLike(gpfilebase.data)
    else:
        raise base.GuitarProException("unsupported version '%s'" % gpfilebase.version)
    
    song = gpfile.readSong()
    return song