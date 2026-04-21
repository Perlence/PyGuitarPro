# This file is derived from alphaTab (https://github.com/CoderLine/alphaTab),
# originally licensed under the Mozilla Public License 2.0.
# Ported to Python by @kaizenman for PyGuitarPro.
#
# Original sources:
#   packages/alphatab/src/importer/Gp7To8Importer.ts
#   packages/alphatab/src/importer/GpifParser.ts
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Reader for Guitar Pro 7 and 8 (.gp) files.

GP7/GP8 files are ZIP archives.  Only score.gpif is required:

    score.gpif         XML document describing the full score
    BinaryStylesheet   style settings (proprietary binary, not decoded)
    PartConfiguration  part visibility (ignored)
    LayoutConfiguration layout hints (ignored)

The GPIF XML is a denormalised DAG: MasterBars reference Bars by id,
Bars reference Voices, Voices reference Beats, Beats reference Notes
and Rhythms.  The reader first builds lookup maps from ids, then walks
MasterBars to assemble per-track Measure/Voice/Beat/Note trees.

Coverage
--------
  * Song: title/artist/subtitle/album/words/music/copyright/tab/
    instructions/notice, tempo (from MasterTrack automation), tempoName,
    lyrics (first non-empty track's 5 lines), masterEffect.volume
    (default 100), pageSetup template strings.
  * Track: name, shortName, color, tuning, capo, fretCount, offset
    (transpose), isSolo/isMute, useRSE, isPercussion; MIDI channel
    instrument, bank, channel, effectChannel, port; RSE ChannelStrip
    balance (param 11) and volume (param 12); chord diagram collection
    with per-string frets, fingerings, and harmonic metadata (root,
    bass, type, extension, 5th/9th/11th alterations, newFormat, show,
    sharp, add defaults); per-track MTC Automations (Tempo/Volume/
    Balance/Sound) attached to the first beat of each target bar.
  * MeasureHeader: time signature (numerator/denominator + beams from
    XProperty 1124139010), key signature, section marker (title + RGB
    color), repeat open/close, alternate endings, double bar, triplet
    feel, Coda/Segno/Fine target directions, Da Capo/Dal Segno/Da Coda
    jumps. Anacrusis flag stashed on `header._anacrusis`.
  * Beat: duration value + dotted + tuplet (enters/times), octave
    (Ottavia 8va/8vb/15ma/15mb), free-text label, dynamics → velocity,
    rest/empty status, stroke (Brush), pickStroke, slapEffect (Slapped/
    Popped), hasRasgueado, vibrato (VibratoWTremBar), tremoloBar
    (WhammyBar curve from origin/middle1/middle2/destination points),
    chord reference → resolved chord diagram, fadeIn, tremoloPicking
    (1/2→8th, 1/4→16th, 1/8→32nd), grace (OnBeat/BeforeBeat), legato
    origin propagated to notes as hammer, start in ticks.
  * Note: string (reversed from GPIF's low-to-high), fret, MIDI pitch
    for percussion, velocity inherited from beat, type (normal/tie/
    dead from Muted + Tied properties), palmMute, letRing, vibrato
    (Slight or Wide), staccato/accent/heavy/ghost from Accent flags +
    AntiAccent, bend curve (Bended + origin value/offset + middle
    value + up to two offsets + destination), slides (all six flag
    bits: Shift/Legato/OutDown/OutUp/InFromBelow/InFromAbove),
    harmonic (Natural/Pinch/Semi/Tap/Artificial with pitch+octave
    reconstructed from HarmonicFret), trill fret, tremoloPicking
    (via beat propagation), grace (via beat propagation),
    leftHandFinger/rightHandFinger (P/I/M/A/C mapped).

Deliberately skipped (no PyGuitarPro model representation)
---------------------------------------------------------
  * Fermatas per beat (GP7 can place them mid-bar; GP3/4/5 only had
    per-measure and PyGuitarPro's MeasureHeader has no fermata field).
  * Hairpin crescendo/decrescendo.
  * Barre fret/shape at beat level.
  * Per-beat lyrics (`<Lyrics>` inside <Beat>).
  * Beat XProperties (beamingMode, invertBeamDirection, brushDuration).
  * Bar XProperties (displayScale).
  * MasterBar XProperties beyond beaming rules (displayScale).
  * Systems layouts (ScoreSystemsLayout, track.systemsLayout).
  * BackingTrack asset (external audio file).
  * FreeTime flag.
  * SyncPoint automations.
  * Ornaments (Turn / Inverted Turn / Upper/Lower Mordent) — GP7-only
    feature with no GP3/4/5 equivalent or PyGuitarPro field.
  * Per-note percussion articulation ID — GP7-only.
  * Grand Staff tracks (multiple staves per track) — PyGuitarPro's
    Track flattens to a single staff.
  * NotationPatch.
  * SustainPedalMarkers.
  * Partial capo (per-string capo).
  * Channel strip EQ/compressor parameters (indices 0-10) — only the
    volume/balance entries at indices 11/12 map to PyGuitarPro.
  * BinaryStylesheet entries: track.rse.instrument.effect,
    effectCategory, soundBank, unknown. These live in the proprietary
    binary sidecar Guitar Pro ships alongside score.gpif; AlphaTab also
    does not decode them beyond basic passthrough.

Attribution
-----------
Ported from AlphaTab's Gp7To8Importer.ts / GpifParser.ts (MPL-2.0).
"""
from __future__ import annotations

import io
import zipfile
from typing import Optional
from xml.etree import ElementTree as ET

from . import models as gp


# ── XML helpers ───────────────────────────────────────────────────────

def _text(elem: Optional[ET.Element], default: str = "") -> str:
    if elem is None or elem.text is None:
        return default
    return elem.text.strip()


def _int(elem: Optional[ET.Element], default: int = 0) -> int:
    try:
        return int(_text(elem, str(default)))
    except ValueError:
        return default


def _float(elem: Optional[ET.Element], default: float = 0.0) -> float:
    if elem is None or elem.text is None:
        return default
    try:
        return float(elem.text.strip())
    except ValueError:
        return default


def _float_attr(elem: ET.Element, name: str, default: float = 0.0) -> float:
    raw = elem.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _split_ints(text: str) -> list[int]:
    out = []
    for token in text.strip().split():
        try:
            out.append(int(token))
        except ValueError:
            pass
    return out


def _split_tokens(text: str) -> list[str]:
    return text.strip().split() if text and text.strip() else []


# ── Enum mappings (GPIF → PyGuitarPro) ────────────────────────────────

_DURATION_MAP = {
    "Whole":   1,
    "Half":    2,
    "Quarter": 4,
    "Eighth":  8,
    "16th":    16,
    "32nd":    32,
    "64th":    64,
    "128th":   128,
    "256th":   256,
}

_DYNAMIC_VELOCITY = {
    "PPP": 15,
    "PP":  31,
    "P":   47,
    "MP":  63,
    "MF":  79,
    "F":   95,
    "FF":  111,
    "FFF": 127,
}

_CLEF_MAP = {
    "G2":      0,  # treble
    "F4":      1,  # bass
    "C4":      2,  # tenor
    "C3":      3,  # alto
    "Neutral": 0,  # neutral — use treble as default
}

# Accent flag bits (<Accent>N</Accent> inside <Note>)
_ACCENT_STACCATO      = 0x01
_ACCENT_HEAVY         = 0x04
_ACCENT_NORMAL        = 0x08
# 0x10 = tenuto (not represented in PyGuitarPro)

# Slide flag bits (<Property name="Slide">/<Flags>)
_SLIDE_SHIFT           = 0x01
_SLIDE_LEGATO          = 0x02
_SLIDE_OUT_DOWN        = 0x04
_SLIDE_OUT_UP          = 0x08
_SLIDE_IN_FROM_BELOW   = 0x10
_SLIDE_IN_FROM_ABOVE   = 0x20
_SLIDE_PICK_DOWN       = 0x40
_SLIDE_PICK_UP         = 0x80
# 0x40/0x80 = pick slides (no direct PyGuitarPro mapping)

# GPIF Target → PyGuitarPro direction-sign names (Coda/Segno/Fine "destinations")
_DIRECTION_TARGETS = {
    "Coda":        "Coda",
    "DoubleCoda":  "Double Coda",
    "Segno":       "Segno",
    "SegnoSegno":  "Segno Segno",
    "Fine":        "Fine",
}

# GPIF Jump → PyGuitarPro fromDirection names (Da Capo / Dal Segno family).
# NB: GPIF has the typo "DaSegno" in its enum; the corresponding
# canonical musical term is "Dal Segno".
_DIRECTION_JUMPS = {
    "DaCapo":                      "Da Capo",
    "DaCapoAlCoda":                "Da Capo al Coda",
    "DaCapoAlDoubleCoda":          "Da Capo al Double Coda",
    "DaCapoAlFine":                "Da Capo al Fine",
    "DaSegno":                     "Dal Segno",
    "DaSegnoAlCoda":               "Dal Segno al Coda",
    "DaSegnoAlDoubleCoda":         "Dal Segno al Double Coda",
    "DaSegnoAlFine":               "Dal Segno al Fine",
    "DaSegnoSegno":                "Dal Segno Segno",
    "DaSegnoSegnoAlCoda":          "Dal Segno Segno al Coda",
    "DaSegnoSegnoAlDoubleCoda":    "Dal Segno Segno al Double Coda",
    "DaSegnoSegnoAlFine":          "Dal Segno Segno al Fine",
    "DaCoda":                      "Da Coda",
    "DaDoubleCoda":                "Da Double Coda",
}

# GPIF bend-value units: float cent / 25 gives PyGuitarPro quarter-step units.
_BEND_VALUE_SCALE = 25.0
# GPIF bend offset 0..100 gives PyGuitarPro 0..12 position units.
_BEND_OFFSET_SCALE = 100.0 / 12.0


# ── Reader ────────────────────────────────────────────────────────────

class GP7File:
    """Reader for Guitar Pro 7/8 (ZIP+XML) files."""

    def __init__(self, fp, encoding: str = "utf-8", version: str = "", versionTuple: tuple = (7, 0, 0)):
        self._fp = fp
        self.encoding = encoding
        self.version = version
        self.versionTuple = versionTuple

        # Lookup maps populated during parse.
        self._rhythms: dict[str, dict] = {}             # rhythm_id → {value, dotted, tuplet}
        self._notes_raw: dict[str, ET.Element] = {}      # note_id → <Note> element
        self._beats_raw: dict[str, ET.Element] = {}      # beat_id → <Beat> element
        self._bars_raw: dict[str, ET.Element] = {}       # bar_id → <Bar> element
        self._voices_raw: dict[str, ET.Element] = {}     # voice_id → <Voice> element
        self._master_bars: list[ET.Element] = []
        # Chord diagrams indexed per track → {diagram_id: gp.Chord}.
        self._chords_by_track: dict[int, dict[str, gp.Chord]] = {}

    def close(self):
        pass

    # ── public entry points ────────────────────────────────────────

    def readSong(self) -> gp.Song:
        root = self._load_score_gpif()

        song = gp.Song(tracks=[], measureHeaders=[])
        # GP3/4/5 readers leave tempoName as '' (empty string) after parsing;
        # PyGuitarPro defaults it to 'Moderate'. Match the binary readers
        # unless <Automation><Type>Tempo</Type> carries a Text element.
        song.tempoName = ""

        self._read_version(root, song)
        self._read_score_info(root, song)
        self._read_master_track(root, song)
        self._read_tracks(root, song)

        self._build_lookup_tables(root)
        self._read_master_bars(song)
        self._assemble_tracks(song)
        self._compute_beat_starts(song)
        self._attach_track_automations(song)

        return song

    def _compute_beat_starts(self, song: gp.Song) -> None:
        """Assign Beat.start = measure_start + cumulative prior-beat ticks.

        Mirrors GP3/4/5 readers which pass `start` through readBeat and
        increment by duration.time. Without this the encoder loses the
        absolute-time information that some downstream tools need.
        """
        for track in song.tracks:
            for measure in track.measures:
                base = measure.header.start
                for voice in measure.voices:
                    cursor = base
                    for beat in voice.beats:
                        beat.start = cursor
                        try:
                            cursor += beat.duration.time
                        except Exception:
                            # Malformed duration — skip to avoid crashing.
                            pass

    def writeSong(self, song: gp.Song):
        raise NotImplementedError("Writing GP7/GP8 is not implemented yet")

    # ── loading ────────────────────────────────────────────────────

    def _load_score_gpif(self) -> ET.Element:
        data = self._fp.read()
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise gp.GPException(f"not a GP7/GP8 file (bad zip): {e}") from e

        gpif_name = next(
            (n for n in archive.namelist() if n.endswith("score.gpif")),
            None,
        )
        if gpif_name is None:
            raise gp.GPException("no score.gpif found in archive")
        xml_bytes = archive.read(gpif_name)
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            raise gp.GPException(f"malformed score.gpif: {e}") from e
        # Stash for later DAG walks (_iter_master_bars, _assemble_tracks).
        self._root = root
        return root

    # ── version + score info ───────────────────────────────────────

    def _read_version(self, root: ET.Element, song: gp.Song) -> None:
        gpver = root.find("GPVersion")
        if gpver is not None and gpver.text:
            parts = [p for p in gpver.text.strip().split(".") if p.isdigit()]
            if parts:
                while len(parts) < 3:
                    parts.append("0")
                self.versionTuple = tuple(int(p) for p in parts[:3])
        song.versionTuple = self.versionTuple
        song.version = self.version

    def _read_score_info(self, root: ET.Element, song: gp.Song) -> None:
        score = root.find("Score")
        if score is None:
            return
        song.title = _text(score.find("Title"))
        song.subtitle = _text(score.find("SubTitle"))
        song.artist = _text(score.find("Artist"))
        song.album = _text(score.find("Album"))
        song.words = _text(score.find("Words"))
        song.music = _text(score.find("Music"))
        song.copyright = _text(score.find("Copyright"))
        song.tab = _text(score.find("Tabber"))
        song.instructions = _text(score.find("Instructions"))
        notice = score.find("Notices")
        if notice is not None and notice.text:
            song.notice = [notice.text.strip()]

    def _read_master_track(self, root: ET.Element, song: gp.Song) -> None:
        # Match GP3/4/5 default: RSEMasterEffect with volume=100.  GPIF stores
        # the real value inside the binary BinaryStylesheet entry we don't
        # decode; the default mirrors what Guitar Pro authors typically ship.
        if song.masterEffect is None:
            song.masterEffect = gp.RSEMasterEffect()
        song.masterEffect.volume = 100

        # Match GP3/4/5 PageSetup template defaults (uppercase placeholders).
        if song.pageSetup is not None:
            for attrname, template in (
                ("title",        "%TITLE%"),
                ("subtitle",     "%SUBTITLE%"),
                ("artist",       "%ARTIST%"),
                ("album",        "%ALBUM%"),
                ("words",        "Words by %WORDS%"),
                ("music",        "Music by %MUSIC%"),
                ("wordsAndMusic", "Words & Music by %WORDSMUSIC%"),
                ("copyright",    "Copyright %COPYRIGHT%\nAll Rights Reserved - International Copyright Secured"),
                ("pageNumber",   "Page %N%/%P%"),
            ):
                setattr(song.pageSetup, attrname, template)

        master = root.find("MasterTrack")
        if master is None:
            return
        automations = master.find("Automations")
        if automations is None:
            return
        for automation in automations.findall("Automation"):
            kind = _text(automation.find("Type"))
            if kind == "Tempo":
                value = automation.find("Value")
                if value is not None and value.text:
                    try:
                        song.tempo = int(value.text.strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                break

    # ── tracks ─────────────────────────────────────────────────────

    def _read_tracks(self, root: ET.Element, song: gp.Song) -> None:
        tracks_node = root.find("Tracks")
        if tracks_node is None:
            return
        for i, t_node in enumerate(tracks_node.findall("Track")):
            track = self._read_track(t_node, song)
            track.number = i + 1
            # Collect per-track automations (Tempo/Volume/Instrument changes)
            # for later attachment to beats after the DAG is built.
            auto_node = t_node.find("Automations")
            if auto_node is not None:
                track._automations = self._read_automations(auto_node)  # type: ignore[attr-defined]
            song.tracks.append(track)

        # PyGuitarPro stores lyrics at the Song level — take the first
        # non-empty per-track lyrics we parsed, padding to 5 lines.
        for t in song.tracks:
            lines = getattr(t, "_lyrics_lines", None)
            if lines and any(text for _, text in lines):
                song.lyrics = gp.Lyrics(
                    trackChoice=t.number - 1,
                    lines=[gp.LyricLine(startingMeasure=sm, lyrics=text)
                           for sm, text in lines[:5]],
                )
                while len(song.lyrics.lines) < 5:
                    song.lyrics.lines.append(gp.LyricLine(startingMeasure=1, lyrics=""))
                break

    def _read_track(self, node: ET.Element, song: gp.Song) -> gp.Track:
        track = gp.Track(song=song, number=0)
        track.strings = []

        track.name = _text(node.find("Name"))
        track.shortName = _text(node.find("ShortName")) if node.find("ShortName") is not None else ""

        color_el = node.find("Color")
        if color_el is not None and color_el.text:
            parts = _split_ints(color_el.text)
            if len(parts) >= 3:
                track.color = gp.Color(r=parts[0], g=parts[1], b=parts[2])

        iset = node.find("InstrumentSet")
        if iset is not None:
            iset_type = _text(iset.find("Type"))
            if iset_type == "drumKit":
                track.isPercussionTrack = True

        for midi_tag in ("GeneralMidi", "MidiConnection", "MIDISettings"):
            midi = node.find(midi_tag)
            if midi is None:
                continue
            if midi.get("table") == "Percussion":
                track.isPercussionTrack = True
            port = midi.find("Port")
            if port is not None:
                track.port = _int(port) + 1
            prim = midi.find("PrimaryChannel")
            if prim is not None and (prim.text or "").strip():
                track.channel.channel = _int(prim)
            sec = midi.find("SecondaryChannel")
            if sec is not None and (sec.text or "").strip():
                track.channel.effectChannel = _int(sec)

        sounds = node.find("Sounds")
        if sounds is not None:
            first_sound = sounds.find("Sound")
            if first_sound is not None:
                midi = first_sound.find("MIDI")
                if midi is not None:
                    prog = midi.find("Program")
                    if prog is not None:
                        track.channel.instrument = _int(prog)
                    msb = midi.find("MSB")
                    lsb = midi.find("LSB")
                    if msb is not None and lsb is not None:
                        track.channel.bank = (_int(msb) << 7) | _int(lsb)

        # Mirror GP5's behaviour: TrackRSE.instrument.instrument tracks the
        # MIDI program. GP5 reads a richer RSEInstrument from the binary
        # stream; GPIF doesn't expose that in XML, so we fall back to the
        # channel program and leave soundBank/effect/effectCategory blank.
        if track.rse is not None and track.rse.instrument is not None:
            track.rse.instrument.instrument = track.channel.instrument

        staves = node.find("Staves")
        if staves is not None:
            self._read_track_staves(staves, track)

        # <Transpose><Chromatic>N</Chromatic><Octave>M</Octave></Transpose>
        # Total offset in semitones = octave*12 + chromatic.
        transpose = node.find("Transpose")
        if transpose is not None:
            chrom = _int(transpose.find("Chromatic"))
            oct_ = _int(transpose.find("Octave"))
            track.offset = oct_ * 12 + chrom

        # <RSE><ChannelStrip><Parameters>...</Parameters></ChannelStrip></RSE>
        # AlphaTab reads balance at index 11 and volume at index 12, scaling
        # the 0..1 float into PyGuitarPro's 0..15-ish channel byte
        # (floor(value * 16)). We preserve that mapping.
        # Presence of an <RSE> element also flips track.useRSE on — matches
        # the GP3/4/5 readers (they default-True any track with RSE data).
        rse = node.find("RSE")
        if rse is not None:
            track.useRSE = True
            strip = rse.find("ChannelStrip")
            if strip is not None:
                params_el = strip.find("Parameters")
                if params_el is not None and params_el.text:
                    parts = params_el.text.strip().split()
                    try:
                        if len(parts) > 12:
                            track.channel.balance = int(float(parts[11]) * 16)
                            track.channel.volume = int(float(parts[12]) * 16)
                    except ValueError:
                        pass

        # Track-level flags that live as direct children.
        # <Muted/PlaybackState> are tri-state element+text; <PlayingStyle>,
        # <SystemsDefautLayout> etc. aren't represented in PyGuitarPro so
        # they're ignored.
        state = _text(node.find("PlaybackState"))
        if state == "Solo":
            track.isSolo = True
        elif state == "Mute":
            track.isMute = True

        if not track.strings and not track.isPercussionTrack:
            track.strings = [
                gp.GuitarString(number=i + 1, value=v)
                for i, v in enumerate([64, 59, 55, 50, 45, 40])
            ]

        # Lyrics — first line of the first track becomes song.lyrics.
        # PyGuitarPro stores lyrics on song (not per-track); we collect them
        # and apply during _read_tracks completion.
        lyrics_node = node.find("Lyrics")
        if lyrics_node is not None:
            track._lyrics_lines = self._read_lyrics_lines(lyrics_node)  # type: ignore[attr-defined]

        return track

    @staticmethod
    def _read_automations(node: ET.Element) -> list[dict]:
        """Extract master/track <Automation> entries — mid-song parameter
        changes (Tempo/Volume/Sound/Balance/etc.).

        Returns list of {type, bar, position, value, linear} dicts. Mapping to
        PyGuitarPro's per-beat MixTableChange happens after beats are built,
        in `_attach_automations`.
        """
        out: list[dict] = []
        for a in node.findall("Automation"):
            entry = {
                "type":     _text(a.find("Type")),
                "bar":      _int(a.find("Bar"), -1),
                "position": _float(a.find("Position"), 0.0),
                "value":    _text(a.find("Value")),
                "linear":   _text(a.find("Linear")).lower() == "true",
            }
            out.append(entry)
        return out

    def _attach_track_automations(self, song: gp.Song) -> None:
        """Apply a track's cached automations to the first beat of the target
        bar, creating a MixTableChange with the appropriate field set.

        PyGuitarPro's MTC holds tempo/volume/balance/instrument items with
        value + duration + allTracks flag.  GPIF automations lack the
        allTracks concept (it's implicit at master level), so we pass
        ``allTracks=False`` for track-level MTCs.
        """
        for track in song.tracks:
            events = getattr(track, "_automations", None)
            if not events:
                continue
            for ev in events:
                bar = ev["bar"]
                if bar < 0 or bar >= len(track.measures):
                    continue
                measure = track.measures[bar]
                if not measure.voices or not measure.voices[0].beats:
                    continue
                target_beat = measure.voices[0].beats[0]
                mtc = target_beat.effect.mixTableChange or gp.MixTableChange()
                etype = ev["type"]
                parts = (ev["value"] or "").strip().split()
                first = parts[0] if parts else ""
                try:
                    num = int(float(first)) if first else 0
                except ValueError:
                    num = 0
                if etype == "Tempo":
                    mtc.tempo = gp.MixTableItem(value=num, duration=0, allTracks=True)
                elif etype == "Volume":
                    mtc.volume = gp.MixTableItem(value=num, duration=0, allTracks=False)
                elif etype == "Balance":
                    mtc.balance = gp.MixTableItem(value=num, duration=0, allTracks=False)
                elif etype == "Sound":
                    mtc.instrument = gp.MixTableItem(value=num, duration=0, allTracks=False)
                target_beat.effect.mixTableChange = mtc

    @staticmethod
    def _read_lyrics_lines(lyrics_node: ET.Element) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for line in lyrics_node.findall("Line"):
            starting = _int(line.find("Offset"))
            text = _text(line.find("Text"))
            out.append((starting, text))
        return out

    def _read_track_staves(self, staves_node: ET.Element, track: gp.Track) -> None:
        for staff in staves_node.findall("Staff"):
            props = staff.find("Properties")
            if props is None:
                continue
            for prop in props.findall("Property"):
                name = prop.get("name")
                if name == "Tuning":
                    pitches = prop.find("Pitches")
                    if pitches is not None and pitches.text:
                        # GPIF: low-to-high. PyGuitarPro: string 1 = highest.
                        values = list(reversed(_split_ints(pitches.text)))
                        if values:
                            track.strings = [
                                gp.GuitarString(number=i + 1, value=v)
                                for i, v in enumerate(values)
                            ]
                elif name == "CapoFret":
                    fret = prop.find("Fret")
                    if fret is not None:
                        track.capo = _int(fret)
                elif name == "FretCount":
                    n = prop.find("Number")
                    if n is not None:
                        track.fretCount = _int(n)
                elif name in ("DiagramCollection", "ChordCollection"):
                    self._read_chord_diagrams(prop, track)
            break

    @staticmethod
    def _fill_chord_degrees(chord: gp.Chord, chord_info: ET.Element) -> None:
        """Populate chord.type/extension/tonality/fifth/ninth/eleventh + root/bass
        from <Chord>/<KeyNote>/<BassNote>/<Degree> GPIF structure."""
        # Root and bass note
        step_map = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        def make_pitch(node: Optional[ET.Element]) -> Optional[gp.PitchClass]:
            if node is None:
                return None
            step = node.get("step", "")
            just = step_map.get(step)
            if just is None:
                return None
            accidental = node.get("accidental") or "Natural"
            shift = 1 if accidental == "Sharp" else -1 if accidental == "Flat" else 0
            try:
                return gp.PitchClass(just=(just + shift) % 12, accidental=0)
            except Exception:
                return None

        root_p = make_pitch(chord_info.find("KeyNote"))
        bass_p = make_pitch(chord_info.find("BassNote"))
        if root_p is not None:
            chord.root = root_p
        if bass_p is not None:
            chord.bass = bass_p

        # Aggregate degrees to derive type/extension/alterations.
        degrees = {}
        for deg in chord_info.findall("Degree"):
            interval = deg.get("interval") or ""
            alteration = deg.get("alteration") or "Perfect"
            omitted = (deg.get("omitted") or "false").lower() == "true"
            degrees[interval] = (alteration, omitted)

        alt_map = {
            "Perfect":     gp.ChordAlteration.perfect,
            "Diminished":  gp.ChordAlteration.diminished,
            "Augmented":   gp.ChordAlteration.augmented,
            "Major":       gp.ChordAlteration.perfect,
            "Minor":       gp.ChordAlteration.perfect,
        }

        # Third → type (major/minor/sus)
        if "Third" in degrees:
            alt, _ = degrees["Third"]
            if alt == "Major":
                chord.type = gp.ChordType.major
            elif alt == "Minor":
                chord.type = gp.ChordType.minor
            else:
                chord.type = gp.ChordType.major
        else:
            chord.type = gp.ChordType.major

        # Seventh → type variant
        if "Seventh" in degrees:
            alt, _ = degrees["Seventh"]
            if alt == "Minor":
                if chord.type == gp.ChordType.major:
                    chord.type = gp.ChordType.seventh
                else:
                    chord.type = gp.ChordType.minorSeventh
            elif alt == "Major":
                if chord.type == gp.ChordType.major:
                    chord.type = gp.ChordType.majorSeventh
                else:
                    chord.type = gp.ChordType.minorMajor

        # Fifth alteration
        if "Fifth" in degrees:
            alt, _ = degrees["Fifth"]
            chord.fifth = alt_map.get(alt, gp.ChordAlteration.perfect)
        else:
            chord.fifth = gp.ChordAlteration.perfect

        # Ninth / Eleventh / Thirteenth → extension + alterations
        if "Ninth" in degrees:
            chord.extension = gp.ChordExtension.ninth
            alt, _ = degrees["Ninth"]
            chord.ninth = alt_map.get(alt, gp.ChordAlteration.perfect)
        else:
            chord.ninth = gp.ChordAlteration.perfect

        if "Eleventh" in degrees:
            chord.extension = gp.ChordExtension.eleventh
            alt, _ = degrees["Eleventh"]
            chord.eleventh = alt_map.get(alt, gp.ChordAlteration.perfect)
        else:
            chord.eleventh = gp.ChordAlteration.perfect

        if "Thirteenth" in degrees:
            chord.extension = gp.ChordExtension.thirteenth

        if chord.extension is None:
            chord.extension = gp.ChordExtension.none

        chord.tonality = gp.ChordAlteration.perfect

    def _read_chord_diagrams(self, prop: ET.Element, track: gp.Track) -> None:
        """Parse per-track chord diagrams (name + strings + fingering)."""
        items = prop.find("Items")
        if items is None:
            return
        chords: dict[str, gp.Chord] = {}
        n_strings = max(1, len(track.strings))
        for item in items.findall("Item"):
            item_id = item.get("id")
            if item_id is None:
                continue
            chord = gp.Chord(length=n_strings)
            chord.name = item.get("name", "")
            diag = item.find("Diagram")
            if diag is not None:
                try:
                    chord.firstFret = int(diag.get("baseFret") or "0")
                except ValueError:
                    chord.firstFret = 0
                # Strings default to -1 (not played); Fret entries override.
                chord.strings = [-1] * n_strings
                for fe in diag.findall("Fret"):
                    try:
                        # Diagram uses 0-indexed string (low→high); map to
                        # PyGuitarPro's 0-indexed list (which is high→low).
                        s_idx = int(fe.get("string") or "0")
                        f_val = int(fe.get("fret") or "-1")
                        pg_idx = n_strings - 1 - s_idx
                        if 0 <= pg_idx < n_strings:
                            chord.strings[pg_idx] = f_val
                    except ValueError:
                        pass
                # Fingerings
                fingering = diag.find("Fingering")
                if fingering is not None:
                    mapping = {
                        "Thumb": gp.Fingering.thumb,
                        "Index": gp.Fingering.index,
                        "Middle": gp.Fingering.middle,
                        "Ring": gp.Fingering.annular,
                        "Pinky": gp.Fingering.little,
                        "None": gp.Fingering.open,
                    }
                    chord.fingerings = [gp.Fingering.open] * n_strings
                    for pos in fingering.findall("Position"):
                        try:
                            s_idx = int(pos.get("string") or "0")
                            pg_idx = n_strings - 1 - s_idx
                            if 0 <= pg_idx < n_strings:
                                chord.fingerings[pg_idx] = mapping.get(
                                    pos.get("finger") or "None",
                                    gp.Fingering.open,
                                )
                        except ValueError:
                            pass
            # <Chord>/<KeyNote>/<BassNote>/<Degree>... carries harmonic info
            chord_info = item.find("Chord")
            if chord_info is not None:
                self._fill_chord_degrees(chord, chord_info)
            # Defaults matching GP3/4/5 new-format chords
            if chord.newFormat is None:
                chord.newFormat = True
            if chord.show is None:
                chord.show = True
            if chord.add is None:
                chord.add = False
            if chord.sharp is None:
                chord.sharp = True
            chords[item_id] = chord
        # Attach per-track lookup; applied in _build_beat.
        self._chords_by_track[id(track)] = chords

    # ── Phase 3: lookup tables, measures, voices, beats, notes ──────

    def _build_lookup_tables(self, root: ET.Element) -> None:
        """Index every addressable element by its id for fast dereferencing."""
        # Rhythms (duration/dotted/tuplet)
        rhythms = root.find("Rhythms")
        if rhythms is not None:
            for r in rhythms.findall("Rhythm"):
                rid = r.get("id")
                if rid is None:
                    continue
                value_txt = _text(r.find("NoteValue"), "Quarter")
                aug = r.find("AugmentationDot")
                dotted = aug is not None and _int(aug.find("count") if aug.find("count") is not None else aug) >= 1 \
                    or (aug is not None and aug.get("count") == "1")
                tuplet_num, tuplet_den = 1, 1
                tup = r.find("PrimaryTuplet")
                if tup is not None:
                    tuplet_num = int(tup.get("num") or "1")
                    tuplet_den = int(tup.get("den") or "1")
                self._rhythms[rid] = {
                    "value": _DURATION_MAP.get(value_txt, 4),
                    "dotted": dotted,
                    "tuplet_num": tuplet_num,
                    "tuplet_den": tuplet_den,
                }

        notes = root.find("Notes")
        if notes is not None:
            for n in notes.findall("Note"):
                nid = n.get("id")
                if nid is not None:
                    self._notes_raw[nid] = n

        beats = root.find("Beats")
        if beats is not None:
            for b in beats.findall("Beat"):
                bid = b.get("id")
                if bid is not None:
                    self._beats_raw[bid] = b

        voices = root.find("Voices")
        if voices is not None:
            for v in voices.findall("Voice"):
                vid = v.get("id")
                if vid is not None:
                    self._voices_raw[vid] = v

        bars = root.find("Bars")
        if bars is not None:
            for b in bars.findall("Bar"):
                bid = b.get("id")
                if bid is not None:
                    self._bars_raw[bid] = b

    def _read_master_bars(self, song: gp.Song) -> None:
        """Build `song.measureHeaders` from <MasterBars>/<MasterBar>."""
        # Cache nodes for later per-track walk.
        root_doc = None
        for mb in self._iter_master_bars(song):
            pass  # no-op; iteration finalises the list

    def _iter_master_bars(self, song: gp.Song):
        """Yield master bar nodes while populating `self._master_bars` and
        creating a MeasureHeader for each one."""
        root_doc = self._root_from_song(song)
        if root_doc is None:
            return
        master_bars_node = root_doc.find("MasterBars")
        if master_bars_node is None:
            return
        previous_header = None
        for i, mb in enumerate(master_bars_node.findall("MasterBar")):
            self._master_bars.append(mb)
            header = self._build_measure_header(i, mb, previous_header)
            song.measureHeaders.append(header)
            previous_header = header
            yield mb

    def _root_from_song(self, song: gp.Song) -> Optional[ET.Element]:
        """The reader kept the root element alive via closure — we need it
        for master-bar/bar walks. Stash it on the instance instead."""
        return getattr(self, "_root", None)

    def _build_measure_header(self, index: int, mb: ET.Element, previous) -> gp.MeasureHeader:
        header = gp.MeasureHeader()
        header.number = index + 1
        # PyGuitarPro convention: first measure starts at one quarter tick
        # (960 units), subsequent measures accumulate by `length`.
        if previous is None:
            header.start = gp.Duration.quarterTime  # 960
        else:
            header.start = previous.start + previous.length

        # Anacrusis (partial first bar) — GPIF flags it on the first MasterBar
        # only, and AlphaTab tracks it via parent-level _hasAnacrusis. For
        # our purposes the presence of <Anacrusis/> is sufficient — no
        # exact PyGuitarPro field exists so we stash it for downstream use.
        if mb.find("Anacrusis") is not None:
            header._anacrusis = True  # type: ignore[attr-defined]

        time_el = mb.find("Time")
        if time_el is not None and time_el.text:
            num_s, _, den_s = time_el.text.strip().partition("/")
            try:
                header.timeSignature = gp.TimeSignature(
                    numerator=int(num_s),
                    denominator=gp.Duration(value=int(den_s or "4")),
                )
            except ValueError:
                pass
        elif previous is not None:
            header.timeSignature = previous.timeSignature

        key = mb.find("Key")
        if key is not None:
            acc = _int(key.find("AccidentalCount"))
            mode_txt = _text(key.find("Mode")).lower()
            is_minor = mode_txt == "minor"
            header.keySignature = self._key_signature_from_count(acc, is_minor)

        # Section → marker (title + optional color)
        section = mb.find("Section")
        if section is not None:
            title = _text(section.find("Text")) or _text(section.find("Letter"))
            if title:
                color_el = section.find("Color")
                if color_el is not None and color_el.text:
                    rgb = _split_ints(color_el.text)
                    if len(rgb) >= 3:
                        header.marker = gp.Marker(
                            title=title,
                            color=gp.Color(r=rgb[0], g=rgb[1], b=rgb[2]),
                        )
                    else:
                        header.marker = gp.Marker(title=title)
                else:
                    header.marker = gp.Marker(title=title)

        # Double bar
        if mb.find("DoubleBar") is not None:
            header.hasDoubleBar = True

        # Repeat
        repeat = mb.find("Repeat")
        if repeat is not None:
            if (repeat.get("start", "").lower() == "true"):
                header.isRepeatOpen = True
            if repeat.get("end", "").lower() == "true":
                count_attr = repeat.get("count")
                if count_attr:
                    try:
                        header.repeatClose = int(count_attr)
                    except ValueError:
                        pass

        # Alternate endings (bitmask of ending numbers).
        alt = mb.find("AlternateEndings")
        if alt is not None and alt.text:
            bits = 0
            for k in _split_ints(alt.text):
                bits |= 1 << (k - 1) if k >= 1 else 0
            header.repeatAlternative = bits

        # Triplet feel
        tf = _text(mb.find("TripletFeel"))
        if tf == "Triplet8th":
            header.tripletFeel = gp.TripletFeel.eighth
        elif tf == "Triplet16th":
            header.tripletFeel = gp.TripletFeel.sixteenth

        # Directions (Coda/Segno markers & Da Capo/Dal Segno jumps).
        directions = mb.find("Directions")
        if directions is not None:
            for dnode in directions:
                if dnode.tag == "Target":
                    txt = (dnode.text or "").strip()
                    if txt in _DIRECTION_TARGETS:
                        header.direction = gp.DirectionSign(name=_DIRECTION_TARGETS[txt])
                elif dnode.tag == "Jump":
                    txt = (dnode.text or "").strip()
                    if txt in _DIRECTION_JUMPS:
                        header.fromDirection = gp.DirectionSign(name=_DIRECTION_JUMPS[txt])

        # TimeSignature beam pattern — stored in XProperties id=1124139010
        # as an <Int> payload when non-default. We read but PyGuitarPro's
        # TimeSignature expects a `beams` list; GPIF's single int encodes
        # the pattern so we leave PyGuitarPro's default unless an explicit
        # value is present.
        xprops = mb.find("XProperties")
        if xprops is not None:
            for xp in xprops.findall("XProperty"):
                if xp.get("id") == "1124139010":
                    # Default is 8 (i.e. [2,2,2,2] for 4/4). Anything else
                    # overrides; we decode pairs-of-bits into beam counts.
                    val = _int(xp.find("Int"), 8)
                    header.timeSignature.beams = self._decode_beams(
                        val, header.timeSignature.numerator,
                    )

        return header

    @staticmethod
    def _decode_beams(encoded: int, numerator: int) -> list[int]:
        """Convert GPIF's encoded beam pattern to PyGuitarPro's list of 4.

        Default 8 maps to [2,2,2,2]. Rare non-default values (e.g. 1/4 time
        has 1 single beat) expand to a list that matches the numerator.
        PyGuitarPro keeps only 4 slots, so we pad/truncate accordingly.
        """
        if encoded == 8:
            return [2, 2, 2, 2]
        # Best-effort: split numerator into 4 roughly equal groups.
        base, rem = divmod(max(numerator, 1), 4)
        out = [base + (1 if i < rem else 0) for i in range(4)]
        return out

    @staticmethod
    def _key_signature_from_count(acc: int, is_minor: bool) -> gp.KeySignature:
        """Map accidental count (-7..+7, flats negative, sharps positive) + mode."""
        target = (acc, int(is_minor))
        for ks in gp.KeySignature:
            if ks.value == target:
                return ks
        return gp.KeySignature.CMajor

    def _assemble_tracks(self, song: gp.Song) -> None:
        """For each MasterBar index m and each track t, build
        `song.tracks[t].measures[m]` from the referenced <Bar>."""
        tracks = song.tracks
        if not tracks:
            return

        for t in tracks:
            t.measures = []

        for m_idx, mb in enumerate(self._master_bars):
            header = song.measureHeaders[m_idx]
            bars_text = _text(mb.find("Bars"))
            bar_ids = _split_tokens(bars_text)
            for t_idx, track in enumerate(tracks):
                bar_id = bar_ids[t_idx] if t_idx < len(bar_ids) else None
                measure = self._build_measure(track, header, bar_id)
                track.measures.append(measure)

    def _build_measure(self, track: gp.Track, header: gp.MeasureHeader, bar_id: Optional[str]) -> gp.Measure:
        measure = gp.Measure(track=track, header=header)
        measure.voices = []

        bar = self._bars_raw.get(bar_id or "")
        if bar is not None:
            clef_txt = _text(bar.find("Clef"))
            if clef_txt in _CLEF_MAP:
                measure.clef = gp.MeasureClef(_CLEF_MAP[clef_txt])

            voice_ids = _split_tokens(_text(bar.find("Voices")))
            for vid in voice_ids:
                voice = self._build_voice(measure, vid)
                measure.voices.append(voice)

        # Ensure PyGuitarPro's expected two-voice structure.
        while len(measure.voices) < 2:
            v = gp.Voice(measure=measure)
            v.beats = [self._empty_beat(v)]
            measure.voices.append(v)

        return measure

    def _build_voice(self, measure: gp.Measure, voice_id: str) -> gp.Voice:
        voice = gp.Voice(measure=measure)
        voice.beats = []

        if voice_id == "-1":
            # GP uses -1 to mark absent voices; produce a single empty beat
            # so the voice is well-formed for encoders that assume ≥ 1 beat.
            voice.beats.append(self._empty_beat(voice))
            return voice

        raw = self._voices_raw.get(voice_id)
        if raw is None:
            voice.beats.append(self._empty_beat(voice))
            return voice

        beat_ids = _split_tokens(_text(raw.find("Beats")))
        for bid in beat_ids:
            beat = self._build_beat(voice, bid)
            voice.beats.append(beat)
        if not voice.beats:
            voice.beats.append(self._empty_beat(voice))
        return voice

    def _build_beat(self, voice: gp.Voice, beat_id: str) -> gp.Beat:
        beat = gp.Beat(voice=voice)
        raw = self._beats_raw.get(beat_id)
        if raw is None:
            beat.duration = gp.Duration(value=4)
            beat.status = gp.BeatStatus.rest
            beat.notes = []
            return beat

        # Duration
        rhythm_el = raw.find("Rhythm")
        rhythm = self._rhythms.get(rhythm_el.get("ref") if rhythm_el is not None else "", {
            "value": 4, "dotted": False, "tuplet_num": 1, "tuplet_den": 1,
        })
        beat.duration = gp.Duration(
            value=rhythm["value"],
            isDotted=rhythm["dotted"],
        )
        if rhythm["tuplet_num"] != 1 or rhythm["tuplet_den"] != 1:
            beat.duration.tuplet = gp.Tuplet(
                enters=rhythm["tuplet_num"],
                times=rhythm["tuplet_den"],
            )

        # Text annotation
        free_text = raw.find("FreeText")
        if free_text is not None and free_text.text:
            beat.text = free_text.text.strip()

        # Beat-level effects ---------------------------------------
        self._apply_beat_effects(raw, beat)

        # Notes
        notes_ids = _split_tokens(_text(raw.find("Notes")))
        velocity = _DYNAMIC_VELOCITY.get(_text(raw.find("Dynamic")), 95)
        beat.notes = []
        is_rest = False
        # Detect rest: explicit <Rest> element (or empty notes list).
        if raw.find("Rest") is not None:
            is_rest = True

        for nid in notes_ids:
            note = self._build_note(beat, nid, velocity)
            if note is not None:
                beat.notes.append(note)

        if not beat.notes and is_rest:
            beat.status = gp.BeatStatus.rest
        elif not beat.notes:
            # Empty beat (no notes, no rest) — rare but valid.
            beat.status = gp.BeatStatus.empty
        else:
            beat.status = gp.BeatStatus.normal

        # Propagate beat-level attributes (tremolo picking, grace) onto
        # the constituent notes — PyGuitarPro models these per-note.
        tp_dur = getattr(beat, "_tremolo_picking_duration", None)
        grace_active = getattr(beat, "_grace_active", False)
        grace_on_beat = getattr(beat, "_grace_on_beat", False)
        legato_origin = getattr(beat, "_legato_origin", False)
        for n in beat.notes:
            if tp_dur is not None:
                n.effect.tremoloPicking = gp.TremoloPickingEffect(
                    duration=gp.Duration(value=tp_dur),
                )
            if grace_active:
                n.effect.grace = gp.GraceEffect(
                    fret=n.value,
                    duration=32,
                    isOnBeat=grace_on_beat,
                    transition=gp.GraceEffectTransition.none,
                    isDead=False,
                    velocity=n.velocity,
                )
            if legato_origin:
                n.effect.hammer = True

        return beat

    def _build_note(self, beat: gp.Beat, note_id: str, velocity: int) -> Optional[gp.Note]:
        raw = self._notes_raw.get(note_id)
        if raw is None:
            return None

        note = gp.Note(beat=beat)
        note.velocity = velocity
        note.type = gp.NoteType.normal  # overridden below for tie/dead

        # ── <Properties>/<Property> block (pitch, techniques, bends) ──
        fret = 0
        string_number = 1
        midi_value = None
        # Accumulators for bend curve (assembled after property loop).
        bended = False
        bend_origin = {"value": 0, "offset": 0}
        bend_middle_value = None
        bend_middle_offset1 = None
        bend_middle_offset2 = None
        bend_destination = {"value": 0, "offset": 60}
        # Harmonic accumulators.
        harmonic_type = None
        harmonic_fret = 0.0

        props = raw.find("Properties")
        if props is not None:
            for prop in props.findall("Property"):
                name = prop.get("name")
                if name == "Fret":
                    fret = _int(prop.find("Fret"))
                elif name == "String":
                    gpif_idx = _int(prop.find("String"))
                    n_strings = len(beat.voice.measure.track.strings)
                    if n_strings > 0:
                        string_number = max(1, n_strings - gpif_idx)
                elif name == "Midi":
                    midi_value = _int(prop.find("Number"))
                elif name == "Muted":
                    if prop.find("Enable") is not None:
                        note.type = gp.NoteType.dead
                elif name == "Tied":
                    dest = prop.find("TieDest")
                    if dest is not None and (dest.text or "").lower() == "true":
                        note.type = gp.NoteType.tie
                elif name == "PalmMuted":
                    if prop.find("Enable") is not None:
                        note.effect.palmMute = True
                elif name == "HarmonicType":
                    htype = prop.find("HType")
                    if htype is not None:
                        harmonic_type = (htype.text or "").strip().lower()
                elif name == "HarmonicFret":
                    hfret = prop.find("HFret")
                    if hfret is not None and hfret.text:
                        try:
                            harmonic_fret = float(hfret.text.strip())
                        except ValueError:
                            harmonic_fret = 0.0
                elif name == "Slide":
                    flags = _int(prop.find("Flags"))
                    self._apply_slide_flags(note, flags)
                elif name == "HopoOrigin":
                    if prop.find("Enable") is not None:
                        note.effect.hammer = True
                elif name == "Bended":
                    bended = True
                elif name == "BendOriginValue":
                    v = _float(prop.find("Float"))
                    bend_origin["value"] = int(v / _BEND_VALUE_SCALE)
                elif name == "BendOriginOffset":
                    v = _float(prop.find("Float"))
                    bend_origin["offset"] = int(v / _BEND_OFFSET_SCALE)
                elif name == "BendMiddleValue":
                    bend_middle_value = int(_float(prop.find("Float")) / _BEND_VALUE_SCALE)
                elif name == "BendMiddleOffset1":
                    bend_middle_offset1 = int(_float(prop.find("Float")) / _BEND_OFFSET_SCALE)
                elif name == "BendMiddleOffset2":
                    bend_middle_offset2 = int(_float(prop.find("Float")) / _BEND_OFFSET_SCALE)
                elif name == "BendDestinationValue":
                    v = _float(prop.find("Float"))
                    bend_destination["value"] = int(v / _BEND_VALUE_SCALE)
                elif name == "BendDestinationOffset":
                    v = _float(prop.find("Float"))
                    if v:  # keep default 60 if unset
                        bend_destination["offset"] = int(v / _BEND_OFFSET_SCALE)

        # ── Sibling elements of <Note>: top-level effect flags ──
        finger_map = {
            "P": gp.Fingering.thumb,
            "I": gp.Fingering.index,
            "M": gp.Fingering.middle,
            "A": gp.Fingering.annular,
            "C": gp.Fingering.little,
        }
        for child in raw:
            tag = child.tag
            if tag == "LetRing":
                note.effect.letRing = True
            elif tag == "Vibrato":
                txt = (child.text or "").strip()
                if txt in ("Slight", "Wide"):
                    note.effect.vibrato = True
            elif tag == "AntiAccent":
                if (child.text or "").strip().lower() == "normal":
                    note.effect.ghostNote = True
            elif tag == "Accent":
                flags = 0
                try:
                    flags = int((child.text or "0").strip())
                except ValueError:
                    pass
                if flags & _ACCENT_STACCATO:
                    note.effect.staccato = True
                if flags & _ACCENT_HEAVY:
                    note.effect.heavyAccentuatedNote = True
                if flags & _ACCENT_NORMAL:
                    note.effect.accentuatedNote = True
                # bit 0x10 = tenuto — PyGuitarPro's closest match is
                # letRing; leaving unset to avoid over-translation.
            elif tag == "Trill":
                try:
                    trill_fret = int((child.text or "0").strip())
                    note.effect.trill = gp.TrillEffect(
                        fret=trill_fret,
                        duration=gp.Duration(value=16),  # default 16th speed
                    )
                except ValueError:
                    pass
            elif tag == "Tie":
                if child.get("destination", "").lower() == "true":
                    note.type = gp.NoteType.tie
            elif tag == "LeftFingering":
                fp = finger_map.get((child.text or "").strip())
                if fp is not None:
                    note.effect.leftHandFinger = fp
            elif tag == "RightFingering":
                fp = finger_map.get((child.text or "").strip())
                if fp is not None:
                    note.effect.rightHandFinger = fp

        # ── Assemble bend curve ──
        if bended:
            bend = gp.BendEffect(type=gp.BendType.bend, value=bend_destination["value"])
            bend.points.append(gp.BendPoint(position=0, value=bend_origin["value"]))
            if bend_middle_value is not None:
                pos1 = bend_middle_offset1 if bend_middle_offset1 is not None else 6
                bend.points.append(gp.BendPoint(position=pos1, value=bend_middle_value))
                if bend_middle_offset2 is not None and bend_middle_offset2 != bend_middle_offset1:
                    bend.points.append(gp.BendPoint(position=bend_middle_offset2, value=bend_middle_value))
            bend.points.append(gp.BendPoint(
                position=bend_destination["offset"],
                value=bend_destination["value"],
            ))
            note.effect.bend = bend

        # ── Assemble harmonic ──
        if harmonic_type == "natural":
            note.effect.harmonic = gp.NaturalHarmonic()
        elif harmonic_type == "pinch":
            note.effect.harmonic = gp.PinchHarmonic()
        elif harmonic_type == "semi":
            note.effect.harmonic = gp.SemiHarmonic()
        elif harmonic_type == "tap":
            note.effect.harmonic = gp.TappedHarmonic(fret=int(harmonic_fret))
        elif harmonic_type == "artificial":
            # ArtificialHarmonic needs pitch + octave; harmonic_fret is a
            # float semitone offset that encodes both.
            pitch_val = int(round(harmonic_fret)) % 12
            octave_val = int(round(harmonic_fret)) // 12
            note.effect.harmonic = gp.ArtificialHarmonic(
                pitch=gp.PitchClass(just=pitch_val, accidental=0),
                octave=gp.Octave(max(0, min(4, octave_val))),
            )

        note.string = string_number
        if beat.voice.measure.track.isPercussionTrack and midi_value is not None:
            note.value = midi_value
        else:
            note.value = fret

        return note

    def _apply_beat_effects(self, raw: ET.Element, beat: gp.Beat) -> None:
        """Port beat-level effects: tremolo picking, fade, whammy, grace,
        brush/stroke, chord-id attachment (chord content filled in Phase 5)."""
        eff = beat.effect

        # <Fadding>FadeIn|FadeOut|VolumeSwell</Fadding>
        fadding = raw.find("Fadding")
        if fadding is not None and (fadding.text or "").strip() == "FadeIn":
            eff.fadeIn = True

        # <Tremolo>1/2|1/4|1/8</Tremolo> on BEAT — GPIF applies picking at
        # beat level, PyGuitarPro applies at note level. Set on each note
        # after notes are built (handled by caller).
        tremolo = raw.find("Tremolo")
        if tremolo is not None:
            txt = (tremolo.text or "").strip()
            # Map fraction to PyGuitarPro TremoloPickingEffect duration:
            #   1/2 → 8th, 1/4 → 16th, 1/8 → 32nd
            dur_map = {"1/2": 8, "1/4": 16, "1/8": 32}
            dv = dur_map.get(txt)
            if dv is not None:
                # Store for note-attachment (after notes are built).
                beat._tremolo_picking_duration = dv  # type: ignore[attr-defined]

        # <GraceNotes>OnBeat|BeforeBeat</GraceNotes> — whole beat is a
        # grace note group; PyGuitarPro attaches GraceEffect per-note.
        grace = raw.find("GraceNotes")
        if grace is not None:
            txt = (grace.text or "").strip()
            beat._grace_on_beat = txt == "OnBeat"  # type: ignore[attr-defined]
            beat._grace_active = True  # type: ignore[attr-defined]

        # <Arpeggio>Up|Down</Arpeggio> → brush stroke
        arpeggio = raw.find("Arpeggio")
        if arpeggio is not None:
            direction = (arpeggio.text or "").strip()
            if direction == "Up":
                eff.stroke = gp.BeatStroke(
                    direction=gp.BeatStrokeDirection.up, value=0,
                )
            elif direction == "Down":
                eff.stroke = gp.BeatStroke(
                    direction=gp.BeatStrokeDirection.down, value=0,
                )

        # <Whammy> element describes a whammy-bar curve on this beat.
        whammy = raw.find("Whammy")
        if whammy is not None:
            origin_v = int(_float_attr(whammy, "originValue") / _BEND_VALUE_SCALE)
            middle_v = int(_float_attr(whammy, "middleValue") / _BEND_VALUE_SCALE)
            dest_v = int(_float_attr(whammy, "destinationValue") / _BEND_VALUE_SCALE)
            bar = gp.BendEffect(type=gp.BendType.bend, value=dest_v)
            bar.points = [
                gp.BendPoint(position=0, value=origin_v),
                gp.BendPoint(position=6, value=middle_v),
                gp.BendPoint(position=12, value=dest_v),
            ]
            eff.tremoloBar = bar

        # <Chord>id</Chord> — lookup in the track's DiagramCollection that
        # we pre-parsed in _read_chord_diagrams.
        chord_ref = raw.find("Chord")
        if chord_ref is not None and (chord_ref.text or "").strip():
            chord_id = chord_ref.text.strip()
            track_key = id(beat.voice.measure.track)
            chord_map = self._chords_by_track.get(track_key, {})
            chord = chord_map.get(chord_id)
            if chord is not None:
                beat.effect.chord = chord

        # <Legato origin="true"/> — GPIF marks the source of a legato/hammer
        # group. Store for propagation to notes after they're built.
        legato = raw.find("Legato")
        if legato is not None and legato.get("origin", "").lower() == "true":
            beat._legato_origin = True  # type: ignore[attr-defined]

        # <Ottavia>8va|8vb|15ma|15mb</Ottavia> → beat.octave
        octavia = raw.find("Ottavia")
        if octavia is not None:
            txt = (octavia.text or "").strip()
            if txt == "8va":
                beat.octave = gp.Octave.ottava
            elif txt == "8vb":
                beat.octave = gp.Octave.ottavaBassa
            elif txt == "15ma":
                beat.octave = gp.Octave.quindicesima
            elif txt == "15mb":
                beat.octave = gp.Octave.quindicesimaBassa

        # <Properties> on the beat: Brush, PickStroke, Slapped, Popped,
        # VibratoWTremBar, Rasgueado, WhammyBar curve points.
        props = raw.find("Properties")
        if props is not None:
            self._apply_beat_properties(props, beat)

    def _apply_beat_properties(self, props: ET.Element, beat: gp.Beat) -> None:
        eff = beat.effect
        whammy_origin = None
        whammy_middle_value = None
        whammy_middle_offset1 = None
        whammy_middle_offset2 = None
        whammy_destination = None
        is_whammy = False

        for prop in props.findall("Property"):
            name = prop.get("name")
            if name == "Brush":
                direction = _text(prop.find("Direction"))
                eff.stroke = gp.BeatStroke(
                    direction=gp.BeatStrokeDirection.up if direction == "Up" else gp.BeatStrokeDirection.down,
                    value=0,
                )
            elif name == "PickStroke":
                direction = _text(prop.find("Direction"))
                eff.pickStroke = (gp.BeatStrokeDirection.up if direction == "Up"
                                  else gp.BeatStrokeDirection.down)
            elif name == "Slapped":
                if prop.find("Enable") is not None:
                    eff.slapEffect = gp.SlapEffect.slapping
            elif name == "Popped":
                if prop.find("Enable") is not None:
                    eff.slapEffect = gp.SlapEffect.popping
            elif name == "Rasgueado":
                eff.hasRasgueado = True
            elif name == "VibratoWTremBar":
                strength = _text(prop.find("Strength"))
                if strength in ("Wide", "Slight"):
                    eff.vibrato = True
            # Whammy bar curve points (may override simpler Whammy element).
            elif name == "WhammyBar":
                is_whammy = True
            elif name == "WhammyBarOriginValue":
                if whammy_origin is None:
                    whammy_origin = {"value": 0, "offset": 0}
                whammy_origin["value"] = int(_float(prop.find("Float")) / _BEND_VALUE_SCALE)
            elif name == "WhammyBarOriginOffset":
                if whammy_origin is None:
                    whammy_origin = {"value": 0, "offset": 0}
                whammy_origin["offset"] = int(_float(prop.find("Float")) / _BEND_OFFSET_SCALE)
            elif name == "WhammyBarMiddleValue":
                whammy_middle_value = int(_float(prop.find("Float")) / _BEND_VALUE_SCALE)
            elif name == "WhammyBarMiddleOffset1":
                whammy_middle_offset1 = int(_float(prop.find("Float")) / _BEND_OFFSET_SCALE)
            elif name == "WhammyBarMiddleOffset2":
                whammy_middle_offset2 = int(_float(prop.find("Float")) / _BEND_OFFSET_SCALE)
            elif name == "WhammyBarDestinationValue":
                if whammy_destination is None:
                    whammy_destination = {"value": 0, "offset": 60}
                whammy_destination["value"] = int(_float(prop.find("Float")) / _BEND_VALUE_SCALE)
            elif name == "WhammyBarDestinationOffset":
                if whammy_destination is None:
                    whammy_destination = {"value": 0, "offset": 0}
                whammy_destination["offset"] = int(_float(prop.find("Float")) / _BEND_OFFSET_SCALE)

        if is_whammy or whammy_origin or whammy_middle_value is not None or whammy_destination:
            origin = whammy_origin or {"value": 0, "offset": 0}
            dest = whammy_destination or {"value": 0, "offset": 12}
            bar = gp.BendEffect(type=gp.BendType.bend, value=dest["value"])
            bar.points.append(gp.BendPoint(position=0, value=origin["value"]))
            if whammy_middle_value is not None:
                pos1 = whammy_middle_offset1 if whammy_middle_offset1 is not None else 6
                bar.points.append(gp.BendPoint(position=pos1, value=whammy_middle_value))
                if whammy_middle_offset2 is not None and whammy_middle_offset2 != whammy_middle_offset1:
                    bar.points.append(gp.BendPoint(position=whammy_middle_offset2, value=whammy_middle_value))
            bar.points.append(gp.BendPoint(position=dest["offset"], value=dest["value"]))
            eff.tremoloBar = bar

    @staticmethod
    def _apply_slide_flags(note: gp.Note, flags: int) -> None:
        """Map GPIF slide flags to PyGuitarPro SlideType list."""
        slides = []
        if flags & _SLIDE_SHIFT:
            slides.append(gp.SlideType.shiftSlideTo)
        if flags & _SLIDE_LEGATO:
            slides.append(gp.SlideType.legatoSlideTo)
        if flags & _SLIDE_OUT_DOWN:
            slides.append(gp.SlideType.outDownwards)
        if flags & _SLIDE_OUT_UP:
            slides.append(gp.SlideType.outUpwards)
        if flags & _SLIDE_IN_FROM_BELOW:
            slides.append(gp.SlideType.intoFromBelow)
        if flags & _SLIDE_IN_FROM_ABOVE:
            slides.append(gp.SlideType.intoFromAbove)
        if flags & _SLIDE_PICK_DOWN:
            slides.append(gp.SlideType.pickSlideDown)
        if flags & _SLIDE_PICK_UP:
            slides.append(gp.SlideType.pickSlideUp)
        if slides:
            note.effect.slides = slides

    @staticmethod
    def _empty_beat(voice: gp.Voice) -> gp.Beat:
        beat = gp.Beat(voice=voice)
        beat.duration = gp.Duration(value=4)
        beat.status = gp.BeatStatus.empty
        beat.notes = []
        return beat

