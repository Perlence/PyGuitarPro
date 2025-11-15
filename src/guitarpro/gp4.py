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
        song.tempo = self.readI32()
        song.key = gp.KeySignature((self.readI32(), 0))
        self.readI8()  # octave
        channels = self.readMidiChannels()
        measureCount = self.readI32()
        trackCount = self.readI32()
        with self.annotateErrors('reading'):
            self.readMeasureHeaders(song, measureCount)
            self.readTracks(song, trackCount, channels)
            self.readMeasures(song)
        return song

    def readClipboard(self):
        if not self.isClipboard():
            return
        clipboard = gp.Clipboard()
        clipboard.startMeasure = self.readI32()
        clipboard.stopMeasure = self.readI32()
        clipboard.startTrack = self.readI32()
        clipboard.stopTrack = self.readI32()
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
        lyrics.trackChoice = self.readI32()
        for line in lyrics.lines:
            line.startingMeasure = self.readI32()
            line.lyrics = self.readIntSizeString()
        return lyrics

    def packMeasureHeaderFlags(self, header, previous=None):
        flags = super().packMeasureHeaderFlags(header, previous)
        if previous is None or header.keySignature != previous.keySignature:
            flags |= 0x40
        if header.hasDoubleBar:
            flags |= 0x80
        return flags

    def writeMeasureHeaderValues(self, header, flags):
        super().writeMeasureHeaderValues(header, flags)
        if flags & 0x40:
            self.writeI8(header.keySignature.value[0])
            self.writeI8(header.keySignature.value[1])

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
        chord.root = gp.PitchClass(self.readU8(), intonation=intonation)
        chord.type = gp.ChordType(self.readU8())
        chord.extension = gp.ChordExtension(self.readU8())
        chord.bass = gp.PitchClass(self.readI32(), intonation=intonation)
        chord.tonality = gp.ChordAlteration(self.readI32())
        chord.add = self.readBool()
        chord.name = self.readByteSizeString(22)
        chord.fifth = gp.ChordAlteration(self.readU8())
        chord.ninth = gp.ChordAlteration(self.readU8())
        chord.eleventh = gp.ChordAlteration(self.readU8())
        chord.firstFret = self.readI32()
        for i in range(7):
            fret = self.readI32()
            if i < len(chord.strings):
                chord.strings[i] = fret
        chord.barres = []
        barresCount = self.readU8()
        barreFrets = [self.readU8() for _ in range(5)]
        barreStarts = [self.readU8() for _ in range(5)]
        barreEnds = [self.readU8() for _ in range(5)]
        for fret, start, end, _ in zip(barreFrets, barreStarts, barreEnds, range(barresCount)):
            barre = gp.Barre(fret, start, end)
            chord.barres.append(barre)
        chord.omissions = [self.readBool() for _ in range(7)]
        self.skip(1)
        chord.fingerings = [gp.Fingering(self.readI8()) for _ in range(7)]
        chord.show = self.readBool()

    def readBeatEffects(self, noteEffect):
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
        flags1 = self.readI8()
        flags2 = self.readI8()
        beatEffect.vibrato = bool(flags1 & 0x02) or beatEffect.vibrato
        beatEffect.fadeIn = bool(flags1 & 0x10)
        if flags1 & 0x20:
            value = self.readI8()
            beatEffect.slapEffect = gp.SlapEffect(value)
        if flags2 & 0x04:
            beatEffect.tremoloBar = self.readTremoloBar()
        if flags1 & 0x40:
            beatEffect.stroke = self.readBeatStroke()
        beatEffect.hasRasgueado = bool(flags2 & 0x01)
        if flags2 & 0x02:
            direction = self.readI8()
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
        tableChange = super().readMixTableChange(measure)
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
        flags = self.readI8()
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
        flags1 = self.readI8()
        flags2 = self.readI8()
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
        value = self.readI8()
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
        return [gp.SlideType(self.readI8())]

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
        harmonicType = self.readI8()
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
        trill.fret = self.readI8()
        trill.duration.value = self.fromTrillPeriod(self.readI8())
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

        self.writeI32(song.tempo)
        self.writeI32(song.key.value[0])
        self.writeI8(0)  # octave

        self.writeMidiChannels(song.tracks)

        measureCount = len(song.tracks[0].measures)
        trackCount = len(song.tracks)
        self.writeI32(measureCount)
        self.writeI32(trackCount)

        with self.annotateErrors('writing'):
            self.writeMeasureHeaders(song.tracks[0].measures)
            self.writeTracks(song.tracks)
            self.writeMeasures(song.tracks)

    def writeClipboard(self, clipboard):
        if clipboard is None:
            return
        self.writeI32(clipboard.startMeasure)
        self.writeI32(clipboard.stopMeasure)
        self.writeI32(clipboard.startTrack)
        self.writeI32(clipboard.stopTrack)

    def writeLyrics(self, lyrics):
        self.writeI32(lyrics.trackChoice)
        for line in lyrics.lines:
            self.writeI32(line.startingMeasure)
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
        self.writeI8(flags)
        if flags & 0x40:
            self.writeU8(beat.status.value)
        self.writeDuration(beat.duration, flags)
        if flags & 0x02:
            self.writeChord(beat.effect.chord)
        if flags & 0x04:
            self.writeIntByteSizeString(beat.text)
        if flags & 0x08:
            self.writeBeatEffects(beat)
        if flags & 0x10:
            self.writeMixTableChange(beat.effect.mixTableChange)
        self.writeNotes(beat)

    def writeChord(self, chord):
        self.writeI8(1)  # signify GP4 chord format
        self.writeBool(chord.sharp)
        self.placeholder(3)
        self.writeU8(chord.root.value if chord.root else 0)
        self.writeU8(self.getEnumValue(chord.type) if chord.type else 0)
        self.writeU8(self.getEnumValue(chord.extension) if chord.extension else 0)
        self.writeI32(chord.bass.value if chord.bass else 0)
        self.writeI32(chord.tonality.value if chord.tonality else 0)
        self.writeBool(chord.add)
        self.writeByteSizeString(chord.name, 22)
        self.writeU8(chord.fifth.value if chord.fifth else 0)
        self.writeU8(chord.ninth.value if chord.ninth else 0)
        self.writeU8(chord.eleventh.value if chord.eleventh else 0)

        self.writeI32(chord.firstFret)
        for fret in clamp(chord.strings, 7, fillvalue=-1):
            self.writeI32(fret)

        self.writeU8(len(chord.barres))
        if chord.barres:
            barreFrets, barreStarts, barreEnds = zip(*map(attr.astuple, chord.barres))
        else:
            barreFrets, barreStarts, barreEnds = [], [], []
        for fret in clamp(barreFrets, 5, fillvalue=0):
            self.writeU8(fret)
        for start in clamp(barreStarts, 5, fillvalue=0):
            self.writeU8(start)
        for end in clamp(barreEnds, 5, fillvalue=0):
            self.writeU8(end)

        for omission in clamp(chord.omissions, 7, fillvalue=True):
            self.writeBool(omission)

        self.placeholder(1)
        placeholder = gp.Fingering(-2)
        for fingering in clamp(chord.fingerings, 7, fillvalue=placeholder):
            self.writeI8(fingering.value)
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

        self.writeI8(flags1)

        flags2 = 0x00
        if beat.effect.hasRasgueado:
            flags2 |= 0x01
        if beat.effect.hasPickStroke:
            flags2 |= 0x02
        if beat.effect.isTremoloBar:
            flags2 |= 0x04

        self.writeI8(flags2)

        if flags1 & 0x20:
            self.writeI8(beat.effect.slapEffect.value)
        if flags2 & 0x04:
            self.writeTremoloBar(beat.effect.tremoloBar)
        if flags1 & 0x40:
            self.writeBeatStroke(beat.effect.stroke)
        if flags2 & 0x02:
            self.writeI8(beat.effect.pickStroke.value)

    def writeTremoloBar(self, tremoloBar):
        self.writeBend(tremoloBar)

    def writeMixTableChange(self, tableChange):
        super().writeMixTableChange(tableChange)
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
        self.writeI8(flags)

    def writeNote(self, note):
        flags = self.packNoteFlags(note)
        self.writeU8(flags)
        if flags & 0x20:
            self.writeU8(self.getEnumValue(note.type))
        if flags & 0x01:
            self.writeI8(note.duration)
            self.writeI8(note.tuplet)
        if flags & 0x10:
            value = self.packVelocity(note.velocity)
            self.writeI8(value)
        if flags & 0x20:
            fret = note.value if note.type != gp.NoteType.tie else 0
            self.writeI8(fret)
        if flags & 0x80:
            self.writeI8(self.getEnumValue(note.effect.leftHandFinger))
            self.writeI8(self.getEnumValue(note.effect.rightHandFinger))
        if flags & 0x08:
            self.writeNoteEffects(note)

    def packNoteFlags(self, note):
        flags = super().packNoteFlags(note)
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
        self.writeI8(flags1)
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
        self.writeI8(flags2)
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
        self.writeI8(self.toTremoloValue(tremoloPicking.duration.value))

    def writeSlides(self, slides):
        self.writeI8(slides[0].value)

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
        self.writeI8(byte)

    def writeTrill(self, trill):
        self.writeI8(trill.fret)
        self.writeI8(self.toTrillPeriod(trill.duration.value))

    def toTrillPeriod(self, value):
        if value == gp.Duration.sixteenth:
            return 1
        if value == gp.Duration.thirtySecond:
            return 2
        if value == gp.Duration.sixtyFourth:
            return 3
