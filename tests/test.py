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
]

for test in tests:
    filepath = path.join(location, test)
    song = guitarpro.parse(filepath)
    for destVersion in range(3, 6):
        destPath = path.join(output, test + '.gp%d' % destVersion)
        guitarpro.write(song, destPath)
