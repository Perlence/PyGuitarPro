from pathlib import Path

import guitarpro as gp
from guitarpro.gpx import decompress, extractGPIF


LOCATION = Path(__file__).parent
SAMPLE = LOCATION / 'A Simple Song.gpx'


def test_extract_gpif_returns_xml():
    data = SAMPLE.read_bytes()
    gpif = extractGPIF(data)
    assert gpif.lstrip().startswith(b'<?xml')
    assert b'<GPIF>' in gpif


def test_decompress_roundtrips_length():
    data = SAMPLE.read_bytes()
    assert data[:4] == b'BCFZ'
    decompressed = decompress(data[4:])
    assert decompressed[:4] == b'BCFS'


def test_parse_score_info():
    song = gp.parse(str(SAMPLE))
    assert song.title == 'A Simple Song'
    assert song.artist == 'Hirokazu Sato (1966-2016)'
    assert song.subtitle == 'www.classclef.com'
    assert song.tempo == 65


def test_parse_track_and_tuning():
    song = gp.parse(str(SAMPLE))
    assert len(song.tracks) == 1
    track = song.tracks[0]
    assert track.name == 'Nylon Guitar'
    # Standard tuning, high E to low E.
    assert [s.value for s in track.strings] == [64, 59, 55, 50, 45, 40]


def test_parse_measures_and_beats():
    song = gp.parse(str(SAMPLE))
    track = song.tracks[0]
    assert len(track.measures) == 31

    # First measure: two eighth notes, time signature 1/4.
    measure = track.measures[0]
    assert measure.timeSignature.numerator == 1
    assert measure.timeSignature.denominator.value == 4
    beats = measure.voices[0].beats
    assert len(beats) == 2
    assert all(b.duration.value == gp.Duration.eighth for b in beats)
    assert beats[0].notes[0].value == 5
    assert beats[0].notes[0].string == 6


def test_parse_counts():
    # GPIF shares voices, beats and notes by reference; the model expands
    # those references into concrete objects per measure.
    song = gp.parse(str(SAMPLE))
    track = song.tracks[0]
    beats = [b for m in track.measures for v in m.voices for b in v.beats]
    notes = sum(len(b.notes) for b in beats)
    assert len(beats) == 268
    assert notes == 227
