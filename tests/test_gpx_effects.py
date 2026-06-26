import io
from pathlib import Path

import pytest

import guitarpro as gp


LOCATION = Path(__file__).parent
SAMPLE = LOCATION / 'A Simple Song.gpx'


def _roundtrip(song):
    buf = io.BytesIO()
    gp.write(song, buf, version=(6, 0, 0))
    buf.seek(0)
    return gp.parse(buf)


def _first_note(song):
    for measure in song.tracks[0].measures:
        for voice in measure.voices:
            for beat in voice.beats:
                if beat.notes:
                    return beat, beat.notes[0]
    raise AssertionError('no note found')


def test_real_file_effects_are_read():
    song = gp.parse(str(SAMPLE))
    effects = [note.effect
               for m in song.tracks[0].measures
               for v in m.voices
               for b in v.beats
               for note in b.notes]
    assert any(e.hammer for e in effects)
    assert any(e.slides for e in effects)
    assert any(e.harmonic is not None for e in effects)
    assert any(e.leftHandFinger is not gp.Fingering.open for e in effects)


def test_real_file_effects_roundtrip():
    song = gp.parse(str(SAMPLE))
    assert song == _roundtrip(song)


@pytest.mark.parametrize('mutate, check', [
    (lambda n: setattr(n.effect, 'heavyAccentuatedNote', True),
     lambda n: n.effect.heavyAccentuatedNote),
    (lambda n: setattr(n.effect, 'accentuatedNote', True),
     lambda n: n.effect.accentuatedNote),
    (lambda n: setattr(n.effect, 'staccato', True),
     lambda n: n.effect.staccato),
    (lambda n: setattr(n.effect, 'hammer', True),
     lambda n: n.effect.hammer),
    (lambda n: setattr(n.effect, 'rightHandFinger', gp.Fingering.middle),
     lambda n: n.effect.rightHandFinger is gp.Fingering.middle),
    (lambda n: setattr(n.effect, 'slides', [gp.SlideType.legatoSlideTo, gp.SlideType.intoFromBelow]),
     lambda n: set(n.effect.slides) == {gp.SlideType.legatoSlideTo, gp.SlideType.intoFromBelow}),
    (lambda n: setattr(n.effect, 'harmonic', gp.NaturalHarmonic()),
     lambda n: isinstance(n.effect.harmonic, gp.NaturalHarmonic)),
    (lambda n: setattr(n.effect, 'harmonic', gp.TappedHarmonic(fret=7)),
     lambda n: isinstance(n.effect.harmonic, gp.TappedHarmonic) and n.effect.harmonic.fret == 7),
])
def test_note_effect_roundtrip(mutate, check):
    song = gp.parse(str(SAMPLE))
    _, note = _first_note(song)
    mutate(note)
    _, restored = _first_note(_roundtrip(song))
    assert check(restored)


def test_beat_text_roundtrip():
    song = gp.parse(str(SAMPLE))
    beat, _ = _first_note(song)
    beat.text = 'riff'
    restored, _ = _first_note(_roundtrip(song))
    assert restored.text == 'riff'
