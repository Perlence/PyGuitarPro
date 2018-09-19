import guitarpro


def test_hashable():
    song = guitarpro.Song()
    hash(song)

    coda = guitarpro.DirectionSign('Coda')
    segno = guitarpro.DirectionSign('Segno')
    assert coda != segno
    assert hash(coda) != hash(segno)
