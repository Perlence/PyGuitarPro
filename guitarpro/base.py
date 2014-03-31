from __future__ import division

import struct

from six import add_metaclass, string_types
from enum import Enum


class GPException(Exception):
    pass


class GPFileBase(object):
    bendPosition = 60
    bendSemitone = 25

    _supportedVersions = []
    _versionTuple = None
    version = None

    def __init__(self, data=None, encoding=None):
        self.data = data
        self.encoding = encoding or 'cp1252'

    def close(self):
        self.data.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    # Reading
    # =======

    def skip(self, count):
        return self.data.read(count)

    def read(self, fmt, count, default=None):
        try:
            result = struct.unpack(fmt, self.data.read(count))
            return result[0]
        except struct.error as e:
            if default is not None:
                return default
            else:
                raise e

    def readByte(self, count=1, default=None):
        """Read 1 byte *count* times."""
        args = ('B', 1)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readSignedByte(self, count=1, default=None):
        """Read 1 signed byte *count* times."""
        args = ('b', 1)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readBool(self, count=1, default=None):
        """Read 1 byte *count* times as a boolean."""
        args = ('?', 1)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readShort(self, count=1, default=None):
        """Read 2 little-endian bytes *count* times as a short integer."""
        args = ('<h', 2)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readInt(self, count=1, default=None):
        """Read 4 little-endian bytes *count* times as an integer."""
        args = ('<i', 4)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readFloat(self, count=1, default=None):
        """Read 4 little-endian bytes *count* times as a float."""
        args = ('<f', 4)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readDouble(self, count=1, default=None):
        """Read 8 little-endian bytes *count* times as a double."""
        args = ('<d', 8)
        return (self.read(*args, default=default) if count == 1 else
                [self.read(*args, default=default) for i in range(count)])

    def readString(self, size, length=None):
        if length is None:
            length = size
        count = size if size > 0 else length
        s = self.data.read(count)
        ss = s[:(length if length >= 0 else size)]
        return ss.decode(self.encoding)

    def readByteSizeString(self, size):
        """Read length of the string stored in 1 byte and followed by character
        bytes."""
        return self.readString(size, self.readByte())

    def readIntSizeString(self):
        """Read length of the string stored in 1 integer and followed by
        character bytes."""
        return self.readString(self.readInt())

    def readIntByteSizeString(self):
        """Read length of the string increased by 1 and stored in 1 integer
        followed by length of the string in 1 byte and finally followed by
        character bytes.
        """
        d = self.readInt() - 1
        return self.readByteSizeString(d)

    def readVersion(self):
        if self.version is None:
            self.version = self.readByteSizeString(30)
        return self.version in self._supportedVersions

    @property
    def versionTuple(self):
        if self._versionTuple is None:
            self._versionTuple = tuple(map(int, self.version[-4:].split('.')))
        return self._versionTuple

    # Writing
    # =======

    def placeholder(self, count, byte=b'\x00'):
        self.data.write(byte * count)

    def writeByte(self, data):
        packed = struct.pack('B', int(data))
        self.data.write(packed)

    def writeSignedByte(self, data):
        packed = struct.pack('b', int(data))
        self.data.write(packed)

    def writeBool(self, data):
        packed = struct.pack('?', bool(data))
        self.data.write(packed)

    def writeShort(self, data):
        packed = struct.pack('<h', int(data))
        self.data.write(packed)

    def writeInt(self, data):
        packed = struct.pack('<i', int(data))
        self.data.write(packed)

    def writeFloat(self, data):
        packed = struct.pack('<f', float(data))
        self.data.write(packed)

    def writeDouble(self, data):
        packed = struct.pack('<d', float(data))
        self.data.write(packed)

    def writeString(self, data, size=None):
        if size is None:
            size = len(data)
        self.data.write(data.encode(self.encoding))
        self.placeholder(size - len(data))

    def writeByteSizeString(self, data, size=None):
        if size is None:
            size = len(data)
        self.writeByte(len(data))
        return self.writeString(data, size)

    def writeIntSizeString(self, data):
        self.writeInt(len(data))
        return self.writeString(data)

    def writeIntByteSizeString(self, data):
        self.writeInt(len(data) + 1)
        return self.writeByteSizeString(data)

    def writeVersion(self, index=None):
        if self.version is not None:
            self.writeByteSizeString(self.version, 30)
        else:
            self.writeByteSizeString(self._supportedVersions[index], 30)


class GPObjectMeta(type):

    def __new__(cls, name, bases, dict_):
        type_ = type.__new__(cls, name, bases, dict_)
        for name in dict_['__attr__']:
            try:
                getattr(type_, name)
            except AttributeError:
                setattr(type_, name, None)
        return type_


@add_metaclass(GPObjectMeta)
class GPObject(object):

    """GPObject is the base of all Guitar Pro objects.

    GPObjects are able to compute hash and be compared one to other.
    To create new GPObject subclass all attribute names must specified in tuple
    :attr:`GPObject.__attr__`. The order of attributes is important as it is
    provides positional arguments for :meth:`GPObject.__init__`.

    """
    __attr__ = ()

    def __init__(self, *args, **kwargs):
        for key, value in zip(self.__attr__, args):
            setattr(self, key, value)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __hash__(self):
        attrs = []
        for name in self.__attr__:
            attr = getattr(self, name)
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

    def __iter__(self):
        for name in self.__attr__:
            yield getattr(self, name)


class RepeatGroup(object):

    """This class can store the information about a group of measures which are
    repeated."""

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

    """This is the top-level node of the song model.

    It contains basic information about the stored song.

    """
    __attr__ = ('title', 'subtitle', 'artist', 'album', 'words', 'music',
                'copyright', 'tab', 'instructions', 'notice', 'lyrics',
                'pageSetup', 'tempoName', 'tempo', 'hideTempo', 'key',
                'tracks', 'masterEffect')

    def __init__(self, *args, **kwargs):
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
        self.key = KeySignature.CMajor
        GPObject.__init__(self, *args, **kwargs)

    def addMeasureHeader(self, header):
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
        track.song = self
        self.tracks.append(track)


class LyricLine(GPObject):

    """A lyrics line."""

    __attr__ = ('startingMeasure', 'lyrics')

    def __init__(self, *args, **kwargs):
        self.startingMeasure = 1
        self.lyrics = ''
        GPObject.__init__(self, *args, **kwargs)


class Lyrics(GPObject):

    """Represents a collection of lyrics lines for a track."""

    __attr__ = ('trackChoice', 'lines')

    maxLineCount = 5

    def __init__(self, *args, **kwargs):
        self.trackChoice = -1
        self.lines = []
        for __ in range(Lyrics.maxLineCount):
            self.lines.append(LyricLine())
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

    """A point construct using floating point coordinates."""

    __attr__ = ('x', 'y')

    def __repr__(self):
        return 'Point({x}, {y})'.format(**vars(self))


class Padding(GPObject):

    """A padding construct."""

    __attr__ = ('right', 'top', 'left', 'bottom')

    def __init__(self, *args, **kwargs):
        GPObject.__init__(self, *args, **kwargs)

    def __repr__(self):
        return 'Padding({right}, {top}, {left}, {bottom})'.format(**vars(self))


class HeaderFooterElements(object):

    """A list of the elements which can be shown in the header and footer of a
    rendered song sheet.

    All values can be combined using bit-operators as they are flags.

    """
    none = 0x000
    title = 0x001
    subtitle = 0x002
    artist = 0x004
    album = 0x008
    words = 0x010
    music = 0x020
    wordsAndMusic = 0x040
    copyright = 0x080
    pageNumber = 0x100
    all = (title | subtitle | artist | album | words | music | wordsAndMusic |
           copyright | pageNumber)


class PageSetup(GPObject):

    """The page setup describes how the document is rendered.

    Page setup contains page size, margins, paddings, and how the title
    elements are rendered.

    Following template vars are available for defining the page texts:

    -   ``%title%``: will be replaced with Song.title
    -   ``%subtitle%``: will be replaced with Song.subtitle
    -   ``%artist%``: will be replaced with Song.artist
    -   ``%album%``: will be replaced with Song.album
    -   ``%words%``: will be replaced with Song.words
    -   ``%music%``: will be replaced with Song.music
    -   ``%WORDSANDMUSIC%``: will be replaced with the according word and
        music values
    -   ``%copyright%``: will be replaced with Song.copyright
    -   ``%N%``: will be replaced with the current page number (if supported
        by layout)
    -   ``%P%``: will be replaced with the number of pages (if supported by
        layout)

    """
    __attr__ = ('pageSize', 'pageMargin', 'scoreSizeProportion',
                'headerAndFooter', 'title', 'subtitle', 'artist', 'album',
                'words', 'music', 'wordsAndMusic', 'copyright', 'pageNumber')

    def __init__(self, *args, **kwargs):
        self.pageSize = Point(210, 297)
        self.pageMargin = Padding(10, 15, 10, 10)
        self.scoreSizeProportion = 1
        self.headerAndFooter = HeaderFooterElements.all
        self.title = '%title%'
        self.subtitle = '%subtitle%'
        self.artist = '%artist%'
        self.album = '%album%'
        self.words = 'Words by %words%'
        self.music = 'Music by %music%'
        self.wordsAndMusic = 'Words & Music by %WORDSMUSIC%'
        self.copyright = ('Copyright %copyright%\n'
                          'All Rights Reserved - International Copyright Secured')
        self.pageNumber = 'Page %N%/%P%'
        GPObject.__init__(self, *args, **kwargs)


class Tempo(GPObject):

    """A song tempo in BPM."""

    __attr__ = ('value',)

    def __init__(self, *args, **kwargs):
        self.value = 120
        GPObject.__init__(self, *args, **kwargs)

    def __str__(self):
        return '{value}bpm'.format(**vars(self))


class MidiChannel(GPObject):

    """A MIDI channel describes playing data for a track."""

    __attr__ = ('channel', 'effectChannel', 'instrument', 'volume', 'balance',
                'chorus', 'reverb', 'phaser', 'tremolo', 'bank')

    DEFAULT_PERCUSSION_CHANNEL = 9

    def __init__(self, *args, **kwargs):
        self.channel = 0
        self.effectChannel = 0
        self.instrument = 24
        self.volume = 104
        self.balance = 64
        self.chorus = 0
        self.reverb = 0
        self.phaser = 0
        self.tremolo = 0
        self.bank = 0
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isPercussionChannel(self):
        return self.channel % 16 == self.DEFAULT_PERCUSSION_CHANNEL


class DirectionSign(GPObject):

    """A navigation sign like Coda or Segno."""

    __attr__ = ('name',)

    def __init__(self, *args, **kwargs):
        self.name = ''
        GPObject.__init__(self, *args, **kwargs)


class MeasureHeader(GPObject):

    """A measure header contains metadata for measures over multiple tracks."""

    __attr__ = ('hasDoubleBar', 'keySignature', 'timeSignature', 'tempo',
                'marker', 'isRepeatOpen', 'repeatAlternative', 'repeatClose',
                'tripletFeel', 'direction', 'fromDirection')

    def __init__(self, *args, **kwargs):
        self.number = 0
        self.start = Duration.quarterTime
        self.timeSignature = TimeSignature()
        self.keySignature = KeySignature.CMajor
        self.tempo = Tempo()
        self.tripletFeel = TripletFeel.none
        self.isRepeatOpen = False
        self.repeatClose = -1
        self.repeatAlternative = 0
        self.realStart = -1
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

    """An RGB Color."""

    __attr__ = ('r', 'g', 'b', 'a')

    def __init__(self, *args, **kwargs):
        self.a = 1
        GPObject.__init__(self, *args, **kwargs)

    def __repr__(self):
        if self.a == 1:
            return 'Color({r}, {g}, {b})'.format(**vars(self))
        else:
            return 'Color({r}, {g}, {b}, {a})'.format(**vars(self))

Color.black = Color(0, 0, 0)
Color.red = Color(255, 0, 0)


class Marker(GPObject):

    """A marker annotation for beats."""

    __attr__ = ('title', 'color')

    def __init__(self, *args, **kwargs):
        self.title = 'Section'
        self.color = Color.red
        self.measureHeader = None
        GPObject.__init__(self, *args, **kwargs)


class TrackSettings(GPObject):

    """Settings of the track."""

    __attr__ = ('tablature', 'notation', 'diagramsAreBelow', 'showRhythm',
                'forceHorizontal', 'forceChannels', 'diagramList',
                'diagramsInScore', 'autoLetRing', 'autoBrush',
                'extendRhythmic')

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

    """A track contains multiple measures."""

    __attr__ = ('fretCount', 'offset', 'isPercussionTrack',
                'is12StringedGuitarTrack', 'isBanjoTrack', 'isVisible',
                'isSolo', 'isMute', 'indicateTuning', 'name', 'measures',
                'strings', 'port', 'channel', 'color', 'settings', 'useRSE',
                'rse')

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
        self.port = 0
        self.isPercussionTrack = False
        self.isBanjoTrack = False
        self.is12StringedGuitarTrack = False
        self.useRSE = False
        GPObject.__init__(self, *args, **kwargs)

    def __str__(self):
        return '<guitarpro.base.Track {}>'.format(self.number)

    def addMeasure(self, measure):
        measure.track = self
        self.measures.append(measure)


class GuitarString(GPObject):

    """A guitar string with a special tuning."""

    __attr__ = ('number', 'value')

    def __str__(self):
        notes = 'C C# D D# E F F# G G# A A# B'.split()
        octave, semitone = divmod(self.value, 12)
        return '{note}{octave}'.format(note=notes[semitone], octave=octave)


class Tuplet(GPObject):

    """Represents a n:m tuplet."""

    __attr__ = ('enters', 'times')

    def __init__(self, *args, **kwargs):
        self.enters = 1
        self.times = 1
        GPObject.__init__(self, *args, **kwargs)

    def convertTime(self, time):
        return int(time * self.times / self.enters)


class Duration(GPObject):

    """A duration."""

    __attr__ = ('value', 'isDotted', 'isDoubleDotted', 'tuplet')

    quarterTime = 960

    whole = 1
    half = 2
    quarter = 4
    eighth = 8
    sixteenth = 16
    thirtySecond = 32
    sixtyFourth = 64
    hundredTwentyEighth = 128

    # The time resulting with a 64th note and a 3/2 tuplet
    minTime = int(int(quarterTime * (4 / sixtyFourth)) * 2 / 3)

    def __init__(self, *args, **kwargs):
        self.value = self.quarter
        self.isDotted = False
        self.isDoubleDotted = False
        self.tuplet = Tuplet()
        GPObject.__init__(self, *args, **kwargs)

    @property
    def time(self):
        result = int(self.quarterTime * (4.0 / self.value))
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
        duration = minimum
        tmp = Duration()
        tmp.value = cls.whole
        tmp.isDotted = True
        while True:
            tmpTime = tmp.time
            if tmpTime - diff <= time:
                if abs(tmpTime - time) < abs(duration.time - time):
                    duration = tmp
            if tmp.isDotted:
                tmp.isDotted = False
            elif tmp.tuplet == Tuplet():
                tmp.tuplet.enters = 3
                tmp.tuplet.times = 2
            else:
                tmp.value = tmp.value * 2
                tmp.isDotted = True
                tmp.tuplet.enters = 1
                tmp.tuplet.times = 1
            if tmp.value > cls.sixtyFourth:
                break
        return duration


class MeasureClef(Enum):

    """A list of available clefs."""

    treble = 0
    bass = 1
    tenor = 2
    alto = 3


class LineBreak(Enum):

    """A line break directive."""

    #: No line break.
    none = 0
    #: Break line.
    break_ = 1
    #: Protect the line from breaking.
    protect = 2


class Measure(GPObject):

    """A measure contains multiple voices of beats."""

    __attr__ = ('clef', 'voices', 'header', 'lineBreak')

    maxVoices = 2

    def __init__(self, header, *args, **kwargs):
        self.header = header
        self.clef = MeasureClef.treble
        self.voices = []
        self.lineBreak = LineBreak.none
        GPObject.__init__(self, *args, **kwargs)

    def __repr__(self):
        return '<{}.{} object {} isEmpty={}>'.format(self.__module__,
                                                     self.__class__.__name__,
                                                     hex(hash(self)),
                                                     self.isEmpty)

    def __str__(self):
        measure = self.number
        track = self.track.number
        return '<guitarpro.base.Measure {} on Track {}>'.format(measure, track)

    @property
    def isEmpty(self):
        return (len(self.beats) == 0 or all(voice.isEmpty
                                            for voice in self.voices))

    @property
    def end(self):
        return self.start + self.length

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
        return self.header.length

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
        return self.header.hasMarker

    @property
    def marker(self):
        return self.header.marker

    def addVoice(self, voice):
        voice.measure = self
        self.voices.append(voice)


class VoiceDirection(Enum):

    """Voice directions indicating the direction of beams."""

    none = 0
    up = 1
    down = 2


class Voice(GPObject):

    """A voice contains multiple beats."""

    __attr__ = ('beats', 'direction', 'isEmpty')

    def __init__(self, *args, **kwargs):
        self.beats = []
        self.direction = VoiceDirection.none
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isEmpty(self):
        return len(self.beats) == 0

    def addBeat(self, beat):
        beat.voice = self
        self.beats.append(beat)


class BeatStrokeDirection(Enum):

    """All beat stroke directions."""

    none = 0
    up = 1
    down = 2


class BeatStroke(GPObject):

    """A stroke effect for beats."""

    __attr__ = ('direction', 'value')

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
                    duration = (currentDuration if currentDuration <= Duration.quarterTime
                                else Duration.quarterTime)
            if duration > 0:
                return round((duration / 8.0) * (4.0 / self.value))
        return 0

    def swapDirection(self):
        if self.direction == BeatStrokeDirection.up:
            direction = BeatStrokeDirection.down
        elif self.direction == BeatStrokeDirection.down:
            direction = BeatStrokeDirection.up
        return BeatStroke(direction, self.value)


class SlapEffect(Enum):

    """Characteristic of articulation."""

    #: No slap effect.
    none = 0

    #: Tapping.
    tapping = 1

    #: Slapping.
    slapping = 2

    #: Popping.
    popping = 3


class BeatEffect(GPObject):

    """This class contains all beat effects."""

    __attr__ = ('stroke', 'hasRasgueado', 'pickStroke', 'chord', 'fadeIn',
                'tremoloBar', 'mixTableChange', 'slapEffect', 'vibrato')

    def __init__(self, *args, **kwargs):
        self.fadeIn = False
        self.pickStroke = BeatStrokeDirection.none
        self.hasRasgueado = False
        self.stroke = BeatStroke()
        self.slapEffect = SlapEffect.none
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
        return self.slapEffect != SlapEffect.none

    @property
    def hasPickStroke(self):
        return self.pickStroke != BeatStrokeDirection.none

    @property
    def isDefault(self):
        default = BeatEffect()
        return (self.stroke == default.stroke and
                self.hasRasgueado == default.hasRasgueado and
                self.pickStroke == default.pickStroke and
                self.fadeIn == default.fadeIn and
                self.vibrato == default.vibrato and
                self.tremoloBar == default.tremoloBar and
                self.slapEffect == default.slapEffect)


class TupletBracket(Enum):
    none = 0
    start = 1
    end = 2


class BeatDisplay(GPObject):

    """Parameters of beat display."""

    __attr__ = ('breakBeam', 'forceBeam', 'beamDirection', 'tupletBracket',
                'breakSecondary', 'breakSecondaryTuplet', 'forceBracket')

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

    """Octave signs."""

    none = 0
    ottava = 1
    quindicesima = 2
    ottavaBassa = 3
    quindicesimaBassa = 4


class Beat(GPObject):

    """A beat contains multiple voices."""

    __attr__ = ('notes', 'duration', 'text', 'start', 'effect', 'index',
                'octave', 'display', 'status')

    def __init__(self, *args, **kwargs):
        self.duration = Duration()
        self.start = Duration.quarterTime
        self.effect = BeatEffect()
        self.octave = Octave.none
        self.display = BeatDisplay()
        self.notes = []
        self.status = True
        GPObject.__init__(self, *args, **kwargs)

    @property
    def realStart(self):
        offset = self.start - self.measure.start()
        return self.measure.header.realStart + offset

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
                return note.effect.harmonic

    def addNote(self, note):
        note.beat = self
        self.notes.append(note)


class BeatStatus(Enum):
    empty = 0
    normal = 1
    rest = 2


class HarmonicEffect(GPObject):

    """A harmonic note effect."""

    __attr__ = ('type',)


class NaturalHarmonic(HarmonicEffect):
    __attr__ = ('type',)

    type = 1


class ArtificialHarmonic(HarmonicEffect):
    __attr__ = ('pitch', 'octave', 'type')

    type = 2


class TappedHarmonic(HarmonicEffect):
    __attr__ = ('fret', 'type')

    type = 3


class PinchHarmonic(HarmonicEffect):
    __attr__ = ('type',)

    type = 4


class SemiHarmonic(HarmonicEffect):
    __attr__ = ('type',)

    type = 5


class GraceEffectTransition(Enum):

    """All transition types for grace notes."""

    #: No transition.
    none = 0

    #: Slide from the grace note to the real one.
    slide = 1

    #: Perform a bend from the grace note to the real one.
    bend = 2

    #: Perform a hammer on.
    hammer = 3


class GraceEffect(GPObject):

    """A grace note effect."""

    __attr__ = ('isDead', 'duration', 'velocity', 'fret', 'isOnBeat',
                'transition')

    def __init__(self, *args, **kwargs):
        """Initializes a new instance of the GraceEffect class."""
        self.fret = 0
        self.duration = 1
        self.velocity = Velocities.default
        self.transition = GraceEffectTransition.none
        self.isOnBeat = False
        self.isDead = False
        GPObject.__init__(self, *args, **kwargs)

    @property
    def durationTime(self):
        """Get the duration of the effect."""
        return int(Duration.quarterTime / 16 * self.duration)


class TrillEffect(GPObject):

    """A trill effect."""

    __attr__ = ('fret', 'duration')

    def __init__(self, *args, **kwargs):
        self.fret = 0
        self.duration = Duration()
        GPObject.__init__(self, *args, **kwargs)


class TremoloPickingEffect(GPObject):

    """A tremolo picking effect."""

    __attr__ = ('duration',)

    def __init__(self, *args, **kwargs):
        self.duration = Duration()
        GPObject.__init__(self, *args, **kwargs)


class SlideType(Enum):

    """Lists all supported slide types."""
    intoFromAbove = -2
    intoFromBelow = -1
    none = 0
    shiftSlideTo = 1
    legatoSlideTo = 2
    outDownwards = 3
    outUpwards = 4


class NoteEffect(GPObject):

    """Contains all effects which can be applied to one note."""

    __attr__ = ('leftHandFinger', 'rightHandFinger', 'bend', 'harmonic',
                'grace', 'trill', 'tremoloPicking', 'vibrato', 'slides',
                'hammer', 'ghostNote', 'accentuatedNote',
                'heavyAccentuatedNote', 'palmMute', 'staccato', 'letRing')

    def __init__(self, *args, **kwargs):
        self.vibrato = False
        self.slides = []
        self.hammer = False
        self.ghostNote = False
        self.accentuatedNote = False
        self.heavyAccentuatedNote = False
        self.palmMute = False
        self.staccato = False
        self.letRing = False
        self.leftHandFinger = Fingering.open
        self.rightHandFinger = Fingering.open
        self.note = None
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
    def isFingering(self):
        return self.leftHandFinger.value > -1 or self.rightHandFinger.value > -1

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
                self.slides == default.slides and
                self.hammer == default.hammer and
                self.palmMute == default.palmMute and
                self.staccato == default.staccato and
                self.letRing == default.letRing)


class NoteType(Enum):
    rest = 0
    normal = 1
    tie = 2
    dead = 3


class Note(GPObject):

    """Describes a single note."""

    __attr__ = ('value', 'velocity', 'string', 'isTiedNote', 'effect',
                'durationPercent', 'swapAccidentals', 'type')

    def __init__(self, *args, **kwargs):
        self.value = 0
        self.velocity = Velocities.default
        self.string = 0
        self.swapAccidentals = False
        self.effect = NoteEffect()
        self.durationPercent = 1.0
        self.type = NoteType.rest
        GPObject.__init__(self, *args, **kwargs)

    @property
    def realValue(self):
        return (self.value +
                self.beat.voice.measure.track.strings[self.string - 1].value)


class Chord(GPObject):

    """A chord annotation for beats."""

    __attr__ = ('sharp', 'root', 'type', 'extension', 'bass', 'tonality',
                'add', 'name', 'fifth', 'ninth', 'eleventh', 'firstFret',
                'strings', 'barres', 'omissions', 'fingerings', 'show',
                'newFormat')

    def __init__(self, length, *args, **kwargs):
        self.strings = [-1] * length
        self.name = ''
        self.barres = []
        self.omissions = []
        self.fingerings = []
        GPObject.__init__(self, *args, **kwargs)

    @property
    def notes(self):
        return [string for string in self.strings if string >= 0]


class ChordType(Enum):

    """Type of the chord."""

    #: Major chord.
    major = 0

    #: Dominant seventh chord.
    seventh = 1

    #: Major seventh chord.
    majorSeventh = 2

    #: Add sixth chord.
    sixth = 3

    #: Minor chord.
    minor = 4

    #: Minor seventh chord.
    minorSeventh = 5

    #: Minor major seventh chord.
    minorMajor = 6

    #: Minor add sixth chord.
    minorSixth = 7

    #: Suspended second chord.
    suspendedSecond = 8

    #: Suspended fourth chord.
    suspendedFourth = 9

    #: Seventh suspended second chord.
    seventhSuspendedSecond = 10

    #: Seventh suspended fourth chord.
    seventhSuspendedFourth = 11

    #: Diminished chord.
    diminished = 12

    #: Augmented chord.
    augmented = 13

    #: Power chord.
    power = 14


class Barre(GPObject):

    """A single barre.

    :param start: first string from the bottom of the barre.
    :param end: last string on the top of the barre.

    """
    __attr__ = ('fret', 'start', 'end')

    def __init__(self, *args, **kwargs):
        self.start = 0
        self.end = 0
        GPObject.__init__(self, *args, **kwargs)

    @property
    def range(self):
        return self.start, self.end


class Fingering(Enum):

    """Left and right hand fingering used in tabs and chord diagram editor."""

    #: Unknown (used only in chord editor).
    unknown = -2
    #: Open or muted.
    open = -1
    #: Thumb.
    thumb = 0
    #: Index finger.
    index = 1
    #: Middle finger.
    middle = 2
    #: Annular finger.
    annular = 3
    #: Little finger.
    little = 4


class ChordAlteration(Enum):

    """Tonality of the chord."""

    #: Perfect.
    perfect = 0

    #: Diminished.
    diminished = 1

    #: Augmented.
    augmented = 2


class ChordExtension(Enum):

    """Extension type of the chord."""

    #: No extension.
    none = 0

    #: Ninth chord.
    ninth = 1

    #: Eleventh chord.
    eleventh = 2

    #: Thirteenth chord.
    thirteenth = 3


class PitchClass(GPObject):

    """A pitch class.

    Constructor provides several overloads. Each overload provides keyword
    argument *intonation* that may be either "sharp" or "flat".

    First of overloads is (tone, accidental):

    :param tone: integer of whole-tone.
    :param accidental: flat (-1), none (0) or sharp (1).

    >>> p = PitchClass(4, -1)
    >>> vars(p)
    {'accidental': -1, 'intonation': 'flat', 'just': 4, 'value': 3}
    >>> print p
    Eb
    >>> p = PitchClass(4, -1, intonation='sharp')
    >>> vars(p)
    {'accidental': -1, 'intonation': 'flat', 'just': 4, 'value': 3}
    >>> print p
    D#

    Second, semitone number can be directly passed to constructor:

    :param semitone: integer of semitone.

    >>> p = PitchClass(3)
    >>> print p
    Eb
    >>> p = PitchClass(3, intonation='sharp')
    >>> print p
    D#

    And last, but not least, note name:

    :param name: string representing note.

    >>> p = PitchClass('D#')
    >>> print p
    D#

    """
    __attr__ = ('just', 'accidental', 'value', 'intonation')

    _notes = {
        'sharp': 'C C# D D# E F F# G G# A A# B'.split(),
        'flat': 'C Db D Eb E F Gb G Ab A Bb B'.split(),
    }

    def __init__(self, *args, **kwargs):
        intonation = kwargs.get('intonation')
        if len(args) == 1:
            if isinstance(args[0], string_types):
                # Assume string input
                string = args[0]
                try:
                    value = self._notes['sharp'].index(string)
                except ValueError:
                    value = self._notes['flat'].index(string)
            elif isinstance(args[0], int):
                value = args[0] % 12
                try:
                    string = self._notes['sharp'][value]
                except KeyError:
                    string = self._notes['flat'][value]
            if string.endswith('b'):
                accidental = -1
            elif string.endswith('#'):
                accidental = 1
            else:
                accidental = 0
            pitch = value - accidental
        elif len(args) == 2:
            pitch, accidental = args
        self.just = pitch % 12
        self.accidental = accidental
        self.value = self.just + accidental
        if intonation is not None:
            self.intonation = intonation
        else:
            if accidental == -1:
                self.intonation = 'flat'
            else:
                self.intonation = 'sharp'

    def __str__(self):
        return self._notes[self.intonation][self.value]


class BeatText(GPObject):

    """A text annotation for beats."""

    __attr__ = ('value',)

    def __init__(self, *args, **kwargs):
        self.value = ''
        GPObject.__init__(self, *args, **kwargs)


class MixTableItem(GPObject):

    """A mix table change describes several track changes."""

    __attr__ = ('value', 'duration', 'allTracks')

    def __init__(self, *args, **kwargs):
        self.value = 0
        self.duration = 0
        self.allTracks = False
        GPObject.__init__(self, *args, **kwargs)


class WahState(Enum):

    """State of wah-wah pedal."""

    #: Wah-wah is off.
    off = -2

    #: No wah-wah.
    none = -1

    #: Wah-wah is opened.
    opened = 0

    #: Wah-wah is closed.
    closed = 100


class WahEffect(GPObject):
    __attr__ = ('state', 'display')

    state = WahState.none
    display = False


class MixTableChange(GPObject):

    """A MixTableChange describes several track changes."""

    __attr__ = ('instrument', 'rse', 'volume', 'balance', 'chorus', 'reverb',
                'phaser', 'tremolo', 'tempoName', 'tempo', 'hideTempo', 'wah',
                'useRSE')

    def __init__(self, *args, **kwargs):
        self.tempoName = ''
        self.hideTempo = True
        self.useRSE = False
        GPObject.__init__(self, *args, **kwargs)

    @property
    def isJustWah(self):
        return (self.instrument is None and
                self.volume is None and
                self.balance is None and
                self.chorus is None and
                self.reverb is None and
                self.phaser is None and
                self.tremolo is None and
                self.tempo is None and
                self.wah is not None)


class BendType(Enum):

    """All Bend presets."""

    #: No Preset.
    none = 0

    # Bends
    # =====

    #: A simple bend.
    bend = 1

    #: A bend and release afterwards.
    bendRelease = 2

    #: A bend, then release and rebend.
    bendReleaseBend = 3

    #: Prebend.
    prebend = 4

    #: Prebend and then release.
    prebendRelease = 5

    # Tremolobar
    # ==========

    #: Dip the bar down and then back up.
    dip = 6

    #: Dive the bar.
    dive = 7

    #: Release the bar up.
    releaseUp = 8

    #: Dip the bar up and then back down.
    invertedDip = 9

    #: Return the bar.
    return_ = 10

    #: Release the bar down.
    releaseDown = 11


class BendPoint(GPObject):

    """A single point within the BendEffect."""

    __attr__ = ('position', 'value', 'vibrato')

    def __init__(self, *args, **kwargs):
        """Initializes a new instance of the BendPoint class."""
        self.position = 0
        self.vibrato = False
        GPObject.__init__(self, *args, **kwargs)

    def getTime(self, duration):
        """Gets the exact time when the point need to be played (MIDI).

        :param duration: the full duration of the effect.

        """
        return int(duration * self.position / BendEffect.maxPosition)


class BendEffect(GPObject):

    """This effect is used to describe string bends and tremolo bars."""

    __attr__ = ('type', 'value', 'points')

    #: The note offset per bend point offset.
    semitoneLength = 1

    #: The max position of the bend points (x axis)
    maxPosition = 12

    #: The max value of the bend points (y axis)
    maxValue = semitoneLength * 12

    def __init__(self, *args, **kwargs):
        self.type = BendType.none
        self.value = 0
        self.points = []
        GPObject.__init__(self, *args, **kwargs)


class TripletFeel(Enum):

    """A list of different triplet feels."""

    #: No triplet feel.
    none = 0

    #: Eighth triplet feel.
    eighth = 1

    #: Sixteenth triplet feel.
    sixteenth = 2


class TimeSignature(GPObject):

    """A time signature."""

    __attr__ = ('numerator', 'denominator', 'beams')

    def __init__(self, *args, **kwargs):
        self.numerator = 4
        self.denominator = Duration()
        self.beams = (0, 0, 0, 0)
        GPObject.__init__(self, *args, **kwargs)


class Velocities(object):

    """A list of velocities / dynamics."""
    minVelocity = 15
    velocityIncrement = 16
    pianoPianissimo = minVelocity
    pianissimo = minVelocity + velocityIncrement
    piano = minVelocity + velocityIncrement * 2
    mezzoPiano = minVelocity + velocityIncrement * 3
    mezzoForte = minVelocity + velocityIncrement * 4
    forte = minVelocity + velocityIncrement * 5
    fortissimo = minVelocity + velocityIncrement * 6
    forteFortissimo = minVelocity + velocityIncrement * 7
    default = forte


class RSEMasterEffect(GPObject):

    """Master effect as seen on "Score information"."""

    __attr__ = ('volume', 'reverb', 'equalizer')


class RSEEqualizer(GPObject):

    """Equalizer found in master effect and track effect.

    Attribute :attr:`RSEEqualizer.knobs` is a list of values in range from -6.0
    to 5.9. Master effect has 10 knobs, track effect has 3 knobs. Gain is a
    value in range from -6.0 to 5.9 which can be found in both master and track
    effects and is named as "PRE" in Guitar Pro 5.

    """

    __attr__ = ('knobs', 'gain')


class Accentuation(Enum):

    """Values of auto-accentuation on the beat found in track RSE settings."""

    #: No auto-accentuation.
    none = 0

    #: Very soft accentuation.
    verySoft = 1

    #: Soft accentuation.
    soft = 2

    #: Medium accentuation.
    medium = 3

    #: Strong accentuation.
    strong = 4

    #: Very strong accentuation.
    veryStrong = 5


class RSEInstrument(GPObject):
    __attr__ = ('instrument', 'unknown', 'soundBank', 'effectNumber',
                'effectCategory', 'effect')

    def __init__(self, *args, **kwargs):
        self.instrument = -1
        self.unknown = 1
        self.soundBank = -1
        self.effectNumber = -1
        self.effectCategory = ''
        self.effect = ''
        GPObject.__init__(self, *args, **kwargs)


class TrackRSE(GPObject):
    __attr__ = ('instrument', 'equalizer', 'humanize', 'autoAccentuation')

    def __init__(self, *args, **kwargs):
        self.instrument = RSEInstrument()
        self.equalizer = RSEEqualizer(knobs=[0, 0, 0], gain=0)
        self.humanize = 0
        self.autoAccentuation = Accentuation.none
        GPObject.__init__(self, *args, **kwargs)


class KeySignature(Enum):
    FMajorFlat = (-8, 0)
    CMajorFlat = (-7, 0)
    GMajorFlat = (-6, 0)
    DMajorFlat = (-5, 0)
    AMajorFlat = (-4, 0)
    EMajorFlat = (-3, 0)
    BMajorFlat = (-2, 0)
    FMajor = (-1, 0)
    CMajor = (0, 0)
    GMajor = (1, 0)
    DMajor = (2, 0)
    AMajor = (3, 0)
    EMajor = (4, 0)
    BMajor = (5, 0)
    FMajorSharp = (6, 0)
    CMajorSharp = (7, 0)
    GMajorSharp = (8, 0)

    DMinorFlat = (-8, 1)
    AMinorFlat = (-7, 1)
    EMinorFlat = (-6, 1)
    BMinorFlat = (-5, 1)
    FMinor = (-4, 1)
    CMinor = (-3, 1)
    GMinor = (-2, 1)
    DMinor = (-1, 1)
    AMinor = (0, 1)
    EMinor = (1, 1)
    BMinor = (2, 1)
    FMinorSharp = (3, 1)
    CMinorSharp = (4, 1)
    GMinorSharp = (5, 1)
    DMinorSharp = (6, 1)
    AMinorSharp = (7, 1)
    EMinorSharp = (8, 1)
