import re


def clamp(iterable, length, fillvalue=None):
    """Set length of iterable to given length. If iterable is shorter then
    ``length`` then fill it with ``fillvalue``, drop items otherwise."""
    i = -1
    for i, x in enumerate(iterable):
        if i < length:
            yield x
        else:
            return
    for __ in xrange(i + 1, length):
        yield fillvalue


def hexify(string):
    """Encode string in hex and insert whitespace after each byte."""
    return ' '.join(re.findall('[0-9a-zA-Z]{2}', string.encode('hex')))
