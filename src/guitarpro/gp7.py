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

Porting strategy (phased):
  * Phase 1 (this file's current state): zip + XML open, pull song-level
    metadata (title/artist/tempo/key), return Song with empty tracks.
    Enough to register the format and stop crashing on .gp files.
  * Phase 2: tracks, tuning, midi channels.
  * Phase 3: measures, voices, beats, notes.
  * Phase 4: effects (bends, slides, harmonics, palm mute, etc.).
  * Phase 5: chord diagrams, markers, repeats, directions.
"""
from __future__ import annotations

import io
import zipfile
from typing import Optional
from xml.etree import ElementTree as ET

from . import models as gp


# Namespaces / tags used in score.gpif. GP7 XML does not declare namespaces,
# so plain tag names suffice.


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


class GP7File:
    """Reader for Guitar Pro 7/8 (ZIP+XML) files.

    Produces :class:`guitarpro.models.Song` objects so the rest of the
    library (tokenizers, analysers, callers) sees a uniform API regardless
    of format.
    """

    def __init__(self, fp, encoding: str = "utf-8", version: str = "", versionTuple: tuple = (7, 0, 0)):
        # Accept the same constructor signature as GP3/4/5 readers.
        self._fp = fp
        self.encoding = encoding
        self.version = version
        self.versionTuple = versionTuple

    def close(self):
        # fp is owned by caller via _open(); nothing to close here.
        pass

    # ── reading ───────────────────────────────────────────────────────

    def readSong(self) -> gp.Song:
        root = self._load_score_gpif()

        song = gp.Song(tracks=[], measureHeaders=[])
        # Refine version from <GPVersion> (e.g. "7.0.0" or "8.1.0").
        gpver = root.find("GPVersion")
        if gpver is not None and gpver.text:
            parts = [p for p in gpver.text.strip().split(".") if p.isdigit()]
            if parts:
                while len(parts) < 3:
                    parts.append("0")
                self.versionTuple = tuple(int(p) for p in parts[:3])
        song.versionTuple = self.versionTuple
        song.version = self.version

        # Score-level metadata: <Score> child of <GPIF>
        score = root.find("Score")
        if score is not None:
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
                # GP7 stores notice as a single multi-line string; keep it as
                # one element to stay compatible with the list-of-lines shape
                # GP3/4/5 readers produce.
                song.notice = [notice.text.strip()]

        # MasterTrack → tempo and key sig (first automation entries)
        master = root.find("MasterTrack")
        if master is not None:
            automations = master.find("Automations")
            if automations is not None:
                tempo_el = next(
                    (a for a in automations.findall("Automation") if _text(a.find("Type")) == "Tempo"),
                    None,
                )
                if tempo_el is not None:
                    value = tempo_el.find("Value")
                    if value is not None and value.text:
                        # Format: "<bpm> <note-value>", keep bpm only for now.
                        try:
                            song.tempo = int(value.text.strip().split()[0])
                        except (ValueError, IndexError):
                            pass

        # TODO Phase 2+: tracks, bars, voices, beats, notes, effects.
        # For now the caller gets a Song with metadata but no tracks, which
        # lets high-level callers (e.g. metric collectors) report the file
        # as parseable without crashing.

        return song

    # ── helpers ───────────────────────────────────────────────────────

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

        # The root element is <GPIF>. Some producers wrap it differently; be
        # lenient by returning the root even if the tag name differs.
        return root

    # ── writing (not yet supported) ───────────────────────────────────

    def writeSong(self, song: gp.Song):
        raise NotImplementedError("Writing GP7/GP8 is not implemented yet")
