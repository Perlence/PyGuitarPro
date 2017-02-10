import re
import math


def clamp(iterable, length, fillvalue=None):
    """Set length of iterable to given length.

    If iterable is shorter then *length* then fill it with *fillvalue*,
    drop items otherwise.
    """
    i = -1
    for i, x in enumerate(iterable):
        if i < length:
            yield x
        else:
            return
    for _ in range(i + 1, length):
        yield fillvalue


def hexify(string):
    """Encode string in hex and insert whitespace after each byte."""
    return ' '.join(re.findall('[0-9a-zA-Z]{2}', string.encode('hex')))


try:
    bit_length = int.bit_length
except AttributeError:
    def bit_length(integer):
        if integer == 0:
            return 0
        else:
            return int(math.log(abs(integer), 2)) + 1
