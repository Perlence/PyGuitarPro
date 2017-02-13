import guitarpro


def test_hashable():
    song = guitarpro.Song()
    hash(song)
