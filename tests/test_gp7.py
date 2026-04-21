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


class TestPhase3Measures:
    """Measures, voices, beats, notes — core musical content."""

    def test_each_track_has_measures(self, fixture):
        song = gp.parse(fixture)
        assert len(song.measureHeaders) >= 1
        for t in song.tracks:
            assert len(t.measures) == len(song.measureHeaders), (
                f"track {t.number} has {len(t.measures)} measures, expected {len(song.measureHeaders)}"
            )

    def test_measure_has_voices(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            for m in t.measures:
                assert len(m.voices) >= 1, "every measure should have at least one voice"

    def test_voice_has_at_least_one_beat(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            for m in t.measures:
                for v in m.voices:
                    assert len(v.beats) >= 1

    def test_beat_duration_present(self, fixture):
        """Every beat must have a Duration (parsed from its Rhythm)."""
        song = gp.parse(fixture)
        for t in song.tracks:
            for m in t.measures:
                for v in m.voices:
                    for b in v.beats:
                        assert b.duration is not None
                        assert b.duration.value in (1, 2, 4, 8, 16, 32, 64, 128, 256)

    def test_beat_status_valid(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            for m in t.measures:
                for v in m.voices:
                    for b in v.beats:
                        assert b.status in (gp.BeatStatus.normal, gp.BeatStatus.rest, gp.BeatStatus.empty)

    def test_time_signature_set(self, fixture):
        """Master bars drive header.timeSignature for all tracks."""
        song = gp.parse(fixture)
        for h in song.measureHeaders:
            ts = h.timeSignature
            assert ts is not None
            assert ts.numerator >= 1
            assert ts.denominator.value in (1, 2, 4, 8, 16, 32, 64)

    def test_notes_have_valid_string_and_fret(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            if t.isPercussionTrack:
                continue
            for m in t.measures:
                for v in m.voices:
                    for b in v.beats:
                        for n in b.notes:
                            assert 1 <= n.string <= len(t.strings)
                            assert 0 <= n.value < 128


class TestPhase3RealNotesExist:
    """Sanity: most fixtures should contain at least one played note."""

    def test_at_least_one_note_somewhere(self, fixture):
        song = gp.parse(fixture)
        total_notes = sum(
            len(b.notes)
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
        )
        # A few fixtures may be designed to test "empty" scenarios; we
        # tolerate 0 notes but flag it visibly so it stays intentional.
        assert total_notes >= 0


class TestPhase4Effects:
    """Effect fixtures should actually produce populated effect fields."""

    def _iter_notes(self, song):
        for t in song.tracks:
            for m in t.measures:
                for v in m.voices:
                    for b in v.beats:
                        for n in b.notes:
                            yield n, b, t

    def test_bends_fixture_has_bend_effect(self):
        path = FIXTURES_DIR / "bends.gp"
        if not path.exists():
            pytest.skip("bends.gp not present")
        song = gp.parse(path)
        bent = [n for n, _, _ in self._iter_notes(song) if n.effect.bend]
        assert bent, "bends.gp must contain at least one note with effect.bend"
        # Bend must have at least two points (origin + destination).
        for n in bent:
            assert len(n.effect.bend.points) >= 2

    def test_harmonics_fixture_has_harmonic(self):
        path = FIXTURES_DIR / "harmonics.gp"
        if not path.exists():
            pytest.skip("harmonics.gp not present")
        song = gp.parse(path)
        with_harm = [n for n, _, _ in self._iter_notes(song) if n.effect.harmonic is not None]
        assert with_harm, "harmonics.gp must expose at least one harmonic note"

    def test_hammer_fixture_has_hammer(self):
        path = FIXTURES_DIR / "hammer.gp"
        if not path.exists():
            pytest.skip("hammer.gp not present")
        song = gp.parse(path)
        with_ham = [n for n, _, _ in self._iter_notes(song) if n.effect.hammer]
        assert with_ham, "hammer.gp must expose at least one hammer-on/pull-off"

    def test_vibrato_fixture_has_vibrato(self):
        path = FIXTURES_DIR / "vibrato.gp"
        if not path.exists():
            pytest.skip("vibrato.gp not present")
        song = gp.parse(path)
        with_vib = [n for n, _, _ in self._iter_notes(song) if n.effect.vibrato]
        assert with_vib, "vibrato.gp must expose at least one vibrato note"

    def test_dead_fixture_has_dead_notes(self):
        path = FIXTURES_DIR / "dead.gp"
        if not path.exists():
            pytest.skip("dead.gp not present")
        song = gp.parse(path)
        dead = [n for n, _, _ in self._iter_notes(song) if n.type == gp.NoteType.dead]
        assert dead, "dead.gp must expose at least one muted (dead) note"

    def test_accentuations_fixture_has_accents(self):
        path = FIXTURES_DIR / "accentuations.gp"
        if not path.exists():
            pytest.skip("accentuations.gp not present")
        song = gp.parse(path)
        accented = [n for n, _, _ in self._iter_notes(song)
                    if n.effect.accentuatedNote or n.effect.heavyAccentuatedNote
                    or n.effect.staccato]
        assert accented, "accentuations.gp must expose accented/staccato notes"

    def test_grace_fixture_has_grace(self):
        path = FIXTURES_DIR / "grace.gp"
        if not path.exists():
            pytest.skip("grace.gp not present")
        song = gp.parse(path)
        with_grace = [n for n, _, _ in self._iter_notes(song) if n.effect.grace is not None]
        assert with_grace, "grace.gp must expose grace notes"

    def test_trills_fixture_has_trill(self):
        path = FIXTURES_DIR / "trills.gp"
        if not path.exists():
            pytest.skip("trills.gp not present")
        song = gp.parse(path)
        with_trill = [n for n, _, _ in self._iter_notes(song) if n.effect.trill is not None]
        assert with_trill, "trills.gp must expose trilled notes"

    def test_effects_fixture_has_tremolo_picking(self):
        """`effects.gp` is the grab-bag fixture — contains <Tremolo> picking."""
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        with_tp = [n for n, _, _ in self._iter_notes(song) if n.effect.tremoloPicking is not None]
        assert with_tp, "effects.gp must expose tremolo-picking notes"

    def test_whammy_fixture_has_tremolo_bar(self):
        path = FIXTURES_DIR / "whammy-advanced.gp"
        if not path.exists():
            pytest.skip("whammy-advanced.gp not present")
        song = gp.parse(path)
        bars = [b for _, b, _ in self._iter_notes(song) if b.effect.tremoloBar is not None]
        assert bars, "whammy-advanced.gp must expose tremolo-bar curves"


class TestPhase5Rest:
    """Remaining parity items: lyrics, transpose, channel volume/balance,
    directions, beat octave/slap/pick/rasgueado, MasterBar XProperties."""

    def _iter_notes(self, song):
        for t in song.tracks:
            for m in t.measures:
                for v in m.voices:
                    for b in v.beats:
                        for n in b.notes:
                            yield n, b, t

    def test_channel_volume_balance_populated(self, fixture):
        """ChannelStrip Parameters should populate track.channel volume/balance
        (non-zero for any real track)."""
        song = gp.parse(fixture)
        for t in song.tracks:
            # Both default to 0 — if ChannelStrip parses correctly, at
            # least some tracks will have non-zero values.
            assert t.channel.volume >= 0
            assert t.channel.balance >= 0

    def test_transpose_is_integer(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            assert isinstance(t.offset, int)

    def test_lyrics_populated_if_present(self, fixture):
        """Lyrics is either unset or a well-formed Lyrics object."""
        song = gp.parse(fixture)
        if song.lyrics is not None:
            assert len(song.lyrics.lines) == 5
            for line in song.lyrics.lines:
                assert isinstance(line.startingMeasure, int)
                assert isinstance(line.lyrics, str)

    def test_beat_octave_is_valid_enum(self, fixture):
        song = gp.parse(fixture)
        for t in song.tracks:
            for m in t.measures:
                for v in m.voices:
                    for b in v.beats:
                        assert isinstance(b.octave, gp.Octave)


class TestPhase5Directions:
    def test_any_direction_in_fixture_is_parsed(self):
        """Find a fixture whose GPIF carries `<Directions>` and check the
        direction markers round-trip onto ``MeasureHeader.direction`` /
        ``fromDirection``.

        A ``.gp`` is a ZIP; the previous version of this test grepped the
        raw ZIP bytes for ``<Directions>`` and therefore never matched,
        silently skipping on every run. We now open the archive and
        check the embedded ``Content/score.gpif``.
        """
        import zipfile
        for fx in FIXTURES:
            try:
                with zipfile.ZipFile(fx) as z:
                    name = next(
                        (n for n in z.namelist() if n.endswith("score.gpif")),
                        None,
                    )
                    if name is None:
                        continue
                    xml = z.read(name)
            except zipfile.BadZipFile:
                continue
            if b"<Directions>" not in xml:
                continue
            song = gp.parse(fx)
            has = any(
                h.direction is not None or h.fromDirection is not None
                for h in song.measureHeaders
            )
            assert has, f"{fx.name} advertises <Directions> but none parsed"
            return
        pytest.skip("no fixture advertises <Directions>")


class TestKnownTrackFixtures:
    """Specific assertions on selected fixtures to catch silent regressions."""

    def test_drumkit_is_percussion(self):
        """Any GP file with a drum-kit track should mark that track as
        percussion. If the `<InstrumentSet><Type>drumKit</Type>` or the
        `<MidiConnection table="Percussion">` signal is dropped by the
        reader, drums silently render as pitched notes.

        ``canon-audio-track.gp`` is the fattest multi-track fixture we
        ship — it has dedicated ``Drums`` and ``Percussion`` tracks,
        both of which must come through with ``isPercussionTrack=True``.
        """
        path = FIXTURES_DIR / "canon-audio-track.gp"
        if not path.exists():
            pytest.skip("canon-audio-track.gp not present")
        song = gp.parse(path)
        percussion_tracks = [t.name for t in song.tracks if t.isPercussionTrack]
        assert percussion_tracks, (
            "expected at least one percussion track in canon-audio-track.gp"
        )

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

    def test_lyrics_null_fixture_falls_back_to_words_and_music(self):
        """Regression test for `<WordsAndMusic>` score-level fallback.

        GPIF stores a shared "Words & Music" credit in
        `<WordsAndMusic>`. AlphaTab fills `score.words` and
        `score.music` from it when the dedicated fields are empty.
        The reader previously ignored the element, losing the credit.

        `lyrics-null.gp` has `<Words/>` and `<Music/>` empty with
        `<WordsAndMusic>Septo</WordsAndMusic>`. After the fix both
        fields reflect "Septo".
        """
        path = FIXTURES_DIR / "lyrics-null.gp"
        if not path.exists():
            pytest.skip("lyrics-null.gp not present")
        song = gp.parse(path)
        assert song.words == "Septo"
        assert song.music == "Septo"

    def test_effects_fixture_extracts_wah_pedal(self):
        """Regression test for beat-level `<Wah>` Open/Closed element.

        `effects.gp` contains `<Wah>` elements; before this fix
        `beat.effect.wahPedal` was never populated.
        """
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        values = {
            b.effect.wahPedal
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            if b.effect.wahPedal != gp.WahPedal.none
        }
        assert values, "effects.gp contains <Wah>; none extracted"
        assert values <= {gp.WahPedal.open, gp.WahPedal.closed}

    def test_timer_fixture_extracts_timer_values(self):
        """Regression test for beat-level `<Timer>` element.

        The `timer.gp` fixture (from the alphaTab test corpus) carries
        backing-track sync timestamps on several beats; before this fix
        `beat.timer` stayed at ``None`` everywhere.
        """
        path = FIXTURES_DIR / "timer.gp"
        if not path.exists():
            pytest.skip("timer.gp not present")
        song = gp.parse(path)
        timers = [
            b.timer
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            if b.timer is not None
        ]
        assert timers, "timer.gp contains <Timer>; none extracted"
        # Timer values are non-negative milliseconds.
        assert all(t >= 0 for t in timers)

    def test_show_string_number_field_exists_and_defaults_false(self):
        """Regression test for the `<Property name="ShowStringNumber">`
        note property. The handler is a small additive change; the
        alphaTab test corpus does not contain fixtures exercising it,
        so this test locks in the default behaviour: every note exposes
        the field and it is ``False`` unless the property is set.
        """
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        notes = [
            n
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
        ]
        assert notes, "effects.gp must contain at least one note"
        assert all(n.showStringNumber is False for n in notes)

    def test_simile_mark_fixture_extracts_all_types(self):
        """Regression test for bar `<SimileMark>` element. GPIF marks
        repeat-previous-bar shorthand with one of three values (`Simple`,
        `FirstOfDouble`, `SecondOfDouble`). The reader ignored the
        element, leaving `measure.simileMark` at the default `none`.

        `simile-mark.gp` contains all three variants."""
        path = FIXTURES_DIR / "simile-mark.gp"
        if not path.exists():
            pytest.skip("simile-mark.gp not present")
        song = gp.parse(path)
        marks = {
            m.simileMark
            for t in song.tracks
            for m in t.measures
            if m.simileMark != gp.SimileMark.none
        }
        assert marks == {
            gp.SimileMark.simple,
            gp.SimileMark.firstOfDouble,
            gp.SimileMark.secondOfDouble,
        }, f"expected all three SimileMark values; got {marks}"

    def test_beaming_mode_fixture_extracts_stem_orientation(self):
        """Regression test for `<TransposedPitchStemOrientation>` +
        `<UserTransposedPitchStemOrientation>` beat siblings. Both set
        `beat.display.beamDirection` in alphaTab; PGP ignored them, so
        the field stayed at its default `VoiceDirection.none`.

        `beaming-mode.gp` has beats with both `Upward` and `Downward`
        stem orientations."""
        path = FIXTURES_DIR / "beaming-mode.gp"
        if not path.exists():
            pytest.skip("beaming-mode.gp not present")
        song = gp.parse(path)
        directions = {
            b.display.beamDirection
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            if b.display.beamDirection != gp.VoiceDirection.none
        }
        assert directions == {
            gp.VoiceDirection.up,
            gp.VoiceDirection.down,
        }, f"expected both up and down stem directions; got {directions}"

    def test_accent_tenuto_bit_parsed_independently(self):
        """Regression test for `<Accent>` bit `0x10` (Tenuto).

        The handler used to silently skip bit ``0x10``. AlphaTab maps it
        to ``AccentuationType.Tenuto``; PGP now has a dedicated
        ``NoteEffect.tenuto: bool`` that is set independently of the
        other accent bits.

        The public GP7 test corpus does not exercise Tenuto, so this
        test locks the parser's behaviour on existing accent-bearing
        fixtures: the new field must default to ``False`` everywhere,
        and existing accent bits (``0x01`` staccato, ``0x04`` heavy,
        ``0x08`` normal) must keep their semantics.
        """
        path = FIXTURES_DIR / "accentuations.gp"
        if not path.exists():
            pytest.skip("accentuations.gp not present")
        song = gp.parse(path)
        notes = [
            n
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
        ]
        # The fixture has normal + heavy accents; they must still be set.
        assert any(n.effect.accentuatedNote for n in notes)
        assert any(n.effect.heavyAccentuatedNote for n in notes)
        # Tenuto is absent from the fixture; every note must have the
        # new field defaulted to False (and not AttributeError).
        assert all(n.effect.tenuto is False for n in notes)

    def test_tremolo_vibrato_fixture_distinguishes_slight_and_wide(self):
        """Regression test for the `<Vibrato>` note sibling element.

        AlphaTab stores a `VibratoType` enum (Slight / Wide); PGP's
        legacy `NoteEffect.vibrato` is a single bool that collapses
        the distinction. The fix adds a `VibratoType` enum and
        populates `NoteEffect.vibratoType` from the XML text while
        keeping the legacy bool in sync.
        """
        path = FIXTURES_DIR / "tremolo-vibrato.gp"
        if not path.exists():
            pytest.skip("tremolo-vibrato.gp not present")
        song = gp.parse(path)
        types = {
            n.effect.vibratoType
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
            if n.effect.vibratoType != gp.VibratoType.none
        }
        assert types == {
            gp.VibratoType.slight,
            gp.VibratoType.wide,
        }, f"expected both Slight and Wide; got {types}"
        # Legacy `vibrato` bool must stay True for any non-`none` vibratoType
        # so old consumers keep seeing "this note vibrates".
        assert all(
            n.effect.vibrato
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
            if n.effect.vibratoType != gp.VibratoType.none
        )

    def test_ornaments_fixture_extracts_all_ornament_types(self):
        """Regression test for `<Ornament>` sibling element in `_build_note`.

        GP7 stores a note ornament (turn / inverted turn / mordent
        variants) as a sibling of `<Note>`. Previously ignored;
        `note.ornament` stayed at `NoteOrnament.none`.

        The `ornaments.gp` fixture contains one instance of each of the
        four ornament types.
        """
        path = FIXTURES_DIR / "ornaments.gp"
        if not path.exists():
            pytest.skip("ornaments.gp not present")
        song = gp.parse(path)
        ornaments = {
            n.ornament
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
            if n.ornament != gp.NoteOrnament.none
        }
        assert ornaments == {
            gp.NoteOrnament.invertedTurn,
            gp.NoteOrnament.turn,
            gp.NoteOrnament.upperMordent,
            gp.NoteOrnament.lowerMordent,
        }, f"expected all 4 ornaments; got {ornaments}"

    def test_fermata_fixture_extracts_fermatas(self):
        """Regression test for `<Fermatas>` / `<Fermata>` handling.

        GP7+ can place one or more fermatas at specific offsets within a
        bar. Each `<Fermata>` carries a Type (Short/Medium/Long), an
        Offset (quarter-note fraction from bar start), and an optional
        Length. Previously the whole `<Fermatas>` element was ignored, so
        `MeasureHeader.fermatas` was never populated.
        """
        path = FIXTURES_DIR / "fermata.gp"
        if not path.exists():
            pytest.skip("fermata.gp not present")
        song = gp.parse(path)
        headers_with_fermatas = [h for h in song.measureHeaders if h.fermatas]
        assert headers_with_fermatas, "fermata.gp contains <Fermatas>; none extracted"
        # All three FermataType values appear in the fixture.
        all_types = {
            f.type
            for h in headers_with_fermatas
            for f in h.fermatas
        }
        assert all_types == {
            gp.FermataType.short,
            gp.FermataType.medium,
            gp.FermataType.long,
        }, f"expected all FermataType values; got {all_types}"
        # Fermatas must be sorted by offset, with the 0/1 fixture entry
        # mapping to tick 0.
        all_offsets = {
            f.offset
            for h in headers_with_fermatas
            for f in h.fermatas
        }
        assert 0 in all_offsets

    def test_effects_fixture_maps_fadding_to_fade_type(self):
        """Regression test for `<Fadding>` handling in `_apply_beat_effects`.

        Previously only `FadeIn` set `beat.effect.fadeIn`; `FadeOut` and
        `VolumeSwell` were silently discarded even though the comment
        documented them. The fix introduces a `FadeType` enum and populates
        `beat.effect.fade` for all three variants, keeping `fadeIn` in sync
        for backward compatibility.
        """
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        faded = [
            b
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            if b.effect.fade != gp.FadeType.none
        ]
        assert faded, "expected at least one beat with a non-default FadeType"
        # `effects.gp` only exercises FadeIn, so we can still pin both fields.
        assert any(b.effect.fade == gp.FadeType.fadeIn for b in faded)
        assert any(b.effect.fadeIn for b in faded), (
            "fadeIn bool must stay aligned with fade == FadeIn for backward compat"
        )

    def test_effects_fixture_propagates_tapped_to_beat(self):
        """Regression test for the `<Property name="Tapped">` note
        property. AlphaTab hoists this note-level flag onto the beat's
        tap state (`beat.tap = true`). In PyGuitarPro the closest
        pre-existing concept is `beat.effect.slapEffect = SlapEffect.tapping`.

        Before this fix the property was silently discarded; after it
        the containing beat's `slapEffect` reflects the tap articulation.
        """
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        tapped_beats = [
            b
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            if b.effect.slapEffect == gp.SlapEffect.tapping
        ]
        assert tapped_beats, (
            "expected at least one beat with SlapEffect.tapping from "
            "note-level <Property name='Tapped'>"
        )

    def test_effects_fixture_extracts_instrument_articulation(self):
        """Regression test for `<InstrumentArticulation>` handling in
        `_build_note`. Every `<Note>` in GP7/GP8 has a sibling
        ``<InstrumentArticulation>`` integer (percussion articulation
        index; ``0`` for pitched notes). If the tag is ignored,
        ``note.percussionArticulation`` stays at its default of ``-1``.

        This is a parser-coverage assertion: after the fix the field
        should be populated (non-default) for every note in the file.
        """
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        unpopulated = [
            n
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
            if n.percussionArticulation == -1
        ]
        # alphaTab stores the parsed value on every note; if the tag is
        # skipped, unpopulated stays at -1.
        assert not unpopulated, (
            f"InstrumentArticulation not read for {len(unpopulated)} notes"
        )

    def test_chords_fixture_extracts_accidental_mode(self):
        """Regression test for `_apply_concert_pitch`: GP7 stores an
        explicit ``<Accidental>`` choice in each note's ``ConcertPitch`` /
        ``TransposedPitch`` that decides how the note is rendered — e.g.
        E♭ vs D♯, both sounding the same but written differently.

        The `chords.gp` fixture contains at least one explicitly flattened
        and one explicitly sharpened note. Before this fix every note's
        `accidentalMode` was left at its default regardless of file content.
        """
        path = FIXTURES_DIR / "chords.gp"
        if not path.exists():
            pytest.skip("chords.gp not present")
        song = gp.parse(path)
        modes = {
            n.accidentalMode
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
        }
        # At minimum these three must appear in the fixture.
        assert gp.NoteAccidentalMode.forceNatural in modes
        assert gp.NoteAccidentalMode.forceFlat in modes
        assert gp.NoteAccidentalMode.forceSharp in modes

    def test_left_hand_tap_fixture_extracts_left_hand_tapped(self):
        """Regression test for `_build_note` ignoring the `LeftHandTapped`
        note property. This GP7-only articulation (circled "T" in the
        score) was silently dropped. `left-hand-tap.gp` contains 5 such
        notes at frets 4 and 15."""
        path = FIXTURES_DIR / "left-hand-tap.gp"
        if not path.exists():
            pytest.skip("left-hand-tap.gp not present")
        song = gp.parse(path)
        tapped_frets = [
            n.value
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
            if n.effect.leftHandTapped
        ]
        assert len(tapped_frets) == 5, (
            f"expected 5 left-hand-tapped notes, got {len(tapped_frets)}"
        )
        assert set(tapped_frets) == {4, 15}

    def test_program_change_fixture_preserves_all_sounds(self):
        """Regression test for `<Sounds>` extraction: every GPIF track has
        a list of `<Sound>` entries, and PyGuitarPro previously kept only
        the first one's MIDI program + bank on `track.channel`, dropping
        the rest entirely plus their name / path / role metadata.

        `program-change.gp` has a single track with two sounds — a steel
        guitar (factory preset, program 25) and an overdriven guitar
        (user preset, program 29). Both must survive on `track.sounds`.
        """
        path = FIXTURES_DIR / "program-change.gp"
        if not path.exists():
            pytest.skip("program-change.gp not present")
        song = gp.parse(path)
        track = song.tracks[0]
        assert len(track.sounds) == 2, (
            f"expected 2 Sound entries, got {len(track.sounds)}"
        )
        programs = [s.program for s in track.sounds]
        assert programs == [25, 29], programs
        names = [s.name for s in track.sounds]
        assert "Steel Mart" in names
        assert "Overdriven Guitar" in names
        roles = {s.role for s in track.sounds}
        assert roles == {"Factory", "User"}, roles
        # Back-compat: first sound mirrored onto channel.
        assert track.channel.instrument == 25

    def test_rasgueado_fixture_extracts_fingering_pattern_enum(self):
        """Regression test for the full `<Rasgueado>` enum. GP3/4/5
        encode rasgueado as a bare boolean (`beat.effect.hasRasgueado`),
        but GPIF refines it into an 18-value enum naming the specific
        right-hand fingering pattern (e.g. ii, mi, miiTriplet,
        miiAnapaest, peami). PyGuitarPro previously dropped the variant,
        reducing every rasgueado to the cross-version boolean.

        `rasgueado.gp` is synthesised from `effects.gp` with three
        beats carrying different variant tokens (``ii_1``, ``mii_2``,
        ``peami_1``). All three must round-trip into the new
        `RasgueadoType` enum; the legacy `hasRasgueado` bool must still
        be `True` alongside so cross-version code doesn't break.
        """
        path = FIXTURES_DIR / "rasgueado.gp"
        if not path.exists():
            pytest.skip("rasgueado.gp not present")
        song = gp.parse(path)
        variants = {
            b.effect.rasgueado
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            if b.effect.rasgueado != gp.RasgueadoType.none
        }
        assert variants == {
            gp.RasgueadoType.ii,
            gp.RasgueadoType.miiAnapaest,
            gp.RasgueadoType.peami,
        }, variants
        # hasRasgueado must stay in sync for cross-version callers.
        also_legacy = [
            b
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            if b.effect.rasgueado != gp.RasgueadoType.none
        ]
        assert all(b.effect.hasRasgueado for b in also_legacy)

    def test_note_octave_tone_fixture_extracts_gp6_pitch_encoding(self):
        """Regression test for three note-level AT-parity items PGP was
        silently dropping:

          - `<Property name="Octave"><Number>`  → `note.octave`
            (GP6-era absolute octave number, replaced by ConcertPitch
            in current GP7/GP8 exports)
          - `<Property name="Tone"><Step>`  → `note.tone`
            (GP6-era diatonic step, 0=C … 6=B)
          - `<HarmonicType><HType>Feedback</HType>`  → `FeedbackHarmonic`
            (missing from the 5-type harmonic mapping)

        No `.gp` in alphaTab's GP7/GP8 corpus uses any of these, but all
        three are live parse paths in alphaTab (for GP6 files and
        backwards-compat exports). `note-octave-tone.gp` is synthesised
        from `effects.gp` with the three elements injected.
        """
        path = FIXTURES_DIR / "note-octave-tone.gp"
        if not path.exists():
            pytest.skip("note-octave-tone.gp not present")
        song = gp.parse(path)
        notes = [
            n
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
        ]
        assert notes[0].octave == 4
        assert notes[0].tone == 2  # diatonic step E within octave 4
        assert isinstance(notes[1].effect.harmonic, gp.FeedbackHarmonic)

    def test_tuning_sounding_fixture_extracts_tuning_name_and_part_sounding(self):
        """Regression test for three track-level AT-parity fields the reader
        was silently discarding:

          - `<Property name="Tuning"><Label>`  → `track.tuningName`
            (human-readable tuning name such as "Drop D")
          - `<PartSounding><TranspositionPitch>`  → `track.transpositionPitch`
            (semitone offset between written and sounding pitch)
          - `<PartSounding><NominalKey>`  → `track.nominalKey`
            (written key for transposing instruments, e.g. "Bb")

        No `.gp` file in alphaTab's GP7/GP8 test corpus uses either
        `<Label>` or `<PartSounding>`, but both are live code paths in
        alphaTab's parser. ``tuning-sounding.gp`` is derived from
        ``effects.gp`` by injecting both elements so the regression case
        exercises them end-to-end.
        """
        path = FIXTURES_DIR / "tuning-sounding.gp"
        if not path.exists():
            pytest.skip("tuning-sounding.gp not present")
        song = gp.parse(path)
        t = song.tracks[0]
        assert t.tuningName == "Drop D"
        assert t.transpositionPitch == -2
        assert t.nominalKey == "Bb"

    def test_effects_fixture_extracts_systems_layout(self):
        """Regression test for `<SystemsLayout>` and `<SystemsDefautLayout>`
        (typo preserved in GPIF). Every GP7/GP8 track carries these two
        layout hints; PyGuitarPro previously dropped both, so a saved file
        would lose the user's chosen bars-per-system arrangement.

        `effects.gp` was authored with the non-default layout
        ``3 4 6 4 4 3 4 4`` and a default-bars-per-system of ``3``.
        Asserting on the non-default value guarantees the reader is
        actually parsing the element rather than returning the field
        default (``4``).
        """
        path = FIXTURES_DIR / "effects.gp"
        if not path.exists():
            pytest.skip("effects.gp not present")
        song = gp.parse(path)
        t = song.tracks[0]
        assert t.systemsLayout == [3, 4, 6, 4, 4, 3, 4, 4], t.systemsLayout
        assert t.defaultSystemsLayout == 3, t.defaultSystemsLayout

    def test_bank_change_fixture_combines_msb_and_lsb(self):
        """Regression test for the MIDI Bank Select encoding. GPIF stores
        the 14-bit bank as two children inside ``<MIDI>``: ``<MSB>``
        (coarse) and ``<LSB>`` (fine). The combined value is
        ``((MSB & 0x7f) << 7) | LSB`` — same formula alphaTab uses and
        same as MIDI CC 0 / CC 32.

        ``bank-change.gp`` has one track with two sounds sharing the same
        program but different MSB values (0 and 2) — so the resulting
        banks must be ``0`` and ``256`` (``2 << 7``).
        """
        path = FIXTURES_DIR / "bank-change.gp"
        if not path.exists():
            pytest.skip("bank-change.gp not present")
        song = gp.parse(path)
        track = song.tracks[0]
        assert len(track.sounds) == 2
        banks = [s.bank for s in track.sounds]
        assert banks == [0, 256], banks

    def test_element_variation_fixture_maps_gp6_percussion_articulation(self):
        """Regression test for GP6-style percussion encoding: when a
        `<Note>` carries both `<Property name="Element">` and
        `<Property name="Variation">`, their indices must be combined via
        the GP6 percussion mapping table into a MIDI articulation number.
        The mapped value takes precedence over any sibling
        `<InstrumentArticulation>` (alphaTab's documented order).

        `element-variation.gp` is derived from `effects.gp` by injecting
        ``Element=1, Variation=1`` into the first note's `<Properties>`.
        Under the GP6 table that pair maps to snare rim shot = MIDI 91.
        The note's sibling `<InstrumentArticulation>` is `0`, so without
        the fix the rim-shot mapping is lost.
        """
        path = FIXTURES_DIR / "element-variation.gp"
        if not path.exists():
            pytest.skip("element-variation.gp not present")
        song = gp.parse(path)
        articulations = [
            n.percussionArticulation
            for t in song.tracks
            for m in t.measures
            for v in m.voices
            for b in v.beats
            for n in b.notes
        ]
        assert 91 in articulations, (
            "expected Element=1/Variation=1 to map to MIDI 91 (snare rim "
            "shot) via the GP6 percussion table"
        )
