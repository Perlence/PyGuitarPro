from __future__ import division

import struct
import copy

from enum import Enum


class GuitarProException(Exception):
    pass


class GPFileBase(object):
    DEFAULT_CHARSET = 'UTF-8'
    BEND_POSITION = 60
    BEND_SEMITONE = 25

    _supportedVersions = []
    version = None

    def __init__(self, data=None):
        self.data = data

    def close(self):
        self.data.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.data.close()

    # Reading
    # =======
    def skip(self, count):
        self.data.read(count)

    def read(self, fmt, count, default=None):
        try:
            result = struct.unpack(fmt, self.data.read(count))
            return result[0]
        except struct.error as e:
            if default is not None:
                return default
            else:
                raise e

    def readByte(self, default=None):
        return self.read('B', 1, default)

    def readSignedByte(self, default=None):
        return self.read('b', 1, default)

    def readBool(self, default=None):
        return self.read('?', 1, default)

    def readShort(self, default=None):
        return self.read('<h', 2, default)

    def readInt(self, default=None):
        return self.read('<i', 4, default)

    def readFloat(self, default=None):
        return self.read('<f', 4, default)

    def readDouble(self, default=None):
        return self.read('<d', 8, default)

    def readString(self, size, length=-2):
        if length == -2:
            length = size
        count = size if size > 0 else length
        s = self.data.read(count)
        return s[:(length if length >= 0 else size)]

    def readByteSizeString(self, size):
        return self.readString(size, self.readByte())

    def readIntSizeCheckByteString(self):
        d = self.readInt() - 1
        return self.readByteSizeString(d)

    def readByteSizeCheckByteString(self):
        return self.readByteSizeString(self.readByte() - 1)

    def readIntSizeString(self):
        return self.readString(self.readInt())

    def readVersion(self):
        if self.version is None:
            self.version = self.readByteSizeString(30)
        return self.version in self._supportedVersions

    def toChannelShort(self, data):
        value = max(-32768, min(32767, (data << 3) - 1))
        return max(value, -1) + 1

    # Writing
    # =======
    def placeholder(self, count, byte='\x00'):
        self.data.write(byte * count)

    def writeByte(self, data):
        packed = struct.pack('B', data)
        self.data.write(packed)

    def writeSignedByte(self, data):
        packed = struct.pack('b', data)
        self.data.write(packed)

    def writeBool(self, data):
        packed = struct.pack('?', data)
        self.data.write(packed)

    def writeShort(self, data):
        packed = struct.pack('<h', data)
        self.data.write(packed)

    def writeInt(self, data):
        packed = struct.pack('<i', data)
        self.data.write(packed)

    def writeFloat(self, data):
        packed = struct.pack('<f', data)
        self.data.write(packed)

    def writeDouble(self, data):
        packed = struct.pack('<d', data)
        self.data.write(packed)

    def writeString(self, data, size=None):
        if size is None:
            size = len(data)
        self.data.write(data)
        self.placeholder(size - len(data))

    def writeByteSizeString(self, data, size=None):
        if size is None:
            size = len(data)
        self.writeByte(len(data))
        return self.writeString(data, size)

    def writeIntSizeCheckByteString(self, data):
        # self.writeInt(len(data) - 1)
        self.writeInt(len(data) + 1)
        return self.writeByteSizeString(data)

    def writeByteSizeCheckByteString(self, data):
        # self.writeByte() - 1
        self.writeByte(len(data) + 1)
        return self.writeByteSizeString(data)

    def writeIntSizeString(self, data):
        self.writeInt(len(data))
        return self.writeString(data)

    def writeVersion(self, index=None):
        if self.version is not None:
            self.writeByteSizeString(self.version, 30)
        else:
            self.writeByteSizeString(self._supportedVersions[index], 30)

    def fromChannelShort(self, data):
        value = max(-128, min(127, (data >> 3) - 1))
        return value + 1

    # Misc
    # ====
    def getTiedNoteValue(self, stringIndex, track):
        measureCount = len(track.measures)
        if measureCount > 0:
            for m2 in range(measureCount):
                m = measureCount - 1 - m2
                measure = track.measures[m]
                for beat in reversed(measure.beats):
                    for voice in beat.voices:
                        if not voice.isEmpty:
                            for note in voice.notes:
                                if note.string == stringIndex:
                                    return note.value
        return -1


class GPObject(object):
    __attr__ = []

    class __metaclass__(type):

        def __new__(cls, name, bases, dict_):
            type_ = type.__new__(cls, name, bases, dict_)
            for name in dict_['__attr__']:
                setattr(type_, name, None)
            return type_

    def __init__(self, *args, **kwargs):
        for key, value in zip(self.__attr__, args):
            setattr(self, key, value)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __hash__(self):
        attrs = []
        for s in self.__attr__:
            attr = getattr(self, s)
            # convert lists to tuples
            if isinstance(attr, list):
                attrs.append(tuple(attr))
            else:
                attrs.append(attr)
        return hash(tuple(attrs))

    def __eq__(self, other):
        if other is None or not isinstance(other, self.__class__):
            return False
        for name in self.__attr__:
            if getattr(self, name) != getattr(other, name):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '<{}.{} object {}>'.format(self.__module__,
                                          self.__class__.__name__,
                                          hex(hash(self)))


class RepeatGroup(object):

    '''This class can store the information about a group of measures which are
    repeated.
    '''

    def __init__(self):
        self.measureHeaders = []
        self.closings = []
        self.openings = []
        self.isClosed = False

    def addMeasureHeader(self, h):
        if not len(self.openings):
            self.openings.append(h)

        self.measureHeaders.append(h)
        h.repeatGroup = self

        if h.repeatClose > 0:
            self.closings.append(h)
            self.isClosed = True
        # a new item after the header was closed? -> repeat alternative reopens
        # the group
        elif self.isClosed:
            self.isClosed = False
            self.openings.append(h)


class Song(GPObject):

    '''This is the toplevel node of the song model.

    It contains basic information about the stored song.
    '''
    __attr__ = ['title',
                'subtitle',
                'artist',
                'album',
                'words',
                'music',
                'copyright',
                'tab',
                'instructions',
                'notice',
                'lyrics',
                'pageSetup',
                'tempoName',
                'tempo',
                'hideTempo',
                'key',
                'octave',
                'tracks']

    def __init__(self, *args, **kwargs):
        '''Initializes a new instance of the Song class.
        '''
        self.measureHeaders = []
        self.tracks = []
        self.title = ''
        self.subtitle = ''
        self.artist = ''
        self.album = ''
        self.words = ''
        self.music = ''
        self.copyright = ''
        self.tab = ''
        self.instructions = ''
        self.notice = []
        self._currentRepeatGroup = RepeatGroup()
        self.hideTempo = False
        self.tempoName = ''
        self.tempo = None
        self.key = None
        self.octave = 0
        GPObject.__init__(self, *args, **kwargs)

    def addMeasureHeader(self, header):
        '''Adds a new measure header to the song.
        :param header: the measure header to add.
        '''
        header.song = self
        self.measureHeaders.append(header)

        # if the group is closed only the next upcoming header can
        # reopen the group in case of a repeat alternative, so we
        # remove the current group
        if header.isRepeatOpen or (self._currentRepeatGroup.isClosed and
                                   header.repeatAlternative <= 0):
            self._currentRepeatGroup = RepeatGroup()

        self._currentRepeatGroup.addMeasureHeader(header)

    def addTrack(self, track):
        '''Adds a new track to the song.
        '''
        track.song = self
        self.tracks.append(track)


class LyricLine(GPObject):

    '''A lyrics line.
    '''
    __attr__ = ['startingMeasure',
                'lyrics']

    def __init__(self, *args, **kwargs):
        self.startingMeasure = -1
        self.lyrics = ''
        GPObject.__init__(self, *args, **kwargs)


class Lyrics(GPObject):

    '''Represents a collection of lyrics lines for a track.
    '''
    __attr__ = ['trackChoice',
                'lines']

    MAX_LINE_COUNT = 5

    def __init__(self, *args, **kwargs):
        self.trackChoice = -1
        self.lines = []
        GPObject.__init__(self, *args, **kwargs)

    def __str__(self):
        full = ''
        for line in self.lines:
            if line is not None:
                full += line.lyrics + '\n'
        ret = full.strip()
        ret = ret.replace('\n', ' ')
        ret = ret.replace('\r', ' ')
        return ret


class Point(GPObject):

    '''A point construct using floating point coordinates.
    '''
    __attr__ = ['x', 'y']

    def __repr__(self):
        return 'Point({x}, {y})'.format(**vars(self))


class Padding(GPObject):

    '''A padding construct.
    '''
    __attr__ = ['right',
                'top',
                'left',
                'bottom']

    def __init__(self, *args, **kwargs):
        self.right = 0
        self.top = 0
        self.left = 0
        self.bottom = 0
        GPObject.__init__(self, *args, **kwargs)

    def __repr__(self):
        return 'Padding({right}, {top}, {left}, {bottom})'.format(**vars(self))


class HeaderFooterElements(object):

    '''A list of the elements which can be shown in the header and footer
    of a rendered song sheet. All values can be combined using bit-operators as they are flags.
    '''
    NONE = 0x0
    TITLE = 0x1
    SUBTITLE = 0x2
    ARTIST = 0x4
    ALBUM = 0x8
    WORDS = 0x10
    MUSIC = 0x20
    WORDS_AND_MUSIC = 0x40
    COPYRIGHT = 0x80
    PAGE_NUMBER = 0x100
    ALL = (NONE | TITLE | SUBTITLE | ARTIST | ALBUM | WORDS | MUSIC |
           WORDS_AND_MUSIC | COPYRIGHT | PAGE_NUMBER)


class PageSetup(GPObject):

    '''The page setup describes how the document is rendered.
    It contains page size, margins, paddings, and how the title elements are rendered.

    Following template vars are available for defining the page texts:
       %TITLE% - Will get replaced with Song.title
       %SUBTITLE% - Will get replaced with Song.subtitle
       %ARTIST% - Will get replaced with Song.artist
       %ALBUM% - Will get replaced with Song.album
       %WORDS% - Will get replaced with Song.words
       %MUSIC% - Will get replaced with Song.music
       %WORDSANDMUSIC% - Will get replaced with the according word and music values
       %COPYRIGHT% - Will get replaced with Song.copyright
       %N% - Will get replaced with the current page number (if supported by layout)
       %P% - Will get replaced with the number of pages (if supported by layout)
    '''
    __attr__ = ['pageSize',
                'pageMargin',
                'scoreSizeProportion',
                'headerAndFooter',
                'title',
                'subtitle',
                'artist',
                'album',
                'words',
                'music',
                'wordsAndMusic',
                'copyright',
                'pageNumber']

    def __init__(self, *args, **kwargs):
        self.pageSize = Point(210, 297)
        self.pageMargin = Padding(10, 15, 10, 10)
        self.scoreSizeProportion = 1
        self.headerAndFooter = HeaderFooterElements.ALL
        self.title = '%TITLE%'
        self.subtitle = '%SUBTITLE%'
        self.artist = '%ARTIST%'
        self.album = '%ALBUM%'
        self.words = 'Words by %WORDS%'
        self.music = 'Music by %MUSIC%'
        self.wordsAndMusic = 'Words & Music by %WORDSMUSIC%'
        self.copyright = ('Copyright %COPYRIGHT%\n'
                          'All Rights Reserved - International Copyright Secured')
        self.pageNumber = 'Page %N%/%P%'
        GPObject.__init__(self, *args, **kwargs)


class Tempo(GPObject):

    '''A song tempo in BPM.
    '''
    __attr__ = ['value']

    def __init__(self, *args, **kwargs):
        self.value = 120
        GPObject.__init__(self, *args, **kwargs)

    def __str__(self):
        return '{value}bpm'.format(**vars(self))

    @property
    def USQ(self):
        return self.tempoToUSQ(self.value)

    def tempoToUSQ(self, tempo):
        # BPM to microseconds per quarternote
        return int(60000000 / tempo)


class MidiChannel(GPObject):

    '''A midi channel describes playing data for a track
    '''
    __attr__ = ['channel',
                'effectChannel',
                'instrument',
                'volume',
                'balance',
                'chorus',
                'reverb',
                'phaser',
                'tremolo',
                'bank']

    DEFAULT_PERCUSSION_CHANNEL = 9
    DEFAULT_INSTRUMENT = 24
    DEFAULT_VOLUME = 104
    DEFAULT_BALANCE = 64
    DEFAULT_CHORUS = 0
    DEFAULT_REVERB = 0
    DEFAULT_PHASER = 0
    DEFAULT_TREMOLO = 0
    DEFAULT_BANK = 0

    def __init__(self, *args, **kwargs):
        self.channel = 0
        self.effectChannel = 0
        self.instrument = self.DEFAULT_INSTRUMENT
        self.volume = self.DEFAULT_VOLUME
        self.balance = self.DEFAULT_BALANCE
        self.chorus = self.DEFAULT_CHORUS
        self.reverb = self.DEFAULT_REVERB
        self.phaser = self.DEFAULT_PHASER
        self.tremolo = self.DEFAULT_TREMOLO
        self.bank = self.DEFAULT_BANK
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isPercussionChannel(self):
        return self.channel % 16 == self.DEFAULT_PERCUSSION_CHANNEL


class DirectionSign(GPObject):

    '''A navigation sign like Coda or Segno
    '''
    __attr__ = ['name']

    def __init__(self, *args, **kwargs):
        self.name = ''
        GPObject.__init__(self, *args, **kwargs)


class MeasureHeader(GPObject):

    '''A measure header contains metadata for measures over multiple tracks.
    '''
    __attr__ = ['hasDoubleBar',
                'keySignature',
                'keySignatureType',
                # 'number',
                # 'start',
                # 'realStart',
                'timeSignature',
                'tempo',
                'marker',
                'isRepeatOpen',
                'repeatAlternative',
                'repeatClose',
                'tripletFeel',
                'direction',
                'fromDirection']

    DEFAULT_KEY_SIGNATURE = 0

    def __init__(self, *args, **kwargs):
        self.number = 0
        self.start = Duration.QUARTER_TIME
        self.timeSignature = TimeSignature()
        self.keySignature = self.DEFAULT_KEY_SIGNATURE
        self.keySignatureType = 0
        self.keySignaturePresence = False
        self.tempo = Tempo()
        self.marker = None
        self.tripletFeel = TripletFeel.none
        self.isRepeatOpen = False
        self.repeatClose = -1
        self.repeatAlternative = 0
        self.realStart = -1
        self.direction = None
        self.fromDirection = None
        self.hasDoubleBar = False
        GPObject.__init__(self, *args, **kwargs)

    @property
    def hasMarker(self):
        return self.marker is not None

    @property
    def length(self):
        return (self.timeSignature.numerator *
                self.timeSignature.denominator.time)


class Color(GPObject):

    '''A RGB Color.
    '''
    __attr__ = ['r', 'g', 'b', 'a']

    def __init__(self, *args, **kwargs):
        self.a = 1
        GPObject.__init__(self, *args, **kwargs)

    def __repr__(self):
        if self.a == 1:
            return 'Color({r}, {g}, {b})'.format(**vars(self))
        else:
            return 'Color({r}, {g}, {b}, {a})'.format(**vars(self))

Color.Black = Color(0, 0, 0)
Color.Red = Color(255, 0, 0)


class Marker(GPObject):

    '''A marker annotation for beats
    '''
    __attr__ = ['title',
                'color']

    DEFAULT_COLOR = Color.Red
    DEFAULT_TITLE = 'Untitled'

    def __init__(self, *args, **kwargs):
        self.title = ''
        self.color = None
        self.measureHeader = None
        GPObject.__init__(self, *args, **kwargs)


class TrackSettings(GPObject):

    '''Settings of the track
    '''
    __attr__ = ['tablature',
                'notation',
                'diagramsAreBelow',
                'showRhythm',
                'forceHorizontal',
                'forceChannels',
                'diagramList',
                'diagramsInScore',
                'autoLetRing',
                'autoBrush',
                'extendRhythmic']

    def __init__(self, *args, **kwargs):
        self.tablature = True
        self.notation = True
        self.diagramsAreBelow = False
        self.showRhythm = False
        self.forceHorizontal = False
        self.forceChannels = False
        self.diagramList = True
        self.diagramsInScore = False
        self.autoLetRing = False
        self.autoBrush = False
        self.extendRhythmic = False
        GPObject.__init__(self, *args, **kwargs)


class Track(GPObject):

    '''A track contains multiple measures
    '''
    __attr__ = ['fretCount',
                # 'number',
                'offset',
                'isPercussionTrack',
                'is12StringedGuitarTrack',
                'isBanjoTrack',
                'isVisible',
                'isSolo',
                'isMute',
                'indicateTuning',
                'name',
                'measures',
                'strings',
                'port',
                'channel',
                'color',
                'settings']

    def __init__(self, *args, **kwargs):
        self.number = 0
        self.offset = 0
        self.isSolo = False
        self.isMute = False
        self.isVisible = True
        self.indicateTuning = True
        self.name = ''
        self.measures = []
        self.strings = []
        self.channel = MidiChannel()
        self.color = Color(255, 0, 0)
        self.settings = TrackSettings()
        self.fretCount = None
        self.port = 0
        self.isPercussionTrack = False
        self.isBanjoTrack = False
        self.is12StringedGuitarTrack = False
        GPObject.__init__(self, *args, **kwargs)

    def __str__(self):
        return '<guitarpro.base.Track {}>'.format(self.number)

    def addMeasure(self, measure):
        measure.track = self
        self.measures.append(measure)


class GuitarString(GPObject):

    '''A guitar string with a special tuning.
    '''
    __attr__ = ['number',
                'value']

    def __init__(self, *args, **kwargs):
        self.number = 0
        self.value = 0
        GPObject.__init__(self, *args, **kwargs)

    def __str__(self):
        notes = 'C C# D D# E F F# G G# A A# B'.split()
        octave, semitone = divmod(self.value, 12)
        return '{note}{octave}'.format(note=notes[semitone], octave=octave)


class Tuplet(GPObject):

    '''Represents a n:m tuplet
    '''
    __attr__ = ['enters',
                'times']

    def __init__(self, *args, **kwargs):
        self.enters = 1
        self.times = 1
        GPObject.__init__(self, *args, **kwargs)

    def convertTime(self, time):
        return int(time * self.times / self.enters)

Tuplet.NORMAL = Tuplet()


class Duration(GPObject):

    '''A duration.
    '''
    __attr__ = ['value',
                'isDotted',
                'isDoubleDotted',
                'tuplet']

    QUARTER_TIME = 960

    WHOLE = 1
    HALF = 2
    QUARTER = 4
    EIGHTH = 8
    SIXTEENTH = 16
    THIRTY_SECOND = 32
    SIXTY_FOURTH = 64

    # The time resulting with a 64th note and a 3/2 tuplet
    MIN_TIME = int(int(QUARTER_TIME * (4.0 / SIXTY_FOURTH)) * 2 / 3)

    def __init__(self, *args, **kwargs):
        self.value = self.QUARTER
        self.isDotted = False
        self.isDoubleDotted = False
        self.tuplet = Tuplet()
        GPObject.__init__(self, *args, **kwargs)

    @property
    def time(self):
        result = int(self.QUARTER_TIME * (4.0 / self.value))
        if self.isDotted:
            result += int(result / 2)
        elif self.isDoubleDotted:
            result += int((result / 4) * 3)
        return self.tuplet.convertTime(result)

    @property
    def index(self):
        index = 0
        value = self.value
        while True:
            value = (value >> 1)
            if value > 0:
                index += 1
            else:
                break
        return index

    @classmethod
    def fromTime(cls, time, minimum=None, diff=0):
        if minimum is None:
            minimum = Duration()
        duration = copy.deepcopy(minimum)
        tmp = Duration()
        tmp.value = cls.WHOLE
        tmp.isDotted = True
        while True:
            tmpTime = tmp.time
            if tmpTime - diff <= time:
                if abs(tmpTime - time) < abs(duration.time() - time):
                    duration = copy.deepcopy(tmp)
            if tmp.isDotted:
                tmp.isDotted = False
            elif tmp.tuplet == Tuplet.NORMAL:
                tmp.tuplet.enters = 3
                tmp.tuplet.times = 2
            else:
                tmp.value = tmp.value * 2
                tmp.isDotted = True
                tmp.tuplet.enters = 1
                tmp.tuplet.times = 1
            if tmp.value > cls.SIXTY_FOURTH:
                break
        return duration


class MeasureClef(object):

    '''A list of available clefs
    '''
    Treble = 0
    Bass = 1
    Tenor = 2
    Alto = 3


class LineBreak(object):

    '''A line break directive
    '''
    none = 0
    Break = 1
    Protect = 2


class Measure(GPObject):

    '''A measure contains multiple beats
    '''
    __attr__ = ['clef',
                'beats',
                'header',
                'lineBreak']

    DEFAULT_CLEF = MeasureClef.Treble

    def __init__(self, header, *args, **kwargs):
        self.header = header
        self.clef = self.DEFAULT_CLEF
        self.beats = []
        self.lineBreak = 0
        self.track = None
        GPObject.__init__(self, *args, **kwargs)

    def __repr__(self):
        return '<{}.{} object {} isEmpty={}>'.format(self.__module__,
                                                     self.__class__.__name__,
                                                     hex(hash(self)),
                                                     self.isEmpty)

    def __str__(self):
        measure = self.number()
        track = self.track.number
        return '<guitarpro.base.Measure {} on Track {}>'.format(measure, track)

    @property
    def isEmpty(self):
        return (len(self.beats) == 0 or all(beat.isRestBeat()
                                            for beat in self.beats))

    @property
    def end(self):
        return self.start() + self.length()

    @property
    def number(self):
        return self.header.number

    @property
    def keySignature(self):
        return self.header.keySignature

    @property
    def repeatClose(self):
        return self.header.repeatClose

    @property
    def start(self):
        return self.header.start

    @property
    def length(self):
        return self.header.length()

    @property
    def tempo(self):
        return self.header.tempo

    @property
    def timeSignature(self):
        return self.header.timeSignature

    @property
    def isRepeatOpen(self):
        return self.header.isRepeatOpen

    @property
    def tripletFeel(self):
        return self.header.tripletFeel

    @property
    def hasMarker(self):
        return self.header.hasMarker()

    @property
    def marker(self):
        return self.header.marker

    def addBeat(self, beat):
        beat.measure = self
        beat.index = len(self.beats)
        self.beats.append(beat)


class VoiceDirection(object):

    '''Voice directions indicating the direction of beams.
    '''
    none = 0
    Up = 1
    Down = 2


class Voice(GPObject):

    '''A voice contains multiple notes.
    '''
    __attr__ = ['duration',
                'notes',
                'index',
                'direction',
                'isEmpty']

    def __init__(self, *args, **kwargs):
        self.duration = Duration()
        self.notes = []
        self.direction = VoiceDirection.none
        self.isEmpty = True
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isRestVoice(self):
        return len(self.notes) == 0

    @property
    def hasVibrato(self):
        for note in self.notes:
            if note.effect.vibrato:
                return True
        return False

    @property
    def hasHarmonic(self):
        for note in self.notes:
            if note.effect.isHarmonic:
                return note.effect.harmonic.type
        return HarmonicType.none

    def addNote(self, note):
        note.voice = self
        self.notes.append(note)
        self.isEmpty = False


class BeatStrokeDirection(object):

    '''All beat stroke directions
    '''
    none = 0
    Up = 1
    Down = 2


class BeatStroke(GPObject):

    '''A stroke effect for beats.
    '''
    __attr__ = ['direction',
                'value']

    def __init__(self, *args, **kwargs):
        self.direction = BeatStrokeDirection.none
        self.value = 0
        GPObject.__init__(self, *args, **kwargs)

    def getIncrementTime(self, beat):
        duration = 0
        if self.value > 0:
            for voice in beat.voices:
                if voice.isEmpty:
                    continue
                currentDuration = voice.duration.time()
                if duration == 0 or currentDuration < duration:
                    duration = (currentDuration if currentDuration <= Duration.QUARTER_TIME
                                else Duration.QUARTER_TIME)
            if duration > 0:
                return round((duration / 8.0) * (4.0 / self.value))
        return 0


class BeatEffect(GPObject):

    '''This class contains all beat effects.
    '''
    __attr__ = ['stroke',
                'hasRasgueado',
                'pickStroke',
                'chord',
                'fadeIn',
                'tremoloBar',
                'mixTableChange',
                'tapping',
                'slapping',
                'popping']

    def __init__(self, *args, **kwargs):
        self.chord = None
        self.fadeIn = False
        self.hasPickStroke = False
        self.hasRasgueado = False
        self.mixTableChange = None
        self.pickStroke = 0
        self.popping = False
        self.presence = False
        self.slapping = False
        self.stroke = BeatStroke()
        self.tapping = False
        self.tremoloBar = None
        self.vibrato = False
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isChord(self):
        return self.chord is not None

    @property
    def isTremoloBar(self):
        return self.tremoloBar is not None

    @property
    def isSlapEffect(self):
        return self.tapping or self.slapping or self.popping

    @property
    def isDefault(self):
        default = BeatEffect()
        return (self.stroke == default.stroke and
                self.hasRasgueado == default.hasRasgueado and
                self.pickStroke == default.pickStroke and
                self.fadeIn == default.fadeIn and
                self.vibrato == default.vibrato and
                self.tremoloBar == default.tremoloBar and
                self.tapping == default.tapping and
                self.slapping == default.slapping and
                self.popping == default.popping)


class TupletBracket(object):
    none = 0
    Start = 1
    End = 2


class BeatDisplay(GPObject):

    '''Parameters of beat display.
    '''
    __attr__ = ['breakBeam',
                'forceBeam',
                'beamDirection',
                'tupletBracket',
                'breakSecondary',
                'breakSecondaryTuplet',
                'forceBracket']
    # 0x01: break beam with previous beat
    # 0x04: force beam with previous beat
    # 0x02: beam is down
    # 0x08: beam is up

    # 0x02: tuplet bracket start
    # 0x04: tuplet bracket end
    # 0x08: break secondary beams
    # 0x10: break secondary beams in tuplet
    # 0x20: force tuplet bracket

    def __init__(self, *args, **kwargs):
        self.breakBeam = False
        self.forceBeam = False
        self.beamDirection = VoiceDirection.none
        self.tupletBracket = TupletBracket.none
        self.breakSecondary = 0
        self.breakSecondaryTuplet = False
        self.forceBracket = False
        GPObject.__init__(self, *args, **kwargs)


class Octave(Enum):

    '''Octave signs.
    '''
    none = 0
    ottava = 1
    ottavaBassa = 2
    quindicesima = 3
    quindicesimaBassa = 4


class Beat(GPObject):

    '''A beat contains multiple voices.
    '''
    __attr__ = ['voices',
                'text',
                'start',
                'effect',
                'index',
                'octave',
                'display']

    MAX_VOICES = 2

    def __init__(self, *args, **kwargs):
        self.start = Duration.QUARTER_TIME
        self.effect = BeatEffect()
        self.text = None
        self.octave = Octave.none
        self.display = BeatDisplay()
        self.voices = []
        self.measure = None
        for i in range(Beat.MAX_VOICES):
            voice = Voice(i)
            voice.beat = self
            self.voices.append(voice)
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isRestBeat(self):
        for voice in self.voices:
            if not voice.isEmpty and not voice.isRestVoice():
                return False
        return True

    @property
    def realStart(self):
        offset = self.start - self.measure.start()
        return self.measure.header.realStart + offset

    def setText(self, text):
        text.beat = self
        self.text = text

    def setChord(self, chord):
        chord.beat = self
        self.effect.chord = chord

    def ensureVoices(self, count):
        while len(self.voices) < count:  # as long we have not enough voice
            # create new ones
            voice = Voice(len(self.voices))
            voice.beat = self
            self.voices.append(voice)

    @property
    def notes(self):
        notes = []
        for voice in self.voices:
            for note in voice.notes:
                notes.append(note)
        return notes


class HarmonicType(Enum):

    '''All harmonic effect types.
    '''
    none = 0
    natural = 1
    artificial = 2
    tapped = 3
    pinch = 4
    semi = 5


class HarmonicEffect(GPObject):

    '''A harmonic note effect.
    '''
    __attr__ = ['type',
                'data']

    # Lists all harmonic type groups
    # [i][0] -> The note played
    # [i][1] -> The according harmonic note to [i][0]
    NATURAL_FREQUENCIES = [[12, 12], [9, 28],
                           [5, 28], [7, 19], [4, 28], [3, 31]]


class GraceEffectTransition(Enum):

    '''All transition types for grace notes.
    '''
    #: No transition
    none = 0
    #: Slide from the grace note to the real one
    slide = 1
    #: Perform a bend from the grace note to the real one
    bend = 2
    #: Perform a hammer on
    hammer = 3


class GraceEffect(GPObject):

    '''A grace note effect.
    '''
    __attr__ = ['isDead',
                'duration',
                'velocity',
                'fret',
                'isOnBeat',
                'transition']

    def __init__(self, *args, **kwargs):
        '''Initializes a new instance of the GraceEffect class.
        '''
        self.fret = 0
        self.duration = 1
        self.velocity = Velocities.DEFAULT
        self.transition = GraceEffectTransition.none
        self.isOnBeat = False
        self.isDead = False
        GPObject.__init__(self, *args, **kwargs)

    @property
    def durationTime(self):
        '''Get the duration of the effect.
        '''
        return int(Duration.QUARTER_TIME / 16 * self.duration)


class TrillEffect(GPObject):

    '''A trill effect.
    '''
    __attr__ = ['fret',
                'duration']

    def __init__(self, *args, **kwargs):
        self.fret = 0
        self.duration = Duration()
        GPObject.__init__(self, *args, **kwargs)


class TremoloPickingEffect(GPObject):

    '''A tremolo picking effect.
    '''
    __attr__ = ['duration']

    def __init__(self, *args, **kwargs):
        self.duration = Duration()
        GPObject.__init__(self, *args, **kwargs)


class SlideType(Enum):

    '''Lists all supported slide types.
    '''
    intoFromBelow = -2
    intoFromAbove = -1
    none = 0
    shiftSlideTo = 1
    legatoSlideTo = 2
    outDownWards = 3
    outUpWards = 4


class NoteEffect(GPObject):

    '''Contains all effects which can be applied to one note.
    '''
    __attr__ = ['leftHandFinger',
                'rightHandFinger',
                'isFingering',
                'bend',
                'harmonic',
                'grace',
                'trill',
                'tremoloPicking',
                'vibrato',
                'deadNote',
                'slide',
                'hammer',
                'ghostNote',
                'accentuatedNote',
                'heavyAccentuatedNote',
                'palmMute',
                'staccato',
                'letRing']

    def __init__(self, *args, **kwargs):
        self.bend = None
        self.harmonic = None
        self.grace = None
        self.trill = None
        self.tremoloPicking = None
        self.vibrato = False
        self.deadNote = False
        self.slide = SlideType.none
        self.hammer = False
        self.ghostNote = False
        self.accentuatedNote = False
        self.heavyAccentuatedNote = False
        self.palmMute = False
        self.staccato = False
        self.letRing = False
        self.isFingering = False
        self.leftHandFinger = -1
        self.rightHandFinger = -1
        self.presence = False
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isBend(self):
        return self.bend is not None and len(self.bend.points)

    @property
    def isHarmonic(self):
        return self.harmonic is not None

    @property
    def isGrace(self):
        return self.grace is not None

    @property
    def isTrill(self):
        return self.trill is not None

    @property
    def isTremoloPicking(self):
        return self.tremoloPicking is not None

    @property
    def isDefault(self):
        default = NoteEffect()
        return (self.leftHandFinger == default.leftHandFinger and
                self.rightHandFinger == default.rightHandFinger and
                self.bend == default.bend and
                self.harmonic == default.harmonic and
                self.grace == default.grace and
                self.trill == default.trill and
                self.tremoloPicking == default.tremoloPicking and
                self.vibrato == default.vibrato and
                self.slide == default.slide and
                self.hammer == default.hammer and
                self.palmMute == default.palmMute and
                self.staccato == default.staccato and
                self.letRing == default.letRing)


class Note(GPObject):

    '''Describes a single note.
    '''
    __attr__ = ['value',
                'velocity',
                'string',
                'isTiedNote',
                'effect',
                'durationPercent',
                'swapAccidentals']

    def __init__(self, *args, **kwargs):
        self._realValue = -1
        self.value = 0
        self.velocity = Velocities.DEFAULT
        self.string = 1
        self.isTiedNote = False
        self.swapAccidentals = False
        self.effect = NoteEffect()
        self.duration = None
        self.tuplet = None
        self.durationPercent = 1.0
        self.voice = None
        GPObject.__init__(self, *args, **kwargs)

    @property
    def realValue(self):
        if self._realValue == -1:
            self._realValue = (self.value +
                               self.voice.beat.measure.track.strings[self.string - 1].value)
        return self._realValue


class Chord(GPObject):

    '''A chord annotation for beats.
    '''
    __attr__ = ['sharp',
                'root',
                'type',
                'net',
                'bass',
                'tonality',
                'add',
                'name',
                'fifth',
                'ninth',
                'eleventh',
                'firstFret',
                'strings',
                'barres',
                'omissions',
                'fingerings',
                'show']

    def __init__(self, length, *args, **kwargs):
        self.strings = [-1] * length
        self.name = ''
        GPObject.__init__(self, *args, **kwargs)

    @property
    def notes(self):
        return filter(lambda string: string >= 0, self.strings)


class ChordType(Enum):
    major = 0
    seventh = 1
    majorSeventh = 2
    sixth = 3
    minor = 4
    minorSeventh = 5
    minorMajor = 6
    minorSixth = 7
    suspendedSecond = 8
    suspendedFourth = 9
    seventhSuspendedSecond = 10
    seventhSuspendedFourth = 11
    diminished = 12
    augmented = 13
    power = 14


class Barre(GPObject):
    __attr__ = ['fret', 'start', 'end']

    def __init__(self, *args, **kwargs):
        self.start = 0
        self.end = 0
        GPObject.__init__(self, *args, **kwargs)

    @property
    def range(self):
        return self.start, self.end


class Fingering(Enum):
    unknown = -2
    open = -1
    thumb = 0
    index = 1
    middle = 2
    annular = 3
    little = 4


class ChordTonality(Enum):
    perfect = 0
    augmented = 1
    diminished = 2


class BeatText(GPObject):

    '''A text annotation for beats.
    '''
    __attr__ = ['value']

    def __init__(self, *args, **kwargs):
        self.value = ''
        self.beat = None
        GPObject.__init__(self, *args, **kwargs)


class MixTableItem(GPObject):

    '''A mixtablechange describes several track changes.
    '''
    __attr__ = ['value',
                'duration',
                'allTracks']

    def __init__(self, *args, **kwargs):
        self.value = 0
        self.duration = 0
        self.allTracks = False
        GPObject.__init__(self, *args, **kwargs)


class WahEffect(GPObject):
    __attr__ = ['value',
                'enabled',
                'display']

    def __init__(self, *args, **kwargs):
        self.value = 0
        self.enabled = False
        self.display = False
        GPObject.__init__(self, *args, **kwargs)


class MixTableChange(GPObject):

    '''A MixTableChange describes several track changes.
    '''
    __attr__ = ['instrument',
                'volume',
                'balance',
                'chorus',
                'reverb',
                'phaser',
                'tremolo',
                'tempoName',
                'tempo',
                'hideTempo',
                'wah']

    def __init__(self, *args, **kwargs):
        self.instrument = MixTableItem()
        self.volume = MixTableItem()
        self.balance = MixTableItem()
        self.chorus = MixTableItem()
        self.reverb = MixTableItem()
        self.phaser = MixTableItem()
        self.tremolo = MixTableItem()
        self.tempoName = ''
        self.tempo = MixTableItem()
        self.hideTempo = True
        self.wah = WahEffect()
        GPObject.__init__(self, *args, **kwargs)


class BendType(Enum):

    '''All Bend presets
    '''
    # Bends
    #: No Preset
    none = 0
    #: A simple bend
    bend = 1
    #: A bend and release afterwards
    bendRelease = 2
    #: A bend, then release and rebend
    bendReleaseBend = 3
    #: Prebend
    prebend = 4
    #: Prebend and then release
    prebendRelease = 5

    # Tremolobar
    #: Dip the bar down and then back up
    dip = 6
    #: Dive the bar
    dive = 7
    #: Release the bar up
    releaseUp = 8
    #: Dip the bar up and then back down
    invertedDip = 9
    #: Return the bar
    return_ = 10
    #: Release the bar down
    releaseDown = 11


class BendPoint(GPObject):

    '''A single point within the BendEffect or TremoloBarEffect
    '''
    __attr__ = ['position',
                'value',
                'vibrato']

    def __init__(self, *args, **kwargs):
        '''Initializes a new instance of the BendPoint class.
        '''
        self.position = 0
        self.vibrato = False
        GPObject.__init__(self, *args, **kwargs)

    def getTime(self, duration):
        '''Gets the exact time when the point need to be played (midi)
        :param duration: the full duration of the effect
        '''
        return int(duration * self.position / BendEffect.MAX_POSITION)


class BendEffect(GPObject):

    '''This effect is used for creating string bendings and whammybar effects (tremolo bar)
    '''
    __attr__ = ['type',
                'value',
                'points']

    #: The note offset per bend point offset.
    SEMITONE_LENGTH = 1
    #: The max position of the bend points (x axis)
    MAX_POSITION = 12
    #: The max value of the bend points (y axis)
    MAX_VALUE = SEMITONE_LENGTH * 12

    def __init__(self, *args, **kwargs):
        '''Initializes a new instance of the BendEffect
        '''
        self.type = BendType.none
        self.value = 0
        self.points = []
        GPObject.__init__(self, *args, **kwargs)


class TripletFeel(Enum):

    '''A list of different triplet feels
    '''
    none = 0
    eighth = 1
    sixteenth = 2


class TimeSignature(GPObject):

    '''A time signature.
    '''
    __attr__ = ['numerator',
                'denominator',
                'beams']

    def __init__(self, *args, **kwargs):
        self.numerator = 4
        self.denominator = Duration()
        self.beams = (0, 0, 0, 0)
        GPObject.__init__(self, *args, **kwargs)


class Velocities(object):

    '''A list of velocities / dynamics
    '''
    MIN_VELOCITY = 15
    VELOCITY_INCREMENT = 16
    PIANO_PIANISSIMO = MIN_VELOCITY
    PIANISSIMO = MIN_VELOCITY + VELOCITY_INCREMENT
    PIANO = MIN_VELOCITY + (VELOCITY_INCREMENT * 2)
    MEZZO_PIANO = MIN_VELOCITY + (VELOCITY_INCREMENT * 3)
    MEZZO_FORTE = MIN_VELOCITY + (VELOCITY_INCREMENT * 4)
    FORTE = MIN_VELOCITY + (VELOCITY_INCREMENT * 5)
    FORTISSIMO = MIN_VELOCITY + (VELOCITY_INCREMENT * 6)
    FORTE_FORTISSIMO = MIN_VELOCITY + (VELOCITY_INCREMENT * 7)
    DEFAULT = FORTE
