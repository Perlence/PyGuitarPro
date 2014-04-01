import os
from os import path

import guitarpro

LOCATION = path.dirname(__file__)
OUTPUT = path.join(LOCATION, 'output')
TESTS = [
    'Effects.gp3',
    'Ephemera - Dust for Tears.gp3',
    'CarpeDiem - I Ching.gp3',
    'Chords.gp3',
    'Harmonics.gp3',

    'Effects.gp4',
    'Vibrato.gp4',
    'CarpeDiem - Ink.gp4',
    'Chords.gp4',
    'Slides.gp4',
    'Harmonics.gp4',
    'Key.gp4',
    'Repeat.gp4',

    'Mastodon - Curl of the Burl.gp5',
    'Mastodon - Ghost of Karelia.gp5',
    'Effects.gp5',
    'Voices.gp5',
    'Unknown-m.gp5',
    'Harmonics.gp5',
    'Wah-m.gp5',
    'Chords.gp5',
    'Slides.gp5',
    'RSE.gp5',
    'Repeat.gp5',
    'Demo v5.gp5',
]

try:
    os.mkdir(OUTPUT)
except OSError:
    pass


def product(test, song, versions=(3, 4, 5)):
    """Save song in given format *versions*."""
    for dest_version in versions:
        dest_path = path.join(OUTPUT, test + '.gp%d' % dest_version)
        guitarpro.write(song, dest_path)


def bisect(test, song, dest_version=3):
    """Save song in *n* files, where *n* is number of measures in song.

    Resulting tabs have following measures:

    -   ``*-001.gp?``: *1st* measure
    -   ``*-002.gp?``: *1st* and *2nd* measure
    -   ...
    -   ``*-nnn.gp?``: *1st*, *2nd*, ..., *nth* measure

    This function helps to find the measure where erroneous data was written
    using bisection method.

    """
    folder, _ = path.splitext(test)
    try:
        os.mkdir(path.join(OUTPUT, folder))
    except OSError:
        pass
    trackMeasures = [track.measures for track in song.tracks]
    for number, _ in enumerate(trackMeasures[0], 1):
        dest_path = path.join(OUTPUT, folder, test + '-%03d.gp%d' %
                             (number, dest_version))
        for track in song.tracks:
            track.measures = trackMeasures[track.number - 1][:number]
        guitarpro.write(song, dest_path)


def track_bisect(test, song, dest_version=3):
    """Save song in *n* files, where *n* is number of tracks in song.

    Resulting tabs have following tracks:

    -   ``*-T01.gp?``: *1st* track
    -   ``*-T02.gp?``: *1st* and *2nd* track
    -   ...
    -   ``*-Tnn.gp?``: *1st*, *2nd*, ..., *nth* track

    This function helps to find the track where erroneous data was written
    using bisection method.

    """
    folder, _ = path.splitext(test)
    try:
        os.mkdir(path.join(OUTPUT, folder))
    except OSError:
        pass
    tracks = song.tracks[:]
    for number, track in enumerate(tracks, 1):
        dest_path = path.join(OUTPUT, folder, test + '-T%02d.gp%d' %
                             (number, dest_version))
        song.tracks = tracks[:number]
        guitarpro.write(song, dest_path)


def test_conversion():
    for filename in TESTS:
        yield convert_and_compare, filename


def convert_and_compare(filename):
    __, ext = path.splitext(filename)
    filepath = path.join(LOCATION, filename)
    song_a = guitarpro.parse(filepath)
    destpath = path.join(OUTPUT, filename + ext)
    guitarpro.write(song_a, destpath)
    song_b = guitarpro.parse(destpath)
    assert song_a == song_b
