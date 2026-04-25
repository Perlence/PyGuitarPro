"""Tests for the GP6 (GPX container) reader.

Fixtures in tests/gp6/ come from AlphaTab's test-data (MPL-2.0, same
license as the code we're porting).

GP6 uses AlphaTab's proprietary GPX container — either BCFZ (compressed,
a custom Deflate variant) or BCFS (uncompressed). Both wrap the same
embedded ``score.gpif`` XML that GP7/GP8 use, so once the container is
decoded the rest of the parser is the GP7/GP8 path.

Phase 1 asserts: every fixture parses and exposes top-level Song
metadata. Deeper per-feature assertions follow the GP7 test matrix.
"""
from pathlib import Path

import pytest

import guitarpro as gp


FIXTURES_DIR = Path(__file__).parent / "gp6"
FIXTURES = sorted(FIXTURES_DIR.glob("*.gpx"))


def pytest_generate_tests(metafunc):
    """Parametrise any test that takes a ``fixture`` arg with every fixture path."""
    if "fixture" in metafunc.fixturenames:
        metafunc.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)


class TestPhase1ParseSmoke:
    """Every fixture must parse without crashing; version tuple is set."""

    def test_parses(self, fixture):
        song = gp.parse(fixture)
        assert song is not None
        assert song.versionTuple is not None
        # BCFZ/BCFS fixtures are routed to GpifFile with a GP6 initial tuple;
        # the parser may refine to (7,0,0)/(8,0,0) from <GPVersion> if present.
        assert song.versionTuple[0] in (6, 7, 8)

    def test_exposes_title(self, fixture):
        song = gp.parse(fixture)
        assert isinstance(song.title, str)

    def test_exposes_tempo(self, fixture):
        song = gp.parse(fixture)
        assert song.tempo is None or song.tempo >= 0


class TestDispatcher:
    """``io.parse()`` must route BCFZ/BCFS files through ``GpxArchive`` into
    ``GpifFile._load_score_gpif``."""

    def test_bcfz_magic_routes_to_gp7_path(self):
        path = FIXTURES_DIR / "bends.gpx"
        if not path.exists():
            pytest.skip("bends.gpx not present")
        with open(path, "rb") as f:
            magic = f.read(4)
        assert magic == b"BCFZ", f"fixture lost its magic bytes: {magic!r}"
        song = gp.parse(path)
        # successful parse proves dispatch worked
        assert song is not None
        assert len(song.tracks) >= 1

    def test_bcfs_magic_accepted(self, tmp_path):
        """BCFS uncompressed containers are rare in the wild but part of the
        GPX spec; ensure the dispatch handles them too. We synthesise a
        minimal BCFS wrapper around a BCFZ fixture's decompressed body."""
        # We don't have a BCFS fixture from AT; this is a smoke test that the
        # magic-byte dispatch accepts the BCFS prefix without raising at the
        # io layer. Actual decompression on a real BCFS file is exercised by
        # the audit/bcfz-verify.py harness on corpus data.
        from guitarpro.gpx import GpxFileSystem

        bcfz_path = FIXTURES_DIR / "bends.gpx"
        if not bcfz_path.exists():
            pytest.skip("bends.gpx not present")
        # Decompress the BCFZ container to get the raw filesystem body.
        data = bcfz_path.read_bytes()
        from guitarpro.gpx import _BitReader, _ByteSource

        src = _BitReader(_ByteSource(data))
        fs = GpxFileSystem()
        # Re-run decompress directly to obtain the uncompressed body (header skipped).
        header = fs.read_header(src)
        assert header == "BCFZ"
        body = fs.decompress(src, skip_header=True)
        # Prepend a BCFS header and pass through our loader.
        synthetic = b"BCFS" + body
        fs2 = GpxFileSystem()
        fs2.load(synthetic)
        names = [f.file_name for f in fs2.files]
        assert "score.gpif" in names


class TestPhase1KnownFixture:
    """Specific assertions on a known fixture."""

    def test_bends_fixture_has_content(self):
        path = FIXTURES_DIR / "bends.gpx"
        if not path.exists():
            pytest.skip("bends.gpx not present")
        song = gp.parse(path)
        assert song is not None
        assert len(song.tracks) >= 1
        # At least one measure should be present.
        assert any(len(t.measures) > 0 for t in song.tracks)
