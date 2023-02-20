import pytest

import guitarpro as gp


def testHashable():
    song = gp.Song()
    hash(song)

    anotherSong = gp.Song()
    assert song == anotherSong
    assert hash(song) == hash(anotherSong)

    coda = gp.DirectionSign('Coda')
    segno = gp.DirectionSign('Segno')
    assert coda != segno
    assert hash(coda) != hash(segno)


@pytest.mark.parametrize('value', [1, 2, 4, 8, 16, 32, 64])
@pytest.mark.parametrize('isDotted', [False, True])
@pytest.mark.parametrize('tuplet', gp.Tuplet.supportedTuplets)
def testDuration(value, isDotted, tuplet):
    dur = gp.Duration(value, isDotted=isDotted, tuplet=gp.Tuplet(*tuplet))
    time = dur.time
    newDur = gp.Duration.fromTime(time)
    assert isinstance(newDur.value, int)
    assert time == newDur.time


def testGraceDuration():
    g16 = gp.GraceEffect(duration=16)
    assert g16.durationTime == 240
    g32 = gp.GraceEffect(duration=32)
    assert g32.durationTime == 120
    g64 = gp.GraceEffect(duration=64)
    assert g64.durationTime == 60


def testBeatStartInMeasure():
    song = gp.Song()
    measure = song.tracks[0].measures[0]
    voice = measure.voices[0]
    beat = gp.Beat(voice, start=measure.start)
    beat2 = gp.Beat(voice, start=measure.start + beat.duration.time)
    voice.beats.append(beat)
    assert beat.startInMeasure == 0
    assert beat2.startInMeasure == 960

    with pytest.raises(AttributeError):
        beat2.realStart


def testGuitarString():
    assert str(gp.GuitarString(number=1, value=0)) == 'C-1'
    assert str(gp.GuitarString(number=1, value=40)) == 'E2'
    assert str(gp.GuitarString(number=1, value=64)) == 'E4'
