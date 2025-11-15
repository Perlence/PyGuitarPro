import attr

from . import models as gp
from . import gp4


class GP5File(gp4.GP4File):
    """A reader for GuitarPro 5 files."""

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

        - Lyrics. See :meth:`readLyrics`.

        - RSE master effect. See :meth:`readRSEInstrument`.

        - Tempo name: :ref:`int-byte-size-string`.

        - Tempo: :ref:`int`.

        - Hide tempo: :ref:`bool`. Don't display tempo on the sheet if
          set.

        - Key: :ref:`int`. Key signature of the song.

        - Octave: :ref:`int`. Octave of the song.

        - MIDI channels. See :meth:`readMidiChannels`.

        - Directions. See :meth:`readDirections`.

        - Master reverb. See :meth:`readMasterReverb`.

        - Number of measures: :ref:`int`.

        - Number of tracks: :ref:`int`.

        - Measure headers. See :meth:`readMeasureHeaders`.

        - Tracks. See :meth:`readTracks`.

        - Measures. See :meth:`readMeasures`.
        """
        song = gp.Song(tracks=[], measureHeaders=[])
        song.version = self.readVersion()
        song.versionTuple = self.versionTuple

        if self.isClipboard():
            song.clipboard = self.readClipboard()

        self.readInfo(song)
        song.lyrics = self.readLyrics()
        song.masterEffect = self.readRSEMasterEffect()
        song.pageSetup = self.readPageSetup()
        song.tempoName = self.readIntByteSizeString()
        song.tempo = self.readI32()
        song.hideTempo = self.readBool() if self.versionTuple > (5, 0, 0) else False
        song.key = gp.KeySignature((self.readI8(), 0))
        self.readI32()  # octave
        channels = self.readMidiChannels()
        directions = self.readDirections()
        song.masterEffect.reverb = self.readI32()
        measureCount = self.readI32()
        trackCount = self.readI32()
        with self.annotateErrors('reading'):
            self.readMeasureHeaders(song, measureCount, directions)
            self.readTracks(song, trackCount, channels)
            self.readMeasures(song)
        return song

    def readClipboard(self):
        clipboard = super().readClipboard()
        if clipboard is None:
            return
        clipboard.startBeat = self.readI32()
        clipboard.stopBeat = self.readI32()
        clipboard.subBarCopy = bool(self.readI32())
        return clipboard

    def readInfo(self, song):
        """Read score information.

        Score information consists of sequence of
        :ref:`IntByteSizeStrings <int-byte-size-string>`:

        - title
        - subtitle
        - artist
        - album
        - words
        - music
        - copyright
        - tabbed by
        - instructions

        The sequence if followed by notice. Notice starts with the
        number of notice lines stored in :ref:`int`. Each line is
        encoded in :ref:`int-byte-size-string`.
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
        notesCount = self.readI32()
        song.notice = []
        for _ in range(notesCount):
            song.notice.append(self.readIntByteSizeString())

    def readRSEMasterEffect(self):
        """Read RSE master effect.

        Persistence of RSE master effect was introduced in Guitar Pro
        5.1. It is read as:

        - Master volume: :ref:`int`. Values are in range from 0 to 200.

        - 10-band equalizer. See :meth:`readEqualizer`.
        """
        masterEffect = gp.RSEMasterEffect()
        if self.versionTuple > (5, 0, 0):
            masterEffect.volume = self.readI32()
            self.readI32()  # ???
            masterEffect.equalizer = self.readEqualizer(11)
        return masterEffect

    def readEqualizer(self, knobsNumber):
        """Read equalizer values.

        Equalizers are used in RSE master effect and Track RSE. They
        consist of *n* :ref:`SignedBytes <signed-byte>` for each *n*
        bands and one :ref:`signed-byte` for gain (PRE) fader.

        Volume values are stored as opposite to actual value. See
        :meth:`unpackVolumeValue`.
        """
        knobs = [self.unpackVolumeValue(self.readI8()) for _ in range(knobsNumber)]
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

        - Page size: 2 :ref:`Ints <int>`. Width and height of the page.

        - Page padding: 4 :ref:`Ints <int>`. Left, right, top, bottom
          padding of the page.

        - Score size proportion: :ref:`int`.

        - Header and footer elements: :ref:`short`. See
          :class:`guitarpro.models.HeaderFooterElements` for value
          mapping.

        - List of placeholders:

          * title
          * subtitle
          * artist
          * album
          * words
          * music
          * wordsAndMusic
          * copyright1, e.g. *"Copyright %copyright%"*
          * copyright2, e.g. *"All Rights Reserved - International
            Copyright Secured"*
          * pageNumber
        """
        setup = gp.PageSetup()
        setup.pageSize = gp.Point(self.readI32(), self.readI32())
        left = self.readI32()
        right = self.readI32()
        top = self.readI32()
        bottom = self.readI32()
        setup.pageMargin = gp.Padding(left, top, right, bottom)
        setup.scoreSizeProportion = self.readI32() / 100
        setup.headerAndFooter = self.readI16()
        setup.title = self.readIntByteSizeString()
        setup.subtitle = self.readIntByteSizeString()
        setup.artist = self.readIntByteSizeString()
        setup.album = self.readIntByteSizeString()
        setup.words = self.readIntByteSizeString()
        setup.music = self.readIntByteSizeString()
        setup.wordsAndMusic = self.readIntByteSizeString()
        setup.copyright = self.readIntByteSizeString() + '\n' + self.readIntByteSizeString()
        setup.pageNumber = self.readIntByteSizeString()
        return setup

    def readDirections(self):
        """Read directions.

        Directions is a list of 19 :ref:`ShortInts <short>` each
        pointing at the number of measure.

        Directions are read in the following order.

        - Coda
        - Double Coda
        - Segno
        - Segno Segno
        - Fine
        - Da Capo
        - Da Capo al Coda
        - Da Capo al Double Coda
        - Da Capo al Fine
        - Da Segno
        - Da Segno al Coda
        - Da Segno al Double Coda
        - Da Segno al Fine
        - Da Segno Segno
        - Da Segno Segno al Coda
        - Da Segno Segno al Double Coda
        - Da Segno Segno al Fine
        - Da Coda
        - Da Double Coda
        """
        signs = {
            gp.DirectionSign('Coda'): self.readI16(),
            gp.DirectionSign('Double Coda'): self.readI16(),
            gp.DirectionSign('Segno'): self.readI16(),
            gp.DirectionSign('Segno Segno'): self.readI16(),
            gp.DirectionSign('Fine'): self.readI16()
        }
        fromSigns = {
            gp.DirectionSign('Da Capo'): self.readI16(),
            gp.DirectionSign('Da Capo al Coda'): self.readI16(),
            gp.DirectionSign('Da Capo al Double Coda'): self.readI16(),
            gp.DirectionSign('Da Capo al Fine'): self.readI16(),
            gp.DirectionSign('Da Segno'): self.readI16(),
            gp.DirectionSign('Da Segno al Coda'): self.readI16(),
            gp.DirectionSign('Da Segno al Double Coda'): self.readI16(),
            gp.DirectionSign('Da Segno al Fine'): self.readI16(),
            gp.DirectionSign('Da Segno Segno'): self.readI16(),
            gp.DirectionSign('Da Segno Segno al Coda'): self.readI16(),
            gp.DirectionSign('Da Segno Segno al Double Coda'): self.readI16(),
            gp.DirectionSign('Da Segno Segno al Fine'): self.readI16(),
            gp.DirectionSign('Da Coda'): self.readI16(),
            gp.DirectionSign('Da Double Coda'): self.readI16()
        }
        return signs, fromSigns

    def readMeasureHeaders(self, song, measureCount, directions):
        super().readMeasureHeaders(song, measureCount)
        signs, fromSigns = directions
        for sign, number in signs.items():
            if number > -1:
                song.measureHeaders[number - 1].direction = sign
        for sign, number in fromSigns.items():
            if number > -1:
                song.measureHeaders[number - 1].fromDirection = sign

    def readMeasureHeader(self, number, song, previous=None):
        """Read measure header.

        Measure header format in Guitar Pro 5 differs from one in Guitar
        Pro 3.

        First, there is a blank byte if measure is not first. Then
        measure header is read as in GP3's
        :meth:`guitarpro.gp3.readMeasureHeader`. Then measure header is
        read as follows:

        - Time signature beams: 4 :ref:`Bytes <byte>`. Appears If time
          signature was set, i.e. flags *0x01* and *0x02* are both set.

        - Blank :ref:`byte` if flag at *0x10* is set.

        - Triplet feel: :ref:`byte`. See
          :class:`guitarpro.models.TripletFeel`.
        """
        if previous is not None:
            # Always 0
            self.skip(1)

        flags = self.readU8()
        header = gp.MeasureHeader()
        header.number = number
        header.start = 0
        header.tripletFeel = self._tripletFeel
        if flags & 0x01:
            header.timeSignature.numerator = self.readI8()
        else:
            header.timeSignature.numerator = previous.timeSignature.numerator
        if flags & 0x02:
            header.timeSignature.denominator.value = self.readI8()
        else:
            header.timeSignature.denominator.value = previous.timeSignature.denominator.value
        header.isRepeatOpen = bool(flags & 0x04)
        if flags & 0x08:
            header.repeatClose = self.readI8()
        if flags & 0x20:
            header.marker = self.readMarker(header)
        if flags & 0x40:
            root = self.readI8()
            type_ = self.readI8()
            header.keySignature = gp.KeySignature((root, type_))
        elif header.number > 1:
            header.keySignature = previous.keySignature
        if flags & 0x10:
            header.repeatAlternative = self.readRepeatAlternative(song.measureHeaders)
        header.hasDoubleBar = bool(flags & 0x80)

        if header.repeatClose > -1:
            header.repeatClose -= 1
        if flags & 0x03:
            header.timeSignature.beams = [self.readU8() for _ in range(4)]
        else:
            header.timeSignature.beams = previous.timeSignature.beams
        if flags & 0x10 == 0:
            # Always 0
            self.skip(1)
        header.tripletFeel = gp.TripletFeel(self.readU8())
        return header, flags

    def readRepeatAlternative(self, measureHeaders):
        return self.readU8()

    def readTracks(self, song, trackCount, channels):
        """Read tracks.

        Tracks in Guitar Pro 5 have almost the same format as in Guitar
        Pro 3. If it's Guitar Pro 5.0 then 2 blank bytes are read after
        :meth:`guitarpro.gp3.readTracks`. If format version is higher
        than 5.0, 1 blank byte is read.
        """
        super().readTracks(song, trackCount, channels)
        self.skip(2 if self.versionTuple == (5, 0, 0) else 1)  # Always 0

    def readTrack(self, track, channels):
        """Read track.

        If it's Guitar Pro 5.0 format and track is first then one blank
        byte is read.

        Then go track's flags. It presides the track's attributes:

        - *0x01*: drums track
        - *0x02*: 12 stringed guitar track
        - *0x04*: banjo track
        - *0x08*: track visibility
        - *0x10*: track is soloed
        - *0x20*: track is muted
        - *0x40*: RSE is enabled
        - *0x80*: show tuning in the header of the sheet.

        Flags are followed by:

        - Name: `String`. A 40 characters long string containing the
          track's name.

        - Number of strings: :ref:`int`. An integer equal to the number
          of strings of the track.

        - Tuning of the strings: `Table of integers`. The tuning of the
          strings is stored as a 7-integers table, the "Number of
          strings" first integers being really used. The strings are
          stored from the highest to the lowest.

        - Port: :ref:`int`. The number of the MIDI port used.

        - Channel. See :meth:`GP3File.readChannel`.

        - Number of frets: :ref:`int`. The number of frets of the
          instrument.

        - Height of the capo: :ref:`int`. The number of the fret on
          which a capo is set. If no capo is used, the value is 0.

        - Track's color. The track's displayed color in Guitar Pro.

        The properties are followed by second set of flags stored in a
        :ref:`short`.

        - *0x0001*: show tablature
        - *0x0002*: show standard notation
        - *0x0004*: chord diagrams are below standard notation
        - *0x0008*: show rhythm with tab
        - *0x0010*: force horizontal beams
        - *0x0020*: force channels 11 to 16
        - *0x0040*: diagram list on top of the score
        - *0x0080*: diagrams in the score
        - *0x0200*: auto let-ring
        - *0x0400*: auto brush
        - *0x0800*: extend rhythmic inside the tab

        Then follow:

        - Auto accentuation: :ref:`byte`. See
          :class:`guitarpro.models.Accentuation`.

        - MIDI bank: :ref:`byte`.

        - Track RSE. See :meth:`readTrackRSE`.
        """
        if track.number == 1 or self.versionTuple == (5, 0, 0):
            # Always 0
            self.skip(1)
        flags1 = self.readU8()
        track.isPercussionTrack = bool(flags1 & 0x01)
        track.is12StringedGuitarTrack = bool(flags1 & 0x02)
        track.isBanjoTrack = bool(flags1 & 0x04)
        track.isVisible = bool(flags1 & 0x08)
        track.isSolo = bool(flags1 & 0x10)
        track.isMute = bool(flags1 & 0x20)
        track.useRSE = bool(flags1 & 0x40)
        track.indicateTuning = bool(flags1 & 0x80)
        track.name = self.readByteSizeString(40)
        stringCount = self.readI32()
        for i in range(7):
            iTuning = self.readI32()
            if stringCount > i:
                oString = gp.GuitarString(i + 1, iTuning)
                track.strings.append(oString)
        track.port = self.readI32()
        track.channel = self.readChannel(channels)
        if track.channel.channel == 9:
            track.isPercussionTrack = True
        track.fretCount = self.readI32()
        track.offset = self.readI32()
        track.color = self.readColor()

        flags2 = self.readI16()
        track.settings = gp.TrackSettings()
        track.settings.tablature = bool(flags2 & 0x0001)
        track.settings.notation = bool(flags2 & 0x0002)
        track.settings.diagramsAreBelow = bool(flags2 & 0x0004)
        track.settings.showRhythm = bool(flags2 & 0x0008)
        track.settings.forceHorizontal = bool(flags2 & 0x0010)
        track.settings.forceChannels = bool(flags2 & 0x0020)
        track.settings.diagramList = bool(flags2 & 0x0040)
        track.settings.diagramsInScore = bool(flags2 & 0x0080)
        # 0x0100: ???
        track.settings.autoLetRing = bool(flags2 & 0x0200)
        track.settings.autoBrush = bool(flags2 & 0x0400)
        track.settings.extendRhythmic = bool(flags2 & 0x0800)

        track.rse = gp.TrackRSE()
        track.rse.autoAccentuation = gp.Accentuation(self.readU8())
        track.channel.bank = self.readU8()
        self.readTrackRSE(track.rse)

    def readTrackRSE(self, trackRSE):
        """Read track RSE.

        In GuitarPro 5.1 track RSE is read as follows:

        - Humanize: :ref:`byte`.

        - Unknown space: 6 :ref:`Ints <int>`.

        - RSE instrument. See :meth:`readRSEInstrument`.

        - 3-band track equalizer. See :meth:`readEqualizer`.

        - RSE instrument effect. See :meth:`readRSEInstrumentEffect`.
        """
        trackRSE.humanize = self.readU8()
        for _ in range(3):
            self.readI32()  # ???
        self.skip(12)  # ???
        trackRSE.instrument = self.readRSEInstrument()
        if self.versionTuple > (5, 0, 0):
            trackRSE.equalizer = self.readEqualizer(4)
            self.readRSEInstrumentEffect(trackRSE.instrument)
        return trackRSE

    def readRSEInstrument(self):
        """Read RSE instrument.

        - MIDI instrument number: :ref:`int`.

        - Unknown :ref:`int`.

        - Sound bank: :ref:`int`.

        - Effect number: :ref:`int`. Vestige of Guitar Pro 5.0 format.
        """
        instrument = gp.RSEInstrument()
        instrument.instrument = self.readI32()
        instrument.unknown = self.readI32()  # ??? mostly 1
        instrument.soundBank = self.readI32()
        if self.versionTuple == (5, 0, 0):
            instrument.effectNumber = self.readI16()
            self.skip(1)
        else:
            instrument.effectNumber = self.readI32()
        return instrument

    def readRSEInstrumentEffect(self, rseInstrument):
        """Read RSE instrument effect name.

        This feature was introduced in Guitar Pro 5.1.

        - Effect name: :ref:`int-byte-size-string`.

        - Effect category: :ref:`int-byte-size-string`.
        """
        if self.versionTuple > (5, 0, 0):
            effect = self.readIntByteSizeString()
            effectCategory = self.readIntByteSizeString()
            if rseInstrument is not None:
                rseInstrument.effect = effect
                rseInstrument.effectCategory = effectCategory
        return rseInstrument

    def readMeasure(self, measure):
        """Read measure.

        Guitar Pro 5 stores twice more measures compared to Guitar Pro
        3. One measure consists of two sub-measures for each of two
        voices.

        Sub-measures are followed by a
        :class:`~guitarpro.models.LineBreak` stored in :ref:`byte`.
        """
        start = measure.start
        for number, voice in enumerate(measure.voices[:gp.Measure.maxVoices]):
            self._currentVoiceNumber = number + 1
            self.readVoice(start, voice)
        self._currentVoiceNumber = None
        measure.lineBreak = gp.LineBreak(self.readU8(default=0))

    def readBeat(self, start, voice):
        """Read beat.

        First, beat is read is in Guitar Pro 3
        :meth:`guitarpro.gp3.readBeat`. Then it is followed by set of
        flags stored in :ref:`short`.

        - *0x0001*: break beams
        - *0x0002*: direct beams down
        - *0x0004*: force beams
        - *0x0008*: direct beams up
        - *0x0010*: ottava (8va)
        - *0x0020*: ottava bassa (8vb)
        - *0x0040*: quindicesima (15ma)
        - *0x0100*: quindicesima bassa (15mb)
        - *0x0200*: start tuplet bracket here
        - *0x0400*: end tuplet bracket here
        - *0x0800*: break secondary beams
        - *0x1000*: break secondary tuplet
        - *0x2000*: force tuplet bracket

        - Break secondary beams: :ref:`byte`. Appears if flag at
          *0x0800* is set. Signifies how much beams should be broken.
        """
        duration = super().readBeat(start, voice)
        beat = self.getBeat(voice, start)
        flags2 = self.readI16()
        if flags2 & 0x0010:
            beat.octave = gp.Octave.ottava
        if flags2 & 0x0020:
            beat.octave = gp.Octave.ottavaBassa
        if flags2 & 0x0040:
            beat.octave = gp.Octave.quindicesima
        if flags2 & 0x0100:
            beat.octave = gp.Octave.quindicesimaBassa
        display = gp.BeatDisplay()
        display.breakBeam = bool(flags2 & 0x0001)
        display.forceBeam = bool(flags2 & 0x0004)
        display.forceBracket = bool(flags2 & 0x2000)
        display.breakSecondaryTuplet = bool(flags2 & 0x1000)
        if flags2 & 0x0002:
            display.beamDirection = gp.VoiceDirection.down
        if flags2 & 0x0008:
            display.beamDirection = gp.VoiceDirection.up
        if flags2 & 0x0200:
            display.tupletBracket = gp.TupletBracket.start
        if flags2 & 0x0400:
            display.tupletBracket = gp.TupletBracket.end
        if flags2 & 0x0800:
            display.breakSecondary = self.readU8()
        beat.display = display
        return duration

    def readBeatStroke(self):
        """Read beat stroke.

        Beat stroke consists of two :ref:`Bytes <byte>` which correspond
        to stroke down and stroke up speed. See
        :class:`guitarpro.models.BeatStroke` for value mapping.
        """
        stroke = super().readBeatStroke()
        return stroke.swapDirection()

    def readMixTableChange(self, measure):
        """Read mix table change.

        Mix table change was modified to support RSE instruments. It is
        read as in Guitar Pro 3 and is followed by:

        - Wah effect. See :meth:`readWahEffect`.

        - RSE instrument effect. See :meth:`readRSEInstrumentEffect`.
        """
        tableChange = super(gp4.GP4File, self).readMixTableChange(measure)
        flags = self.readMixTableChangeFlags(tableChange)
        tableChange.wah = self.readWahEffect(flags)
        self.readRSEInstrumentEffect(tableChange.rse)
        return tableChange

    def readMixTableChangeValues(self, tableChange, measure):
        """Read mix table change values.

        Mix table change values consist of:

        - Instrument: :ref:`signed-byte`.

        - RSE instrument. See `readRSEInstrument`.

        - Volume: :ref:`signed-byte`.

        - Balance: :ref:`signed-byte`.

        - Chorus: :ref:`signed-byte`.

        - Reverb: :ref:`signed-byte`.

        - Phaser: :ref:`signed-byte`.

        - Tremolo: :ref:`signed-byte`.

        - Tempo name: :ref:`int-byte-size-string`.

        - Tempo: :ref:`int`.

        If the value is -1 then corresponding parameter hasn't changed.
        """
        instrument = self.readI8()
        rse = self.readRSEInstrument()
        if self.versionTuple == (5, 0, 0):
            self.skip(1)
        volume = self.readI8()
        balance = self.readI8()
        chorus = self.readI8()
        reverb = self.readI8()
        phaser = self.readI8()
        tremolo = self.readI8()
        tempoName = self.readIntByteSizeString()
        tempo = self.readI32()
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

    def readMixTableChangeDurations(self, tableChange):
        """Read mix table change durations.

        Durations are read for each non-null
        :class:`~guitarpro.models.MixTableItem`. Durations are encoded
        in :ref:`signed-byte`.

        If tempo did change, then one :ref:`bool` is read. If it's true,
        then tempo change won't be displayed on the score.
        """
        if tableChange.volume is not None:
            tableChange.volume.duration = self.readI8()
        if tableChange.balance is not None:
            tableChange.balance.duration = self.readI8()
        if tableChange.chorus is not None:
            tableChange.chorus.duration = self.readI8()
        if tableChange.reverb is not None:
            tableChange.reverb.duration = self.readI8()
        if tableChange.phaser is not None:
            tableChange.phaser.duration = self.readI8()
        if tableChange.tremolo is not None:
            tableChange.tremolo.duration = self.readI8()
        if tableChange.tempo is not None:
            tableChange.tempo.duration = self.readI8()
            tableChange.hideTempo = self.versionTuple > (5, 0, 0) and self.readBool()

    def readMixTableChangeFlags(self, tableChange):
        """Read mix table change flags.

        Mix table change flags are read as in Guitar Pro 4
        :meth:`guitarpro.gp4.readMixTableChangeFlags`, with one
        additional flag:

        - *0x40*: use RSE
        - *0x80*: show wah-wah
        """
        flags = super().readMixTableChangeFlags(tableChange)
        tableChange.useRSE = bool(flags & 0x40)
        return flags

    def readWahEffect(self, flags):
        """Read wah-wah.

        - Wah value: :ref:`signed-byte`. See
          :class:`guitarpro.models.WahEffect` for value mapping.
        """
        return gp.WahEffect(value=self.readI8(),
                            display=bool(flags & 0x80))

    def readNote(self, note, guitarString, track):
        """Read note.

        The first byte is note flags:

        - *0x01*: duration percent
        - *0x02*: heavy accentuated note
        - *0x04*: ghost note
        - *0x08*: presence of note effects
        - *0x10*: dynamics
        - *0x20*: fret
        - *0x40*: accentuated note
        - *0x80*: right hand or left hand fingering

        Flags are followed by:

        - Note type: :ref:`byte`. Note is normal if values is 1, tied if
          value is 2, dead if value is 3.

        - Note dynamics: :ref:`signed-byte`. See
          :meth:`unpackVelocity`.

        - Fret number: :ref:`signed-byte`. If flag at *0x20* is set then
          read fret number.

        - Fingering: 2 :ref:`SignedBytes <signed-byte>`. See
          :class:`guitarpro.models.Fingering`.

        - Duration percent: :ref:`double`.

        - Second set of flags: :ref:`byte`.

          - *0x02*: swap accidentals.

        - Note effects. See :meth:`guitarpro.gp4.readNoteEffects`.
        """
        flags = self.readU8()
        note.string = guitarString.number
        note.effect.heavyAccentuatedNote = bool(flags & 0x02)
        note.effect.ghostNote = bool(flags & 0x04)
        note.effect.accentuatedNote = bool(flags & 0x40)
        if flags & 0x20:
            note.type = gp.NoteType(self.readU8())
        if flags & 0x10:
            dyn = self.readI8()
            note.velocity = self.unpackVelocity(dyn)
        if flags & 0x20:
            fret = self.readI8()
            if note.type == gp.NoteType.tie:
                value = self.getTiedNoteValue(note)
            else:
                value = fret
            note.value = value if 0 <= value < 100 else 0
        if flags & 0x80:
            note.effect.leftHandFinger = gp.Fingering(self.readI8())
            note.effect.rightHandFinger = gp.Fingering(self.readI8())
        if flags & 0x01:
            note.durationPercent = self.readF64()
        flags2 = self.readU8()
        note.swapAccidentals = bool(flags2 & 0x02)
        if flags & 0x08:
            note.effect = self.readNoteEffects(note)
        return note

    def readGrace(self):
        """Read grace note effect.

        - Fret: :ref:`signed-byte`. Number of fret.

        - Dynamic: :ref:`byte`. Dynamic of a grace note, as in
          :attr:`guitarpro.models.Note.velocity`.

        - Transition: :ref:`byte`. See
          :class:`guitarpro.models.GraceEffectTransition`.

        - Duration: :ref:`byte`. Values are:

          - *1*: Thirty-second note.
          - *2*: Twenty-fourth note.
          - *3*: Sixteenth note.

        - Flags: :ref:`byte`.

          - *0x01*: grace note is muted (dead)
          - *0x02*: grace note is on beat
        """
        grace = gp.GraceEffect()
        grace.fret = self.readU8()
        grace.velocity = self.unpackVelocity(self.readU8())
        grace.transition = gp.GraceEffectTransition(self.readU8())
        grace.duration = 1 << (7 - self.readU8())
        flags = self.readU8()
        grace.isDead = bool(flags & 0x01)
        grace.isOnBeat = bool(flags & 0x02)
        return grace

    def readSlides(self):
        """Read slides.

        First :ref:`byte` stores slide types:

        - *0x01*: shift slide
        - *0x02*: legato slide
        - *0x04*: slide out downwards
        - *0x08*: slide out upwards
        - *0x10*: slide into from below
        - *0x20*: slide into from above
        """
        slideType = self.readU8()
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
        """Read harmonic.

        First :ref:`byte` is harmonic type:

        - *1*: natural harmonic
        - *2*: artificial harmonic
        - *3*: tapped harmonic
        - *4*: pinch harmonic
        - *5*: semi-harmonic

        In case harmonic types is artificial, following data is read:

        - Note: :ref:`byte`.
        - Accidental: :ref:`signed-byte`.
        - Octave: :ref:`byte`.

        If harmonic type is tapped:

        - Fret: :ref:`byte`.
        """
        harmonicType = self.readI8()
        if harmonicType == 1:
            harmonic = gp.NaturalHarmonic()
        elif harmonicType == 2:
            # C = 0, D = 2, E = 4, F = 5...
            # b = -1, # = 1
            # loco = 0, 8va = 1, 15ma = 2
            semitone = self.readU8()
            accidental = self.readI8()
            pitchClass = gp.PitchClass(semitone, accidental)
            octave = gp.Octave(self.readU8())
            harmonic = gp.ArtificialHarmonic(pitchClass, octave)
        elif harmonicType == 3:
            fret = self.readU8()
            harmonic = gp.TappedHarmonic(fret)
        elif harmonicType == 4:
            harmonic = gp.PinchHarmonic()
        elif harmonicType == 5:
            harmonic = gp.SemiHarmonic()
        return harmonic

    # Writing
    # =======

    def writeSong(self, song):
        self.writeVersion()
        self.writeClipboard(song.clipboard)

        self.writeInfo(song)
        self.writeLyrics(song.lyrics)
        self.writeRSEMasterEffect(song.masterEffect)
        self.writePageSetup(song.pageSetup)

        self.writeIntByteSizeString(song.tempoName)
        self.writeI32(song.tempo)

        if self.versionTuple > (5, 0, 0):
            self.writeBool(song.hideTempo)

        self.writeI8(song.key.value[0])
        self.writeI32(0)  # octave

        self.writeMidiChannels(song.tracks)

        self.writeDirections(song.measureHeaders)
        self.writeMasterReverb(song.masterEffect)

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
        super().writeClipboard(clipboard)
        self.writeI32(clipboard.startBeat)
        self.writeI32(clipboard.stopBeat)
        self.writeI32(int(clipboard.subBarCopy))

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
        self.writeNotice(song.notice)

    def writeRSEMasterEffect(self, masterEffect):
        if self.versionTuple > (5, 0, 0):
            masterEffect.volume = masterEffect.volume or 100
            masterEffect.reverb = masterEffect.reverb or 0
            masterEffect.equalizer = masterEffect.equalizer or gp.RSEEqualizer(knobs=[0] * 10, gain=0)
            self.writeI32(masterEffect.volume)
            self.writeI32(0)
            self.writeEqualizer(masterEffect.equalizer)

    def writeEqualizer(self, equalizer):
        for knob in equalizer.knobs:
            self.writeI8(self.packVolumeValue(knob))
        self.writeI8(self.packVolumeValue(equalizer.gain))

    def packVolumeValue(self, value):
        return int(-round(value, 1) * 10)

    def writePageSetup(self, setup):
        self.writeI32(setup.pageSize.x)
        self.writeI32(setup.pageSize.y)

        self.writeI32(setup.pageMargin.left)
        self.writeI32(setup.pageMargin.right)
        self.writeI32(setup.pageMargin.top)
        self.writeI32(setup.pageMargin.bottom)
        self.writeI32(int(setup.scoreSizeProportion * 100))

        self.writeU8(setup.headerAndFooter & 0xff)

        flags2 = 0x00
        if setup.headerAndFooter and gp.HeaderFooterElements.pageNumber != 0:
            flags2 |= 0x01
        self.writeU8(flags2)

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
            self.writeI16(signs.get(name, -1))

    def writeMasterReverb(self, masterEffect):
        if masterEffect is not None:
            self.writeI32(masterEffect.reverb)
        else:
            self.writeI32(0)

    def writeMeasureHeader(self, header, previous=None):
        flags = self.packMeasureHeaderFlags(header, previous)
        if previous is not None:
            self.placeholder(1)
        self.writeMeasureHeaderValues(header, flags)

    def packMeasureHeaderFlags(self, header, previous=None):
        flags = super().packMeasureHeaderFlags(header, previous)
        if previous is not None:
            if header.timeSignature.beams != previous.timeSignature.beams:
                flags |= 0x03
        return flags

    def writeMeasureHeaderValues(self, header, flags):
        header = attr.evolve(header, repeatClose=header.repeatClose+1)
        self.writeU8(flags)
        if flags & 0x01:
            self.writeI8(header.timeSignature.numerator)
        if flags & 0x02:
            self.writeI8(header.timeSignature.denominator.value)
        if flags & 0x08:
            self.writeI8(header.repeatClose)
        if flags & 0x20:
            self.writeMarker(header.marker)
        if flags & 0x40:
            self.writeI8(header.keySignature.value[0])
            self.writeI8(header.keySignature.value[1])
        if flags & 0x10:
            self.writeRepeatAlternative(header.repeatAlternative)
        if flags & 0x03:
            for beam in header.timeSignature.beams:
                self.writeU8(beam)
        if flags & 0x10 == 0:
            self.placeholder(1)
        self.writeU8(header.tripletFeel.value)

    def writeRepeatAlternative(self, repeatAlternative):
        self.writeU8(repeatAlternative & 255)

    def writeTracks(self, tracks):
        super().writeTracks(tracks)
        self.placeholder(2 if self.versionTuple == (5, 0, 0) else 1)

    def writeTrack(self, track, number):
        if number == 1 or self.versionTuple == (5, 0, 0):
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

        self.writeU8(flags1)

        self.writeByteSizeString(track.name, 40)
        self.writeI32(len(track.strings))
        for i in range(7):
            if i < len(track.strings):
                tuning = track.strings[i].value
            else:
                tuning = 0
            self.writeI32(tuning)
        self.writeI32(track.port)
        self.writeChannel(track)
        self.writeI32(track.fretCount)
        self.writeI32(track.offset)
        self.writeColor(track.color)

        flags2 = 0x0000
        if track.settings.tablature:
            flags2 |= 0x0001
        if track.settings.notation:
            flags2 |= 0x0002
        if track.settings.diagramsAreBelow:
            flags2 |= 0x0004
        if track.settings.showRhythm:
            flags2 |= 0x0008
        if track.settings.forceHorizontal:
            flags2 |= 0x0010
        if track.settings.forceChannels:
            flags2 |= 0x0020
        if track.settings.diagramList:
            flags2 |= 0x0040
        if track.settings.diagramsInScore:
            flags2 |= 0x0080
        if track.settings.autoLetRing:
            flags2 |= 0x0200
        if track.settings.autoBrush:
            flags2 |= 0x0400
        if track.settings.extendRhythmic:
            flags2 |= 0x0800
        self.writeI16(flags2)

        if track.rse is not None and track.rse.autoAccentuation is not None:
            self.writeU8(track.rse.autoAccentuation.value)
        else:
            self.writeU8(0)
        self.writeU8(track.channel.bank)

        self.writeTrackRSE(track.rse)

    def writeTrackRSE(self, trackRSE):
        self.writeU8(trackRSE.humanize)
        self.writeI32(0)
        self.writeI32(0)
        self.writeI32(100)
        self.placeholder(12)
        self.writeRSEInstrument(trackRSE.instrument)
        if self.versionTuple > (5, 0, 0):
            self.writeEqualizer(trackRSE.equalizer)
            self.writeRSEInstrumentEffect(trackRSE.instrument)

    def writeRSEInstrument(self, instrument):
        self.writeI32(instrument.instrument)
        self.writeI32(instrument.unknown)
        self.writeI32(instrument.soundBank)
        if self.versionTuple == (5, 0, 0):
            self.writeI16(instrument.effectNumber)
            self.placeholder(1)
        else:
            self.writeI32(instrument.effectNumber)

    def writeRSEInstrumentEffect(self, instrument):
        if self.versionTuple > (5, 0, 0):
            self.writeIntByteSizeString(instrument.effect)
            self.writeIntByteSizeString(instrument.effectCategory)

    def writeMeasure(self, measure):
        for number, voice in enumerate(measure.voices[:gp.Measure.maxVoices]):
            self._currentVoiceNumber = number + 1
            self.writeVoice(voice)
        self._currentVoiceNumber = None
        self.writeU8(measure.lineBreak.value)

    def writeBeat(self, beat):
        super().writeBeat(beat)
        flags2 = 0x0000
        if beat.display.breakBeam:
            flags2 |= 0x0001
        if beat.display.beamDirection == gp.VoiceDirection.down:
            flags2 |= 0x0002
        if beat.display.forceBeam:
            flags2 |= 0x0004
        if beat.display.beamDirection == gp.VoiceDirection.up:
            flags2 |= 0x0008
        if beat.octave == gp.Octave.ottava:
            flags2 |= 0x0010
        if beat.octave == gp.Octave.ottavaBassa:
            flags2 |= 0x0020
        if beat.octave == gp.Octave.quindicesima:
            flags2 |= 0x0040
        if beat.octave == gp.Octave.quindicesimaBassa:
            flags2 |= 0x0100
        if beat.display.tupletBracket == gp.TupletBracket.start:
            flags2 |= 0x0200
        if beat.display.tupletBracket == gp.TupletBracket.end:
            flags2 |= 0x0400
        if beat.display.breakSecondary:
            flags2 |= 0x0800
        if beat.display.breakSecondaryTuplet:
            flags2 |= 0x1000
        if beat.display.forceBracket:
            flags2 |= 0x2000
        self.writeI16(flags2)
        if flags2 & 0x0800:
            self.writeU8(beat.display.breakSecondary)

    def writeBeatStroke(self, stroke):
        super().writeBeatStroke(stroke.swapDirection())

    def writeMixTableChange(self, tableChange):
        super(gp4.GP4File, self).writeMixTableChange(tableChange)
        self.writeMixTableChangeFlags(tableChange)
        self.writeWahEffect(tableChange.wah)
        self.writeRSEInstrumentEffect(tableChange.rse)

    def writeMixTableChangeValues(self, tableChange):
        self.writeI8(tableChange.instrument.value if tableChange.instrument is not None else -1)
        self.writeRSEInstrument(tableChange.rse)
        if self.versionTuple == (5, 0, 0):
            self.placeholder(1)
        self.writeI8(tableChange.volume.value if tableChange.volume is not None else -1)
        self.writeI8(tableChange.balance.value if tableChange.balance is not None else -1)
        self.writeI8(tableChange.chorus.value if tableChange.chorus is not None else -1)
        self.writeI8(tableChange.reverb.value if tableChange.reverb is not None else -1)
        self.writeI8(tableChange.phaser.value if tableChange.phaser is not None else -1)
        self.writeI8(tableChange.tremolo.value if tableChange.tremolo is not None else -1)
        self.writeIntByteSizeString(tableChange.tempoName)
        self.writeI32(tableChange.tempo.value if tableChange.tempo is not None else -1)

    def writeMixTableChangeDurations(self, tableChange):
        if tableChange.volume is not None:
            self.writeI8(tableChange.volume.duration)
        if tableChange.balance is not None:
            self.writeI8(tableChange.balance.duration)
        if tableChange.chorus is not None:
            self.writeI8(tableChange.chorus.duration)
        if tableChange.reverb is not None:
            self.writeI8(tableChange.reverb.duration)
        if tableChange.phaser is not None:
            self.writeI8(tableChange.phaser.duration)
        if tableChange.tremolo is not None:
            self.writeI8(tableChange.tremolo.duration)
        if tableChange.tempo is not None:
            self.writeI8(tableChange.tempo.duration)
            if self.versionTuple > (5, 0, 0):
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
        self.writeU8(flags)

    def writeWahEffect(self, wah):
        if wah is not None:
            self.writeI8(wah.value)
        else:
            self.writeI8(gp.WahEffect.none.value)

    def writeNote(self, note):
        flags = self.packNoteFlags(note)
        self.writeU8(flags)
        if flags & 0x20:
            self.writeU8(self.getEnumValue(note.type))
        if flags & 0x10:
            value = self.packVelocity(note.velocity)
            self.writeI8(value)
        if flags & 0x20:
            fret = note.value if note.type != gp.NoteType.tie else 0
            self.writeI8(fret)
        if flags & 0x80:
            self.writeI8(self.getEnumValue(note.effect.leftHandFinger))
            self.writeI8(self.getEnumValue(note.effect.rightHandFinger))
        if flags & 0x01:
            self.writeF64(note.durationPercent)
        flags2 = 0x00
        if note.swapAccidentals:
            flags2 |= 0x02
        self.writeU8(flags2)
        if flags & 0x08:
            self.writeNoteEffects(note)

    def packNoteFlags(self, note):
        flags = super().packNoteFlags(note)
        if abs(note.durationPercent - 1.0) >= 1e-3:
            flags |= 0x01
        return flags

    def writeGrace(self, grace):
        self.writeU8(grace.fret)
        self.writeU8(self.packVelocity(grace.velocity))
        self.writeU8(grace.transition.value)
        self.writeU8(8 - grace.duration.bit_length())
        flags = 0x00
        if grace.isDead:
            flags |= 0x01
        if grace.isOnBeat:
            flags |= 0x02
        self.writeU8(flags)

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
        self.writeU8(slideType)

    def writeHarmonic(self, note, harmonic):
        self.writeI8(harmonic.type)
        if isinstance(harmonic, gp.ArtificialHarmonic):
            if not harmonic.pitch or not harmonic.octave:
                harmonic.pitch = gp.PitchClass(note.realValue % 12)
                harmonic.octave = gp.Octave.ottava
            self.writeU8(harmonic.pitch.just)
            self.writeI8(harmonic.pitch.accidental)
            self.writeU8(harmonic.octave.value)
        elif isinstance(harmonic, gp.TappedHarmonic):
            self.writeU8(harmonic.fret)
