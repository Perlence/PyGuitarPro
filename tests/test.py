import os
from os import path

import guitarpro

location = '.'
output = './output'
tests = [
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


def product(test, song):
    for destVersion in range(3, 6):
        destPath = path.join(output, test + '.gp%d' % destVersion)
        guitarpro.write(song, destPath)


def bisect(test, song, destVersion=3):
    folder, _ = path.splitext(test)
    try:
        os.mkdir(path.join(output, folder))
    except OSError:
        pass
    trackMeasures = [track.measures for track in song.tracks]
    for number, _ in enumerate(trackMeasures[0], 1):
        destPath = path.join(output, folder, test + '-%03d.gp%d' %
                             (number, destVersion))
        for track in song.tracks:
            track.measures = trackMeasures[track.number - 1][:number]
        guitarpro.write(song, destPath)


def trackBisect(test, song, destVersion=3):
    folder, _ = path.splitext(test)
    try:
        os.mkdir(path.join(output, folder))
    except OSError:
        pass
    tracks = song.tracks[:]
    for number, track in enumerate(tracks, 1):
        destPath = path.join(output, folder, test + '-T%02d.gp%d' %
                             (number, destVersion))
        song.tracks = tracks[:number]
        guitarpro.write(song, destPath)


def main():
    for test in tests:
        filepath = path.join(location, test)
        song = guitarpro.parse(filepath)
        product(test, song)


if __name__ == '__main__':
    main()
