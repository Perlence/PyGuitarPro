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
    BinaryStylesheet   style settings (ignored)
    PartConfiguration  part visibility (ignored)
    LayoutConfiguration layout hints (ignored)

The GPIF XML is a denormalised DAG: MasterBars reference Bars by id,
Bars reference Voices, Voices reference Beats, Beats reference Notes
and Rhythms.  The reader first builds lookup maps from ids, then walks
MasterBars to assemble per-track Measure/Voice/Beat/Note trees.

Phased port:
  * Phase 1 (done): song metadata, version detection
  * Phase 2 (done): tracks, tuning, MIDI channels
  * Phase 3 (in progress): measures, voices, beats, notes (no effects yet)
  * Phase 4: effects (bends, slides, harmonics, palm mute, etc.)
  * Phase 5: chord diagrams, markers, repeats, directions
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

    def close(self):
        pass

    # ── public entry points ────────────────────────────────────────

    def readSong(self) -> gp.Song:
        root = self._load_score_gpif()

        song = gp.Song(tracks=[], measureHeaders=[])
        self._read_version(root, song)
        self._read_score_info(root, song)
        self._read_master_track(root, song)
        self._read_tracks(root, song)

        self._build_lookup_tables(root)
        self._read_master_bars(song)
        self._assemble_tracks(song)

        return song

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
            song.tracks.append(track)

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

        staves = node.find("Staves")
        if staves is not None:
            self._read_track_staves(staves, track)

        if not track.strings and not track.isPercussionTrack:
            track.strings = [
                gp.GuitarString(number=i + 1, value=v)
                for i, v in enumerate([64, 59, 55, 50, 45, 40])
            ]

        return track

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
            break

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
        header.start = 0 if previous is None else (previous.start + previous.length)

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

        # Section → marker
        section = mb.find("Section")
        if section is not None:
            title = _text(section.find("Text")) or _text(section.find("Letter"))
            if title:
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

        return header

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

        return beat

    def _build_note(self, beat: gp.Beat, note_id: str, velocity: int) -> Optional[gp.Note]:
        raw = self._notes_raw.get(note_id)
        if raw is None:
            return None

        note = gp.Note(beat=beat)
        note.velocity = velocity
        note.type = gp.NoteType.normal  # default; overridden below for tie/dead

        props = raw.find("Properties")
        fret = 0
        string_number = 1
        midi_value = None
        if props is not None:
            for prop in props.findall("Property"):
                name = prop.get("name")
                if name == "Fret":
                    fret = _int(prop.find("Fret"))
                elif name == "String":
                    # XML string is 0-indexed low-to-high; PyGuitarPro is
                    # 1-indexed high-to-low. track.strings length gives N.
                    gpif_idx = _int(prop.find("String"))
                    n_strings = len(beat.voice.measure.track.strings)
                    if n_strings > 0:
                        string_number = n_strings - gpif_idx
                        if string_number < 1:
                            string_number = 1
                elif name == "Midi":
                    midi_value = _int(prop.find("Number"))
                elif name == "Muted":
                    enable = prop.find("Enable")
                    if enable is not None:
                        note.type = gp.NoteType.dead
                elif name == "Tied":
                    dest = prop.find("TieDest")
                    if dest is not None and (dest.text or "").lower() == "true":
                        note.type = gp.NoteType.tie

        note.string = string_number
        # For percussion tracks, `value` is the MIDI drum note; otherwise
        # it's the fret number. We keep fret here; the MIDI value is
        # reconstructable from string pitch + fret by consumers.
        if beat.voice.measure.track.isPercussionTrack and midi_value is not None:
            note.value = midi_value
        else:
            note.value = fret

        return note

    @staticmethod
    def _empty_beat(voice: gp.Voice) -> gp.Beat:
        beat = gp.Beat(voice=voice)
        beat.duration = gp.Duration(value=4)
        beat.status = gp.BeatStatus.empty
        beat.notes = []
        return beat

