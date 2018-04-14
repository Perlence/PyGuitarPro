from __future__ import division

import attr

from . import models as gp
from . import gp3
from .utils import clamp


class GP4File(gp3.GP3File):

    """A reader for GuitarPro 4 files."""

    # Reading
    # =======

    def readSong(self):
        """Read the song.

        A song consists of score information, triplet feel, lyrics,
        tempo, song key, MIDI channels, measure and track count, measure
        headers, tracks, measures.

        - Version: :ref:`byte-size-string` of size 30.

        - Score information.
          See :meth:`readInfo`.

        - Triplet feel: :ref:`bool`.
          If value is true, then triplet feel is set to eigth.

        - Lyrics. See :meth:`readLyrics`.

        - Tempo: :ref:`int`.

        - Key: :ref:`int`. Key signature of the song.

        - Octave: :ref:`signed-byte`. Reserved for future uses.

        - MIDI channels. See :meth:`readMidiChannels`.

        - Number of measures: :ref:`int`.

        - Number of tracks: :ref:`int`.

        - Measure headers. See :meth:`readMeasureHeaders`.

        - Tracks. See :meth:`readTracks`.

        - Measures. See :meth:`readMeasures`.

        """
        song = gp.Song(tracks=[], measureHeaders=[])
        song.version = self.readVersion()
        song.versionTuple = self.versionTuple
        song.clipboard = self.readClipboard()

        self.readInfo(song)
        self._tripletFeel = gp.TripletFeel.eighth if self.readBool() else gp.TripletFeel.none
        song.lyrics = self.readLyrics()
        song.tempo = self.readInt()
        song.key = gp.KeySignature((self.readInt(), 0))
        self.readSignedByte()  # octave
        channels = self.readMidiChannels()
        measureCount = self.readInt()
        trackCount = self.readInt()
        self.readMeasureHeaders(song, measureCount)
        self.readTracks(song, trackCount, channels)
        self.readMeasures(song)
        return song

    def readClipboard(self):
        if not self.isClipboard():
            return
        clipboard = gp.Clipboard()
        clipboard.startMeasure = self.readInt()
        clipboard.stopMeasure = self.readInt()
        clipboard.startTrack = self.readInt()
        clipboard.stopTrack = self.readInt()
        return clipboard

    def isClipboard(self):
        return self.version.startswith('CLIPBOARD')

    def readLyrics(self):
        """Read lyrics.

        First, read an :ref:`int` that points to the track lyrics are
        bound to. Then it is followed by 5 lyric lines. Each one
        constists of number of starting measure encoded in :ref:`int`
        and :ref:`int-size-string` holding text of the lyric line.

        """
        lyrics = gp.Lyrics()
        lyrics.trackChoice = self.readInt()
        for line in lyrics.lines:
            line.startingMeasure = self.readInt()
            line.lyrics = self.readIntSizeString()
        return lyrics

    def packMeasureHeaderFlags(self, header, previous=None):
        flags = super(GP4File, self).packMeasureHeaderFlags(header, previous)
        if previous is None or header.keySignature != previous.keySignature:
            flags |= 0x40
        if header.hasDoubleBar:
            flags |= 0x80
        return flags

    def writeMeasureHeaderValues(self, header, flags):
        super(GP4File, self).writeMeasureHeaderValues(header, flags)
        if flags & 0x40:
            self.writeSignedByte(header.keySignature.value[0])
            self.writeSignedByte(header.keySignature.value[1])

    def readNewChord(self, chord):
        """Read new-style (GP4) chord diagram.

        New-style chord diagram is read as follows:

        - Sharp: :ref:`bool`. If true, display all semitones as sharps,
          otherwise display as flats.

        - Blank space, 3 :ref:`Bytes <byte>`.

        - Root: :ref:`byte`. Values are:

          * -1 for customized chords
          *  0: C
          *  1: C#
          * ...

        - Type: :ref:`byte`. Determines the chord type as followed. See
          :class:`guitarpro.models.ChordType` for mapping.

        - Chord extension: :ref:`byte`. See
          :class:`guitarpro.models.ChordExtension` for mapping.

        - Bass note: :ref:`int`. Lowest note of chord as in *C/Am*.

        - Tonality: :ref:`int`. See
          :class:`guitarpro.models.ChordAlteration` for mapping.

        - Add: :ref:`bool`. Determines if an "add" (added note) is
          present in the chord.

        - Name: :ref:`byte-size-string`. Max length is 22.

        - Fifth tonality: :ref:`byte`. Maps to
          :class:`guitarpro.models.ChordExtension`.

        - Ninth tonality: :ref:`byte`. Maps to
          :class:`guitarpro.models.ChordExtension`.

        - Eleventh tonality: :ref:`byte`. Maps to
          :class:`guitarpro.models.ChordExtension`.

        - List of frets: 6 :ref:`Ints <int>`. Fret values are saved as
          in default format.

        - Count of barres: :ref:`byte`. Maximum count is 5.

        - Barre frets: 5 :ref:`Bytes <byte>`.

        - Barre start strings: 5 :ref:`Bytes <byte>`.

        - Barre end string: 5 :ref:`Bytes <byte>`.

        - Omissions: 7 :ref:`Bools <bool>`. If the value is true then
          note is played in chord.

        - Blank space, 1 :ref:`byte`.

        - Fingering: 7 :ref:`SignedBytes <signed-byte>`. For value
          mapping, see :class:`guitarpro.models.Fingering`.

        """
        chord.sharp = self.readBool()
        intonation = 'sharp' if chord.sharp else 'flat'
        self.skip(3)
        chord.root = gp.PitchClass(self.readByte(), intonation=intonation)
        chord.type = gp.ChordType(self.readByte())
        chord.extension = gp.ChordExtension(self.readByte())
        chord.bass = gp.PitchClass(self.readInt(), intonation=intonation)
        chord.tonality = gp.ChordAlteration(self.readInt())
        chord.add = self.readBool()
        chord.name = self.readByteSizeString(22)
        chord.fifth = gp.ChordAlteration(self.readByte())
        chord.ninth = gp.ChordAlteration(self.readByte())
        chord.eleventh = gp.ChordAlteration(self.readByte())
        chord.firstFret = self.readInt()
        for i in range(7):
            fret = self.readInt()
            if i < len(chord.strings):
                chord.strings[i] = fret
        chord.barres = []
        barresCount = self.readByte()
        barreFrets = self.readByte(5)
        barreStarts = self.readByte(5)
        barreEnds = self.readByte(5)
        for fret, start, end, _ in zip(barreFrets, barreStarts, barreEnds, range(barresCount)):
            barre = gp.Barre(fret, start, end)
            chord.barres.append(barre)
        chord.omissions = self.readBool(7)
        self.skip(1)
        chord.fingerings = list(map(gp.Fingering, self.readSignedByte(7)))
        chord.show = self.readBool()

    def readBeatEffects(self, effect):
        """Read beat effects.

        Beat effects are read using two byte flags.

        The first byte of flags is:

        - *0x01*: *blank*
        - *0x02*: wide vibrato
        - *0x04*: *blank*
        - *0x08*: *blank*
        - *0x10*: fade in
        - *0x20*: slap effect
        - *0x40*: beat stroke
        - *0x80*: *blank*

        The second byte of flags is:

        - *0x01*: rasgueado
        - *0x02*: pick stroke
        - *0x04*: tremolo bar
        - *0x08*: *blank*
        - *0x10*: *blank*
        - *0x20*: *blank*
        - *0x40*: *blank*
        - *0x80*: *blank*

        Flags are followed by:

        - Slap effect: :ref:`signed-byte`. For value mapping see
          :class:`guitarpro.models.SlapEffect`.

        - Tremolo bar. See :meth:`readTremoloBar`.

        - Beat stroke. See :meth:`readBeatStroke`.

        - Pick stroke: :ref:`signed-byte`. For value mapping see
          :class:`guitarpro.models.BeatStrokeDirection`.

        """
        beatEffect = gp.BeatEffect()
        flags1 = self.readSignedByte()
        flags2 = self.readSignedByte()
        beatEffect.vibrato = bool(flags1 & 0x02) or beatEffect.vibrato
        beatEffect.fadeIn = bool(flags1 & 0x10)
        if flags1 & 0x20:
            value = self.readSignedByte()
            beatEffect.slapEffect = gp.SlapEffect(value)
        if flags2 & 0x04:
            beatEffect.tremoloBar = self.readTremoloBar()
        if flags1 & 0x40:
            beatEffect.stroke = self.readBeatStroke()
        beatEffect.hasRasgueado = bool(flags2 & 0x01)
        if flags2 & 0x02:
            direction = self.readSignedByte()
            beatEffect.pickStroke = gp.BeatStrokeDirection(direction)
        return beatEffect

    def readTremoloBar(self):
        return self.readBend()

    def readMixTableChange(self, measure):
        """Read mix table change.

        Mix table change in Guitar Pro 4 format extends Guitar Pro 3
        format. It constists of :meth:`values
        <guitarpro.gp3.GP3File.readMixTableChangeValues>`,
        :meth:`durations
        <guitarpro.gp3.GP3File.readMixTableChangeDurations>`, and, new
        to GP3, :meth:`flags <readMixTableChangeFlags>`.

        """
        tableChange = super(GP4File, self).readMixTableChange(measure)
        self.readMixTableChangeFlags(tableChange)
        return tableChange

    def readMixTableChangeFlags(self, tableChange):
        """Read mix table change flags.

        The meaning of flags:

        - *0x01*: change volume for all tracks
        - *0x02*: change balance for all tracks
        - *0x04*: change chorus for all tracks
        - *0x08*: change reverb for all tracks
        - *0x10*: change phaser for all tracks
        - *0x20*: change tremolo for all tracks

        """
        flags = self.readSignedByte()
        if tableChange.volume is not None:
            tableChange.volume.allTracks = bool(flags & 0x01)
        if tableChange.balance is not None:
            tableChange.balance.allTracks = bool(flags & 0x02)
        if tableChange.chorus is not None:
            tableChange.chorus.allTracks = bool(flags & 0x04)
        if tableChange.reverb is not None:
            tableChange.reverb.allTracks = bool(flags & 0x08)
        if tableChange.phaser is not None:
            tableChange.phaser.allTracks = bool(flags & 0x10)
        if tableChange.tremolo is not None:
            tableChange.tremolo.allTracks = bool(flags & 0x20)
        return flags

    def readNoteEffects(self, note):
        """Read note effects.

        The effects presence for the current note is set by the 2 bytes
        of flags.

        First set of flags:

        - *0x01*: bend
        - *0x02*: hammer-on/pull-off
        - *0x04*: *blank*
        - *0x08*: let-ring
        - *0x10*: grace note
        - *0x20*: *blank*
        - *0x40*: *blank*
        - *0x80*: *blank*

        Second set of flags:

        - *0x01*: staccato
        - *0x02*: palm mute
        - *0x04*: tremolo picking
        - *0x08*: slide
        - *0x10*: harmonic
        - *0x20*: trill
        - *0x40*: vibrato
        - *0x80*: *blank*

        Flags are followed by:

        - Bend. See :meth:`readBend`.

        - Grace note. See :meth:`readGrace`.

        - Tremolo picking. See :meth:`readTremoloPicking`.

        - Slide. See :meth:`readSlides`.

        - Harmonic. See :meth:`readHarmonic`.

        - Trill. See :meth:`readTrill`.

        """
        noteEffect = note.effect or gp.NoteEffect()
        flags1 = self.readSignedByte()
        flags2 = self.readSignedByte()
        noteEffect.hammer = bool(flags1 & 0x02)
        noteEffect.letRing = bool(flags1 & 0x08)
        noteEffect.staccato = bool(flags2 & 0x01)
        noteEffect.palmMute = bool(flags2 & 0x02)
        noteEffect.vibrato = bool(flags2 & 0x40) or noteEffect.vibrato
        if flags1 & 0x01:
            noteEffect.bend = self.readBend()
        if flags1 & 0x10:
            noteEffect.grace = self.readGrace()
        if flags2 & 0x04:
            noteEffect.tremoloPicking = self.readTremoloPicking()
        if flags2 & 0x08:
            noteEffect.slides = self.readSlides()
        if flags2 & 0x10:
            noteEffect.harmonic = self.readHarmonic(note)
        if flags2 & 0x20:
            noteEffect.trill = self.readTrill()
        return noteEffect

    def readTremoloPicking(self):
        """Read tremolo picking.

        Tremolo constists of picking speed encoded in
        :ref:`signed-byte`. For value mapping refer to
        :meth:`fromTremoloValue`.

        """
        value = self.readSignedByte()
        tp = gp.TremoloPickingEffect()
        tp.duration.value = self.fromTremoloValue(value)
        return tp

    def fromTremoloValue(self, value):
        """Convert tremolo picking speed to actual duration.

        Values are:

        - *1*: eighth
        - *2*: sixteenth
        - *3*: thirtySecond

        """
        if value == 1:
            return gp.Duration.eighth
        elif value == 2:
            return gp.Duration.sixteenth
        elif value == 3:
            return gp.Duration.thirtySecond

    def readSlides(self):
        """Read slides.

        Slide is encoded in :ref:`signed-byte`. See
        :class:`guitarpro.models.SlideType` for value mapping.

        """
        return [gp.SlideType(self.readSignedByte())]

    def readHarmonic(self, note):
        """Read harmonic.

        Harmonic is encoded in :ref:`signed-byte`. Values correspond to:

        - *1*: natural harmonic
        - *3*: tapped harmonic
        - *4*: pinch harmonic
        - *5*: semi-harmonic
        - *15*: artificial harmonic on (*n + 5*)th fret
        - *17*: artificial harmonic on (*n + 7*)th fret
        - *22*: artificial harmonic on (*n + 12*)th fret

        """
        harmonicType = self.readSignedByte()
        if harmonicType == 1:
            harmonic = gp.NaturalHarmonic()
        elif harmonicType == 3:
            harmonic = gp.TappedHarmonic()
        elif harmonicType == 4:
            harmonic = gp.PinchHarmonic()
        elif harmonicType == 5:
            harmonic = gp.SemiHarmonic()
        elif harmonicType == 15:
            pitch = gp.PitchClass((note.realValue + 7) % 12)
            octave = gp.Octave.ottava
            harmonic = gp.ArtificialHarmonic(pitch, octave)
        elif harmonicType == 17:
            pitch = gp.PitchClass(note.realValue)
            octave = gp.Octave.quindicesima
            harmonic = gp.ArtificialHarmonic(pitch, octave)
        elif harmonicType == 22:
            pitch = gp.PitchClass(note.realValue)
            octave = gp.Octave.ottava
            harmonic = gp.ArtificialHarmonic(pitch, octave)
        return harmonic

    def readTrill(self):
        """Read trill.

        - Fret: :ref:`signed-byte`.

        - Period: :ref:`signed-byte`. See :meth:`fromTrillPeriod`.

        """
        trill = gp.TrillEffect()
        trill.fret = self.readSignedByte()
        trill.duration.value = self.fromTrillPeriod(self.readSignedByte())
        return trill

    def fromTrillPeriod(self, period):
        """Convert trill period to actual duration.

        Values are:

        - *1*: sixteenth
        - *2*: thirty-second
        - *3*: sixty-fourth

        """
        if period == 1:
            return gp.Duration.sixteenth
        elif period == 2:
            return gp.Duration.thirtySecond
        elif period == 3:
            return gp.Duration.sixtyFourth

    # Writing
    # =======

    def writeSong(self, song):
        self.writeVersion()
        self.writeClipboard(song.clipboard)

        self.writeInfo(song)
        self._tripletFeel = song.tracks[0].measures[0].tripletFeel.value
        self.writeBool(self._tripletFeel)
        self.writeLyrics(song.lyrics)

        self.writeInt(song.tempo)
        self.writeInt(song.key.value[0])
        self.writeSignedByte(0)  # octave

        self.writeMidiChannels(song.tracks)

        measureCount = len(song.tracks[0].measures)
        trackCount = len(song.tracks)
        self.writeInt(measureCount)
        self.writeInt(trackCount)

        self.writeMeasureHeaders(song.tracks[0].measures)
        self.writeTracks(song.tracks)
        self.writeMeasures(song.tracks)

    def writeClipboard(self, clipboard):
        if clipboard is None:
            return
        self.writeInt(clipboard.startMeasure)
        self.writeInt(clipboard.stopMeasure)
        self.writeInt(clipboard.startTrack)
        self.writeInt(clipboard.stopTrack)

    def writeLyrics(self, lyrics):
        self.writeInt(lyrics.trackChoice)
        for line in lyrics.lines:
            self.writeInt(line.startingMeasure)
            self.writeIntSizeString(line.lyrics)

    def writeBeat(self, beat):
        flags = 0x00
        if beat.duration.isDotted:
            flags |= 0x01
        if beat.effect.isChord:
            flags |= 0x02
        if beat.text is not None:
            flags |= 0x04
        if not beat.effect.isDefault:
            flags |= 0x08
        if beat.effect.mixTableChange is not None:
            if not beat.effect.mixTableChange.isJustWah or self.versionTuple[0] > 4:
                flags |= 0x10
        if beat.duration.tuplet != gp.Tuplet():
            flags |= 0x20
        if beat.status != gp.BeatStatus.normal:
            flags |= 0x40
        self.writeSignedByte(flags)
        if flags & 0x40:
            self.writeByte(beat.status.value)
        self.writeDuration(beat.duration, flags)
        if flags & 0x02:
            self.writeChord(beat.effect.chord)
        if flags & 0x04:
            self.writeText(beat.text)
        if flags & 0x08:
            self.writeBeatEffects(beat)
        if flags & 0x10:
            self.writeMixTableChange(beat.effect.mixTableChange)
        self.writeNotes(beat)

    def writeChord(self, chord):
        self.writeSignedByte(1)  # signify GP4 chord format
        self.writeBool(chord.sharp)
        self.placeholder(3)
        self.writeByte(chord.root.value if chord.root else 0)
        self.writeByte(chord.type.value if chord.type else 0)
        self.writeByte(chord.extension.value if chord.extension else 0)
        self.writeInt(chord.bass.value if chord.bass else 0)
        self.writeInt(chord.tonality.value if chord.tonality else 0)
        self.writeBool(chord.add)
        self.writeByteSizeString(chord.name, 22)
        self.writeByte(chord.fifth.value if chord.fifth else 0)
        self.writeByte(chord.ninth.value if chord.ninth else 0)
        self.writeByte(chord.eleventh.value if chord.eleventh else 0)

        self.writeInt(chord.firstFret)
        for fret in clamp(chord.strings, 7, fillvalue=-1):
            self.writeInt(fret)

        self.writeByte(len(chord.barres))
        if chord.barres:
            barreFrets, barreStarts, barreEnds = zip(*map(attr.astuple, chord.barres))
        else:
            barreFrets, barreStarts, barreEnds = [], [], []
        for fret in clamp(barreFrets, 5, fillvalue=0):
            self.writeByte(fret)
        for start in clamp(barreStarts, 5, fillvalue=0):
            self.writeByte(start)
        for end in clamp(barreEnds, 5, fillvalue=0):
            self.writeByte(end)

        for omission in clamp(chord.omissions, 7, fillvalue=True):
            self.writeBool(omission)

        self.placeholder(1)
        for fingering in clamp(chord.fingerings, 7, fillvalue=gp.Fingering.unknown):
            self.writeSignedByte(fingering.value)
        self.writeBool(chord.show)

    def writeBeatEffects(self, beat):
        flags1 = 0x00
        if beat.effect.vibrato:
            flags1 |= 0x02
        if beat.effect.fadeIn:
            flags1 |= 0x10
        if beat.effect.isSlapEffect:
            flags1 |= 0x20
        if beat.effect.stroke != gp.BeatStroke():
            flags1 |= 0x40

        self.writeSignedByte(flags1)

        flags2 = 0x00
        if beat.effect.hasRasgueado:
            flags2 |= 0x01
        if beat.effect.hasPickStroke:
            flags2 |= 0x02
        if beat.effect.isTremoloBar:
            flags2 |= 0x04

        self.writeSignedByte(flags2)

        if flags1 & 0x20:
            self.writeSignedByte(beat.effect.slapEffect.value)
        if flags2 & 0x04:
            self.writeTremoloBar(beat.effect.tremoloBar)
        if flags1 & 0x40:
            self.writeBeatStroke(beat.effect.stroke)
        if flags2 & 0x02:
            self.writeSignedByte(beat.effect.pickStroke.value)

    def writeTremoloBar(self, tremoloBar):
        self.writeBend(tremoloBar)

    def writeMixTableChange(self, tableChange):
        super(GP4File, self).writeMixTableChange(tableChange)
        self.writeMixTableChangeFlags(tableChange)

    def writeMixTableChangeFlags(self, tableChange):
        flags = 0x00
        if tableChange.volume is not None and tableChange.volume.allTracks:
            flags |= 0x01
        if tableChange.balance is not None and tableChange.balance.allTracks:
            flags |= 0x02
        if tableChange.chorus is not None and tableChange.chorus.allTracks:
            flags |= 0x04
        if tableChange.reverb is not None and tableChange.reverb.allTracks:
            flags |= 0x08
        if tableChange.phaser is not None and tableChange.phaser.allTracks:
            flags |= 0x10
        if tableChange.tremolo is not None and tableChange.tremolo.allTracks:
            flags |= 0x20
        self.writeSignedByte(flags)

    def writeNote(self, note):
        flags = self.packNoteFlags(note)
        self.writeByte(flags)
        if flags & 0x20:
            self.writeByte(note.type.value)
        if flags & 0x01:
            self.writeSignedByte(note.duration)
            self.writeSignedByte(note.tuplet)
        if flags & 0x10:
            value = self.packVelocity(note.velocity)
            self.writeSignedByte(value)
        if flags & 0x20:
            fret = note.value if note.type != gp.NoteType.tie else 0
            self.writeSignedByte(fret)
        if flags & 0x80:
            self.writeSignedByte(note.effect.leftHandFinger.value)
            self.writeSignedByte(note.effect.rightHandFinger.value)
        if flags & 0x08:
            self.writeNoteEffects(note)

    def packNoteFlags(self, note):
        flags = super(GP4File, self).packNoteFlags(note)
        if note.effect.accentuatedNote:
            flags |= 0x40
        if note.effect.isFingering:
            flags |= 0x80
        return flags

    def writeNoteEffects(self, note):
        noteEffect = note.effect
        flags1 = 0x00
        if noteEffect.isBend:
            flags1 |= 0x01
        if noteEffect.hammer:
            flags1 |= 0x02
        if noteEffect.letRing:
            flags1 |= 0x08
        if noteEffect.isGrace:
            flags1 |= 0x10
        self.writeSignedByte(flags1)
        flags2 = 0x00
        if noteEffect.staccato:
            flags2 |= 0x01
        if noteEffect.palmMute:
            flags2 |= 0x02
        if noteEffect.isTremoloPicking:
            flags2 |= 0x04
        if noteEffect.slides:
            flags2 |= 0x08
        if noteEffect.isHarmonic:
            flags2 |= 0x10
        if noteEffect.isTrill:
            flags2 |= 0x20
        if noteEffect.vibrato:
            flags2 |= 0x40
        self.writeSignedByte(flags2)
        if flags1 & 0x01:
            self.writeBend(noteEffect.bend)
        if flags1 & 0x10:
            self.writeGrace(noteEffect.grace)
        if flags2 & 0x04:
            self.writeTremoloPicking(noteEffect.tremoloPicking)
        if flags2 & 0x08:
            self.writeSlides(noteEffect.slides)
        if flags2 & 0x10:
            self.writeHarmonic(note, noteEffect.harmonic)
        if flags2 & 0x20:
            self.writeTrill(noteEffect.trill)

    def writeTremoloPicking(self, tremoloPicking):
        self.writeSignedByte(self.toTremoloValue(tremoloPicking.duration.value))

    def writeSlides(self, slides):
        self.writeSignedByte(slides[0].value)

    def toTremoloValue(self, value):
        if value == gp.Duration.eighth:
            return 1
        elif value == gp.Duration.sixteenth:
            return 2
        elif value == gp.Duration.thirtySecond:
            return 3

    def writeHarmonic(self, note, harmonic):
        if not isinstance(harmonic, gp.ArtificialHarmonic):
            byte = harmonic.type
        else:
            if harmonic.pitch and harmonic.octave:
                if harmonic.pitch.value == (note.realValue + 7) % 12 and harmonic.octave == gp.Octave.ottava:
                    byte = 15
                elif harmonic.pitch.value == note.realValue % 12 and harmonic.octave == gp.Octave.quindicesima:
                    byte = 17
                elif harmonic.pitch.value == note.realValue % 12 and harmonic.octave == gp.Octave.ottava:
                    byte = 22
                else:
                    byte = 22
            else:
                byte = 22
        self.writeSignedByte(byte)

    def writeTrill(self, trill):
        self.writeSignedByte(trill.fret)
        self.writeSignedByte(self.toTrillPeriod(trill.duration.value))

    def toTrillPeriod(self, value):
        if value == gp.Duration.sixteenth:
            return 1
        if value == gp.Duration.thirtySecond:
            return 2
        if value == gp.Duration.sixtyFourth:
            return 3
