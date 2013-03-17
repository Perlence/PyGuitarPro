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
import gp3

class GP4File(gp3.GP3File):
    def __init__(self, *args, **kwargs):
        super(GP4File, self).__init__(*args, **kwargs)
        self.initVersions(['FICHIER GUITAR PRO v4.00', 'FICHIER GUITAR PRO v4.06', 'FICHIER GUITAR PRO L4.06'])
    
    def readSong(self):
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
            self.readChord(track.stringCount(), beat)

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
            if stringFlags & (1 << i) != 0 and (6 - i) < track.stringCount():
                # guitarString = track.strings[6 - i].clone(factory)
                guitarString = copy.copy(track.strings[6 - i])
                note = self.readNote(guitarString, track, gp.NoteEffect())
                voice.addNote(note)
            # duration.copy(voice.duration)
            voice.duration = copy.copy(duration)
        
        return duration.time() if not voice.isEmpty else 0
    
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
            noteEffect.slide = True
            slideType = self.readSignedByte()
            if slideType == 1:
                noteEffect.slideType = gp.SlideType.FastSlideTo
            elif slideType == 2:
                noteEffect.slideType = gp.SlideType.SlowSlideTo
            elif slideType == 4:
                noteEffect.slideType = gp.SlideType.OutDownWards
            elif slideType == 8:
                noteEffect.slideType = gp.SlideType.OutUpWards
            elif slideType == 16:
                noteEffect.slideType = gp.SlideType.IntoFromBelow
            elif slideType == 32:
                noteEffect.slideType = gp.SlideType.IntoFromAbove
        if flags2 & 0x10 != 0:
            self.readArtificialHarmonic(noteEffect)
        if flags2 & 0x20 != 0:
            self.readTrill(noteEffect)
        noteEffect.letRing = (flags1 & 0x08) != 0
        noteEffect.hammer = (flags1 & 0x02) != 0
        noteEffect.vibrato = (flags2 & 0x40) != 0 or noteEffect.vibrato
        noteEffect.palmMute = (flags2 & 0x02) != 0
        noteEffect.staccato = (flags2 & 0x01) != 0
    
    def readTrill(self, noteEffect):
        fret = self.readSignedByte()
        period = self.readSignedByte()
        trill = gp.TrillEffect()
        trill.fret = fret
        if period == 1:
            trill.duration.value = gp.Duration.SIXTEENTH
        elif period == 2:
            trill.duration.value = gp.Duration.THIRTY_SECOND
        elif period == 3:
            trill.duration.value = gp.Duration.SIXTY_FOURTH
        noteEffect.trill = trill
    
    def readArtificialHarmonic(self, noteEffect):
        harmonicType = self.readSignedByte()
        oHarmonic = gp.HarmonicEffect()
        if harmonicType == 1:
            oHarmonic.data = 0
            oHarmonic.type = gp.HarmonicType.Natural
        elif harmonicType == 3:
            self.skip(1) # Key?
            oHarmonic.data = 0
            oHarmonic.type = gp.HarmonicType.Tapped
        elif harmonicType == 4:
            oHarmonic.data = 0
            oHarmonic.type = gp.HarmonicType.Pinch
        elif harmonicType == 5:
            oHarmonic.data = 0
            oHarmonic.type = gp.HarmonicType.Semi
        elif harmonicType == 15:
            oHarmonic.data = 2
            oHarmonic.type = gp.HarmonicType.Artificial
        elif harmonicType == 17:
            oHarmonic.data = 3
            oHarmonic.type = gp.HarmonicType.Artificial
        elif harmonicType == 22:
            oHarmonic.data = 0
            oHarmonic.type = gp.HarmonicType.Artificial
        noteEffect.harmonic = oHarmonic
    
    def readTremoloPicking(self, noteEffect):
        value = self.readSignedByte()
        tp = gp.TremoloPickingEffect()
        if value == 1:
            tp.duration.value = gp.Duration.EIGHTH
        elif value == 2:
            tp.duration.value = gp.Duration.SIXTEENTH
        elif value == 3:
            tp.duration.value = gp.Duration.THIRTY_SECOND
        noteEffect.tremoloPicking = tp
    
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
        barEffect.type = self.readSignedByte()
        barEffect.value = self.readInt()
        pointCount = self.readInt()
        for i in range(pointCount):
            pointPosition = round(self.readInt() * gp.BendEffect.MAX_POSITION / self.BEND_POSITION)
            pointValue = round(self.readInt() / (self.BEND_SEMITONE * 2.0))
            vibrato = self.readBool()
            barEffect.points.append(gp.BendPoint(pointPosition, pointValue, vibrato))
        
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
            self.skip(16)
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
