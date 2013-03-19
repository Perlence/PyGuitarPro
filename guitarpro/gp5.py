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

# TODO: There must be a wah wah flag somewhere. 
class GP5File(gp4.GP4File):
    '''A reader for GuitarPro 5 files. 
    '''
    def __init__(self, *args, **kwargs):
        super(GP5File, self).__init__(*args, **kwargs)
        self.initVersions(['FICHIER GUITAR PRO v5.00', 'FICHIER GUITAR PRO v5.10'])
    
    def readSong(self) :
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
        
        song.key = self.readByte()
        song.octave = self.readInt()
        
        channels = self.readMidiChannels()
        
        self.skip(42) # RSE info?
        measureCount = self.readInt()
        trackCount = self.readInt()
        
        self.readMeasureHeaders(song, measureCount)
        self.readTracks(song, trackCount, channels)
        self.readMeasures(song)
        
        return song
        
    def readMeasure(self, measure, track):
        for voice in range(gp.Beat.MAX_VOICES):
            start = measure.start()
            beats = self.readInt()
            for beat in range(beats):
                start += self.readBeat(start, measure, track, voice)
        self.skip(1)
    
    def readBeat(self, start, measure, track, voiceIndex):
        flags = self.readByte()
        
        beat = self.getBeat(measure, start)
        voice = beat.voices[voiceIndex]
        
        if flags & 0x40 != 0:
            beatType = self.readByte()
            voice.isEmpty = (beatType & 0x02) == 0
        
        duration = self.readDuration(flags)
        if flags & 0x02 != 0:
            self.readChord(track.stringCount(), beat)

        if flags & 0x04 != 0:
            self.readText(beat)

        if flags & 0x08 != 0:
            self.readBeatEffects(beat, None)

        if flags & 0x10 != 0:
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
        
        self.skip(1)
        
        read = self.readByte()
        if read == 8 or read == 10:
            self.skip(1)

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
            self.skip(3) # Note?
            return (0, gp.HarmonicType.Artificial)
        elif harmonicType == 3:
            self.skip(1) # Key?
            return (0, gp.HarmonicType.Tapped)
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

        self.skip(1)
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
    
    def readTracks(self, song, trackCount, channels) :
        for i in range(trackCount):
            song.addTrack(self.readTrack(i + 1, channels))
        self.skip(2 if self.version.endswith('5.00') else 1)
    
    def readTrack(self, number, channels) :
        flags = self.readByte()
        if number == 1 or self.version.endswith('5.00'):
            self.skip(1)
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
        self.skip(49 if not self.version.endswith('5.00') else 44)
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
    
    def readMeasureHeader(self, i, timeSignature, song):
        if i > 0:
            self.skip(1)
        
        flags = self.readByte()
        
        header = gp.MeasureHeader()
        header.number = i + 1
        header.start = 0
        header.tempo.value = song.tempo
        
        if flags & 0x01 != 0:
            timeSignature.numerator = self.readByte()
        if flags & 0x02 != 0:
            timeSignature.denominator.value = self.readByte()
        
        header.isRepeatOpen = (flags & 0x04) != 0
        
        # timeSignature.copy(header.timeSignature)
        header.timeSignature = copy.deepcopy(timeSignature)
        
        if flags & 0x08 != 0:
            header.repeatClose = self.readByte() - 1
        
        if flags & 0x20 != 0:
            header.marker = self.readMarker(header)
        
        if flags & 0x10 != 0:
            header.repeatAlternative = self.readByte()
        
        if flags & 0x40 != 0:
            header.keySignature = self.toKeySignature(self.readSignedByte())
            header.keySignatureType = self.readByte()
        elif header.number > 1:
            header.keySignature = song.measureHeaders[i - 1].keySignature
            header.keySignatureType = song.measureHeaders[i - 1].keySignatureType

        header.hasDoubleBar = (flags & 0x80) != 0

        if flags & 0x01 != 0:
            self.skip(4)

        if flags & 0x10 == 0:
            self.skip(1)
        
        header.tripletFeel = self.unpackTripletFeel(self.readByte())
        
        return header
    
    def readPageSetup(self, song):
        setup = gp.PageSetup()
        if not self.version.endswith('5.00'):
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
