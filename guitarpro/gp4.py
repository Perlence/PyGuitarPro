from __future__ import division

import copy

from . import base as gp
from . import gp3


class GP4File(gp3.GP3File):

    '''A reader for GuitarPro 4 files.
    '''
    _supportedVersions = ['FICHIER GUITAR PRO v4.00',
                          'FICHIER GUITAR PRO v4.06',
                          'FICHIER GUITAR PRO L4.06']

    def __init__(self, *args, **kwargs):
        super(GP4File, self).__init__(*args, **kwargs)

    #
    # Reading
    #

    def readSong(self):
        if not self.readVersion():
            raise gp.GuitarProException(
                "unsupported version '%s'" %
                self.version)

        song = gp.Song()

        self.readInfo(song)

        self._tripletFeel = (gp.TripletFeel.eighth if self.readBool()
                             else gp.TripletFeel.none)

        self.readLyrics(song)

        self.readPageSetup(song)

        song.tempoName = ''
        song.tempo = self.readInt()
        song.hideTempo = False

        song.key = self.readInt()
        song.octave = self.readSignedByte()

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
        for i in range(gp.Lyrics.MAX_LINE_COUNT):
            line = gp.LyricLine()
            line.startingMeasure = self.readInt()
            line.lyrics = self.readIntSizeString()
            song.lyrics.lines.append(line)

    def readBeat(self, start, measure, track, voiceIndex):
        flags = self.readSignedByte()

        beat = self.getBeat(measure, start)
        voice = beat.voices[voiceIndex]

        if flags & 0x40 != 0:
            beatType = self.readSignedByte()
            voice.isEmpty = (beatType & 0x02) == 0

        duration = self.readDuration(flags)
        if flags & 0x02 != 0:
            self.readChord(len(track.strings), beat)

        if flags & 0x04 != 0:
            self.readText(beat)

        if flags & 0x08 != 0:
            self.readBeatEffects(beat, None)

        if flags & 0x10 != 0:
            mixTableChange = self.readMixTableChange(measure)
            beat.effect.mixTableChange = mixTableChange

        stringFlags = self.readSignedByte()
        for j in range(7):
            i = 6 - j
            if stringFlags & (1 << i) != 0 and (6 - i) < len(track.strings):
                # guitarString = track.strings[6 - i].clone(factory)
                guitarString = copy.copy(track.strings[6 - i])
                note = self.readNote(guitarString, track, gp.NoteEffect())
                voice.addNote(note)
            # duration.copy(voice.duration)
            voice.duration = copy.copy(duration)

        return duration.time if not voice.isEmpty else 0

    def readNoteEffects(self, noteEffect):
        flags1 = self.readSignedByte()
        flags2 = self.readSignedByte()
        if flags1 & 0x01 != 0:
            self.readBend(noteEffect)
        if flags1 & 0x10 != 0:
            self.readGrace(noteEffect)
        if flags2 & 0x04 != 0:
            self.readTremoloPicking(noteEffect)
        if flags2 & 0x08 != 0:
            import ipdb; ipdb.set_trace()
            noteEffect.slide = gp.SlideType(self.readSignedByte())
        if flags2 & 0x10 != 0:
            self.readArtificialHarmonic(noteEffect)
        if flags2 & 0x20 != 0:
            self.readTrill(noteEffect)
        noteEffect.letRing = (flags1 & 0x08) != 0
        noteEffect.hammer = (flags1 & 0x02) != 0
        noteEffect.vibrato = (flags2 & 0x40) != 0 or noteEffect.vibrato
        noteEffect.palmMute = (flags2 & 0x02) != 0
        noteEffect.staccato = (flags2 & 0x01) != 0

    def fromTrillPeriod(self, period):
        if period == 1:
            return gp.Duration.SIXTEENTH
        elif period == 2:
            return gp.Duration.THIRTY_SECOND
        elif period == 3:
            return gp.Duration.SIXTY_FOURTH

    def readTrill(self, noteEffect):
        fret = self.readSignedByte()
        period = self.readSignedByte()
        trill = gp.TrillEffect()
        trill.fret = fret
        trill.duration.value = self.fromTrillPeriod(period)
        noteEffect.trill = trill

    def fromHarmonicType(self, harmonicType):
        if harmonicType == 1:
            return (0, gp.HarmonicType.natural)
        elif harmonicType == 3:
            return (0, gp.HarmonicType.tapped)
        elif harmonicType == 4:
            return (0, gp.HarmonicType.pinch)
        elif harmonicType == 5:
            return (0, gp.HarmonicType.semi)
        elif harmonicType == 15:
            data = 0, 0, 1
            return (data, gp.HarmonicType.artificial)
        elif harmonicType == 17:
            data = 7, 0, 1
            return (data, gp.HarmonicType.artificial)
        elif harmonicType == 22:
            data = 0, 0, 0
            return (data, gp.HarmonicType.artificial)

    def readArtificialHarmonic(self, noteEffect):
        harmonicType = self.readSignedByte()
        data, type_ = self.fromHarmonicType(harmonicType)
        noteEffect.harmonic = gp.HarmonicEffect(type_, data)

    def fromTremoloValue(self, value):
        if value == 1:
            return gp.Duration.EIGHTH
        elif value == 2:
            return gp.Duration.SIXTEENTH
        elif value == 3:
            return gp.Duration.THIRTY_SECOND

    def readTremoloPicking(self, noteEffect):
        value = self.readSignedByte()
        tp = gp.TremoloPickingEffect()
        tp.duration.value = self.fromTremoloValue(value)
        noteEffect.tremoloPicking = tp

    def readMixTableChange(self, measure):
        tableChange = super(GP4File, self).readMixTableChange(measure)

        allTracksFlags = self.readSignedByte()
        if tableChange.volume is not None:
            tableChange.volume.allTracks = (allTracksFlags & 0x01) != 0
        if tableChange.balance is not None:
            tableChange.balance.allTracks = (allTracksFlags & 0x02) != 0
        if tableChange.chorus is not None:
            tableChange.chorus.allTracks = (allTracksFlags & 0x04) != 0
        if tableChange.reverb is not None:
            tableChange.reverb.allTracks = (allTracksFlags & 0x08) != 0
        if tableChange.phaser is not None:
            tableChange.phaser.allTracks = (allTracksFlags & 0x10) != 0
        if tableChange.tremolo is not None:
            tableChange.tremolo.allTracks = (allTracksFlags & 0x20) != 0
        if tableChange.tempo is not None:
            tableChange.tempo.allTracks = True

        return tableChange

    def readBeatEffects(self, beat, effect):
        flags1 = self.readSignedByte()
        flags2 = self.readSignedByte()
        beat.effect.fadeIn = (flags1 & 0x10) != 0
        beat.effect.vibrato = (flags1 & 0x02) != 0 or beat.effect.vibrato
        if flags1 & 0x20 != 0:
            slapEffect = self.readSignedByte()
            beat.effect.tapping = slapEffect == 1
            beat.effect.slapping = slapEffect == 2
            beat.effect.popping = slapEffect == 3
        if flags2 & 0x04 != 0:
            self.readTremoloBar(beat.effect)
        if flags1 & 0x40 != 0:
            strokeUp = self.readSignedByte()
            strokeDown = self.readSignedByte()
            if strokeUp > 0:
                beat.effect.stroke.direction = gp.BeatStrokeDirection.Up
                beat.effect.stroke.value = self.toStrokeValue(strokeUp)
            elif strokeDown > 0:
                beat.effect.stroke.direction = gp.BeatStrokeDirection.Down
                beat.effect.stroke.value = self.toStrokeValue(strokeDown)
        beat.effect.hasRasgueado = (flags2 & 0x01) != 0
        if flags2 & 0x02 != 0:
            beat.effect.pickStroke = self.readSignedByte()
            beat.effect.hasPickStroke = True

    def readTremoloBar(self, effect):
        barEffect = gp.BendEffect()
        barEffect.type = gp.BendType(self.readSignedByte())
        barEffect.value = self.readInt()
        pointCount = self.readInt()
        for i in range(pointCount):
            pointPosition = round(self.readInt() * gp.BendEffect.MAX_POSITION /
                                  self.BEND_POSITION)
            pointValue = round(self.readInt() / (self.BEND_SEMITONE * 2.0))
            vibrato = self.readBool()
            barEffect.points.append(gp.BendPoint(pointPosition, pointValue,
                                                 vibrato))
        if pointCount > 0:
            effect.tremoloBar = barEffect

    def readChord(self, stringCount, beat):
        chord = gp.Chord(stringCount)
        if self.readSignedByte() & 0x01 == 0:
            chord.name = self.readIntSizeCheckByteString()
            chord.firstFret = self.readInt()
            if chord.firstFret != 0:
                for i in range(6):
                    fret = self.readInt()
                    if i < len(chord.strings):
                        chord.strings[i] = fret
        else:
            chord.sharp = self.readByte()
            self.skip(3)
            chord.root = self.readByte()
            chord.type = gp.ChordType(self.readByte())
            chord.net = self.readByte()
            chord.bass = self.readInt()
            chord.tonality = gp.ChordTonality(self.readInt())
            chord.add = self.readBool()
            chord.name = self.readByteSizeString(20)
            self.skip(2)
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
            barreFrets = [self.readByte() for __ in range(5)]
            barreStarts = [self.readByte() for __ in range(5)]
            barreEnds = [self.readByte() for __ in range(5)]
            for fret, start, end, __ in zip(barreFrets, barreStarts, barreEnds,
                                            range(barresCount)):
                barre = gp.Barre(fret, start, end)
                chord.barres.append(barre)
            chord.omissions = [self.readByte() for __ in range(7)]
            self.skip(1)
            chord.fingerings = [gp.Fingering(self.readSignedByte())
                                for __ in range(7)]
            chord.show = self.readBool()
        if len(chord.notes) > 0:
            beat.setChord(chord)

    #
    # Writing
    #

    def writeSong(self, song):
        self.writeVersion(1)
        self.writeInfo(song)

        self._tripletFeel = song.tracks[0].measures[0].tripletFeel
        self.writeBool(self._tripletFeel)

        self.writeLyrics(song.lyrics)
        self.writePageSetup(None)

        self.writeInt(song.tempo)
        self.writeInt(song.key)
        self.writeSignedByte(song.octave)

        self.writeMidiChannels(song.tracks)

        measureCount = len(song.tracks[0].measures)
        trackCount = len(song.tracks)
        self.writeInt(measureCount)
        self.writeInt(trackCount)

        self.writeMeasureHeaders(song.tracks[0].measures)
        self.writeTracks(song.tracks)
        self.writeMeasures(song.tracks)

    def writeLyrics(self, lyrics):
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

        if flags & 0x40 != 0:
            beatType = 0x00 if voice.isEmpty else 0x02
            self.writeSignedByte(beatType)

        self.writeDuration(voice.duration, flags)

        if flags & 0x02 != 0:
            self.writeChord(beat.effect.chord)

        if flags & 0x04 != 0:
            self.writeText(beat.text)

        if flags & 0x08 != 0:
            self.writeBeatEffects(beat.effect)

        if flags & 0x10 != 0:
            self.writeMixTableChange(beat.effect.mixTableChange)

        stringFlags = 0x00
        for note in voice.notes:
            stringFlags |= 1 << (7 - note.string)
        self.writeSignedByte(stringFlags)

        previous = None
        for note in voice.notes:
            self.writeNote(note, previous)
            previous = note

    def writeNote(self, note, previous):
        flags = 0x00
        try:
            if note.duration is not None and note.tuplet is not None:
                flags |= 0x01
        except AttributeError:
            pass
        if note.effect.heavyAccentuatedNote:
            flags |= 0x02
        if note.effect.ghostNote:
            flags |= 0x04
        if not note.effect.isDefault or note.effect.presence:
            flags |= 0x08
        # if previous is not None and note.velocity != previous.velocity:
        if note.velocity != gp.Velocities.DEFAULT:
            flags |= 0x10
        # if note.isTiedNote or note.effect.deadNote:
        flags |= 0x20
        if note.effect.accentuatedNote:
            flags |= 0x40
        if note.effect.isFingering:
            flags |= 0x80

        self.writeByte(flags)

        if flags & 0x20 != 0:
            if note.isTiedNote:
                noteType = 0x02
            elif note.effect.deadNote:
                noteType = 0x03
            else:
                noteType = 0x01
            self.writeByte(noteType)

        if flags & 0x01 != 0:
            self.writeSignedByte(note.duration)
            self.writeSignedByte(note.tuplet)

        if flags & 0x10 != 0:
            value = self.packVelocity(note.velocity)
            self.writeSignedByte(value)

        if flags & 0x20 != 0:
            fret = note.value if not note.isTiedNote else 0
            self.writeSignedByte(fret)

        if flags & 0x80 != 0:
            self.writeSignedByte(note.effect.leftHandFinger)
            self.writeSignedByte(note.effect.rightHandFinger)

        if flags & 0x08 != 0:
            self.writeNoteEffects(note.effect)

    def writeNoteEffects(self, noteEffect):
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
        if noteEffect.slide:
            flags2 |= 0x08
        if noteEffect.isHarmonic:
            flags2 |= 0x10
        if noteEffect.isTrill:
            flags2 |= 0x20
        if noteEffect.vibrato:
            flags2 |= 0x40

        self.writeSignedByte(flags2)

        if flags1 & 0x01 != 0:
            self.writeBend(noteEffect.bend)
        if flags1 & 0x10 != 0:
            self.writeGrace(noteEffect.grace)
        if flags2 & 0x04 != 0:
            self.writeTremoloPicking(noteEffect.tremoloPicking)
        if flags2 & 0x08 != 0:
            self.writeSignedByte(noteEffect.slide.value)
        if flags2 & 0x10 != 0:
            self.writeArtificialHarmonic(noteEffect.harmonic)
        if flags2 & 0x20 != 0:
            self.writeTrill(noteEffect.trill)

    def toTrillPeriod(self, value):
        if value == gp.Duration.SIXTEENTH:
            return 1
        if value == gp.Duration.THIRTY_SECOND:
            return 2
        if value == gp.Duration.SIXTY_FOURTH:
            return 3

    def writeTrill(self, trill):
        self.writeSignedByte(trill.fret)
        self.writeSignedByte(self.toTrillPeriod(trill.duration.value))

    def toHarmonicType(self, harmonic):
        if harmonic.type != gp.HarmonicType.artificial:
            return harmonic.type.value
        else:
            if harmonic.data == (0, 0, 1):
                return 15
            elif harmonic.data == (7, 0, 1):
                return 17
            else:
                return 22

    def writeArtificialHarmonic(self, harmonic):
        self.writeSignedByte(self.toHarmonicType(harmonic))

    def toTremoloValue(self, value):
        if value == gp.Duration.EIGHTH:
            return 1
        elif value == gp.Duration.SIXTEENTH:
            return 2
        elif value == gp.Duration.THIRTY_SECOND:
            return 3

    def writeTremoloPicking(self, tremoloPicking):
        self.writeSignedByte(
            self.toTremoloValue(tremoloPicking.duration.value))

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

        if flags1 & 0x20 != 0:
            if beatEffect.tapping:
                slapEffect = 1
            if beatEffect.slapping:
                slapEffect = 2
            if beatEffect.popping:
                slapEffect = 3
            self.writeSignedByte(slapEffect)
        if flags2 & 0x04 != 0:
            self.writeTremoloBar(beatEffect.tremoloBar)
        if flags1 & 0x40 != 0:
            if beatEffect.stroke.direction == gp.BeatStrokeDirection.Up:
                strokeUp = self.fromStrokeValue(beatEffect.stroke.value)
                strokeDown = 0
            elif beatEffect.stroke.direction == gp.BeatStrokeDirection.Down:
                strokeUp = 0
                strokeDown = self.fromStrokeValue(beatEffect.stroke.value)
            self.writeSignedByte(strokeUp)
            self.writeSignedByte(strokeDown)
        if flags2 & 0x02 != 0:
            self.writeSignedByte(beatEffect.pickStroke)

    def writeTremoloBar(self, tremoloBar):
        self.writeSignedByte(tremoloBar.type.value)
        self.writeInt(tremoloBar.value)
        self.writeInt(len(tremoloBar.points))
        for point in tremoloBar.points:
            self.writeInt(round(point.position * self.BEND_POSITION /
                                gp.BendEffect.MAX_POSITION))
            self.writeInt(round(point.value * (self.BEND_SEMITONE * 2.0)))
            self.writeBool(point.vibrato)

    def writeChord(self, chord):
        # if self.writeSignedByte() & 0x01 == 0:
        #     chord.name = self.writeIntSizeCheckByteString()
        #     chord.firstFret = self.writeInt()
        #     if chord.firstFret != 0:
        #         for i in range(6):
        #             fret = self.writeInt()
        #             if i < len(chord.strings):
        #                 chord.strings[i] = fret
        self.writeSignedByte(1)
        self.placeholder(16)
        self.writeByteSizeString(chord.name, 21)
        self.placeholder(4)
        self.writeInt(chord.firstFret)
        for i in range(7):
            fret = -1
            if i < len(chord.strings):
                fret = chord.strings[i]
            self.writeInt(fret)
        self.placeholder(32)
