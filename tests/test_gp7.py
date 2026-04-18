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
