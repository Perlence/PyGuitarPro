import re
from itertools import izip_longest

def clamp(iterable, length, fillvalue=None):
    '''Set length of iterable to given length. If iterable is shorter then
    ``length`` then fill it with ``fillvalue``, drop items otherwise.
    '''
    for x, i in izip_longest(iterable, xrange(length), fillvalue=fillvalue):
        if i < length:
            yield x
        else:
            return

def hexify(string):
    '''Encode string in hex and insert whitespace after each byte.
    '''
    return ' '.join(re.findall('[0-9a-zA-Z]{2}', string.encode('hex')))
