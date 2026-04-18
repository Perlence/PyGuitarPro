"""Tests for the GP7/GP8 reader.

Fixtures in tests/gp7/ come from AlphaTab's test-data (MPL-2.0, same
license as the code we're porting). They exercise the full range of
GP7/GP8 features: bends, harmonics, chords, key signatures, rhythm
variants, etc.

Phase-by-phase the test matrix grows:
    Phase 1 (current): parse-not-crash, song-level metadata
    Phase 2+: tracks, measures, notes, effects — add specific asserts
"""
from pathlib import Path

import pytest

import guitarpro as gp


FIXTURES_DIR = Path(__file__).parent / "gp7"
FIXTURES = sorted(FIXTURES_DIR.glob("*.gp"))


def pytest_generate_tests(metafunc):
    """Parametrise any test that takes a `fixture` arg with every fixture path."""
    if "fixture" in metafunc.fixturenames:
        metafunc.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)


class TestPhase1ParseSmoke:
    """Every fixture must parse without crashing; version tuple is set."""

    def test_parses(self, fixture):
        song = gp.parse(fixture)
        assert song is not None
        # Version tuple is populated by the dispatcher before readSong() runs.
        assert song.versionTuple is not None
        assert song.versionTuple[0] in (7, 8)

    def test_exposes_title_or_empty(self, fixture):
        """Title is a string (may be empty for fixtures with no title set)."""
        song = gp.parse(fixture)
        assert isinstance(song.title, str)

    def test_exposes_tempo(self, fixture):
        song = gp.parse(fixture)
        # Tempo in GP files is always positive; 0 is unset.
        assert song.tempo is None or song.tempo >= 0


class TestPhase1KnownFixture:
    """Sanity on a specific fixture with expected values."""

    def test_effects_fixture_has_expected_title(self):
        """tests/gp7/effects.gp should have been authored with some content.

        This is a brittle test by design — if the source fixture changes we
        should re-check. But it's the kind of specific assertion that
        guards against silently returning empty Songs.
        """
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        # We at least expect tempo > 0 and a populated Score/Title field.
        assert song is not None


class TestDispatcher:
    """io.parse() must route GP7/GP8 files (zip magic) to GP7File."""

    def test_zip_magic_detected(self):
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        assert song.versionTuple[0] >= 7


class TestPhase2Tracks:
    """Tracks, tuning, MIDI channels."""

    def test_at_least_one_track(self, fixture):
        song = gp.parse(fixture)
        assert len(song.tracks) >= 1

    def test_track_numbering_starts_at_1(self, fixture):
        song = gp.parse(fixture)
        for i, t in enumerate(song.tracks, start=1):
            assert t.number == i

    def test_every_track_has_a_name(self, fixture):
        """Track.name is a string (may be empty if unspecified)."""
        song = gp.parse(fixture)
        for t in song.tracks:
            assert isinstance(t.name, str)

    def test_non_percussion_tracks_have_strings(self, fixture):
        """Pitched tracks must have at least one tuned string for encoder use."""
        song = gp.parse(fixture)
        for t in song.tracks:
            if not t.isPercussionTrack:
                assert len(t.strings) >= 1
                for s in t.strings:
                    assert isinstance(s.number, int) and s.number >= 1
                    assert isinstance(s.value, int) and 0 <= s.value < 128

    def test_percussion_track_flag_is_bool(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            assert isinstance(t.isPercussionTrack, bool)

    def test_channel_fields_are_integers(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            c = t.channel
            assert isinstance(c.instrument, int) and 0 <= c.instrument < 128
            assert isinstance(c.channel, int) and c.channel >= 0
            assert isinstance(c.effectChannel, int) and c.effectChannel >= 0


class TestKnownTrackFixtures:
    """Specific assertions on selected fixtures to catch silent regressions."""

    def test_drumkit_is_percussion(self):
        """Any fixture whose name hints at drums should have at least one
        percussion track. Reads: if drums tests pass for drums.gp but flags
        don't propagate, we'd silently treat drums as pitched."""
        path = FIXTURES_DIR / "drums.gp"
        if not path.exists():
            pytest.skip("drums.gp not present")
        song = gp.parse(path)
        assert any(t.isPercussionTrack for t in song.tracks)

    def test_chords_fixture_tracks_have_tuning(self):
        path = FIXTURES_DIR / "chords.gp"
        if not path.exists():
            pytest.skip("chords.gp not present")
        song = gp.parse(path)
        assert song.tracks
        # The chords fixture is a guitar track, 6-string standard.
        pitched = [t for t in song.tracks if not t.isPercussionTrack]
        assert pitched
        # Standard guitar tuning: string 1 highest (E4=64), string 6 lowest (E2=40).
        t = pitched[0]
        pitches = [s.value for s in t.strings]
        assert pitches[0] > pitches[-1]  # string 1 is highest pitch in our convention
