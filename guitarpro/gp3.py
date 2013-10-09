# This file is part of alphaTab.
#
#  alphaTab is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  alphaTab is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with alphaTab.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division

import math
import copy

import base as gp

class GP3File(gp.GPFileBase):
    '''A reader for GuitarPro 3 files. 
    '''
    _supportedVersions = ['FICHIER GUITAR PRO v3.00']
    _tripletFeel = gp.TripletFeel.None_

    def __init__(self, *args, **kwargs):
        super(GP3File, self).__init__(*args, **kwargs)
    
    #################################################################
    ### Reading
    #################################################################

    def readSong(self):
        '''Reads the song

        :returns: The song read from the given stream using the specified factory
        '''
        if not self.readVersion():
            raise gp.GuitarProException("unsupported version '%s'" % self.version)
        
        song = gp.Song()

        self.readInfo(song)
        
        self._tripletFeel = (gp.TripletFeel.Eighth if self.readBool()
                             else gp.TripletFeel.None_)
        
        self.readLyrics(song)
        
        self.readPageSetup(song)
        
        song.tempoName = ""
        song.tempo = self.readInt()
        song.hideTempo = False
       
        song.key = self.readInt()
        song.octave = 0
        
        channels = self.readMidiChannels()
        
        measureCount = self.readInt()
        trackCount = self.readInt()
        
        self.readMeasureHeaders(song, measureCount)
        self.readTracks(song, trackCount, channels)
        self.readMeasures(song)

        return song
    
    def readMeasures(self, song):
        tempo = gp.Tempo()
        tempo.value = song.tempo
        start = gp.Duration.QUARTER_TIME
        for header in song.measureHeaders:
            header.start = start
            for track in song.tracks:
                measure = gp.Measure(header)
                # header.tempo.copy(tempo)
                tempo = header.tempo
                track.addMeasure(measure)
                self.readMeasure(measure, track)
            
            # tempo.copy(header.tempo)
            header.tempo = tempo
            start += header.length()
    
    def readMeasure(self, measure, track):
        start = measure.start()
        beats = self.readInt()
        for beat in range(beats):
            start += self.readBeat(start, measure, track, 0)
    
    def readBeat(self, start, measure, track, voiceIndex):
        flags = self.readByte()
        
        beat = self.getBeat(measure, start)
        voice = beat.voices[voiceIndex]

        if flags & 0x40 != 0:
            beatType = self.readByte()
            voice.isEmpty = (beatType & 0x02) == 0
        
        duration = self.readDuration(flags)
        effect = gp.NoteEffect()
        if flags & 0x02 != 0:
            self.readChord(track.stringCount(), beat)
        
        if flags & 0x04 != 0:
            self.readText(beat)
        
        if flags & 0x08 != 0:
            self.readBeatEffects(beat, effect)
            # some BeatEffects are not supported in GP3
            # nonetheless effect flag is 1
            beat.effect.presence = True
        
        if flags & 0x10 != 0:
            mixTableChange = self.readMixTableChange(measure)
            beat.effect.mixTableChange = mixTableChange
        
        stringFlags = self.readByte()
        for j in range(7):
            i = 6 - j
            if stringFlags & (1 << i) != 0 and (6 - i) < track.stringCount():
                # guitarString = track.strings[6 - i].clone(factory)
                guitarString = copy.copy(track.strings[6 - i])
                # note = self.readNote(guitarString, track, effect.clone(factory))
                note = self.readNote(guitarString, track, copy.deepcopy(effect))
                voice.addNote(note)
            
            # duration.copy(voice.duration)
            voice.duration = copy.copy(duration)
        
        return duration.time() if not voice.isEmpty else 0
        
    def readNote(self, guitarString, track, effect):
        flags = self.readByte()
        note = gp.Note()
        note.string = guitarString.number
        note.effect = effect
        note.effect.accentuatedNote = (flags & 0x40) != 0
        note.effect.heavyAccentuatedNote = (flags & 0x02) != 0
        note.effect.ghostNote = (flags & 0x04) != 0
        if flags & 0x20 != 0:
            noteType = self.readByte()
            note.isTiedNote = noteType == 0x02
            note.effect.deadNote = noteType == 0x03
        
        if flags & 0x01 != 0:
            note.duration = self.readSignedByte()
            note.tuplet = self.readSignedByte()
        
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
        
        if flags & 0x08 != 0:
            self.readNoteEffects(note.effect)
            if note.effect.isHarmonic() and note.effect.harmonic.type == gp.HarmonicType.Tapped:
                note.effect.harmonic.data = note.value + 12
            # as with BeatEffects, some effects like 'slide into' are not supported in GP3, 
            # but effect flag is still 1
            note.effect.presence = True
        
        return note
    
    def unpackVelocity(self, dyn):
        return (gp.Velocities.MIN_VELOCITY + 
                gp.Velocities.VELOCITY_INCREMENT * dyn -
                gp.Velocities.VELOCITY_INCREMENT)
    
    def readNoteEffects(self, noteEffect):
        flags1 = self.readByte()
        noteEffect.slide = (flags1 & 0x04) != 0
        noteEffect.hammer = (flags1 & 0x02) != 0
        noteEffect.letRing = (flags1 & 0x08) != 0

        if flags1 & 0x01 != 0:
            self.readBend(noteEffect)
        
        if flags1 & 0x10 != 0:
            self.readGrace(noteEffect)
    
    def readGrace(self, noteEffect):
        fret = self.readByte()
        dyn = self.readByte()
        transition = self.readSignedByte()
        duration = self.readByte()
        grace = gp.GraceEffect()
        
        grace.fret = fret
        grace.velocity = self.unpackVelocity(dyn)
        grace.duration = duration
        grace.isDead = fret == 255
        grace.isOnBeat = False
        grace.transition = self.toGraceTransition(transition)
        
        noteEffect.grace = grace

    def toGraceTransition(self, transition):
        if transition == 0:
            return gp.GraceEffectTransition.None_
        elif transition == 1:
            return gp.GraceEffectTransition.Slide
        elif transition == 2:
            return gp.GraceEffectTransition.Bend
        elif transition == 3:
            return gp.GraceEffectTransition.Hammer
        else:
            return gp.GraceEffectTransition.None_
    
    def readBend(self, noteEffect):
        bendEffect = gp.BendEffect()
        bendEffect.type = self.readSignedByte()
        bendEffect.value = self.readInt()
        pointCount = self.readInt()
        for i in range(pointCount):
            pointPosition = round(self.readInt() * gp.BendEffect.MAX_POSITION / gp.GPFileBase.BEND_POSITION)
            pointValue = round(self.readInt() * gp.BendEffect.SEMITONE_LENGTH / gp.GPFileBase.BEND_SEMITONE)
            vibrato = self.readBool()
            bendEffect.points.append(gp.BendPoint(pointPosition, pointValue, vibrato))

        if pointCount > 0:
            noteEffect.bend = bendEffect
    
    def readMixTableChange(self, measure):
        tableChange = gp.MixTableChange()
        tableChange.instrument.value = self.readSignedByte()
        tableChange.volume.value = self.readSignedByte()
        tableChange.balance.value = self.readSignedByte()
        tableChange.chorus.value = self.readSignedByte()
        tableChange.reverb.value = self.readSignedByte()
        tableChange.phaser.value = self.readSignedByte()
        tableChange.tremolo.value = self.readSignedByte()
        tableChange.tempoName = ""
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
            tableChange.hideTempo = False
        else:
            tableChange.tempo = None

        return tableChange
    
    def readBeatEffects(self, beat, effect):
        flags1 = self.readByte()
        beat.effect.fadeIn = (flags1 & 0x10) != 0
        effect.vibrato = (flags1 & 0x01) != 0 or effect.vibrato
        beat.effect.vibrato = (flags1 & 0x02) != 0 or beat.effect.vibrato
        if flags1 & 0x20 != 0:
            slapEffect = self.readByte()
            if slapEffect == 0:
                self.readTremoloBar(beat.effect)
            else:
                beat.effect.tapping = slapEffect == 1
                beat.effect.slapping = slapEffect == 2
                beat.effect.popping = slapEffect == 3
                self.readInt()
        if flags1 & 0x40 != 0:
            strokeUp = self.readSignedByte()
            strokeDown = self.readSignedByte()
            if strokeUp > 0:
                beat.effect.stroke.direction = gp.BeatStrokeDirection.Up
                beat.effect.stroke.value = self.toStrokeValue(strokeUp)
            elif strokeDown > 0:
                beat.effect.stroke.direction = gp.BeatStrokeDirection.Down
                beat.effect.stroke.value = self.toStrokeValue(strokeDown)
        if flags1 & 0x04 != 0:
            harmonic = gp.HarmonicEffect()
            harmonic.type = gp.HarmonicType.Natural
            harmonic.data = 0
            effect.harmonic = harmonic
        
        if flags1 & 0x08 != 0:
            harmonic = gp.HarmonicEffect()
            harmonic.type = gp.HarmonicType.Artificial
            harmonic.data = 0
            effect.harmonic = harmonic
    
    def readTremoloBar(self, effect):
        barEffect = gp.BendEffect()
        barEffect.type = gp.BendTypes.Dip
        barEffect.value = self.readInt()
        
        barEffect.points.append(gp.BendPoint(0, 0))
        barEffect.points.append(gp.BendPoint(round(gp.BendEffect.MAX_POSITION / 2), 
                                             round(barEffect.value / (self.BEND_SEMITONE * 2))))
        barEffect.points.append(gp.BendPoint(gp.BendEffect.MAX_POSITION, 0))
        
        effect.tremoloBar = barEffect
    
    def readText(self, beat):
        text = gp.BeatText()
        text.value = self.readIntSizeCheckByteString()
        beat.setText(text)
    
    def readChord(self, stringCount, beat):
        # chord = factory.newChord(stringCount)
        chord = gp.Chord(stringCount)
        if (self.readByte() & 0x01) == 0:
            chord.name = self.readIntSizeCheckByteString()
            chord.firstFret = self.readInt()
            if chord.firstFret != 0:
                for i in range(6):
                    fret = self.readInt()
                    if i < len(chord.strings):
                        chord.strings[i] = fret
        else:
            self.skip(25)
            chord.name = self.readByteSizeString(34)
            chord.firstFret = self.readInt()
            for i in range(6):
                fret = self.readInt()
                if i < len(chord.strings):
                    chord.strings[i] = fret
            self.skip(36)
        if chord.noteCount() > 0:
            beat.setChord(chord)
    
    def readDuration(self, flags):
        duration = gp.Duration()
        duration.value = round(2 ** (self.readSignedByte() + 2))
        duration.isDotted = (flags & 0x01) != 0
        if (flags & 0x20) != 0:
            iTuplet = self.readInt()
            if iTuplet == 3:
                duration.tuplet.enters = 3
                duration.tuplet.times = 2
            elif iTuplet == 5:
                duration.tuplet.enters = 5
                duration.tuplet.times = 4
            elif iTuplet == 6:
                duration.tuplet.enters = 6
                duration.tuplet.times = 4
            elif iTuplet == 7:
                duration.tuplet.enters = 7
                duration.tuplet.times = 4
            elif iTuplet == 9:
                duration.tuplet.enters = 9
                duration.tuplet.times = 8
            elif iTuplet == 10:
                duration.tuplet.enters = 10
                duration.tuplet.times = 8
            elif iTuplet == 11:
                duration.tuplet.enters = 11
                duration.tuplet.times = 8
            elif iTuplet == 12:
                duration.tuplet.enters = 12
                duration.tuplet.times = 8
        return duration
    
    def getBeat(self, measure, start):
        for beat in measure.beats:
            if beat.start == start:
                return beat
        newBeat = gp.Beat()
        newBeat.start = start
        measure.addBeat(newBeat)
        return newBeat
    
    def readTracks(self, song, trackCount, channels):
        for i in range(trackCount):
            song.addTrack(self.readTrack(i + 1, channels))
        
    def readTrack(self, number, channels):
        flags = self.readByte()
        track = gp.Track()
        track.isPercussionTrack = (flags & 0x1) != 0
        track.is12StringedGuitarTrack = (flags & 0x02) != 0
        track.isBanjoTrack = (flags & 0x04) != 0
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
        
        return track
    
    def readChannel(self, track, channels):
        index = self.readInt() - 1
        effectChannel = self.readInt() - 1
        if 0 <= index < len(channels):
            # channels[index].copy(track.channel)
            track.channel = copy.copy(channels[index])
            if track.channel.instrument < 0:
                track.channel.instrument = 0
            if not track.channel.isPercussionChannel():
                track.channel.effectChannel = effectChannel
    
    def readMeasureHeaders(self, song, measureCount):
        previous = None
        for i in range(measureCount):
            header = self.readMeasureHeader(i, song, previous)
            song.addMeasureHeader(header)
            previous = header
    
    def readMeasureHeader(self, i, song, previous=None):
        flags = self.readByte()
        
        header = gp.MeasureHeader()
        header.number = i + 1
        header.start = 0
        header.tempo.value = song.tempo
        header.tripletFeel = self._tripletFeel
        
        if (flags & 0x01) != 0:
            header.timeSignature.numerator = self.readSignedByte()
        else:
            header.timeSignature.numerator = previous.timeSignature.numerator
        if (flags & 0x02) != 0:
            header.timeSignature.denominator.value = self.readSignedByte()
        else:
            header.timeSignature.denominator.value = previous.timeSignature.denominator.value
        
        header.isRepeatOpen = ((flags & 0x04) != 0)
        
        if (flags & 0x08) != 0:
            header.repeatClose = (self.readSignedByte() - 1)
        
        if (flags & 0x10) != 0:
            header.repeatAlternative = self.unpackRepeatAlternative(song, header.number, self.readByte())
        
        if (flags & 0x20) != 0:
            header.marker = self.readMarker(header)
        
        if (flags & 0x40) != 0:
            header.keySignature = self.toKeySignature(self.readSignedByte())
            header.keySignatureType = self.readSignedByte()
            header.keySignaturePresence = True
        
        elif header.number > 1:
            header.keySignature = previous.keySignature
            header.keySignatureType = previous.keySignatureType

        header.hasDoubleBar = (flags & 0x80) != 0
       
        return header
    
    def unpackRepeatAlternative(self, song, measure, value):
        repeatAlternative = 0
        existentAlternatives = 0
        for header in song.measureHeaders:
            if header.number == measure:
                break
            if header.isRepeatOpen:
                existentAlternatives = 0
            existentAlternatives |= header.repeatAlternative
        for i in range(8):
            if value > i and (existentAlternatives & (1 << i)) == 0:
                repeatAlternative |= (1 << i)
        return repeatAlternative
    
    def readMarker(self, header):
        marker = gp.Marker()
        marker.measureHeader = header
        marker.title = self.readIntSizeCheckByteString()
        marker.color = self.readColor()
        return marker
    
    def readColor(self):
        r = self.readByte()
        g = self.readByte()
        b = self.readByte()
        self.skip(1)
        return gp.Color.fromRgb(r, g, b)
    
    def readMidiChannels(self):
        channels = []
        for i in range(64):
            newChannel = gp.MidiChannel()
            newChannel.channel = i
            newChannel.effectChannel = i
            instrument = self.readInt()
            if newChannel.isPercussionChannel() and instrument == -1:
                instrument = 0
            newChannel.instrument = instrument

            newChannel.volume = self.toChannelShort(self.readSignedByte())
            newChannel.balance = self.toChannelShort(self.readSignedByte())
            newChannel.chorus = self.toChannelShort(self.readSignedByte())
            newChannel.reverb = self.toChannelShort(self.readSignedByte())
            newChannel.phaser = self.toChannelShort(self.readSignedByte())
            newChannel.tremolo = self.toChannelShort(self.readSignedByte())
            channels.append(newChannel)
            # Backward compatibility with version 3.0
            self.skip(2)
        
        return channels
    
    def readPageSetup(self, song):
        song.pageSetup = gp.PageSetup()
    
    def readLyrics(self, song):
        song.lyrics = gp.Lyrics()
        for i in range(gp.Lyrics.MAX_LINE_COUNT):
            line = gp.LyricLine()            
            line.startingMeasure = 1
            line.lyrics = ''
            song.lyrics.lines.append(line)
    
    def readInfo(self, song):
        song.title = self.readIntSizeCheckByteString()
        song.subtitle = self.readIntSizeCheckByteString()
        song.artist = self.readIntSizeCheckByteString()
        song.album = self.readIntSizeCheckByteString()
        song.words = self.readIntSizeCheckByteString()
        song.music = song.words
        song.copyright = self.readIntSizeCheckByteString()
        song.tab = self.readIntSizeCheckByteString()
        song.instructions = self.readIntSizeCheckByteString()
        
        iNotes = self.readInt()
        song.notice = []
        for i in range(iNotes):
            song.notice.append(self.readIntSizeCheckByteString())
    
    def toKeySignature(self, p):
        return 7 + abs(p) if p < 0 else p
    
    def toStrokeValue(self, value):
        if value == 1:
            return gp.Duration.SIXTY_FOURTH
        elif value == 2:
            return gp.Duration.SIXTY_FOURTH
        elif value == 3:
            return gp.Duration.THIRTY_SECOND
        elif value == 4:
            return gp.Duration.SIXTEENTH
        elif value == 5:
            return gp.Duration.EIGHTH
        elif value == 6:
            return gp.Duration.QUARTER
        else:
            return gp.Duration.SIXTY_FOURTH

    #################################################################
    ### Writing
    #################################################################

    def writeSong(self, song):
        '''Writes the song
        '''
        self.writeVersion(0)
        self.writeInfo(song)

        self._tripletFeel = song.tracks[0].measures[0].tripletFeel()
        self.writeBool(self._tripletFeel)
        
        self.writeLyrics(None)
        self.writePageSetup(None)
        
        self.writeInt(song.tempo)
        self.writeInt(song.key)
        self.writeMidiChannels(song.tracks)
        
        measureCount = len(song.tracks[0].measures)
        trackCount = len(song.tracks)
        self.writeInt(measureCount)
        self.writeInt(trackCount)
        
        self.writeMeasureHeaders(song.tracks[0].measures)
        self.writeTracks(song.tracks)
        self.writeMeasures(song.tracks)

        self.writeInt(0)

    def writeInfo(self, song):
        self.writeIntSizeCheckByteString(song.title)
        self.writeIntSizeCheckByteString(song.subtitle)
        self.writeIntSizeCheckByteString(song.artist)
        self.writeIntSizeCheckByteString(song.album)
        self.writeIntSizeCheckByteString(song.words)
        self.writeIntSizeCheckByteString(song.copyright)
        self.writeIntSizeCheckByteString(song.tab)
        self.writeIntSizeCheckByteString(song.instructions)
        
        self.writeInt(len(song.notice))
        for line in song.notice:
            self.writeIntSizeCheckByteString(line)

    def writeLyrics(self, lyrics):
        pass

    def writePageSetup(self, setup):
        pass

    def writeMidiChannels(self, tracks):
        def getTrackChannelByChannel(channel):
            for track in tracks:
                if channel in (track.channel.channel, track.channel.effectChannel):
                    return track.channel
            default = gp.MidiChannel()
            default.channel = channel
            default.effectChannel = channel
            if default.isPercussionChannel():
                default.instrument = 0
            return default

        for channel in map(getTrackChannelByChannel, range(64)):
            if channel.isPercussionChannel() and channel.instrument == 0:
                self.writeInt(-1)
            else:
                self.writeInt(channel.instrument)
            
            self.writeSignedByte(self.fromChannelShort(channel.volume))
            self.writeSignedByte(self.fromChannelShort(channel.balance))
            self.writeSignedByte(self.fromChannelShort(channel.chorus))
            self.writeSignedByte(self.fromChannelShort(channel.reverb))
            self.writeSignedByte(self.fromChannelShort(channel.phaser))
            self.writeSignedByte(self.fromChannelShort(channel.tremolo))
            # Backward compatibility with version 3.0
            self.placeholder(2)

    def writeMeasureHeaders(self, measures):
        previous = None
        for measure in measures:
            self.writeMeasureHeader(measure.header, previous)
            previous = measure.header
    
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
        # elif header.number > 1 or header.keySignature != 0:
        #     flags |= 0x40
        elif header.keySignaturePresence:
            flags |= 0x40
        if header.hasDoubleBar:
            flags |= 0x80

        self.writeByte(flags)
                
        if (flags & 0x01) != 0:
            self.writeSignedByte(header.timeSignature.numerator)
        if (flags & 0x02) != 0:
            self.writeSignedByte(header.timeSignature.denominator.value)
        
        if (flags & 0x08) != 0:
            self.writeSignedByte(header.repeatClose + 1)
        
        if (flags & 0x10) != 0:
            self.writeByte(self.packRepeatAlternative(header.repeatAlternative))
        
        if (flags & 0x20) != 0:
            self.writeMarker(header.marker)
        
        if (flags & 0x40) != 0:
            self.writeSignedByte(self.fromKeySignature(header.keySignature))
            self.writeSignedByte(header.keySignatureType)

    def packRepeatAlternative(self, value):
        return value.bit_length()

    def writeMarker(self, marker):
        self.writeIntSizeCheckByteString(marker.title)
        self.writeColor(marker.color)

    def writeColor(self, color):
        self.writeByte(color.r)
        self.writeByte(color.g)
        self.writeByte(color.b)
        self.placeholder(1)

    def fromKeySignature(self, p):
        return -(p - 7) if p > 7 else p

    def writeTracks(self, tracks):
        for track in tracks:
            self.writeTrack(track)
        
    def writeTrack(self, track):
        flags = 0x00
        if track.isPercussionTrack:
            flags |= 0x01
        if track.is12StringedGuitarTrack:
            flags |= 0x02
        if track.isBanjoTrack:
            flags |= 0x04

        self.writeByte(flags)

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
    
    def writeChannel(self, track):
        self.writeInt(track.channel.channel + 1)
        self.writeInt(track.channel.effectChannel + 1)

    def writeMeasures(self, tracks):
        partwiseMeasures = [track.measures for track in tracks]
        for timewiseMeasures in zip(*partwiseMeasures):
            for measure in timewiseMeasures:
                self.writeMeasure(measure)
    
    def writeMeasure(self, measure):
        self.writeInt(measure.beatCount())
        for beat in measure.beats:
            self.writeBeat(beat)
    
    def writeBeat(self, beat, voiceIndex=0):
        voice = beat.voices[voiceIndex]

        flags = 0x00
        if voice.duration.isDotted:
            flags |= 0x01
        if beat.effect.isChord():
            flags |= 0x02
        if beat.text is not None:
            flags |= 0x04
        if (not beat.effect.isDefault() or voice.hasVibrato() or
            voice.hasHarmonic() or beat.effect.presence):
            flags |= 0x08
        if beat.effect.mixTableChange is not None:
            flags |= 0x10
        if voice.duration.tuplet != gp.Tuplet():
            flags |= 0x20
        if voice.isEmpty or voice.isRestVoice():
            flags |= 0x40

        self.writeByte(flags)
        
        if flags & 0x40 != 0:
            beatType = 0x00 if voice.isEmpty else 0x02
            self.writeByte(beatType)
        
        self.writeDuration(voice.duration, flags)

        if flags & 0x02 != 0:
            self.writeChord(beat.effect.chord)
        
        if flags & 0x04 != 0:
            self.writeText(beat.text)
        
        if flags & 0x08 != 0:
            # try:
            #     noteEffect = voice.notes[0].effect
            # except IndexError:
            #     noteEffect = gp.NoteEffect()
            self.writeBeatEffects(beat.effect, voice)
        
        if flags & 0x10 != 0:
            self.writeMixTableChange(beat.effect.mixTableChange)

        stringFlags = 0x00
        for note in voice.notes:
            stringFlags |= 1 << (7 - note.string)
        self.writeByte(stringFlags)

        previous = None
        for note in voice.notes:
            self.writeNote(note, previous)
            previous = note
        
    def writeNote(self, note, previous):
        # In GP3 NoteEffect doesn't have vibrato attribute
        noteEffect = copy.copy(note.effect)
        noteEffect.vibrato = False

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
        if not noteEffect.isDefault() or note.effect.presence:
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
        if noteEffect.isBend():
            flags1 |= 0x01
        if noteEffect.hammer:
            flags1 |= 0x02
        if noteEffect.slide in (gp.SlideType.ShiftSlideTo, gp.SlideType.LegatoSlideTo):
            flags1 |= 0x04
        if noteEffect.letRing:
            flags1 |= 0x08
        if noteEffect.isGrace():
            flags1 |= 0x10

        self.writeByte(flags1)

        if flags1 & 0x01 != 0:
            self.writeBend(noteEffect.bend)
        
        if flags1 & 0x10 != 0:
            self.writeGrace(noteEffect.grace)
    
    def writeGrace(self, grace):
        self.writeByte(grace.fret)
        self.writeByte(self.packVelocity(grace.velocity))
        self.writeSignedByte(grace.transition)
        self.writeByte(grace.duration)
    
    def packVelocity(self, velocity):
        return (velocity + gp.Velocities.VELOCITY_INCREMENT - gp.Velocities.MIN_VELOCITY) / gp.Velocities.VELOCITY_INCREMENT

    def writeBend(self, bend):
        self.writeSignedByte(bend.type)
        self.writeInt(bend.value)
        self.writeInt(len(bend.points))
        for point in bend.points:
            self.writeInt(round(point.position * self.BEND_POSITION / gp.BendEffect.MAX_POSITION))
            self.writeInt(round(point.value * self.BEND_SEMITONE / gp.BendEffect.SEMITONE_LENGTH))
            self.writeBool(point.vibrato)
    
    def writeMixTableChange(self, tableChange):
        items = [(tableChange.instrument, self.writeSignedByte),
                 (tableChange.volume, self.writeSignedByte),
                 (tableChange.balance, self.writeSignedByte),
                 (tableChange.chorus, self.writeSignedByte),
                 (tableChange.reverb, self.writeSignedByte),
                 (tableChange.phaser, self.writeSignedByte),
                 (tableChange.tremolo, self.writeSignedByte),
                 (tableChange.tempo, self.writeInt)]

        for item, write in items:
            if item is not None:
                write(item.value)
            else:
                write(-1)

        # instrument change doesn't have duration
        for item, write in items[1:]:
            if item is not None:
                write(item.duration)

    def writeBeatEffects(self, beatEffect, voice):
        flags1 = 0x00
        if voice.hasVibrato():
            flags1 |= 0x01
        if beatEffect.vibrato:
            flags1 |= 0x02
        if voice.hasHarmonic() == gp.HarmonicType.Natural:
            flags1 |= 0x04
        if voice.hasHarmonic() == gp.HarmonicType.Artificial:
            flags1 |= 0x08
        if beatEffect.fadeIn:
            flags1 |= 0x10
        if beatEffect.isTremoloBar() or beatEffect.isSlapEffect():
            flags1 |= 0x20
        if beatEffect.stroke != gp.BeatStroke():
            flags1 |= 0x40
        self.writeByte(flags1)
        
        if flags1 & 0x20 != 0:
            if not beatEffect.isSlapEffect():
                self.writeByte(0)
                self.writeTremoloBar(beatEffect.tremoloBar)
            else:
                if beatEffect.tapping:
                    slapEffect = 1
                if beatEffect.slapping:
                    slapEffect = 2
                if beatEffect.popping:
                    slapEffect = 3
                self.writeByte(slapEffect)
                self.placeholder(4)
        if flags1 & 0x40 != 0:
            if beatEffect.stroke.direction == gp.BeatStrokeDirection.Up:
                strokeUp = self.fromStrokeValue(beatEffect.stroke.value)
                strokeDown = 0
            elif beatEffect.stroke.direction == gp.BeatStrokeDirection.Down:
                strokeUp = 0
                strokeDown = self.fromStrokeValue(beatEffect.stroke.value)
            self.writeSignedByte(strokeUp)
            self.writeSignedByte(strokeDown)

    def fromStrokeValue(self, value):
        if value == gp.Duration.SIXTY_FOURTH:
            return 1
        elif value == gp.Duration.SIXTY_FOURTH:
            return 2
        elif value == gp.Duration.THIRTY_SECOND:
            return 3
        elif value == gp.Duration.SIXTEENTH:
            return 4
        elif value == gp.Duration.EIGHTH:
            return 5
        elif value == gp.Duration.QUARTER:
            return 6
        else:
            return 1
    
    def writeTremoloBar(self, tremoloBar):
        self.writeInt(tremoloBar.value)
    
    def writeText(self, text):
        self.writeIntSizeCheckByteString(text.value)
    
    def writeChord(self, chord):
        self.writeByte(0)
        self.writeIntSizeCheckByteString(chord.name)
        self.writeInt(chord.firstFret)
        if chord.firstFret != 0:
            for i in range(6):
                self.writeInt(chord.strings[i])
        # else:
        #     self.skip(25)
        #     chord.name = self.writeByteSizeString(34)
        #     chord.firstFret = self.writeInt()
        #     for i in range(6):
        #         fret = self.writeInt()
        #         if i < len(chord.strings):
        #             chord.strings[i] = fret
        #     self.skip(36)
    
    def writeDuration(self, duration, flags):
        value = round(math.log(duration.value, 2) - 2)
        self.writeSignedByte(value)
        if flags & 0x20 != 0:
            if duration.tuplet.enters == 3 and duration.tuplet.times == 2:
                iTuplet = 3
            elif duration.tuplet.enters == 5 and duration.tuplet.times == 4:
                iTuplet = 5
            elif duration.tuplet.enters == 6 and duration.tuplet.times == 4:
                iTuplet = 6
            elif duration.tuplet.enters == 7 and duration.tuplet.times == 4:
                iTuplet = 7
            elif duration.tuplet.enters == 9 and duration.tuplet.times == 8:
                iTuplet = 9
            elif duration.tuplet.enters == 10 and duration.tuplet.times == 8:
                iTuplet = 10
            elif duration.tuplet.enters == 11 and duration.tuplet.times == 8:
                iTuplet = 11
            elif duration.tuplet.enters == 12 and duration.tuplet.times == 8:
                iTuplet = 12
            self.writeInt(iTuplet)