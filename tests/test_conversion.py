import os
from os import path

import pytest

import guitarpro


LOCATION = path.dirname(__file__)
OUTPUT = path.join(LOCATION, 'output')
TESTS = [
    'Effects.gp3',
    # 'Ephemera - Dust for Tears.gp3',
    # 'CarpeDiem - I Ching.gp3',
    'Chords.gp3',
    'Harmonics.gp3',

    'Effects.gp4',
    'Vibrato.gp4',
    # 'CarpeDiem - Ink.gp4',
    'Chords.gp4',
    'Slides.gp4',
    'Harmonics.gp4',
    'Key.gp4',
    'Repeat.gp4',
    'Strokes.gp4',

    # 'Mastodon - Curl of the Burl.gp5',
    # 'Mastodon - Ghost of Karelia.gp5',
    'Effects.gp5',
    'Voices.gp5',
    'Unknown-m.gp5',
    'Harmonics.gp5',
    'Wah-m.gp5',
    'Chords.gp5',
    'Slides.gp5',
    'RSE.gp5',
    'Repeat.gp5',
    'Strokes.gp5',
    'Demo v5.gp5',
]
CLIPBOARD_TESTS = [
    '2 whole bars.tmp',
]


@pytest.mark.parametrize('filename', TESTS)
def test_conversion(output_folder, filename):
    __, ext = path.splitext(filename)
    filepath = path.join(LOCATION, filename)
    song_a = guitarpro.parse(filepath)
    destpath = path.join(output_folder, filename + ext)
    guitarpro.write(song_a, destpath)
    song_b = guitarpro.parse(destpath)
    assert song_a == song_b


def test_clipboard(output_folder):
    filepath = path.join(LOCATION, '2 whole bars.tmp')
    song_a = guitarpro.parse(filepath)
    song_a.clipboard = None
    destpath = path.join(output_folder, '2 whole bars.tmp.gp5')
    guitarpro.write(song_a, destpath)
    song_b = guitarpro.parse(destpath)
    assert song_a == song_b


def test_empty(output_folder):
    empty_a = guitarpro.Song()
    destpath = path.join(output_folder, 'Empty.gp5')
    guitarpro.write(empty_a, destpath, version=(5, 2, 0))

    empty_b = guitarpro.parse(destpath)
    assert empty_a == empty_b


def test_guess_version(output_folder):
    filename = 'Effects.gp5'
    filepath = path.join(LOCATION, filename)
    song_a = guitarpro.parse(filepath)
    song_a.version = song_a.versionTuple = None

    for ext, versionTuple in guitarpro.io._EXT_VERSIONS.items():
        if ext == 'tmp':
            continue
        destpath = path.join(output_folder, filename + '.' + ext)
        guitarpro.write(song_a, destpath)
        song_b = guitarpro.parse(destpath)
        assert song_b.versionTuple == versionTuple


@pytest.fixture
def output_folder():
    try:
        os.mkdir(OUTPUT)
    except OSError:
        pass
    return OUTPUT


def product(test, song, versions=(3, 4, 5)):
    """Save song in given format *versions*."""
    for dest_version in versions:
        dest_path = path.join(OUTPUT, test + '.gp%d' % dest_version)
        guitarpro.write(song, dest_path)


def bisect(test, song, dest_version=3):
    """Save song in *n* files, where *n* is number of measures in song.

    Resulting tabs have following measures:

    - ``*-001.gp?``: *1st* measure
    - ``*-002.gp?``: *1st* and *2nd* measure
    - ...
    - ``*-nnn.gp?``: *1st*, *2nd*, ..., *nth* measure

    This function helps to find the measure where erroneous data was
    written using bisection method.

    """
    folder, _ = path.splitext(test)
    try:
        os.mkdir(path.join(OUTPUT, folder))
    except OSError:
        pass
    trackMeasures = [track.measures for track in song.tracks]
    for number, _ in enumerate(trackMeasures[0], 1):
        dest_path = path.join(OUTPUT, folder, test + '-%03d.gp%d' % (number, dest_version))
        for track in song.tracks:
            track.measures = trackMeasures[track.number - 1][:number]
        guitarpro.write(song, dest_path)


def track_bisect(test, song, dest_version=3):
    """Save song in *n* files, where *n* is number of tracks in song.

    Resulting tabs have following tracks:

    - ``*-T01.gp?``: *1st* track
    - ``*-T02.gp?``: *1st* and *2nd* track
    - ...
    - ``*-Tnn.gp?``: *1st*, *2nd*, ..., *nth* track

    This function helps to find the track where erroneous data was
    written using bisection method.

    """
    folder, _ = path.splitext(test)
    try:
        os.mkdir(path.join(OUTPUT, folder))
    except OSError:
        pass
    tracks = song.tracks[:]
    for number, track in enumerate(tracks, 1):
        dest_path = path.join(OUTPUT, folder, test + '-T%02d.gp%d' % (number, dest_version))
        song.tracks = tracks[:number]
        guitarpro.write(song, dest_path)
