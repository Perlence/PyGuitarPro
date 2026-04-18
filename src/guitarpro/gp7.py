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

GP7/GP8 files are ZIP archives with the following entries of interest:
  - score.gpif             XML document with the full score (required)
  - BinaryStylesheet       style settings (ignored)
  - PartConfiguration      part visibility (ignored)
  - LayoutConfiguration    layout hints (ignored)

Only score.gpif is needed to reconstruct the musical content required for
tokenization; the rest is rendering/display metadata.

Phased port:
  * Phase 1 (done): song metadata, version detection
  * Phase 2 (in progress): tracks, tuning, MIDI channels
  * Phase 3: measures + voices + beats + notes
  * Phase 4: effects (bends, slides, harmonics, etc.)
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
    """Return stripped element text or `default`."""
    if elem is None or elem.text is None:
        return default
    return elem.text.strip()


def _int(elem: Optional[ET.Element], default: int = 0) -> int:
    try:
        return int(_text(elem, str(default)))
    except ValueError:
        return default


def _split_ints(text: str) -> list[int]:
    """Parse whitespace-separated integers; GP7 uses this for tunings, colors, etc."""
    out = []
    for token in text.strip().split():
        try:
            out.append(int(token))
        except ValueError:
            pass
    return out


# ── Reader ────────────────────────────────────────────────────────────

class GP7File:
    """Reader for Guitar Pro 7/8 (ZIP+XML) files.

    Produces :class:`guitarpro.models.Song` objects so the rest of the
    library (tokenizers, analysers, callers) sees a uniform API regardless
    of format.
    """

    def __init__(self, fp, encoding: str = "utf-8", version: str = "", versionTuple: tuple = (7, 0, 0)):
        self._fp = fp
        self.encoding = encoding
        self.version = version
        self.versionTuple = versionTuple

    def close(self):
        # fp is owned by caller via _open(); nothing to close here.
        pass

    # ── public entry points ────────────────────────────────────────

    def readSong(self) -> gp.Song:
        root = self._load_score_gpif()

        song = gp.Song(tracks=[], measureHeaders=[])
        self._read_version(root, song)
        self._read_score_info(root, song)
        self._read_master_track(root, song)
        self._read_tracks(root, song)

        return song

    def writeSong(self, song: gp.Song):
        raise NotImplementedError("Writing GP7/GP8 is not implemented yet")

    # ── loading ────────────────────────────────────────────────────

    def _load_score_gpif(self) -> ET.Element:
        """Open the ZIP archive and return the parsed <GPIF> root element."""
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

        return root

    # ── version + score info ───────────────────────────────────────

    def _read_version(self, root: ET.Element, song: gp.Song) -> None:
        """Refine versionTuple from <GPVersion> (e.g. "7.0.0" or "8.1.0")."""
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
        """Tempo and other song-level automations live under <MasterTrack>."""
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
                    # "<bpm> <note-value>" — keep the BPM for now.
                    try:
                        song.tempo = int(value.text.strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                break

    # ── tracks ─────────────────────────────────────────────────────

    def _read_tracks(self, root: ET.Element, song: gp.Song) -> None:
        """Parse every <Track> under <Tracks>; attach to song.tracks."""
        tracks_node = root.find("Tracks")
        if tracks_node is None:
            return
        for i, t_node in enumerate(tracks_node.findall("Track")):
            track = self._read_track(t_node, song)
            track.number = i + 1
            song.tracks.append(track)

    def _read_track(self, node: ET.Element, song: gp.Song) -> gp.Track:
        """Build a Track from one <Track id="N">...</Track> element."""
        track = gp.Track(song=song, number=0)
        track.strings = []
        # PyGuitarPro Track defaults a MidiChannel; we populate its fields.

        # Basic fields ---------------------------------------------
        track.name = _text(node.find("Name"))
        track.shortName = _text(node.find("ShortName")) if node.find("ShortName") is not None else ""

        color_el = node.find("Color")
        if color_el is not None and color_el.text:
            parts = _split_ints(color_el.text)
            if len(parts) >= 3:
                track.color = gp.Color(r=parts[0], g=parts[1], b=parts[2])

        # InstrumentSet → detect percussion ------------------------
        iset = node.find("InstrumentSet")
        if iset is not None:
            iset_type = _text(iset.find("Type"))
            if iset_type == "drumKit":
                track.isPercussionTrack = True

        # MIDI: prefer explicit GeneralMidi / MidiConnection nodes
        midi_nodes = [n for n in ("GeneralMidi", "MidiConnection", "MIDISettings") if node.find(n) is not None]
        for midi_tag in midi_nodes:
            midi = node.find(midi_tag)
            if midi is None:
                continue
            if midi.get("table") == "Percussion":
                track.isPercussionTrack = True
            prog = midi.find("Program")
            if prog is not None:
                track.channel.instrument = _int(prog)
            port = midi.find("Port")
            if port is not None:
                track.port = _int(port) + 1  # PyGuitarPro port is 1-indexed
            prim = midi.find("PrimaryChannel")
            if prim is not None and (prim.text or "").strip():
                track.channel.channel = _int(prim)
            sec = midi.find("SecondaryChannel")
            if sec is not None and (sec.text or "").strip():
                track.channel.effectChannel = _int(sec)

        # Sounds → program/bank (first sound is the primary/current sound).
        # AlphaTab applies the first sound's program/bank to the track; GeneralMidi
        # doesn't carry a Program field in GPIF, so Sounds is the source of truth.
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

        # Staves → tuning, capo, fret count ------------------------
        staves = node.find("Staves")
        if staves is not None:
            self._read_track_staves(staves, track)

        # Fallback: if percussion track has no strings set, leave empty;
        # otherwise default to empty list rather than PyGuitarPro's
        # auto-created E-standard 6-string.
        if not track.strings and not track.isPercussionTrack:
            # Most GP7 tracks declare tuning in Staves; if missing (rare),
            # fall back to a standard 6-string layout so downstream code
            # does not divide by zero.
            track.strings = [
                gp.GuitarString(number=i + 1, value=v)
                for i, v in enumerate([64, 59, 55, 50, 45, 40])
            ]

        return track

    def _read_track_staves(self, staves_node: ET.Element, track: gp.Track) -> None:
        """Read tuning, capo, fret count from <Staves>/<Staff>/<Properties>."""
        for staff in staves_node.findall("Staff"):
            props = staff.find("Properties")
            if props is None:
                continue
            for prop in props.findall("Property"):
                name = prop.get("name")
                if name == "Tuning":
                    pitches = prop.find("Pitches")
                    if pitches is not None and pitches.text:
                        # GPIF order: low-to-high. PyGuitarPro convention:
                        # string 1 = highest pitch → reverse.
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
            break  # PyGuitarPro models one staff per track; first is enough
