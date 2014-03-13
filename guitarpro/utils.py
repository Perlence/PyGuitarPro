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
