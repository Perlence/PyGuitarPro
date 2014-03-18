from __future__ import division

from . import base as gp
from . import gp4
from .utils import hexify


class GP5File(gp4.GP4File):

    '''A reader for GuitarPro 5 files.
    '''
    _supportedVersions = ['FICHIER GUITAR PRO v5.00',
                          'FICHIER GUITAR PRO v5.10']

    def __init__(self, *args, **kwargs):
        super(GP5File, self).__init__(*args, **kwargs)

    # Reading
    # =======

    def readSong(self):
        if not self.readVersion():
            raise gp.GuitarProException("unsupported version '%s'" %
                                        self.version)

        song = gp.Song()
        self.readInfo(song)

        self.readLyrics(song)
        self.readRSEMasterEffect(song)
        self.readPageSetup(song)

        song.tempoName = self.readIntSizeCheckByteString()
        song.tempo = self.readInt()

        if not self.version.endswith('5.00'):
            song.hideTempo = self.readBool()
        else:
            song.hideTempo = False

        song.key = self.readByte()
        self.readInt()  # octave

        channels = self.readMidiChannels()

        directions = self.readDirections()
        self.readMasterReverb(song)

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
            gp.DirectionSign('Da Segno al Coda'): self.readShort(),
            gp.DirectionSign('Da Segno al Double Coda'): self.readShort(),
            gp.DirectionSign('Da Segno al Fine'): self.readShort(),
            gp.DirectionSign('Da Segno Segno'): self.readShort(),
            gp.DirectionSign('Da Segno Segno al Coda'): self.readShort(),
            gp.DirectionSign('Da Segno Segno al Double Coda'): self.readShort(),
            gp.DirectionSign('Da Segno Segno al Fine'): self.readShort(),
            gp.DirectionSign('Da Coda'): self.readShort(),
            gp.DirectionSign('Da Double Coda'): self.readShort()
        }
        return signs, fromSigns

    def readMasterReverb(self, song):
        # Opeth - Baying of the Hounds.gp5: ffffffff
        # Mastodon - Colony of Birchmen.gp5: 01000000
        # Mostly 00000000
        song.masterEffect.reverb = self.readByte()
        self.skip(3)  # ???

    def readMeasure(self, measure, track):
        for voice in range(gp.Beat.MAX_VOICES):
            start = measure.start
            beats = self.readInt()
            for __ in range(beats):
                start += self.readBeat(start, measure, track, voice)
        measure.lineBreak = gp.LineBreak(self.readByte(default=0))

    def readBeat(self, start, measure, track, voiceIndex):
        flags1 = self.readByte()

        beat = self.getBeat(measure, start)
        voice = beat.voices[voiceIndex]

        if flags1 & 0x40:
            beatType = self.readByte()
            voice.isEmpty = (beatType & 0x02) == 0

        duration = self.readDuration(flags1)

        if flags1 & 0x02:
            self.readChord(len(track.strings), beat)

        if flags1 & 0x04:
            self.readText(beat)

        if flags1 & 0x08:
            self.readBeatEffects(beat, None)

        if flags1 & 0x10:
            mixTableChange = self.readMixTableChange(measure)
            beat.effect.mixTableChange = mixTableChange

        stringFlags = self.readByte()
        for j in range(7):
            i = 6 - j
            if stringFlags & (1 << i) and (6 - i) < len(track.strings):
                guitarString = track.strings[6 - i]
                note = gp.Note()
                voice.addNote(note)
                self.readNote(note, guitarString, track, gp.NoteEffect())
            voice.duration = duration

        flags2 = self.readByte()
        flags3 = self.readByte()

        if flags2 & 0x10:
            beat.octave = gp.Octave.ottava
        if flags2 & 0x20:
            beat.octave = gp.Octave.ottavaBassa
        if flags2 & 0x40:
            beat.octave = gp.Octave.quindicesima
        if flags3 & 0x01:
            beat.octave = gp.Octave.quindicesimaBassa

        display = gp.BeatDisplay()
        display.breakBeam = bool(flags2 & 0x01)
        display.forceBeam = bool(flags2 & 0x04)
        display.forceBracket = bool(flags3 & 0x20)
        display.breakSecondaryTuplet = bool(flags3 & 0x10)
        if flags2 & 0x02:
            display.beamDirection = gp.VoiceDirection.down
        if flags2 & 0x08:
            display.beamDirection = gp.VoiceDirection.up
        if flags3 & 0x02:
            display.tupletBracket = gp.TupletBracket.start
        if flags3 & 0x04:
            display.tupletBracket = gp.TupletBracket.end
        if flags3 & 0x08:
            display.breakSecondary = self.readByte()

        beat.display = display

        return duration.time if not voice.isEmpty else 0

    def readNote(self, note, guitarString, track, effect):
        flags = self.readByte()
        note.string = guitarString.number
        note.effect.accentuatedNote = bool(flags & 0x40)
        note.effect.heavyAccentuatedNote = bool(flags & 0x02)
        note.effect.ghostNote = bool(flags & 0x04)
        if flags & 0x20:
            noteType = self.readByte()
            note.isTiedNote = noteType == 0x02
            note.effect.deadNote = noteType == 0x03

        if flags & 0x10:
            dyn = self.readSignedByte()
            note.velocity = self.unpackVelocity(dyn)

        if flags & 0x20:
            fret = self.readSignedByte()
            value = self.getTiedNoteValue(guitarString.number,
                                          track) if note.isTiedNote else fret
            note.value = value if 0 <= value < 100 else 0

        if flags & 0x80:
            note.effect.leftHandFinger = self.readSignedByte()
            note.effect.rightHandFinger = self.readSignedByte()
            note.effect.isFingering = True

        if flags & 0x01:
            note.durationPercent = self.readDouble()
        flags2 = self.readByte()
        note.swapAccidentals = bool(flags2 & 0x02)

        if flags & 0x08:
            self.readNoteEffects(note)

        return note

    def readNoteEffects(self, note):
        noteEffect = note.effect
        flags1 = self.readByte()
        flags2 = self.readByte()
        if flags1 & 0x01:
            self.readBend(noteEffect)
        if flags1 & 0x10:
            self.readGrace(noteEffect)
        if flags2 & 0x04:
            self.readTremoloPicking(noteEffect)
        if flags2 & 0x08:
            self.readSlides(noteEffect)
        if flags2 & 0x10:
            self.readHarmonic(note)
        if flags2 & 0x20:
            self.readTrill(noteEffect)
        noteEffect.letRing = bool(flags1 & 0x08)
        noteEffect.hammer = bool(flags1 & 0x02)
        noteEffect.vibrato = bool(flags2 & 0x40) or noteEffect.vibrato
        noteEffect.palmMute = bool(flags2 & 0x02)
        noteEffect.staccato = bool(flags2 & 0x01)

    def readSlides(self, noteEffect):
        slideType = self.readByte()
        slides = []
        if slideType & 0x01:
            slides.append(gp.SlideType.shiftSlideTo)
        if slideType & 0x02:
            slides.append(gp.SlideType.legatoSlideTo)
        if slideType & 0x04:
            slides.append(gp.SlideType.outDownwards)
        if slideType & 0x08:
            slides.append(gp.SlideType.outUpwards)
        if slideType & 0x10:
            slides.append(gp.SlideType.intoFromBelow)
        if slideType & 0x20:
            slides.append(gp.SlideType.intoFromAbove)
        noteEffect.slides = slides

    def readHarmonic(self, note):
        noteEffect = note.effect
        harmonicType = self.readSignedByte()
        if harmonicType == 1:
            harmonic = gp.NaturalHarmonic()
        elif harmonicType == 2:
            # C = 0, D = 2, E = 4, F = 5...
            # b = -1, # = 1
            # loco = 0, 8va = 1, 15ma = 2
            semitone = self.readByte()
            accidental = self.readSignedByte()
            pitchClass = gp.PitchClass(semitone, accidental)
            octave = gp.Octave(self.readByte())
            harmonic = gp.ArtificialHarmonic(pitchClass, octave)
        elif harmonicType == 3:
            fret = self.readByte()
            harmonic = gp.TappedHarmonic(fret)
        elif harmonicType == 4:
            harmonic = gp.PinchHarmonic()
        elif harmonicType == 5:
            harmonic = gp.SemiHarmonic()
        noteEffect.harmonic = harmonic

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
        grace.isDead = bool(flags & 0x01)
        grace.isOnBeat = bool(flags & 0x02)
        grace.transition = gp.GraceEffectTransition(transition)

        noteEffect.grace = grace

    def readMixTableChange(self, measure):
        tableChange = gp.MixTableChange()
        tableChange.instrument.value = self.readSignedByte()
        tableChange.rse = self.readRSEInstrument()
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
            measure.tempo.value = tableChange.tempo.value
            tableChange.hideTempo = (not self.version.endswith('5.00') and
                                     self.readBool())
        else:
            tableChange.tempo = None

        allTracksFlags = self.readByte()
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
        if allTracksFlags & 0x80:
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
            tableChange.rse.effect = self.readIntSizeCheckByteString()
            tableChange.rse.effectCategory = self.readIntSizeCheckByteString()

        return tableChange

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
        track.isPercussionTrack = bool(flags1 & 0x01)
        track.is12StringedGuitarTrack = bool(flags1 & 0x02)
        track.isBanjoTrack = bool(flags1 & 0x04)
        track.isVisible = bool(flags1 & 0x08)
        track.isSolo = bool(flags1 & 0x10)
        track.isMute = bool(flags1 & 0x20)
        track.useRSE = bool(flags1 & 0x40)
        track.indicateTuning = bool(flags1 & 0x80)
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
        trackSettings.tablature = bool(flags2 & 0x01)
        trackSettings.notation = bool(flags2 & 0x02)
        trackSettings.diagramsAreBelow = bool(flags2 & 0x04)
        trackSettings.showRhythm = bool(flags2 & 0x08)
        trackSettings.forceHorizontal = bool(flags2 & 0x10)
        trackSettings.forceChannels = bool(flags2 & 0x20)
        trackSettings.diagramList = bool(flags2 & 0x40)
        trackSettings.diagramsInScore = bool(flags2 & 0x80)

        # 0x01: ???
        trackSettings.autoLetRing = bool(flags3 & 0x02)
        trackSettings.autoBrush = bool(flags3 & 0x04)
        trackSettings.extendRhythmic = bool(flags3 & 0x08)
        track.settings = trackSettings

        trackRSE = gp.TrackRSE()
        trackRSE.autoAccentuation = gp.Accentuation(self.readByte())

        bank = self.readByte()
        track.channel.bank = bank

        track.rse = self.readTrackRSE(trackRSE)
        return track

    def readTrackRSE(self, trackRSE=None):
        if trackRSE is None:
            trackRSE = gp.TrackRSE()
        if self.version.endswith('5.00'):
            trackRSE.humanize = self.readByte()
            self.readInt(3)  # ???
            data = self.data.read(12)  # ???
            self.skip(15)
        else:
            trackRSE.humanize = self.readByte()
            self.readInt(3)  # ???
            data = self.data.read(12)  # ???
            trackRSE.instrument = self.readRSEInstrument()
            trackRSE.equalizer = self.readEqualizer(4)
            trackRSE.instrument.effect = self.readIntSizeCheckByteString()
            trackRSE.instrument.effectCategory = self.readIntSizeCheckByteString()
            return trackRSE

    def readRSEInstrument(self):
        instrument = gp.RSEInstrument()
        instrument.instrument = self.readInt()
        self.readInt()  # ??? mostly 1
        instrument.soundBank = self.readInt()
        self.readInt()  # ??? mostly -1
        return instrument

    def readMeasureHeaders(self, song, measureCount, directions):
        super(GP5File, self).readMeasureHeaders(song, measureCount)
        signs, fromSigns = directions
        for sign, number in signs.items():
            if number > -1:
                song.measureHeaders[number - 1].direction = sign
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

        if flags & 0x01:
            header.timeSignature.numerator = self.readByte()
        else:
            header.timeSignature.numerator = previous.timeSignature.numerator
        if flags & 0x02:
            header.timeSignature.denominator.value = self.readByte()
        else:
            header.timeSignature.denominator.value = previous.timeSignature.denominator.value

        header.isRepeatOpen = bool(flags & 0x04)

        if flags & 0x08:
            header.repeatClose = self.readByte() - 1

        if flags & 0x20:
            header.marker = self.readMarker(header)

        if flags & 0x10:
            header.repeatAlternative = self.readByte()

        if flags & 0x40:
            header.keySignature = self.toKeySignature(self.readSignedByte())
            header.keySignatureType = self.readByte()
        elif previous is not None:
            header.keySignature = previous.keySignature
            header.keySignatureType = previous.keySignatureType

        header.hasDoubleBar = bool(flags & 0x80)

        if flags & 0x03:
            header.timeSignature.beams = [self.readByte() for __ in range(4)]
        else:
            header.timeSignature.beams = previous.timeSignature.beams

        if flags & 0x10 == 0:
            # Always 0
            self.skip(1)

        header.tripletFeel = gp.TripletFeel(self.readByte())

        return header

    def readRSEMasterEffect(self, song):
        if not self.version.endswith('5.00'):
            masterEffect = gp.RSEMasterEffect()
            masterEffect.volume = self.readByte()
            data = self.data.read(7)  # ???
            if data != '\x00' * 7:
                import ipdb; ipdb.set_trace()
            masterEffect.equalizer = self.readEqualizer(11)
            song.masterEffect = masterEffect

    def readEqualizer(self, knobsNumber):
        knobs = map(self.unpackVolumeValue, self.readSignedByte(count=knobsNumber))
        return gp.RSEEqualizer(knobs=knobs[:-1], gain=knobs[-1])

    def unpackVolumeValue(self, value):
        return -value / 10
        
    def readPageSetup(self, song):
        setup = gp.PageSetup()
        setup.pageSize = gp.Point(self.readInt(), self.readInt())

        l = self.readInt()
        r = self.readInt()
        t = self.readInt()
        b = self.readInt()
        setup.pageMargin = gp.Padding(l, t, r, b)
        setup.scoreSizeProportion = self.readInt() / 100.0

        setup.headerAndFooter = self.readByte()

        flags2 = self.readByte()
        if flags2 & 0x01:
            setup.headerAndFooter |= gp.HeaderFooterElements.PAGE_NUMBER

        setup.title = self.readIntSizeCheckByteString()
        setup.subtitle = self.readIntSizeCheckByteString()
        setup.artist = self.readIntSizeCheckByteString()
        setup.album = self.readIntSizeCheckByteString()
        setup.words = self.readIntSizeCheckByteString()
        setup.music = self.readIntSizeCheckByteString()
        setup.wordsAndMusic = self.readIntSizeCheckByteString()
        setup.copyright = (self.readIntSizeCheckByteString() + '\n' +
                           self.readIntSizeCheckByteString())
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
        for __ in range(iNotes):
            song.notice.append(self.readIntSizeCheckByteString())

    # Writing
    # =======

    def writeSong(self, song):
        self.version = self._supportedVersions[1]
        self.writeVersion(1)

        self.writeInfo(song)
        self.writeLyrics(song.lyrics)
        self.writeRSEMasterEffect(song.masterEffect)
        self.writePageSetup(song.pageSetup)

        self.writeIntSizeCheckByteString(song.tempoName)
        self.writeInt(song.tempo)

        if not self.version.endswith('5.00'):
            self.writeBool(song.hideTempo)

        self.writeByte(song.key)
        self.writeInt(0)  # octave

        self.writeMidiChannels(song.tracks)

        self.writeDirections(song.measureHeaders)
        self.writeMasterReverb(song.masterEffect)

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
                 'Da Segno al Coda',
                 'Da Segno al Double Coda',
                 'Da Segno al Fine',
                 'Da Segno Segno',
                 'Da Segno Segno al Coda',
                 'Da Segno Segno al Double Coda',
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

    def writeMasterReverb(self, masterEffect):
        if masterEffect is not None:
            self.writeByte(masterEffect.reverb)
            self.placeholder(3)

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

    def writeRSEMasterEffect(self, masterEffect):
        if masterEffect is not None and not self.version.endswith('5.00'):
            self.writeByte(masterEffect.volume)
            self.placeholder(7)
            self.writeEqualizer(masterEffect.equalizer)

    def writeEqualizer(self, equalizer):
        for knob in equalizer.knobs:
            self.writeSignedByte(self.packVolumeValue(knob))
        self.writeSignedByte(self.packVolumeValue(equalizer.gain))

    def packVolumeValue(self, value):
        return int(-round(value, 1) * 10)

    def writePageSetup(self, setup):
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
        if header.repeatAlternative:
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

        if flags & 0x01:
            self.writeByte(header.timeSignature.numerator)
        if flags & 0x02:
            self.writeByte(header.timeSignature.denominator.value)

        if flags & 0x08:
            self.writeByte(header.repeatClose + 1)

        if flags & 0x20:
            self.writeMarker(header.marker)

        if flags & 0x10:
            self.writeByte(header.repeatAlternative)

        if flags & 0x40:
            self.writeSignedByte(self.fromKeySignature(header.keySignature))
            self.writeByte(header.keySignatureType)

        if flags & 0x01:
            for beam in header.timeSignature.beams:
                self.writeByte(beam)

        if flags & 0x10 == 0:
            self.placeholder(1)

        self.writeByte(header.tripletFeel.value)

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
        if track.useRSE:
            flags1 |= 0x40
        if track.indicateTuning:
            flags1 |= 0x80

        self.writeByte(flags1)

        self.writeByteSizeString(track.name, 40)
        self.writeInt(len(track.strings))
        for i in range(7):
            if i < len(track.strings):
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
        if track.rse is not None and track.rse.autoAccentuation is not None:
            self.writeByte(track.rse.autoAccentuation.value)
        else:
            self.writeByte(0)
        self.writeByte(track.channel.bank)

        self.writeTrackRSE(track.rse)

    def writeTrackRSE(self, trackRSE):
        if trackRSE is None:
            trackRSE = gp.TrackRSE()
        if self.version.endswith('5.00'):
            self.writeByte(trackRSE.humanize)
            self.writeInt(0)
            self.writeInt(0)
            self.writeInt(100)
            self.placeholder(12)
            self.placeholder(15, '\xff')
        else:
            self.writeByte(trackRSE.humanize)
            self.writeInt(0)
            self.writeInt(0)
            self.writeInt(100)
            self.placeholder(12)
            self.writeRSEInstrument(trackRSE.instrument)
            self.writeEqualizer(trackRSE.equalizer)
        self.writeRSEInstrumentEffect(trackRSE.instrument)

    def writeRSEInstrument(self, instrument):
        if instrument is None:
            instrument = gp.RSEInstrument()
        self.writeInt(instrument.instrument)
        self.writeInt(1)
        self.writeInt(instrument.soundBank)
        self.writeInt(-1)

    def writeMeasure(self, measure):
        for index in range(gp.Beat.MAX_VOICES):
            beats = measure.voice(index)
            self.writeInt(len(beats))
            for beat in beats:
                self.writeBeat(beat, index)
        self.writeByte(measure.lineBreak.value)

    def writeBeat(self, beat, voiceIndex=0):
        voice = beat.voices[voiceIndex]

        flags1 = 0x00
        if voice.duration.isDotted:
            flags1 |= 0x01
        if beat.effect.isChord:
            flags1 |= 0x02
        if beat.text is not None:
            flags1 |= 0x04
        if not beat.effect.isDefault:
            flags1 |= 0x08
        if beat.effect.mixTableChange is not None:
            flags1 |= 0x10
        if voice.duration.tuplet != gp.Tuplet():
            flags1 |= 0x20
        if voice.isEmpty or voice.isRestVoice:
            flags1 |= 0x40

        self.writeByte(flags1)

        if flags1 & 0x40:
            beatType = 0x00 if voice.isEmpty else 0x02
            self.writeByte(beatType)

        self.writeDuration(voice.duration, flags1)

        if flags1 & 0x02:
            self.writeChord(beat.effect.chord)

        if flags1 & 0x04:
            self.writeText(beat.text)

        if flags1 & 0x08:
            self.writeBeatEffects(beat.effect)

        if flags1 & 0x10:
            self.writeMixTableChange(beat.effect.mixTableChange)

        stringFlags = 0x00
        for note in voice.notes:
            stringFlags |= 1 << (7 - note.string)
        self.writeByte(stringFlags)

        for note in voice.notes:
            self.writeNote(note)

        flags2 = 0x00
        if beat.display.breakBeam:
            flags2 |= 0x01
        if beat.display.beamDirection == gp.VoiceDirection.down:
            flags2 |= 0x02
        if beat.display.forceBeam:
            flags2 |= 0x04
        if beat.display.beamDirection == gp.VoiceDirection.up:
            flags2 |= 0x08
        if beat.octave == gp.Octave.ottava:
            flags2 |= 0x10
        if beat.octave == gp.Octave.ottavaBassa:
            flags2 |= 0x20
        if beat.octave == gp.Octave.quindicesima:
            flags2 |= 0x40

        self.writeByte(flags2)

        flags3 = 0x00
        if beat.octave == gp.Octave.quindicesimaBassa:
            flags3 |= 0x01
        if beat.display.tupletBracket == gp.TupletBracket.start:
            flags3 |= 0x02
        if beat.display.tupletBracket == gp.TupletBracket.end:
            flags3 |= 0x04
        if beat.display.breakSecondary:
            flags3 |= 0x08
        if beat.display.breakSecondaryTuplet:
            flags3 |= 0x10
        if beat.display.forceBracket:
            flags3 |= 0x20

        self.writeByte(flags3)

        if flags3 & 0x08:
            self.writeByte(beat.display.breakSecondary)

    def writeNote(self, note):
        flags = 0x00
        if abs(note.durationPercent - 1.0) >= 1e-2:
            flags |= 0x01
        if note.effect.heavyAccentuatedNote:
            flags |= 0x02
        if note.effect.ghostNote:
            flags |= 0x04
        if not note.effect.isDefault:
            flags |= 0x08
        if note.velocity != gp.Velocities.DEFAULT:
            flags |= 0x10
        # if note.isTiedNote or note.effect.deadNote:
        flags |= 0x20
        if note.effect.accentuatedNote:
            flags |= 0x40
        if note.effect.isFingering:
            flags |= 0x80

        self.writeByte(flags)

        if flags & 0x20:
            if note.isTiedNote:
                noteType = 0x02
            elif note.effect.deadNote:
                noteType = 0x03
            else:
                noteType = 0x01
            self.writeByte(noteType)

        if flags & 0x10:
            value = self.packVelocity(note.velocity)
            self.writeSignedByte(value)

        if flags & 0x20:
            fret = note.value if not note.isTiedNote else 0
            self.writeSignedByte(fret)

        if flags & 0x80:
            self.writeSignedByte(note.effect.leftHandFinger)
            self.writeSignedByte(note.effect.rightHandFinger)

        if flags & 0x01:
            self.writeDouble(note.durationPercent)

        flags2 = 0x00
        if note.swapAccidentals:
            flags2 |= 0x02

        self.writeByte(flags2)

        if flags & 0x08:
            self.writeNoteEffects(note)

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

        self.writeByte(flags1)

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

        self.writeByte(flags2)

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

    def writeSlides(self, slides):
        slideType = 0
        for slide in slides:
            if slide == gp.SlideType.shiftSlideTo:
                slideType |= 0x01
            elif slide == gp.SlideType.legatoSlideTo:
                slideType |= 0x02
            elif slide == gp.SlideType.outDownwards:
                slideType |= 0x04
            elif slide == gp.SlideType.outUpwards:
                slideType |= 0x08
            elif slide == gp.SlideType.intoFromBelow:
                slideType |= 0x10
            elif slide == gp.SlideType.intoFromAbove:
                slideType |= 0x20
        self.writeByte(slideType)

    def writeHarmonic(self, note, harmonic):
        self.writeSignedByte(harmonic.type)
        if isinstance(harmonic, gp.ArtificialHarmonic):
            if not harmonic.pitch or not harmonic.octave:
                harmonic.pitch = gp.PitchClass(note.realValue % 12)
                harmonic.octave = gp.Octave.ottava
            self.writeByte(harmonic.pitch.just)
            self.writeSignedByte(harmonic.pitch.accidental)
            self.writeByte(harmonic.octave.value)
        elif isinstance(harmonic, gp.TappedHarmonic):
            self.writeByte(harmonic.fret)

    def writeGrace(self, grace):
        self.writeByte(grace.fret)
        self.writeByte(self.packVelocity(grace.velocity))
        self.writeByte(grace.transition.value)
        self.writeByte(grace.duration)

        flags = 0x00
        if grace.isDead:
            flags |= 0x01
        if grace.isOnBeat:
            flags |= 0x02

        self.writeByte(flags)

    def writeMixTableChange(self, tableChange):
        items = [('instrument', self.writeSignedByte),
                 ('rse', self.writeRSEInstrument),
                 ('volume', self.writeSignedByte),
                 ('balance', self.writeSignedByte),
                 ('chorus', self.writeSignedByte),
                 ('reverb', self.writeSignedByte),
                 ('phaser', self.writeSignedByte),
                 ('tremolo', self.writeSignedByte),
                 ('tempoName', self.writeIntSizeCheckByteString),
                 ('tempo', self.writeInt)]

        for name, write in items:
            item = getattr(tableChange, name)
            if item is None:
                write(-1)
            elif isinstance(item, tuple):
                write(*item)
            elif isinstance(item, gp.MixTableItem):
                write(item.value)
            else:
                write(item)

        allTracksFlags = 0x00
        # instrument change doesn't have duration
        for i, (name, __) in enumerate(items[2:]):
            item = getattr(tableChange, name)
            if isinstance(item, gp.MixTableItem):
                self.writeSignedByte(item.duration)
                if name == 'tempo':
                    if not self.version.endswith('5.00'):
                        self.writeBool(tableChange.hideTempo)
                if item.allTracks:
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

        self.writeRSEInstrumentEffect(tableChange.rse)
    
    def writeRSEInstrumentEffect(self, rseInstrument):
        if not self.version.endswith('5.00'):
            if rseInstrument is None:
                rseInstrument = gp.RSEInstrument()
            self.writeIntSizeCheckByteString(rseInstrument.effect)
            self.writeIntSizeCheckByteString(rseInstrument.effectCategory)

    def writeMidiChannels(self, tracks):
        def getTrackChannelByChannel(channel):
            for track in tracks:
                if channel in (track.channel.channel, track.channel.effectChannel):
                    return track.channel
            return gp.MidiChannel(channel, channel)

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
