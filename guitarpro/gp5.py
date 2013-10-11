# This file is part of alphaTab.
#
#  alphaTab is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  alphaTab is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with alphaTab.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division

import math
import copy

import base as gp
import gp4

class GP5File(gp4.GP4File):
    '''A reader for GuitarPro 5 files. 
    '''
    _supportedVersions = ['FICHIER GUITAR PRO v5.00', 'FICHIER GUITAR PRO v5.10']
    
    def __init__(self, *args, **kwargs):
        super(GP5File, self).__init__(*args, **kwargs)
    
    #################################################################
    #### Reading
    #################################################################

    def readSong(self):
        if not self.readVersion():
            raise gp.GuitarProException("unsupported version '%s'" % self.version)

        song = gp.Song()
        self.readInfo(song)
        
        self.readLyrics(song)
        self.readPageSetup(song)

        song.tempoName = self.readIntSizeCheckByteString()
        song.tempo = self.readInt()
                
        if not self.version.endswith('5.00'):
            song.hideTempo = self.readBool()
        else:
            song.hideTempo = False
        
        song.key = self.readByte()
        song.octave = self.readInt()
        
        channels = self.readMidiChannels()
        
        directions = self.readDirections()

        measureCount = self.readInt()
        trackCount = self.readInt()
        
        self.readMeasureHeaders(song, measureCount, directions)
        self.readTracks(song, trackCount, channels)
        self.readMeasures(song)
        
        return song

    def readDirections(self):
        signs = {
            gp.DirectionSign('Coda'): self.readShort(),
            gp.DirectionSign('Double Coda'): self.readShort(),
            gp.DirectionSign('Segno'): self.readShort(),
            gp.DirectionSign('Segno Segno'): self.readShort(),
            gp.DirectionSign('Fine'): self.readShort()
        }
        fromSigns = {
            gp.DirectionSign('Da Capo'): self.readShort(),
            gp.DirectionSign('Da Capo al Coda'): self.readShort(),
            gp.DirectionSign('Da Capo al Double Coda'): self.readShort(),
            gp.DirectionSign('Da Capo al Fine'): self.readShort(),
            gp.DirectionSign('Da Segno'): self.readShort(),
            gp.DirectionSign('Da Segno Segno al Coda'): self.readShort(),
            gp.DirectionSign('Da Segno Segno'): self.readShort(),
            gp.DirectionSign('Da Segno al Coda'): self.readShort(),
            gp.DirectionSign('Da Segno Segno al Double Coda'): self.readShort(),
            gp.DirectionSign('Da Segno al Fine'): self.readShort(),
            gp.DirectionSign('Da Segno al Double Coda'): self.readShort(),
            gp.DirectionSign('Da Segno Segno al Fine'): self.readShort(),
            gp.DirectionSign('Da Coda'): self.readShort(),
            gp.DirectionSign('Da Double Coda'): self.readShort()
        }
        # Opeth - Baying of the Hounds.gp5: ffffffff
        # Mastodon - Colony of Birchmen.gp5: 01000000
        # Mostly 00000000
        self.skip(4) # ???
        return signs, fromSigns
        
    def readMeasure(self, measure, track):
        for voice in range(gp.Beat.MAX_VOICES):
            start = measure.start()
            beats = self.readInt()
            for beat in range(beats):
                start += self.readBeat(start, measure, track, voice)
        measure.lineBreak = self.readByte(default=gp.LineBreak.None_)
    
    def readBeat(self, start, measure, track, voiceIndex):
        flags1 = self.readByte()
        
        beat = self.getBeat(measure, start)
        voice = beat.voices[voiceIndex]
        
        if flags1 & 0x40 != 0:
            beatType = self.readByte()
            voice.isEmpty = (beatType & 0x02) == 0
        
        duration = self.readDuration(flags1)

        if flags1 & 0x02 != 0:
            self.readChord(track.stringCount(), beat)

        if flags1 & 0x04 != 0:
            self.readText(beat)

        if flags1 & 0x08 != 0:
            self.readBeatEffects(beat, None)

        if flags1 & 0x10 != 0:
            mixTableChange = self.readMixTableChange(measure)
            beat.effect.mixTableChange = mixTableChange

        stringFlags = self.readByte()
        for j in range(7):
            i = 6 - j
            if stringFlags & (1 << i) != 0 and (6 - i) < track.stringCount():
                # guitarString = track.strings[6 - i].clone(factory)
                guitarString = copy.copy(track.strings[6 - i])
                note = self.readNote(guitarString, track, gp.NoteEffect())
                voice.addNote(note)
            # duration.copy(voice.duration)
            voice.duration = copy.copy(duration)
        
        flags2 = self.readByte()
        flags3 = self.readByte()

        if flags2 & 0x10 != 0:
            beat.octave = gp.Octave.Ottava
        if flags2 & 0x20 != 0:
            beat.octave = gp.Octave.OttavaBassa
        if flags2 & 0x40 != 0:
            beat.octave = gp.Octave.Quindicesima
        if flags3 & 0x01 != 0:
            beat.octave = gp.Octave.QuindicesimaBassa

        display = gp.BeatDisplay()
        display.breakBeam = (flags2 & 0x01) != 0
        display.forceBeam = (flags2 & 0x04) != 0
        display.forceBracket = (flags3 & 0x20) != 0
        display.breakSecondaryTuplet = (flags3 & 0x10) != 0
        if flags2 & 0x02 != 0:
            display.beamDirection = gp.VoiceDirection.Down
        if flags2 & 0x08 != 0:
            display.beamDirection = gp.VoiceDirection.Up
        if flags3 & 0x02 != 0:
            display.tupletBracket = gp.TupletBracket.Start
        if flags3 & 0x04 != 0:
            display.tupletBracket = gp.TupletBracket.End
        if flags3 & 0x08 != 0:
            display.breakSecondary = self.readByte()

        beat.display = display

        return duration.time() if not voice.isEmpty else 0
    
    def readNote(self, guitarString, track, effect):
        flags = self.readByte()
        note = gp.Note()
        note.string = guitarString.number
        note.effect.accentuatedNote = (flags & 0x40) != 0
        note.effect.heavyAccentuatedNote = (flags & 0x02) != 0
        note.effect.ghostNote = (flags & 0x04) != 0
        if flags & 0x20 != 0:
            noteType = self.readByte()
            note.isTiedNote = noteType == 0x02
            note.effect.deadNote = noteType == 0x03
        
        if flags & 0x10 != 0:
            dyn = self.readSignedByte()
            note.velocity = self.unpackVelocity(dyn)
        
        if flags & 0x20 != 0:
            fret = self.readSignedByte()
            value = self.getTiedNoteValue(guitarString.number, track) if note.isTiedNote else fret
            note.value = value if 0 <= value < 100 else 0
        
        if flags & 0x80 != 0:
            note.effect.leftHandFinger = self.readSignedByte()
            note.effect.rightHandFinger = self.readSignedByte()
            note.effect.isFingering = True

        if flags & 0x01 != 0:
            note.durationPercent = self.readDouble()
        flags2 = self.readByte()
        note.swapAccidentals = (flags2 & 0x02) != 0
        
        if flags & 0x08 != 0:
            self.readNoteEffects(note.effect)
            # as with BeatEffects, some effects like 'slide into' are not supported in GP3, 
            # but effect flag is still 1
            note.effect.presence = True
        
        return note

    def readNoteEffects(self, noteEffect):
        flags1 = self.readByte()
        flags2 = self.readByte()
        if flags1 & 0x01 != 0:
            self.readBend(noteEffect)
        if flags1 & 0x10 != 0:
            self.readGrace(noteEffect)
        if flags2 & 0x04 != 0:
            self.readTremoloPicking(noteEffect)
        if flags2 & 0x08 != 0:
            noteEffect.slide = self.fromSlideType(self.readByte())
        if flags2 & 0x10 != 0:
            self.readArtificialHarmonic(noteEffect)
        if flags2 & 0x20 != 0:
            self.readTrill(noteEffect)
        noteEffect.letRing = (flags1 & 0x08) != 0
        noteEffect.hammer = (flags1 & 0x02) != 0
        noteEffect.vibrato = (flags2 & 0x40) != 0 or noteEffect.vibrato
        noteEffect.palmMute = (flags2 & 0x02) != 0
        noteEffect.staccato = (flags2 & 0x01) != 0    
    
    def fromHarmonicType(self, harmonicType):
        if harmonicType == 1:
            return (0, gp.HarmonicType.Natural)
        elif harmonicType == 2:
            # C = 0, D = 2, E = 4, F = 5...
            # b = -1, # = 1
            # loco = 0, 8va = 1, 15ma = 2
            semitone = self.readByte()
            accidental = self.readSignedByte()
            octave = self.readByte()
            return ((semitone, accidental, octave), gp.HarmonicType.Artificial)
        elif harmonicType == 3:
            fret = self.readByte()
            return (fret, gp.HarmonicType.Tapped)
        elif harmonicType == 4:
            return (0, gp.HarmonicType.Pinch)
        elif harmonicType == 5:
            return (0, gp.HarmonicType.Semi)

    def readGrace(self, noteEffect):
        fret = self.readByte()
        dyn = self.readByte()
        transition = self.readByte()
        duration = self.readByte()
        flags = self.readByte()
        grace = gp.GraceEffect()
        
        grace.fret = fret
        grace.velocity = self.unpackVelocity(dyn)
        grace.duration = duration
        grace.isDead = (flags & 0x01) != 0
        grace.isOnBeat = (flags & 0x02) != 0
        grace.transition = self.toGraceTransition(transition)
        
        noteEffect.grace = grace
    
    def readMixTableChange(self, measure):
        tableChange = gp.MixTableChange()
        tableChange.instrument.value = self.readSignedByte()
        self.skip(16) # RSE info
        tableChange.volume.value = self.readSignedByte()
        tableChange.balance.value = self.readSignedByte()
        tableChange.chorus.value = self.readSignedByte()
        tableChange.reverb.value = self.readSignedByte()
        tableChange.phaser.value = self.readSignedByte()
        tableChange.tremolo.value = self.readSignedByte()
        tableChange.tempoName = self.readIntSizeCheckByteString()
        tableChange.tempo.value = self.readInt()
        
        if tableChange.instrument.value < 0:
            tableChange.instrument = None
        
        if tableChange.volume.value >= 0:
            tableChange.volume.duration = self.readSignedByte()
        else:
            tableChange.volume = None
        if tableChange.balance.value >= 0:
            tableChange.balance.duration = self.readSignedByte()
        else:
            tableChange.balance = None
        if tableChange.chorus.value >= 0:
            tableChange.chorus.duration = self.readSignedByte()
        else:
            tableChange.chorus = None
        if tableChange.reverb.value >= 0:
            tableChange.reverb.duration = self.readSignedByte()
        else:
            tableChange.reverb = None
        if tableChange.phaser.value >= 0:
            tableChange.phaser.duration = self.readSignedByte()
        else:
            tableChange.phaser = None
        if tableChange.tremolo.value >= 0:
            tableChange.tremolo.duration = self.readSignedByte()
        else:
            tableChange.tremolo = None
        if tableChange.tempo.value >= 0:
            tableChange.tempo.duration = self.readSignedByte()
            measure.tempo().value = tableChange.tempo.value
            tableChange.hideTempo = not self.version.endswith('5.00') and self.readBool()
        else:
            tableChange.tempo = None

        allTracksFlags = self.readByte()
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
        if allTracksFlags & 0x80 != 0:
            tableChange.wah.display = True

        # Wah-Wah flag
        #  0: Open
        # 64: Close
        # -2: Off
        # -1: No wah info
        wahValue = self.readSignedByte()
        if wahValue > -1:
            tableChange.wah.value = wahValue
            tableChange.wah.enabled = True
        elif wahValue == -2:
            tableChange.wah.value = 0
            tableChange.wah.enabled = False
        else:
            tableChange.wah = None

        if not self.version.endswith('5.00'):
            self.readIntSizeCheckByteString()
            self.readIntSizeCheckByteString()

        return tableChange
    
    def readChord(self, stringCount, beat):
        chord = gp.Chord(stringCount)
        self.skip(17)
        chord.name = self.readByteSizeString(21)
        self.skip(4)
        chord.firstFret = self.readInt()
        for i in range(7):
            fret = self.readInt()
            if i < len(chord.strings):
                chord.strings[i] = fret
        self.skip(32)
        if chord.noteCount() > 0:
            beat.setChord(chord)
    
    def readTracks(self, song, trackCount, channels):
        for i in range(trackCount):
            song.addTrack(self.readTrack(i + 1, channels))
        # Always 0
        self.skip(2 if self.version.endswith('5.00') else 1)
    
    def readTrack(self, number, channels):
        if number == 1 or self.version.endswith('5.00'):
            # Always 0
            self.skip(1)
        flags1 = self.readByte()
        track = gp.Track()
        track.isPercussionTrack = (flags1 & 0x01) != 0
        track.is12StringedGuitarTrack = (flags1 & 0x02) != 0
        track.isBanjoTrack = (flags1 & 0x04) != 0
        track.isVisible = (flags1 & 0x08) != 0
        track.isSolo = (flags1 & 0x10) != 0
        track.isMute = (flags1 & 0x20) != 0
        track.indicateTuning = (flags1 & 0x80) != 0
        track.number = number
        track.name = self.readByteSizeString(40)
        stringCount = self.readInt()
        for i in range(7):
            iTuning = self.readInt()
            if stringCount > i:
                oString = gp.GuitarString()
                oString.number = i + 1
                oString.value = iTuning
                track.strings.append(oString)
        track.port = self.readInt()
        self.readChannel(track, channels)
        if track.channel.channel == 9:
            track.isPercussionTrack = True
        track.fretCount = self.readInt()
        track.offset = self.readInt()
        track.color = self.readColor()

        flags2 = self.readByte()
        flags3 = self.readByte()
        trackSettings = gp.TrackSettings()
        trackSettings.tablature = (flags2 & 0x01) != 0
        trackSettings.notation = (flags2 & 0x02) != 0
        trackSettings.diagramsAreBelow = (flags2 & 0x04) != 0
        trackSettings.showRhythm = (flags2 & 0x08) != 0
        trackSettings.forceHorizontal = (flags2 & 0x10) != 0
        trackSettings.forceChannels = (flags2 & 0x20) != 0
        trackSettings.diagramList = (flags2 & 0x40) != 0
        trackSettings.diagramsInScore = (flags2 & 0x80) != 0

        # 0x01: ???
        trackSettings.autoLetRing = (flags3 & 0x02) != 0
        trackSettings.autoBrush = (flags3 & 0x04) != 0
        trackSettings.extendRhythmic = (flags3 & 0x08) != 0
        track.settings = trackSettings

        # Always 0
        self.skip(1)

        bank = self.readByte()
        track.channel.bank = bank
        
        self.skip(45 if not self.version.endswith('5.00') else 40)
        if not self.version.endswith('5.00'):
            self.readIntSizeCheckByteString()
            self.readIntSizeCheckByteString()
        return track

    def unpackTripletFeel(self, tripletFeel):
        if tripletFeel == 1:
            return gp.TripletFeel.Eighth
        elif tripletFeel == 2:
            return gp.TripletFeel.Sixteenth
        else:
            return gp.TripletFeel.None_
    
    def readMeasureHeaders(self, song, measureCount, directions):
        super(GP5File, self).readMeasureHeaders(song, measureCount)
        signs, fromSigns = directions
        for sign, number in signs.items():
            if number > -1:
                song.measureHeaders[number - 1].directions = sign
        for sign, number in fromSigns.items():
            if number > -1:
                song.measureHeaders[number - 1].fromDirection = sign

    def readMeasureHeader(self, number, song, previous=None):
        if previous is not None:
            # Always 0
            self.skip(1)

        flags = self.readByte()
        
        header = gp.MeasureHeader()
        header.number = number
        header.start = 0
        header.tempo.value = song.tempo
        
        if flags & 0x01 != 0:
            header.timeSignature.numerator = self.readByte()
        else:
            header.timeSignature.numerator = previous.timeSignature.numerator
        if flags & 0x02 != 0:
            header.timeSignature.denominator.value = self.readByte()
        else:
            header.timeSignature.denominator.value = previous.timeSignature.denominator.value
        
        header.isRepeatOpen = (flags & 0x04) != 0
        
        if flags & 0x08 != 0:
            header.repeatClose = self.readByte() - 1
        
        if flags & 0x20 != 0:
            header.marker = self.readMarker(header)
        
        if flags & 0x10 != 0:
            header.repeatAlternative = self.readByte()
        
        if flags & 0x40 != 0:
            header.keySignature = self.toKeySignature(self.readSignedByte())
            header.keySignatureType = self.readByte()
        elif previous is not None:
            header.keySignature = previous.keySignature
            header.keySignatureType = previous.keySignatureType

        header.hasDoubleBar = (flags & 0x80) != 0

        if flags & 0x03 != 0:
            header.timeSignature.beams = [self.readByte() for i in range(4)]
        else:
            header.timeSignature.beams = previous.timeSignature.beams

        if flags & 0x10 == 0:
            # Always 0
            self.skip(1)
        
        header.tripletFeel = self.unpackTripletFeel(self.readByte())
        
        return header
    
    def readPageSetup(self, song):
        setup = gp.PageSetup()
        if not self.version.endswith('5.00'):
            # Master RSE info
            self.skip(19)
        setup.pageSize = gp.Point(self.readInt(), self.readInt())
        
        l = self.readInt()
        r = self.readInt()
        t = self.readInt()
        b = self.readInt() 
        setup.pageMargin = gp.Padding(l, t, r, b)
        setup.scoreSizeProportion = self.readInt() / 100.0
        
        setup.headerAndFooter = self.readByte()
        
        flags2 = self.readByte()
        if flags2 & 0x01 != 0:
            setup.headerAndFooter |= gp.HeaderFooterElements.PAGE_NUMBER
        
        setup.title = self.readIntSizeCheckByteString()
        setup.subtitle = self.readIntSizeCheckByteString()
        setup.artist = self.readIntSizeCheckByteString()
        setup.album = self.readIntSizeCheckByteString()
        setup.words = self.readIntSizeCheckByteString()
        setup.music = self.readIntSizeCheckByteString()
        setup.wordsAndMusic = self.readIntSizeCheckByteString()
        setup.copyright = self.readIntSizeCheckByteString() + '\n' + self.readIntSizeCheckByteString()
        setup.pageNumber = self.readIntSizeCheckByteString()
        song.pageSetup = setup
    
    def readInfo(self, song):
        song.title = self.readIntSizeCheckByteString()
        song.subtitle = self.readIntSizeCheckByteString()
        song.artist = self.readIntSizeCheckByteString()
        song.album = self.readIntSizeCheckByteString()
        song.words = self.readIntSizeCheckByteString()
        song.music = self.readIntSizeCheckByteString()
        song.copyright = self.readIntSizeCheckByteString()
        song.tab = self.readIntSizeCheckByteString()
        song.instructions = self.readIntSizeCheckByteString()
        
        iNotes = self.readInt()
        song.notice = []
        for i in range(iNotes):
            song.notice.append(self.readIntSizeCheckByteString())

    #################################################################
    #### Writing
    #################################################################

    def writeSong(self, song):
        self.version = self._supportedVersions[1]
        self.writeVersion(1)

        self.writeInfo(song)
        self.writeLyrics(song.lyrics)
        self.writePageSetup(song.pageSetup)

        self.writeIntSizeCheckByteString(song.tempoName)
        self.writeInt(song.tempo)
        
        if not self.version.endswith('5.00'):
            self.writeBool(song.hideTempo)
        
        self.writeByte(song.key)
        self.writeInt(song.octave)
        
        self.writeMidiChannels(song.tracks)
        
        self.writeDirections(song.measureHeaders)

        measureCount = len(song.tracks[0].measures)
        trackCount = len(song.tracks)        
        self.writeInt(measureCount)
        self.writeInt(trackCount)
        
        self.writeMeasureHeaders(song.tracks[0].measures)
        self.writeTracks(song.tracks)
        self.writeMeasures(song.tracks)

    def writeDirections(self, measureHeaders):
        order = ['Coda',
                 'Double Coda',
                 'Segno',
                 'Segno Segno',
                 'Fine',
                 'Da Capo',
                 'Da Capo al Coda',
                 'Da Capo al Double Coda',
                 'Da Capo al Fine',
                 'Da Segno',
                 'Da Segno Segno al Coda',
                 'Da Segno Segno',
                 'Da Segno al Coda',
                 'Da Segno Segno al Double Coda',
                 'Da Segno al Fine',
                 'Da Segno al Double Coda',
                 'Da Segno Segno al Fine',
                 'Da Coda',
                 'Da Double Coda']
        
        signs = {}
        for number, header in enumerate(measureHeaders, start=1):
            if header.direction is not None:
                signs[header.direction.name] = number
            if header.fromDirection is not None:
                signs[header.fromDirection.name] = number


        for name in order:
            self.writeShort(signs.get(name, -1))

        self.placeholder(4)

    def writeInfo(self, song):
        self.writeIntSizeCheckByteString(song.title)
        self.writeIntSizeCheckByteString(song.subtitle)
        self.writeIntSizeCheckByteString(song.artist)
        self.writeIntSizeCheckByteString(song.album)
        self.writeIntSizeCheckByteString(song.words)
        self.writeIntSizeCheckByteString(song.music)
        self.writeIntSizeCheckByteString(song.copyright)
        self.writeIntSizeCheckByteString(song.tab)
        self.writeIntSizeCheckByteString(song.instructions)
        
        self.writeInt(len(song.notice))
        for line in song.notice:
            self.writeIntSizeCheckByteString(line)

    def writePageSetup(self, setup):
        if not self.version.endswith('5.00'):
            self.placeholder(19)
        self.writeInt(setup.pageSize.x)
        self.writeInt(setup.pageSize.y)
        
        self.writeInt(setup.pageMargin.left)
        self.writeInt(setup.pageMargin.right)
        self.writeInt(setup.pageMargin.top)
        self.writeInt(setup.pageMargin.bottom)
        self.writeInt(setup.scoreSizeProportion * 100)
        
        self.writeByte(setup.headerAndFooter & 0xff)
        
        flags2 = 0x00
        if setup.headerAndFooter & gp.HeaderFooterElements.PAGE_NUMBER != 0:
            flags2 |= 0x01
        self.writeByte(flags2)
        
        self.writeIntSizeCheckByteString(setup.title)
        self.writeIntSizeCheckByteString(setup.subtitle)
        self.writeIntSizeCheckByteString(setup.artist)
        self.writeIntSizeCheckByteString(setup.album)
        self.writeIntSizeCheckByteString(setup.words)
        self.writeIntSizeCheckByteString(setup.music)
        self.writeIntSizeCheckByteString(setup.wordsAndMusic)
        copyrighta, copyrightb = setup.copyright.split('\n', 1)
        self.writeIntSizeCheckByteString(copyrighta)
        self.writeIntSizeCheckByteString(copyrightb)
        self.writeIntSizeCheckByteString(setup.pageNumber)

    def packTripletFeel(self, tripletFeel):
        if tripletFeel == gp.TripletFeel.None_:
            return 0
        elif tripletFeel == gp.TripletFeel.Eighth:
            return 1
        elif tripletFeel == gp.TripletFeel.Sixteenth:
            return 2

    def writeMeasureHeader(self, header, previous=None):
        flags = 0x00
        if previous is not None:
            if header.timeSignature.numerator != previous.timeSignature.numerator:
                flags |= 0x01
            if header.timeSignature.denominator.value != previous.timeSignature.denominator.value:
                flags |= 0x02
        else:
            flags |= 0x01
            flags |= 0x02
        if header.isRepeatOpen:
            flags |= 0x04
        if header.repeatClose > -1:
            flags |= 0x08
        if header.repeatAlternative != 0:
            flags |= 0x10
        if header.marker is not None:
            flags |= 0x20
        if previous is not None:
            if header.keySignature != previous.keySignature:
                flags |= 0x40
        else:
            flags |= 0x40
        if header.hasDoubleBar:
            flags |= 0x80

        if previous is not None:
            self.placeholder(1)

        self.writeByte(flags)
                
        if flags & 0x01 != 0:
            self.writeByte(header.timeSignature.numerator)
        if flags & 0x02 != 0:
            self.writeByte(header.timeSignature.denominator.value)
        
        if flags & 0x08 != 0:
            self.writeByte(header.repeatClose + 1)

        if flags & 0x20 != 0:
            self.writeMarker(header.marker)
        
        if flags & 0x10 != 0:
            self.writeByte(header.repeatAlternative)
        
        if flags & 0x40 != 0:
            self.writeSignedByte(self.fromKeySignature(header.keySignature))
            self.writeByte(header.keySignatureType)

        if flags & 0x01 != 0:
            for beam in header.timeSignature.beams:
                self.writeByte(beam)

        if flags & 0x10 == 0:
            self.placeholder(1)
        
        self.writeByte(self.packTripletFeel(header.tripletFeel))

    def writeTracks(self, tracks):
        super(GP5File, self).writeTracks(tracks)
        self.placeholder(2 if self.version.endswith('5.00') else 1)
        
    def writeTrack(self, track):
        if track.number == 1 or self.version.endswith('5.00'):
            self.placeholder(1)

        flags1 = 0x00
        if track.isPercussionTrack:
            flags1 |= 0x01
        if track.is12StringedGuitarTrack:
            flags1 |= 0x02
        if track.isBanjoTrack:
            flags1 |= 0x04
        if track.isVisible:
            flags1 |= 0x08
        if track.isSolo:
            flags1 |= 0x10
        if track.isMute:
            flags1 |= 0x20
        if track.indicateTuning:
            flags1 |= 0x80

        self.writeByte(flags1)

        self.writeByteSizeString(track.name, 40)
        self.writeInt(track.stringCount())
        for i in range(7):
            if i < track.stringCount():
                tuning = track.strings[i].value
            else:
                tuning = 0
            self.writeInt(tuning)
        self.writeInt(track.port)
        self.writeChannel(track)
        self.writeInt(track.fretCount)
        self.writeInt(track.offset)
        self.writeColor(track.color)

        flags2 = 0x00
        if track.settings.tablature:
            flags2 |= 0x01
        if track.settings.notation:
            flags2 |= 0x02
        if track.settings.diagramsAreBelow:
            flags2 |= 0x04
        if track.settings.showRhythm:
            flags2 |= 0x08
        if track.settings.forceHorizontal:
            flags2 |= 0x10
        if track.settings.forceChannels:
            flags2 |= 0x20
        if track.settings.diagramList:
            flags2 |= 0x40
        if track.settings.diagramsInScore:
            flags2 |= 0x80

        self.writeByte(flags2)

        flags3 = 0x00
        if track.settings.autoLetRing:
            flags3 |= 0x02
        if track.settings.autoBrush:
            flags3 |= 0x04
        if track.settings.extendRhythmic:
            flags3 |= 0x08

        self.writeByte(flags3)
        self.placeholder(1)
        self.writeByte(track.channel.bank)

        if self.version.endswith('5.00'):
            self.data.write('\x00\x00\x00\x00\x00\x00\x00\x00'
                            '\x00\x64\x00\x00\x00\x01\x02\x03'
                            '\x04\x05\x06\x07\x08\x09\x0a\xff'
                            '\x03\xff\xff\xff\xff\xff\xff\xff'
                            '\xff\xff\xff\xff\xff\xff\xff\xff')
        else:
            self.data.write('\x00\x00\x00\x00\x00\x00\x00\x00'
                            '\x00\x64\x00\x00\x00\x01\x02\x03'
                            '\x04\x05\x06\x07\x08\x09\x0a\xff'
                            '\x03\xff\xff\xff\xff\xff\xff\xff'
                            '\xff\xff\xff\xff\xff\xff\xff\xff'
                            '\xff\xff\xff\xff\xff')

        if not self.version.endswith('5.00'):
            self.writeIntSizeCheckByteString('')
            self.writeIntSizeCheckByteString('')

    def writeMeasure(self, measure):
        sortedBeats = sorted(measure.beats, key=lambda y: y.start)
        for voice in range(gp.Beat.MAX_VOICES):
            beatsOfVoice = filter(lambda x: not x.voices[voice].isEmpty, sortedBeats)
            beatCount = len(beatsOfVoice)
            self.writeInt(beatCount)
            for beat in beatsOfVoice:
                self.writeBeat(beat, voice)
        self.writeByte(measure.lineBreak)

    def writeBeat(self, beat, voiceIndex=0):
        voice = beat.voices[voiceIndex]

        flags1 = 0x00
        if voice.duration.isDotted:
            flags1 |= 0x01
        if beat.effect.isChord():
            flags1 |= 0x02
        if beat.text is not None:
            flags1 |= 0x04
        if not beat.effect.isDefault():
            flags1 |= 0x08
        if beat.effect.mixTableChange is not None:
            flags1 |= 0x10
        if voice.duration.tuplet != gp.Tuplet():
            flags1 |= 0x20
        if voice.isEmpty or voice.isRestVoice():
            flags1 |= 0x40

        self.writeByte(flags1)
                
        if flags1 & 0x40 != 0:
            beatType = 0x00 if voice.isEmpty else 0x02
            self.writeByte(beatType)
        
        self.writeDuration(voice.duration, flags1)

        if flags1 & 0x02 != 0:
            self.writeChord(beat.effect.chord)

        if flags1 & 0x04 != 0:
            self.writeText(beat.text)

        if flags1 & 0x08 != 0:
            self.writeBeatEffects(beat.effect)

        if flags1 & 0x10 != 0:
            self.writeMixTableChange(beat.effect.mixTableChange)

        stringFlags = 0x00
        for note in voice.notes:
            stringFlags |= 1 << (7 - note.string)
        self.writeByte(stringFlags)

        previous = None
        for note in voice.notes:
            self.writeNote(note, previous)
            previous = note

        flags2 = 0x00
        if beat.display.breakBeam:
            flags2 |= 0x01
        if beat.display.beamDirection == gp.VoiceDirection.Down:
            flags2 |= 0x02
        if beat.display.forceBeam:
            flags2 |= 0x04
        if beat.display.beamDirection == gp.VoiceDirection.Up:
            flags2 |= 0x08
        if beat.octave == gp.Octave.Ottava:
            flags2 |= 0x10
        if beat.octave == gp.Octave.OttavaBassa:
            flags2 |= 0x20
        if beat.octave == gp.Octave.Quindicesima:
            flags2 |= 0x40

        self.writeByte(flags2)
        
        flags3 = 0x00
        if beat.octave == gp.Octave.QuindicesimaBassa:
            flags3 |= 0x01
        if beat.display.tupletBracket == gp.TupletBracket.Start:
            flags3 |= 0x02
        if beat.display.tupletBracket == gp.TupletBracket.End:
            flags3 |= 0x04
        if beat.display.breakSecondary:
            flags3 |= 0x08
        if beat.display.breakSecondaryTuplet:
            flags3 |= 0x10
        if beat.display.forceBracket:
            flags3 |= 0x20

        self.writeByte(flags3)

        if flags3 & 0x08 != 0:
            self.writeByte(beat.display.breakSecondary)

    def writeNote(self, note, previous):
        flags = 0x00
        if abs(note.durationPercent - 1.0) >= 1e-2:
            flags |= 0x01
        if note.effect.heavyAccentuatedNote:
            flags |= 0x02
        if note.effect.ghostNote:
            flags |= 0x04
        if not note.effect.isDefault() or note.effect.presence:
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
        
        if flags & 0x10 != 0:
            value = self.packVelocity(note.velocity)
            self.writeSignedByte(value)
        
        if flags & 0x20 != 0:
            fret = note.value if not note.isTiedNote else 0
            self.writeSignedByte(fret)
        
        if flags & 0x80 != 0:
            self.writeSignedByte(note.effect.leftHandFinger)
            self.writeSignedByte(note.effect.rightHandFinger)

        if flags & 0x01 != 0:
            self.writeDouble(note.durationPercent)
        
        flags2 = 0x00        
        if note.swapAccidentals:
            flags2 |= 0x02

        self.writeByte(flags2)
        
        if flags & 0x08 != 0:
            self.writeNoteEffects(note.effect)


    def writeNoteEffects(self, noteEffect):
        flags1 = 0x00
        if noteEffect.isBend():
            flags1 |= 0x01
        if noteEffect.hammer:
            flags1 |= 0x02
        if noteEffect.letRing:
            flags1 |= 0x08
        if noteEffect.isGrace():
            flags1 |= 0x10

        self.writeByte(flags1)

        flags2 = 0x00
        if noteEffect.staccato:
            flags2 |= 0x01
        if noteEffect.palmMute:
            flags2 |= 0x02
        if noteEffect.isTremoloPicking():
            flags2 |= 0x04
        if noteEffect.slide:
            flags2 |= 0x08
        if noteEffect.isHarmonic():
            flags2 |= 0x10
        if noteEffect.isTrill():
            flags2 |= 0x20
        if noteEffect.vibrato:
            flags2 |= 0x40

        self.writeByte(flags2)

        if flags1 & 0x01 != 0:
            self.writeBend(noteEffect.bend)
        if flags1 & 0x10 != 0:
            self.writeGrace(noteEffect.grace)
        if flags2 & 0x04 != 0:
            self.writeTremoloPicking(noteEffect.tremoloPicking)
        if flags2 & 0x08 != 0:
            self.writeByte(self.toSlideType(noteEffect.slide))            
        if flags2 & 0x10 != 0:
            self.writeArtificialHarmonic(noteEffect.harmonic)
        if flags2 & 0x20 != 0:
            self.writeTrill(noteEffect.trill)

    def toHarmonicType(self, harmonic):
        if harmonic.type == gp.HarmonicType.Natural:
            return 1
        elif harmonic.type == gp.HarmonicType.Artificial:
            return 2
        elif harmonic.type == gp.HarmonicType.Tapped:
            return 3
        elif harmonic.type == gp.HarmonicType.Pinch:
            return 4
        elif harmonic.type == gp.HarmonicType.Semi:
            return 5

    def writeArtificialHarmonic(self, harmonic):
        self.writeSignedByte(self.toHarmonicType(harmonic))
        if harmonic.type == gp.HarmonicType.Artificial:
            semitone, accidental, octave = harmonic.data
            self.writeByte(semitone)
            self.writeSignedByte(accidental)
            self.writeByte(octave)
        elif harmonic.type == gp.HarmonicType.Tapped:
            self.writeByte(harmonic.data)

    def writeGrace(self, grace):
        self.writeByte(grace.fret)
        self.writeByte(self.packVelocity(grace.velocity))
        self.writeByte(grace.transition)
        self.writeByte(grace.duration)

        flags = 0x00
        if grace.isDead:
            flags |= 0x01
        if grace.isOnBeat:
            flags |= 0x02

        self.writeByte(flags)

    def writeMixTableChange(self, tableChange):      
        items = [('instrument', tableChange.instrument, self.writeSignedByte),
                 ('rse', (16, '\xff'), self.placeholder), # RSE info
                 ('volume', tableChange.volume, self.writeSignedByte),
                 ('balance', tableChange.balance, self.writeSignedByte),
                 ('chorus', tableChange.chorus, self.writeSignedByte),
                 ('reverb', tableChange.reverb, self.writeSignedByte),
                 ('phaser', tableChange.phaser, self.writeSignedByte),
                 ('tremolo', tableChange.tremolo, self.writeSignedByte),
                 ('tempoName', tableChange.tempoName, self.writeIntSizeCheckByteString),
                 ('tempo', tableChange.tempo, self.writeInt)]

        for _, item, write in items:
            if item is None:
                write(-1)
            elif isinstance(item, tuple):
                write(*item)
            elif isinstance(item, gp.MixTableItem):
                write(item.value)
            else:
                write(item)

        # instrument change doesn't have duration
        for name, item, _ in items[2:]:
            if isinstance(item, gp.MixTableItem):
                self.writeSignedByte(item.duration)
                if name == 'tempo':
                    if not self.version.endswith('5.00'):
                        self.writeBool(tableChange.hideTempo)

        allTracksFlags = 0x00
        for i, item in enumerate(items):
            if isinstance(item, gp.MixTableItem) and item.allTracks:
                allTracksFlags |= 1 << i

        if tableChange.wah is not None and tableChange.wah.display:
            allTracksFlags |= 0x80

        self.writeByte(allTracksFlags)

        if tableChange.wah is not None:
            if tableChange.wah.enabled:
                self.writeSignedByte(tableChange.wah.value)
            else:
                self.writeSignedByte(-2)
        else:
            self.writeSignedByte(-1)

        if not self.version.endswith('5.00'):
            self.writeIntSizeCheckByteString('')
            self.writeIntSizeCheckByteString('')

    def writeChord(self, chord):
        self.data.write('01010000000c0000ffffffff0000000000'.decode('hex'))
        self.writeByteSizeString(chord.name, 21)
        self.placeholder(4)
        self.writeInt(chord.firstFret)
        for i in range(7):
            fret = -1
            if i < len(chord.strings):
                fret = chord.strings[i]
            self.writeInt(fret)
        self.placeholder(32)

    def writeMidiChannels(self, tracks):
        def getTrackChannelByChannel(channel):
            for track in tracks:
                if channel in (track.channel.channel, track.channel.effectChannel):
                    return track.channel
            default = gp.MidiChannel()
            default.channel = channel
            default.effectChannel = channel
            default.instrument = 0
            default.volume = 0
            default.balance = 0
            default.chorus = 0
            default.reverb = 0
            default.phaser = 0
            default.tremolo = 0
            return default

        for channel in map(getTrackChannelByChannel, range(64)):
            self.writeInt(channel.instrument)
            
            self.writeSignedByte(self.fromChannelShort(channel.volume))
            self.writeSignedByte(self.fromChannelShort(channel.balance))
            self.writeSignedByte(self.fromChannelShort(channel.chorus))
            self.writeSignedByte(self.fromChannelShort(channel.reverb))
            self.writeSignedByte(self.fromChannelShort(channel.phaser))
            self.writeSignedByte(self.fromChannelShort(channel.tremolo))
            # Backward compatibility with version 3.0
            self.placeholder(2)
