import io
from pathlib import Path

import pytest

import guitarpro as gp


LOCATION = Path(__file__).parent
TESTS = [
    'Effects.gp3',
    'Chords.gp3',
    'Duration.gp3',
    'Harmonics.gp3',
    'Measure Header.gp3',

    'Effects.gp4',
    'Vibrato.gp4',
    'Chords.gp4',
    'Slides.gp4',
    'Harmonics.gp4',
    'Key.gp4',
    'Repeat.gp4',
    'Strokes.gp4',
    'Measure Header.gp4',

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
    'Measure Header.gp5',
    'Demo v5.gp5',
]
CONVERSION_TESTS = [
    # ('Effects.gp3', 'gp4'),
    ('Duration.gp3', 'gp4'),

    ('Slides.gp4', 'gp5'),
    ('Vibrato.gp4', 'gp5'),

    ('Repeat.gp4', 'gp5'),
]


@pytest.mark.parametrize('filename', TESTS)
def testReadWriteEquals(tmpdir, filename):
    filepath = LOCATION / filename
    songA = gp.parse(filepath)
    destpath = str(tmpdir.join(filename))
    gp.write(songA, destpath)
    songB = gp.parse(destpath)
    assert songA == songB


@pytest.mark.parametrize('source, targetExt', CONVERSION_TESTS)
def testConversion(tmpdir, source, targetExt):
    sourcepath = LOCATION / source
    songA = gp.parse(sourcepath)
    songA.versionTuple = None  # Remove the version so it's determined by the extension
    destpath = str(tmpdir.join(f'{source}.{targetExt}'))
    gp.write(songA, destpath)
    songB = gp.parse(destpath)
    assert songA == songB


def testClipboard(tmpdir):
    filepath = LOCATION / '2 whole bars.tmp'
    songA = gp.parse(filepath)
    songA.clipboard = None
    destpath = str(tmpdir.join('2 whole bars.tmp.gp5'))
    gp.write(songA, destpath)
    songB = gp.parse(destpath)
    assert songA == songB


def testEmpty(tmpdir):
    emptyA = gp.Song()
    destpath = str(tmpdir.join('Empty.gp5'))
    gp.write(emptyA, destpath, version=(5, 2, 0))

    emptyB = gp.parse(destpath)
    assert emptyA == emptyB


def testGuessVersion(tmpdir):
    filename = 'Effects.gp5'
    filepath = LOCATION / filename
    songA = gp.parse(filepath)
    songA.version = songA.versionTuple = None

    for ext, versionTuple in gp.io._EXT_VERSIONS.items():
        if ext == 'tmp':
            continue
        destpath = str(tmpdir.join(filename + '.' + ext))
        gp.write(songA, destpath)
        songB = gp.parse(destpath)
        assert songB.versionTuple == versionTuple


@pytest.mark.parametrize('filename', [
    'chord_without_notes.gp5',
    '001_Funky_Guy.gp5',
    'Unknown Chord Extension.gp5',
])
def testChord(tmpdir, caplog, filename):
    filepath = LOCATION / filename
    song = gp.parse(filepath)
    assert song.tracks[0].measures[0].voices[0].beats[0].effect.chord is not None

    destpath = str(tmpdir.join('no_chord_strings.gp5'))
    gp.write(song, destpath)
    if filename == 'Unknown Chord Extension.gp5':
        iobase_logs = [log for log in caplog.records if log.name == 'guitarpro.iobase']
        [record] = iobase_logs
        assert 'is an unknown ChordExtension' in record.msg
    song2 = gp.parse(destpath)
    assert song == song2


@pytest.mark.parametrize('version', ['gp3', 'gp4', 'gp5'])
def testReadErrorAnnotation(version):
    def writeToBytesIO(song):
        stream = io.BytesIO()
        stream.name = f'percusion.{version}'
        gp.write(song, stream, encoding='cp1252')
        stream.seek(0)
        return stream

    song = gp.Song()
    song.tracks[0].name = "Percusión"
    stream = writeToBytesIO(song)
    # readMeasureHeader
    with pytest.raises(gp.GPException, match="reading track 1, got UnicodeDecodeError: "):
        gp.parse(stream, encoding='ascii')

    song = gp.Song()
    song.tracks[0].measures[0].marker = gp.Marker(title="Percusión")
    stream = writeToBytesIO(song)
    # readTracks
    with pytest.raises(gp.GPException, match="reading measure 1, got UnicodeDecodeError: "):
        gp.parse(stream, encoding='ascii')

    song = gp.Song()
    voice = song.tracks[0].measures[0].voices[0]
    beat = gp.Beat(voice, text="Percusión")
    voice.beats.append(beat)
    stream = writeToBytesIO(song)
    # readMeasures
    with pytest.raises(gp.GPException, match="reading track 1, measure 1, voice 1, beat 1, got UnicodeDecodeError: "):
        gp.parse(stream, encoding='ascii')


@pytest.mark.parametrize('version', ['gp3', 'gp4', 'gp5'])
def testWriteErrorAnnotation(version):
    fp = io.BytesIO()
    fp.name = f'beep.{version}'

    song = gp.Song()
    song.tracks[0].measures[0].timeSignature.numerator = 'nooo'
    # writeMeasureHeader
    with pytest.raises(gp.GPException, match="writing measure 1, got ValueError: invalid"):
        gp.write(song, fp)

    song = gp.Song()
    song.tracks[0].fretCount = 'nooo'
    # writeTracks
    with pytest.raises(gp.GPException, match="writing track 1, got ValueError: invalid"):
        gp.write(song, fp)

    song = gp.Song()
    voice = song.tracks[0].measures[0].voices[0]
    invalidBeat = gp.Beat(voice, status='nooo')
    voice.beats.append(invalidBeat)
    # writeMeasures
    with pytest.raises(gp.GPException, match="writing track 1, measure 1, voice 1, beat 1, got AttributeError: 'str'"):
        gp.write(song, fp)
