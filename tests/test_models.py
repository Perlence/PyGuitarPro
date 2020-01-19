import pytest

import guitarpro as gp
import warnings


def test_hashable():
    song = gp.Song()
    hash(song)

    coda = gp.DirectionSign('Coda')
    segno = gp.DirectionSign('Segno')
    assert coda != segno
    assert hash(coda) != hash(segno)


@pytest.mark.parametrize('value', [1, 2, 4, 8, 16, 32, 64])
@pytest.mark.parametrize('isDotted', [False, True])
@pytest.mark.parametrize('tuplet', [gp.Tuplet(1, 1), gp.Tuplet(3, 2)])
def test_duration(value, isDotted, tuplet):
    dur = gp.Duration(value, isDotted=isDotted, tuplet=tuplet)
    time = dur.time
    new_dur = gp.Duration.fromTime(time)
    assert isinstance(new_dur.value, int)
    assert time == new_dur.time


def test_beat_start_in_measure():
    song = gp.Song()
    measure = song.tracks[0].measures[0]
    voice = measure.voices[0]
    beat = gp.Beat(voice, start=measure.start)
    beat2 = gp.Beat(voice, start=measure.start + beat.duration.time)
    voice.beats.append(beat)
    assert beat.startInMeasure == 0
    assert beat2.startInMeasure == 960

    warnings.simplefilter('always')
    with pytest.deprecated_call():
        assert beat2.realStart == 960
