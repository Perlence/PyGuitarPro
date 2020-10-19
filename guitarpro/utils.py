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
