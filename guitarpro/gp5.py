from __future__ import division

from . import base as gp
from . import gp4


class GP5File(gp4.GP4File):

    """A reader for GuitarPro 5 files."""

    _supportedVersions = ['FICHIER GUITAR PRO v5.00',
                          'FICHIER GUITAR PRO v5.10']

    def __init__(self, *args, **kwargs):
        super(GP5File, self).__init__(*args, **kwargs)

    # Reading
    # =======

    def readSong(self):
        """Read the song.

        A song consists of score information, triplet feel, lyrics, tempo, song
        key, MIDI channels, measure and track count, measure headers,
        tracks, measures.

        -   Score information.
            See :meth:`readInfo`.

        -   Lyrics.  See :meth:`readLyrics`.

        -   RSE master effect.  See :meth:`readRSEInstrument`.

        -   Tempo name: :ref:`int-byte-size-string`.

        -   Tempo: :ref:`int`.

        -   Hide tempo: :ref:`bool`.  Don't display tempo on the sheet if set.

        -   Key: :ref:`int`.  Key signature of the song.

        -   Octave: :ref:`int`.  Octave of the song.

        -   MIDI channels.  See :meth:`readMidiChannels`.

        -   Directions.  See :meth:`readDirections`.

        -   Master reverb.  See :meth:`readMasterReverb`.

        -   Number of measures: :ref:`int`.

        -   Number of tracks: :ref:`int`.

        -   Measure headers.  See :meth:`readMeasureHeaders`.

        -   Tracks.  See :meth:`readTracks`.

        -   Measures.  See :meth:`readMeasures`.

        """
        if not self.readVersion():
            raise gp.GPException("unsupported version '%s'" %
                                 self.version)
        song = gp.Song()
        self.readInfo(song)
        song.lyrics = self.readLyrics()
        song.masterEffect = self.readRSEMasterEffect()
        song.pageSetup = self.readPageSetup()
        song.tempoName = self.readIntByteSizeString()
        song.tempo = self.readInt()
        song.hideTempo = (self.readBool() if self.versionTuple > (5, 0)
                          else False)
        song.key = gp.KeySignature((self.readSignedByte(), 0))
        self.readInt()  # octave
        channels = self.readMidiChannels()
        directions = self.readDirections()
        song.masterEffect.reverb = self.readInt()
        measureCount = self.readInt()
        trackCount = self.readInt()
        self.readMeasureHeaders(song, measureCount, directions)
        self.readTracks(song, trackCount, channels)
        self.readMeasures(song)
        return song

    def readInfo(self, song):
        """Read score information.

        Score information consists of sequence of :ref:`IntByteSizeStrings
        <int-byte-size-string>`:

        -   title
        -   subtitle
        -   artist
        -   album
        -   words
        -   music
        -   copyright
        -   tabbed by
        -   instructions

        The sequence if followed by notice.  Notice starts with the number of
        notice lines stored in :ref:`int`.  Each line is encoded in
        :ref:`int-byte-size-string`.

        """
        song.title = self.readIntByteSizeString()
        song.subtitle = self.readIntByteSizeString()
        song.artist = self.readIntByteSizeString()
        song.album = self.readIntByteSizeString()
        song.words = self.readIntByteSizeString()
        song.music = self.readIntByteSizeString()
        song.copyright = self.readIntByteSizeString()
        song.tab = self.readIntByteSizeString()
        song.instructions = self.readIntByteSizeString()
        notesCount = self.readInt()
        song.notice = []
        for __ in range(notesCount):
            song.notice.append(self.readIntByteSizeString())

    def readRSEMasterEffect(self):
        """Read RSE master effect.

        Persistence of RSE master effect was introduced in Guitar Pro 5.1.
        It is read as:

        -   Master volume: :ref:`int`.  Values are in range from 0 to 200.

        -   Equalizer.  See :meth:`readEqualizer`.

        """
        if self.versionTuple > (5, 0):
            masterEffect = gp.RSEMasterEffect()
            masterEffect.volume = self.readInt()
            self.readInt()  # ???
            masterEffect.equalizer = self.readEqualizer(11)
            return masterEffect

    def readEqualizer(self, knobsNumber):
        """Read equalizer values.

        Equlizers are used in RSE master effect and Track RSE.  They consist of
        *n* :ref:`SignedBytes <signed-byte>` for each *n* frequency faders and
        one :ref:`signed-byte` for gain (PRE) fader.

        Volume values are stored as opposite to actual value.  See
        :meth:`unpackVolumeValue`.

        """
        knobs = map(self.unpackVolumeValue,
                    self.readSignedByte(count=knobsNumber))
        return gp.RSEEqualizer(knobs=knobs[:-1], gain=knobs[-1])

    def unpackVolumeValue(self, value):
        """Unpack equalizer volume value.

        Equalizer volumes are float but stored as
        :ref:`SignedBytes <signed-byte>`.

        """
        return -value / 10

    def readPageSetup(self):
        """Read page setup.

        Page setup is read as follows:

        -   Page size: 2 :ref:`Ints <int>`.  Width and height of the page.

        -   Page padding: 4 :ref:`Ints <int>`.  Left, right, top, bottom
            padding of the page.

        -   Score size proportion: :ref:`int`.

        -   Header and footer elements: :ref:`short`.  See
            :class:`HeaderFooterElements` for value mapping.

        -   List of placeholders:

            *   title
            *   subtitle
            *   artist
            *   album
            *   words
            *   music
            *   wordsAndMusic
            *   copyright1, e.g. Copyright %copyright%
            *   copyright2, e.g. All Rights Reserved - International Copyright
                Secured
            *   pageNumber

        """
        setup = gp.PageSetup()
        setup.pageSize = gp.Point(self.readInt(), self.readInt())
        l = self.readInt()
        r = self.readInt()
        t = self.readInt()
        b = self.readInt()
        setup.pageMargin = gp.Padding(l, t, r, b)
        setup.scoreSizeProportion = self.readInt() / 100
        setup.headerAndFooter = self.readShort()
        setup.title = self.readIntByteSizeString()
        setup.subtitle = self.readIntByteSizeString()
        setup.artist = self.readIntByteSizeString()
        setup.album = self.readIntByteSizeString()
        setup.words = self.readIntByteSizeString()
        setup.music = self.readIntByteSizeString()
        setup.wordsAndMusic = self.readIntByteSizeString()
        setup.copyright = (self.readIntByteSizeString() + '\n' +
                           self.readIntByteSizeString())
        setup.pageNumber = self.readIntByteSizeString()
        return setup

    def readDirections(self):
        """Read directions.

        Directions is a list of 19 :ref:`ShortInts <short-int>` each pointing
        at the number of measure.

        Directions are read in the following order.

        -   Coda
        -   Double Coda
        -   Segno
        -   Segno Segno
        -   Fine
        -   Da Capo
        -   Da Capo al Coda
        -   Da Capo al Double Coda
        -   Da Capo al Fine
        -   Da Segno
        -   Da Segno al Coda
        -   Da Segno al Double Coda
        -   Da Segno al Fine
        -   Da Segno Segno
        -   Da Segno Segno al Coda
        -   Da Segno Segno al Double Coda
        -   Da Segno Segno al Fine
        -   Da Coda
        -   Da Double Coda

        """
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
        """Read measure header.

        Measure header format in Guitar Pro 5 differs from one if Guitar Pro 3.

        First, there is a blank byte if measure is not first.  Then measure
        header is read as in GP3's :meth:`guitarpro.gp3.readMeasureHeader`.
        Then measure header is read as follows:

        -   Time signature beams: 4 :ref:`Bytes <byte>`.  Appears If time
            signature was set, i.e. flags *0x01* and *0x02* are both set.

        -   Blank :ref:`byte` if flag at *0x10* is set.

        -   Triplet feel: :ref:`byte`.  See
            :class:`guitarpro.base.TripletFeel`.

        """
        if previous is not None:
            # Always 0
            self.skip(1)
        header, flags = super(GP5File, self).readMeasureHeader(number, song,
                                                               previous)
        header.repeatClose -= 1
        if flags & 0x03:
            header.timeSignature.beams = self.readByte(4)
        else:
            header.timeSignature.beams = previous.timeSignature.beams
        if flags & 0x10 == 0:
            # Always 0
            self.skip(1)
        header.tripletFeel = gp.TripletFeel(self.readByte())
        return header, flags

    def readRepeatAlternative(self, measureHeaders):
        return self.readByte()

    def readTracks(self, song, trackCount, channels):
        for i in range(trackCount):
            song.addTrack(self.readTrack(i + 1, channels))
        # Always 0
        self.skip(2 if self.versionTuple == (5, 0) else 1)

    def readTrack(self, number, channels):
        if number == 1 or self.versionTuple == (5, 0):
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
        track.channel = self.readChannel(channels)
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
        if self.versionTuple == (5, 0):
            trackRSE.humanize = self.readByte()
            self.readInt(3)  # ???
            self.skip(12)  # ???
            self.skip(15)
        else:
            trackRSE.humanize = self.readByte()
            self.readInt(3)  # ???
            self.skip(12)  # ???
            trackRSE.instrument = self.readRSEInstrument()
            trackRSE.equalizer = self.readEqualizer(4)
            self.readRSEInstrumentEffect(trackRSE.instrument)
            return trackRSE

    def readRSEInstrument(self):
        instrument = gp.RSEInstrument()
        instrument.instrument = self.readInt()
        self.readInt()  # ??? mostly 1
        instrument.soundBank = self.readInt()
        self.readInt()  # ??? mostly -1
        return instrument

    def readRSEInstrumentEffect(self, rseInstrument):
        if self.versionTuple > (5, 0):
            effect = self.readIntByteSizeString()
            effectCategory = self.readIntByteSizeString()
            if rseInstrument is not None:
                rseInstrument.effect = effect
                rseInstrument.effectCategory = effectCategory
        return rseInstrument

    def readMeasure(self, measure, track, voiceIndex=None):
        for voiceIndex in range(gp.Beat.maxVoices):
            super(GP5File, self).readMeasure(measure, track, voiceIndex)
        measure.lineBreak = gp.LineBreak(self.readByte(default=0))

    def readBeat(self, start, measure, track, voiceIndex):
        duration = super(GP5File, self).readBeat(start, measure, track, voiceIndex)
        beat = self.getBeat(measure, start)
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
        return duration

    def readBeatStroke(self):
        stroke = super(GP5File, self).readBeatStroke()
        if stroke.direction == gp.BeatStrokeDirection.up:
            stroke.direction = gp.BeatStrokeDirection.down
        elif stroke.direction == gp.BeatStrokeDirection.down:
            stroke.direction = gp.BeatStrokeDirection.up
        return stroke

    def readMixTableChange(self, measure):
        tableChange = super(gp4.GP4File, self).readMixTableChange(measure)
        flags = self.readMixTableChangeFlags(tableChange)
        tableChange.wah = self.readWahEffect(flags)
        self.readRSEInstrumentEffect(tableChange.rse)
        return tableChange

    def readMixTableChangeValues(self, tableChange, measure):
        instrument = self.readSignedByte()
        rse = self.readRSEInstrument()
        volume = self.readSignedByte()
        balance = self.readSignedByte()
        chorus = self.readSignedByte()
        reverb = self.readSignedByte()
        phaser = self.readSignedByte()
        tremolo = self.readSignedByte()
        tempoName = self.readIntByteSizeString()
        tempo = self.readInt()
        if instrument >= 0:
            tableChange.instrument = gp.MixTableItem(instrument)
            tableChange.rse = rse
        if volume >= 0:
            tableChange.volume = gp.MixTableItem(volume)
        if balance >= 0:
            tableChange.balance = gp.MixTableItem(balance)
        if chorus >= 0:
            tableChange.chorus = gp.MixTableItem(chorus)
        if reverb >= 0:
            tableChange.reverb = gp.MixTableItem(reverb)
        if phaser >= 0:
            tableChange.phaser = gp.MixTableItem(phaser)
        if tremolo >= 0:
            tableChange.tremolo = gp.MixTableItem(tremolo)
        if tempo >= 0:
            tableChange.tempo = gp.MixTableItem(tempo)
            tableChange.tempoName = tempoName
            measure.tempo.value = tempo

    def readMixTableChangeDurations(self, tableChange):
        if tableChange.volume is not None:
            tableChange.volume.duration = self.readSignedByte()
        if tableChange.balance is not None:
            tableChange.balance.duration = self.readSignedByte()
        if tableChange.chorus is not None:
            tableChange.chorus.duration = self.readSignedByte()
        if tableChange.reverb is not None:
            tableChange.reverb.duration = self.readSignedByte()
        if tableChange.phaser is not None:
            tableChange.phaser.duration = self.readSignedByte()
        if tableChange.tremolo is not None:
            tableChange.tremolo.duration = self.readSignedByte()
        if tableChange.tempo is not None:
            tableChange.tempo.duration = self.readSignedByte()
            tableChange.hideTempo = (self.versionTuple > (5, 0) and
                                     self.readBool())

    def readMixTableChangeFlags(self, tableChange):
        flags = super(GP5File, self).readMixTableChangeFlags(tableChange)
        tableChange.useRSE = bool(flags & 0x40)
        return flags

    def readWahEffect(self, flags):
        wah = gp.WahEffect()
        wah.display = bool(flags & 0x80)
        wah.state = gp.WahState(self.readSignedByte())
        return wah

    def readNote(self, note, guitarString, track, effect):
        flags = self.readByte()
        note.string = guitarString.number
        note.effect.accentuatedNote = bool(flags & 0x40)
        note.effect.heavyAccentuatedNote = bool(flags & 0x02)
        note.effect.ghostNote = bool(flags & 0x04)
        if flags & 0x20:
            note.type = gp.NoteType(self.readByte())
            note.effect.deadNote = note.type == gp.NoteType.dead
        if flags & 0x10:
            dyn = self.readSignedByte()
            note.velocity = self.unpackVelocity(dyn)
        if flags & 0x20:
            fret = self.readSignedByte()
            if note.type == gp.NoteType.tie:
                value = self.getTiedNoteValue(guitarString.number, track)
            else:
                value = fret
            note.value = value if 0 <= value < 100 else 0
        if flags & 0x80:
            note.effect.leftHandFinger = gp.Fingering(self.readSignedByte())
            note.effect.rightHandFinger = gp.Fingering(self.readSignedByte())
        if flags & 0x01:
            note.durationPercent = self.readDouble()
        flags2 = self.readByte()
        note.swapAccidentals = bool(flags2 & 0x02)
        if flags & 0x08:
            note.effect = self.readNoteEffects(note)
        return note

    def readGrace(self):
        grace = gp.GraceEffect()
        grace.fret = self.readByte()
        grace.velocity = self.unpackVelocity(self.readByte())
        grace.transition = gp.GraceEffectTransition(self.readByte())
        grace.duration = 1 << (7 - self.readByte())
        flags = self.readByte()
        grace.isDead = bool(flags & 0x01)
        grace.isOnBeat = bool(flags & 0x02)
        return grace

    def readSlides(self):
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
        return slides

    def readHarmonic(self, note):
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
        return harmonic

    # Writing
    # =======

    def writeSong(self, song):
        self.version = self._supportedVersions[1]
        self.writeVersion(1)

        self.writeInfo(song)
        self.writeLyrics(song.lyrics)
        self.writeRSEMasterEffect(song.masterEffect)
        self.writePageSetup(song.pageSetup)

        self.writeIntByteSizeString(song.tempoName)
        self.writeInt(song.tempo)

        if self.versionTuple > (5, 0):
            self.writeBool(song.hideTempo)

        self.writeSignedByte(song.key.value[0])
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

    def writeInfo(self, song):
        self.writeIntByteSizeString(song.title)
        self.writeIntByteSizeString(song.subtitle)
        self.writeIntByteSizeString(song.artist)
        self.writeIntByteSizeString(song.album)
        self.writeIntByteSizeString(song.words)
        self.writeIntByteSizeString(song.music)
        self.writeIntByteSizeString(song.copyright)
        self.writeIntByteSizeString(song.tab)
        self.writeIntByteSizeString(song.instructions)

        self.writeInt(len(song.notice))
        for line in song.notice:
            self.writeIntByteSizeString(line)

    def writeRSEMasterEffect(self, masterEffect):
        if self.versionTuple > (5, 0):
            if masterEffect is None:
                masterEffect = gp.RSEMasterEffect()
                masterEffect.volume = 100
                masterEffect.reverb = 0
                masterEffect.equalizer = gp.RSEEqualizer(knobs=[0] * 10, gain=0)
            self.writeInt(masterEffect.volume)
            self.writeInt(0)
            self.writeEqualizer(masterEffect.equalizer)

    def writeEqualizer(self, equalizer):
        for knob in equalizer.knobs:
            self.writeSignedByte(self.packVolumeValue(knob))
        self.writeSignedByte(self.packVolumeValue(equalizer.gain))

    def packVolumeValue(self, value):
        return int(-round(value, 1) * 10)

    def writePageSetup(self, setup):
        if setup is None:
            setup = gp.PageSetup()

        self.writeInt(setup.pageSize.x)
        self.writeInt(setup.pageSize.y)

        self.writeInt(setup.pageMargin.left)
        self.writeInt(setup.pageMargin.right)
        self.writeInt(setup.pageMargin.top)
        self.writeInt(setup.pageMargin.bottom)
        self.writeInt(setup.scoreSizeProportion * 100)

        self.writeByte(setup.headerAndFooter & 0xff)

        flags2 = 0x00
        if setup.headerAndFooter and gp.HeaderFooterElements.pageNumber != 0:
            flags2 |= 0x01
        self.writeByte(flags2)

        self.writeIntByteSizeString(setup.title)
        self.writeIntByteSizeString(setup.subtitle)
        self.writeIntByteSizeString(setup.artist)
        self.writeIntByteSizeString(setup.album)
        self.writeIntByteSizeString(setup.words)
        self.writeIntByteSizeString(setup.music)
        self.writeIntByteSizeString(setup.wordsAndMusic)
        copyrighta, copyrightb = setup.copyright.split('\n', 1)
        self.writeIntByteSizeString(copyrighta)
        self.writeIntByteSizeString(copyrightb)
        self.writeIntByteSizeString(setup.pageNumber)

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
        else:
            self.writeByte(0)
        self.placeholder(3)

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
            self.writeRepeatAlternative(header.repeatAlternative)

        if flags & 0x40:
            self.writeSignedByte(header.keySignature.value[0])
            self.writeByte(header.keySignature.value[1])

        if flags & 0x01:
            for beam in header.timeSignature.beams:
                self.writeByte(beam)

        if flags & 0x10 == 0:
            self.placeholder(1)

        self.writeByte(header.tripletFeel.value)

    def writeRepeatAlternative(self, repeatAlternative):
        self.writeByte(repeatAlternative)

    def writeTracks(self, tracks):
        super(GP5File, self).writeTracks(tracks)
        self.placeholder(2 if self.versionTuple == (5, 0) else 1)

    def writeTrack(self, track):
        if track.number == 1 or self.versionTuple == (5, 0):
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
        if self.versionTuple == (5, 0):
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

    def writeRSEInstrumentEffect(self, rseInstrument):
        if self.versionTuple > (5, 0):
            if rseInstrument is None:
                rseInstrument = gp.RSEInstrument()
            self.writeIntByteSizeString(rseInstrument.effect)
            self.writeIntByteSizeString(rseInstrument.effectCategory)

    def writeMeasure(self, measure):
        for index in range(gp.Beat.maxVoices):
            beats = measure.voice(index)
            self.writeInt(len(beats))
            for beat in beats:
                self.writeBeat(beat, index)
        self.writeByte(measure.lineBreak.value)

    def writeBeat(self, beat, voiceIndex=0):
        super(GP5File, self).writeBeat(beat, voiceIndex)
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

    def writeBeatStroke(self, stroke):
        if stroke.direction == gp.BeatStrokeDirection.up:
            stroke.direction = gp.BeatStrokeDirection.down
        elif stroke.direction == gp.BeatStrokeDirection.down:
            stroke.direction = gp.BeatStrokeDirection.up
        super(GP5File, self).writeBeatStroke(stroke)

    def writeMixTableChange(self, tableChange):
        super(gp4.GP4File, self).writeMixTableChange(tableChange)
        self.writeMixTableChangeFlags(tableChange)
        self.writeWahEffect(tableChange.wah)
        self.writeRSEInstrumentEffect(tableChange.rse)

    def writeMixTableChangeValues(self, tableChange):
        self.writeSignedByte(tableChange.instrument.value
                             if tableChange.instrument is not None else -1)
        self.writeRSEInstrument(tableChange.rse)
        self.writeSignedByte(tableChange.volume.value
                             if tableChange.volume is not None else -1)
        self.writeSignedByte(tableChange.balance.value
                             if tableChange.balance is not None else -1)
        self.writeSignedByte(tableChange.chorus.value
                             if tableChange.chorus is not None else -1)
        self.writeSignedByte(tableChange.reverb.value
                             if tableChange.reverb is not None else -1)
        self.writeSignedByte(tableChange.phaser.value
                             if tableChange.phaser is not None else -1)
        self.writeSignedByte(tableChange.tremolo.value
                             if tableChange.tremolo is not None else -1)
        self.writeIntByteSizeString(tableChange.tempoName)
        self.writeInt(tableChange.tempo.value
                      if tableChange.tempo is not None else -1)

    def writeMixTableChangeDurations(self, tableChange):
        if tableChange.volume is not None:
            self.writeSignedByte(tableChange.volume.duration)
        if tableChange.balance is not None:
            self.writeSignedByte(tableChange.balance.duration)
        if tableChange.chorus is not None:
            self.writeSignedByte(tableChange.chorus.duration)
        if tableChange.reverb is not None:
            self.writeSignedByte(tableChange.reverb.duration)
        if tableChange.phaser is not None:
            self.writeSignedByte(tableChange.phaser.duration)
        if tableChange.tremolo is not None:
            self.writeSignedByte(tableChange.tremolo.duration)
        if tableChange.tempo is not None:
            self.writeSignedByte(tableChange.tempo.duration)
            if self.versionTuple > (5, 0):
                self.writeBool(tableChange.hideTempo)

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
        if tableChange.useRSE:
            flags |= 0x40
        if tableChange.wah is not None and tableChange.wah.display:
            flags |= 0x80
        self.writeByte(flags)

    def writeWahEffect(self, wah):
        if wah is not None:
            self.writeSignedByte(wah.state.value)
        else:
            self.writeSignedByte(gp.WahState.none.value)

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
        if note.velocity != gp.Velocities.default:
            flags |= 0x10
        flags |= 0x20
        if note.effect.accentuatedNote:
            flags |= 0x40
        if note.effect.isFingering:
            flags |= 0x80

        self.writeByte(flags)

        if flags & 0x20:
            self.writeByte(note.type.value)

        if flags & 0x10:
            value = self.packVelocity(note.velocity)
            self.writeSignedByte(value)

        if flags & 0x20:
            fret = note.value if note.type != gp.NoteType.tie else 0
            self.writeSignedByte(fret)

        if flags & 0x80:
            self.writeSignedByte(note.effect.leftHandFinger.value)
            self.writeSignedByte(note.effect.rightHandFinger.value)

        if flags & 0x01:
            self.writeDouble(note.durationPercent)

        flags2 = 0x00
        if note.swapAccidentals:
            flags2 |= 0x02

        self.writeByte(flags2)

        if flags & 0x08:
            self.writeNoteEffects(note)

    def writeGrace(self, grace):
        self.writeByte(grace.fret)
        self.writeByte(self.packVelocity(grace.velocity))
        self.writeByte(grace.transition.value)
        self.writeByte(8 - grace.duration.bit_length())
        flags = 0x00
        if grace.isDead:
            flags |= 0x01
        if grace.isOnBeat:
            flags |= 0x02
        self.writeByte(flags)

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
