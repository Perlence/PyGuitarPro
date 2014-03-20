from __future__ import division

from . import base as gp
from . import gp3
from .utils import clamp


class GP4File(gp3.GP3File):

    '''A reader for GuitarPro 4 files.
    '''
    _supportedVersions = ['FICHIER GUITAR PRO v4.00',
                          'FICHIER GUITAR PRO v4.06',
                          'FICHIER GUITAR PRO L4.06']

    def __init__(self, *args, **kwargs):
        super(GP4File, self).__init__(*args, **kwargs)

    # Reading
    # =======

    def readSong(self):
        if not self.readVersion():
            raise gp.GPException("unsupported version '%s'" %
                                 self.version)
        song = gp.Song()
        self.readInfo(song)
        self._tripletFeel = (gp.TripletFeel.eighth if self.readBool()
                             else gp.TripletFeel.none)
        self.readLyrics(song)
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

    def readLyrics(self, song):
        song.lyrics = gp.Lyrics()
        song.lyrics.trackChoice = self.readInt()
        for line in song.lyrics.lines:
            line.startingMeasure = self.readInt()
            line.lyrics = self.readIntSizeString()

    def readNewChord(self, chord):
        chord.sharp = self.readBool()
        intonation = 'sharp' if chord.sharp else 'flat'
        self.skip(3)
        chord.root = gp.PitchClass(self.readByte(), intonation=intonation)
        chord.type = gp.ChordType(self.readByte())
        chord.extension = gp.ChordExtension(self.readByte())
        chord.bass = gp.PitchClass(self.readInt(), intonation=intonation)
        chord.tonality = gp.ChordTonality(self.readInt())
        chord.add = self.readBool()
        chord.name = self.readByteSizeString(22)
        chord.fifth = gp.ChordTonality(self.readByte())
        chord.ninth = gp.ChordTonality(self.readByte())
        chord.eleventh = gp.ChordTonality(self.readByte())
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
        for fret, start, end, __ in zip(barreFrets, barreStarts, barreEnds,
                                        range(barresCount)):
            barre = gp.Barre(fret, start, end)
            chord.barres.append(barre)
        chord.omissions = self.readByte(7)
        self.skip(1)
        chord.fingerings = map(gp.Fingering, self.readSignedByte(7))
        chord.show = self.readBool()

    def readBeatEffects(self, beat, effect):
        flags1 = self.readSignedByte()
        flags2 = self.readSignedByte()
        beat.effect.vibrato = bool(flags1 & 0x02) or beat.effect.vibrato
        beat.effect.fadeIn = bool(flags1 & 0x10)
        if flags1 & 0x20:
            slapEffect = self.readSignedByte()
            beat.effect.tapping = slapEffect == 1
            beat.effect.slapping = slapEffect == 2
            beat.effect.popping = slapEffect == 3
        if flags2 & 0x04:
            self.readTremoloBar(beat.effect)
        if flags1 & 0x40:
            strokeUp = self.readSignedByte()
            strokeDown = self.readSignedByte()
            if strokeUp > 0:
                beat.effect.stroke.direction = gp.BeatStrokeDirection.up
                beat.effect.stroke.value = self.toStrokeValue(strokeUp)
            elif strokeDown > 0:
                beat.effect.stroke.direction = gp.BeatStrokeDirection.down
                beat.effect.stroke.value = self.toStrokeValue(strokeDown)
        beat.effect.hasRasgueado = bool(flags2 & 0x01)
        if flags2 & 0x02:
            beat.effect.pickStroke = self.readSignedByte()
            beat.effect.hasPickStroke = True

    def readTremoloBar(self, effect):
        barEffect = gp.BendEffect()
        barEffect.type = gp.BendType(self.readSignedByte())
        barEffect.value = self.readInt()
        pointCount = self.readInt()
        for i in range(pointCount):
            pointPosition = round(self.readInt() * gp.BendEffect.maxPosition /
                                  self.bendPosition)
            pointValue = round(self.readInt() / (self.bendSemitone * 2.0))
            vibrato = self.readBool()
            barEffect.points.append(gp.BendPoint(pointPosition, pointValue,
                                                 vibrato))
        if pointCount > 0:
            effect.tremoloBar = barEffect

    def readMixTableChange(self, measure):
        tableChange = super(GP4File, self).readMixTableChange(measure)

        allTracksFlags = self.readSignedByte()
        if tableChange.volume is not None:
            tableChange.volume.allTracks = bool(allTracksFlags & 0x01)
        if tableChange.balance is not None:
            tableChange.balance.allTracks = bool(allTracksFlags & 0x02)
        if tableChange.chorus is not None:
            tableChange.chorus.allTracks = bool(allTracksFlags & 0x04)
        if tableChange.reverb is not None:
            tableChange.reverb.allTracks = bool(allTracksFlags & 0x08)
        if tableChange.phaser is not None:
            tableChange.phaser.allTracks = bool(allTracksFlags & 0x10)
        if tableChange.tremolo is not None:
            tableChange.tremolo.allTracks = bool(allTracksFlags & 0x20)
        if tableChange.tempo is not None:
            tableChange.tempo.allTracks = True

        return tableChange

    def readNoteEffects(self, note):
        noteEffect = note.effect
        flags1 = self.readSignedByte()
        flags2 = self.readSignedByte()
        if flags1 & 0x01:
            self.readBend(noteEffect)
        if flags1 & 0x10:
            self.readGrace(noteEffect)
        if flags2 & 0x04:
            self.readTremoloPicking(noteEffect)
        if flags2 & 0x08:
            noteEffect.slides = [gp.SlideType(self.readSignedByte())]
        if flags2 & 0x10:
            self.readHarmonic(note)
        if flags2 & 0x20:
            self.readTrill(noteEffect)
        noteEffect.hammer = bool(flags1 & 0x02)
        noteEffect.letRing = bool(flags1 & 0x08)
        noteEffect.staccato = bool(flags2 & 0x01)
        noteEffect.palmMute = bool(flags2 & 0x02)
        noteEffect.vibrato = bool(flags2 & 0x40) or noteEffect.vibrato

    def readTremoloPicking(self, noteEffect):
        value = self.readSignedByte()
        tp = gp.TremoloPickingEffect()
        tp.duration.value = self.fromTremoloValue(value)
        noteEffect.tremoloPicking = tp

    def fromTremoloValue(self, value):
        if value == 1:
            return gp.Duration.eighth
        elif value == 2:
            return gp.Duration.sixteenth
        elif value == 3:
            return gp.Duration.thirtySecond

    def readHarmonic(self, note):
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
        note.effect.harmonic = harmonic

    def readTrill(self, noteEffect):
        fret = self.readSignedByte()
        period = self.readSignedByte()
        trill = gp.TrillEffect()
        trill.fret = fret
        trill.duration.value = self.fromTrillPeriod(period)
        noteEffect.trill = trill

    def fromTrillPeriod(self, period):
        if period == 1:
            return gp.Duration.sixteenth
        elif period == 2:
            return gp.Duration.thirtySecond
        elif period == 3:
            return gp.Duration.sixtyFourth

    # Writing
    # =======

    def writeSong(self, song):
        self.writeVersion(1)
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

    def writeLyrics(self, lyrics):
        if lyrics is None:
            lyrics = gp.Lyrics()
        self.writeInt(lyrics.trackChoice)
        for line in lyrics.lines:
            self.writeInt(line.startingMeasure)
            self.writeIntSizeString(line.lyrics)

    def writeBeat(self, beat, voiceIndex=0):
        voice = beat.voices[voiceIndex]

        flags = 0x00
        if voice.duration.isDotted:
            flags |= 0x01
        if beat.effect.isChord:
            flags |= 0x02
        if beat.text is not None:
            flags |= 0x04
        if not beat.effect.isDefault:
            flags |= 0x08
        if beat.effect.mixTableChange is not None:
            flags |= 0x10
        if voice.duration.tuplet != gp.Tuplet():
            flags |= 0x20
        if voice.isEmpty or voice.isRestVoice:
            flags |= 0x40

        self.writeSignedByte(flags)

        if flags & 0x40:
            beatType = 0x00 if voice.isEmpty else 0x02
            self.writeSignedByte(beatType)

        self.writeDuration(voice.duration, flags)

        if flags & 0x02:
            self.writeChord(beat.effect.chord)

        if flags & 0x04:
            self.writeText(beat.text)

        if flags & 0x08:
            self.writeBeatEffects(beat.effect)

        if flags & 0x10:
            self.writeMixTableChange(beat.effect.mixTableChange)

        self.writeNotes(voice)

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

        self.writeByte(len(chord.barres or []))
        if chord.barres:
            barreFrets, barreStarts, barreEnds = zip(*chord.barres)
        else:
            barreFrets, barreStarts, barreEnds = [], [], []
        for fret in clamp(barreFrets, 5, fillvalue=0):
            self.writeByte(fret)
        for start in clamp(barreStarts, 5, fillvalue=0):
            self.writeByte(start)
        for end in clamp(barreEnds, 5, fillvalue=0):
            self.writeByte(end)

        for omission in clamp(chord.omissions or [], 7, fillvalue=1):
            self.writeByte(omission)

        self.placeholder(1)
        for fingering in clamp(chord.fingerings or [], 7,
                               fillvalue=gp.Fingering.unknown):
            self.writeSignedByte(fingering.value)
        self.writeBool(chord.show)

    def writeBeatEffects(self, beatEffect, voice=None):
        flags1 = 0x00
        if beatEffect.vibrato:
            flags1 |= 0x02
        if beatEffect.fadeIn:
            flags1 |= 0x10
        if beatEffect.isSlapEffect:
            flags1 |= 0x20
        if beatEffect.stroke != gp.BeatStroke():
            flags1 |= 0x40

        self.writeSignedByte(flags1)

        flags2 = 0x00
        if beatEffect.hasRasgueado:
            flags2 |= 0x01
        if beatEffect.hasPickStroke:
            flags2 |= 0x02
        if beatEffect.isTremoloBar:
            flags2 |= 0x04

        self.writeSignedByte(flags2)

        if flags1 & 0x20:
            if beatEffect.tapping:
                slapEffect = 1
            if beatEffect.slapping:
                slapEffect = 2
            if beatEffect.popping:
                slapEffect = 3
            self.writeSignedByte(slapEffect)
        if flags2 & 0x04:
            self.writeTremoloBar(beatEffect.tremoloBar)
        if flags1 & 0x40:
            if beatEffect.stroke.direction == gp.BeatStrokeDirection.up:
                strokeUp = self.fromStrokeValue(beatEffect.stroke.value)
                strokeDown = 0
            elif beatEffect.stroke.direction == gp.BeatStrokeDirection.down:
                strokeUp = 0
                strokeDown = self.fromStrokeValue(beatEffect.stroke.value)
            self.writeSignedByte(strokeUp)
            self.writeSignedByte(strokeDown)
        if flags2 & 0x02:
            self.writeSignedByte(beatEffect.pickStroke)

    def writeTremoloBar(self, tremoloBar):
        self.writeSignedByte(tremoloBar.type.value)
        self.writeInt(tremoloBar.value)
        self.writeInt(len(tremoloBar.points))
        for point in tremoloBar.points:
            self.writeInt(round(point.position * self.bendPosition /
                                gp.BendEffect.maxPosition))
            self.writeInt(round(point.value * (self.bendSemitone * 2.0)))
            self.writeBool(point.vibrato)

    def writeMixTableChange(self, tableChange):
        super(GP4File, self).writeMixTableChange(tableChange)

        items = [tableChange.volume,
                 tableChange.balance,
                 tableChange.chorus,
                 tableChange.reverb,
                 tableChange.phaser,
                 tableChange.tremolo]

        allTracksFlags = 0x00
        for i, item in enumerate(items):
            if item is not None and item.allTracks:
                allTracksFlags |= 1 << i

        self.writeSignedByte(allTracksFlags)

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
            self.writeSignedByte(noteEffect.slides[0].value)
        if flags2 & 0x10:
            self.writeHarmonic(note, noteEffect.harmonic)
        if flags2 & 0x20:
            self.writeTrill(noteEffect.trill)

    def writeTremoloPicking(self, tremoloPicking):
        self.writeSignedByte(
            self.toTremoloValue(tremoloPicking.duration.value))

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
                if (harmonic.pitch.value == (note.realValue + 7) % 12
                        and harmonic.octave == gp.Octave.ottava):
                    byte = 15
                elif (harmonic.pitch.value == note.realValue % 12
                        and harmonic.octave == gp.Octave.quindicesima):
                    byte = 17
                elif (harmonic.pitch.value == note.realValue % 12
                        and harmonic.octave == gp.Octave.ottava):
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
