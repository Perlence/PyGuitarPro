import io
import zipfile
from pathlib import Path

import pytest

import guitarpro as gp
from guitarpro.gpx import decompress, extractGPIF


LOCATION = Path(__file__).parent
SAMPLE = LOCATION / 'A Simple Song.gpx'
# Triggers the zero-padded final byte in the BCFZ stream.
DEAR_SONG = LOCATION / 'Dear Song.gpx'


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


def test_parse_zero_padded_stream():
    # The BCFZ payload of this file ends mid-byte, exercising the
    # zero-padding path in the bit reader.
    song = gp.parse(str(DEAR_SONG))
    assert song.title == 'Dear Song'
    assert song.tempo == 55
    track = song.tracks[0]
    assert len(track.measures) == 22
    # Compound and simple meters both appear.
    signatures = {(m.timeSignature.numerator, m.timeSignature.denominator.value)
                  for m in track.measures}
    assert (3, 8) in signatures
    assert (6, 8) in signatures
    # A dotted duration is present.
    assert any(b.duration.isDotted
               for m in track.measures
               for v in m.voices
               for b in v.beats)


def test_parse_gp7_zip_container():
    # A GP7 (.gp) file is a ZIP archive with the score at
    # Content/score.gpif. Repackage a .gpx score into that layout and
    # confirm it produces the same song.
    gpif = extractGPIF(SAMPLE.read_bytes())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('VERSION', '7.0')
        archive.writestr('Content/score.gpif', gpif)
    buf.seek(0)

    song = gp.parse(buf)
    reference = gp.parse(str(SAMPLE))
    assert song.title == reference.title
    assert song == reference


def test_compress_decompress_roundtrip():
    from guitarpro.gpx import compress, decompress
    gpif = extractGPIF(SAMPLE.read_bytes())
    assert decompress(compress(gpif)) == gpif
    for payload in (b'', b'A', b'ABC', b'\x00\x00\x00\x00', bytes(range(256)) * 8):
        assert decompress(compress(payload)) == payload


@pytest.mark.parametrize('sample', [SAMPLE, DEAR_SONG])
def test_write_gpx_roundtrip(tmp_path, sample):
    song = gp.parse(str(sample))
    dest = tmp_path / 'out.gpx'
    gp.write(song, str(dest), version=(6, 0, 0))
    assert dest.read_bytes()[:4] == b'BCFZ'
    reparsed = gp.parse(str(dest))
    assert song == reparsed
    assert hash(song) == hash(reparsed)


def test_write_gp7_roundtrip(tmp_path):
    song = gp.parse(str(SAMPLE))
    dest = tmp_path / 'out.gp'
    gp.write(song, str(dest), version=(7, 0, 0))
    assert dest.read_bytes()[:2] == b'PK'
    reparsed = gp.parse(str(dest))
    assert song == reparsed


def test_write_dispatches_by_extension(tmp_path):
    song = gp.parse(str(SAMPLE))
    for ext, magic in (('gpx', b'BCFZ'), ('gp', b'PK')):
        dest = tmp_path / f'out.{ext}'
        gp.write(song, str(dest))  # no explicit version
        assert dest.read_bytes()[:len(magic)] == magic
        assert gp.parse(str(dest)) == song


def test_parse_counts():
    # GPIF shares voices, beats and notes by reference; the model expands
    # those references into concrete objects per measure.
    song = gp.parse(str(SAMPLE))
    track = song.tracks[0]
    beats = [b for m in track.measures for v in m.voices for b in v.beats]
    notes = sum(len(b.notes) for b in beats)
    assert len(beats) == 268
    assert notes == 227
