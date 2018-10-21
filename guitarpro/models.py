from __future__ import division, print_function

from fractions import Fraction
from functools import partial
from math import log
from warnings import warn

import attr
from enum import Enum, IntEnum
from six import string_types

__all__ = (
    'GPException', 'RepeatGroup', 'Clipboard', 'KeySignature', 'Song',
    'LyricLine', 'Lyrics', 'Point', 'Padding', 'HeaderFooterElements',
    'PageSetup', 'Tempo', 'MidiChannel', 'DirectionSign', 'Tuplet', 'Duration',
    'TimeSignature', 'TripletFeel', 'MeasureHeader', 'Color', 'Marker',
    'TrackSettings', 'Track', 'GuitarString', 'MeasureClef', 'LineBreak',
    'Measure', 'VoiceDirection', 'Voice', 'BeatStrokeDirection', 'BeatStroke',
    'SlapEffect', 'BeatEffect', 'TupletBracket', 'BeatDisplay', 'Octave',
    'BeatStatus', 'Beat', 'HarmonicEffect', 'NaturalHarmonic',
    'ArtificialHarmonic', 'TappedHarmonic', 'PinchHarmonic', 'SemiHarmonic',
    'GraceEffectTransition', 'Velocities', 'GraceEffect', 'TrillEffect',
    'TremoloPickingEffect', 'SlideType', 'Fingering', 'NoteEffect', 'NoteType',
    'Note', 'Chord', 'ChordType', 'Barre', 'ChordAlteration', 'ChordExtension',
    'PitchClass', 'BeatText', 'MixTableItem', 'WahEffect', 'MixTableChange',
    'BendType', 'BendPoint', 'BendEffect', 'RSEMasterEffect', 'RSEEqualizer',
    'Accentuation', 'RSEInstrument', 'TrackRSE'
)


class GPException(Exception):
    pass


def hashableAttrs(cls=None, repr=True):
    """A fully hashable attrs decorator.

    Converts unhashable attributes, e.g. lists, to hashable ones, e.g.
    tuples.
    """
    if cls is None:
        return partial(hashableAttrs, repr=repr)

    def hash_(self):
        obj = self
        for field in attr.fields(self.__class__):
            value = getattr(self, field.name)
            if isinstance(value, (list, set)):
                new_value = tuple(value)
            else:
                new_value = value
            if new_value != value:
                obj = attr.evolve(obj, **{field.name: new_value})
        return hash(attr.astuple(obj, recurse=False, filter=lambda a, v: a.hash is not False))

    decorated = attr.s(cls, hash=False, repr=repr)
    decorated.__hash__ = hash_
    return decorated


@hashableAttrs
class RepeatGroup(object):

    """This class can store the information about a group of measures
    which are repeated."""

    measureHeaders = attr.ib(default=attr.Factory(list))
    closings = attr.ib(default=attr.Factory(list))
    openings = attr.ib(default=attr.Factory(list))
    isClosed = attr.ib(default=False)

    def addMeasureHeader(self, h):
        if not len(self.openings):
            self.openings.append(h)

        self.measureHeaders.append(h)
        h.repeatGroup = self

        if h.repeatClose > 0:
            self.closings.append(h)
            self.isClosed = True
        # A new item after the header was closed? -> repeat alternative
        # reopens the group
        elif self.isClosed:
            self.isClosed = False
            self.openings.append(h)


@hashableAttrs
class Clipboard(object):
    startMeasure = attr.ib(default=1)
    stopMeasure = attr.ib(default=1)
    startTrack = attr.ib(default=1)
    stopTrack = attr.ib(default=1)
    startBeat = attr.ib(default=1)
    stopBeat = attr.ib(default=1)
    subBarCopy = attr.ib(default=False)


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


@hashableAttrs
class LyricLine(object):

    """A lyrics line."""

    startingMeasure = attr.ib(default=1)
    lyrics = attr.ib(default='')


@hashableAttrs(repr=False)
class Lyrics(object):

    """A collection of lyrics lines for a track."""

    trackChoice = attr.ib(default=0)
    lines = attr.ib(default=None)

    maxLineCount = 5

    def __attrs_post_init__(self):
        if self.lines is None:
            self.lines = []
            for _ in range(Lyrics.maxLineCount):
                self.lines.append(LyricLine())

    def __str__(self):
        full = ''
        for line in self.lines:
            if line is not None:
                full += line.lyrics + '\n'
        ret = full.strip()
        ret = ret.replace('\n', ' ')
        ret = ret.replace('\r', ' ')
        return ret


@hashableAttrs
class Point(object):

    """A point construct using floating point coordinates."""

    x = attr.ib()
    y = attr.ib()


@hashableAttrs
class Padding(object):

    """A padding construct."""

    right = attr.ib()
    top = attr.ib()
    left = attr.ib()
    bottom = attr.ib()


class HeaderFooterElements(IntEnum):

    """An enumeration of the elements which can be shown in the header
    and footer of a rendered song sheet.

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
    all = title | subtitle | artist | album | words | music | wordsAndMusic | copyright | pageNumber


@hashableAttrs
class PageSetup(object):

    """The page setup describes how the document is rendered.

    Page setup contains page size, margins, paddings, and how the title
    elements are rendered.

    Following template vars are available for defining the page texts:

    - ``%title%``: will be replaced with Song.title
    - ``%subtitle%``: will be replaced with Song.subtitle
    - ``%artist%``: will be replaced with Song.artist
    - ``%album%``: will be replaced with Song.album
    - ``%words%``: will be replaced with Song.words
    - ``%music%``: will be replaced with Song.music
    - ``%WORDSANDMUSIC%``: will be replaced with the according word
      and music values
    - ``%copyright%``: will be replaced with Song.copyright
    - ``%N%``: will be replaced with the current page number (if
      supported by layout)
    - ``%P%``: will be replaced with the number of pages (if supported
      by layout)

    """
    pageSize = attr.ib(default=Point(210, 297))
    pageMargin = attr.ib(default=Padding(10, 15, 10, 10))
    scoreSizeProportion = attr.ib(default=1.0)
    headerAndFooter = attr.ib(default=HeaderFooterElements.all)
    title = attr.ib(default='%title%')
    subtitle = attr.ib(default='%subtitle%')
    artist = attr.ib(default='%artist%')
    album = attr.ib(default='%album%')
    words = attr.ib(default='Words by %words%')
    music = attr.ib(default='Music by %music%')
    wordsAndMusic = attr.ib(default='Words & Music by %WORDSMUSIC%')
    copyright = attr.ib(default='Copyright %copyright%\n'
                                'All Rights Reserved - International Copyright Secured')
    pageNumber = attr.ib(default='Page %N%/%P%')


@hashableAttrs
class RSEEqualizer(object):

    """Equalizer found in master effect and track effect.

    Attribute :attr:`RSEEqualizer.knobs` is a list of values in range
    from -6.0 to 5.9. Master effect has 10 knobs, track effect has 3
    knobs. Gain is a value in range from -6.0 to 5.9 which can be found
    in both master and track effects and is named as "PRE" in Guitar Pro
    5.

    """

    knobs = attr.ib(default=attr.Factory(list))
    gain = attr.ib(default=0.0)


@hashableAttrs
class RSEMasterEffect(object):

    """Master effect as seen in "Score information"."""

    volume = attr.ib(default=0)
    reverb = attr.ib(default=0)
    equalizer = attr.ib(default=attr.Factory(RSEEqualizer))

    def __attrs_post_init__(self):
        if not self.equalizer.knobs:
            self.equalizer.knobs = [0.0] * 10


@hashableAttrs(repr=False)
class Song(object):

    """The top-level node of the song model.

    It contains basic information about the stored song.

    """
    # TODO: Store file format version here
    versionTuple = attr.ib(default=None, hash=False, cmp=False)
    clipboard = attr.ib(default=None)
    title = attr.ib(default='')
    subtitle = attr.ib(default='')
    artist = attr.ib(default='')
    album = attr.ib(default='')
    words = attr.ib(default='')
    music = attr.ib(default='')
    copyright = attr.ib(default='')
    tab = attr.ib(default='')
    instructions = attr.ib(default='')
    notice = attr.ib(default=attr.Factory(list))
    lyrics = attr.ib(default=attr.Factory(Lyrics))
    pageSetup = attr.ib(default=attr.Factory(PageSetup))
    tempoName = attr.ib(default='Moderate')
    tempo = attr.ib(default=120)
    hideTempo = attr.ib(default=False)
    key = attr.ib(default=KeySignature.CMajor)
    measureHeaders = attr.ib(default=None)
    tracks = attr.ib(default=None)
    masterEffect = attr.ib(default=attr.Factory(RSEMasterEffect))

    _currentRepeatGroup = attr.ib(default=attr.Factory(RepeatGroup), hash=False, cmp=False, repr=False)

    def __attrs_post_init__(self):
        if self.measureHeaders is None:
            self.measureHeaders = [MeasureHeader()]
        if self.tracks is None:
            self.tracks = [Track(self)]

    def addMeasureHeader(self, header):
        header.song = self
        self.measureHeaders.append(header)

        # if the group is closed only the next upcoming header can
        # reopen the group in case of a repeat alternative, so we remove
        # the current group
        if header.isRepeatOpen or self._currentRepeatGroup.isClosed and header.repeatAlternative <= 0:
            self._currentRepeatGroup = RepeatGroup()

        self._currentRepeatGroup.addMeasureHeader(header)

    def newMeasure(self):
        for track in self.tracks:
            measure = Measure(track)
            track.measures.append(measure)


@hashableAttrs
class Tempo(object):

    """A song tempo in BPM."""

    value = attr.ib(default=120)

    def __str__(self):
        return '{value}bpm'.format(**vars(self))


@hashableAttrs
class MidiChannel(object):

    """A MIDI channel describes playing data for a track."""

    channel = attr.ib(default=0)
    effectChannel = attr.ib(default=1)
    instrument = attr.ib(default=25)
    volume = attr.ib(default=104)
    balance = attr.ib(default=64)
    chorus = attr.ib(default=0)
    reverb = attr.ib(default=0)
    phaser = attr.ib(default=0)
    tremolo = attr.ib(default=0)
    bank = attr.ib(default=0)

    DEFAULT_PERCUSSION_CHANNEL = 9

    @property
    def isPercussionChannel(self):
        return self.channel % 16 == self.DEFAULT_PERCUSSION_CHANNEL


@hashableAttrs
class DirectionSign(object):

    """A navigation sign like *Coda* or *Segno*."""

    name = attr.ib(default='')


@hashableAttrs
class Tuplet(object):

    """A *n:m* tuplet."""

    enters = attr.ib(default=1)
    times = attr.ib(default=1)

    supportedTuplets = [
        (1, 1),
        (3, 2),
        (5, 4),
        (6, 4),
        (7, 4),
        (9, 8),
        (10, 8),
        (11, 8),
        (12, 8),
        (13, 8),
    ]

    def convertTime(self, time):
        return int(time * self.times / self.enters)

    def isSupported(self):
        return (self.enters, self.times) in self.supportedTuplets

    @classmethod
    def fromFraction(cls, frac):
        return cls(frac.denominator, frac.numerator)


@hashableAttrs
class Duration(object):

    """A duration."""

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

    value = attr.ib(default=quarter)
    isDotted = attr.ib(default=False)
    isDoubleDotted = attr.ib(default=False)
    tuplet = attr.ib(default=attr.Factory(Tuplet))

    def __attrs_post_init__(self):
        self._attrs_inited = True

    def __setattr__(self, name, value):
        if name == 'isDoubleDotted' and getattr(self, '_attrs_inited', False):
            warn('Duration.isDoubleDotted is deprecated and will be removed in 0.6 release', DeprecationWarning)
        return super(self.__class__, self).__setattr__(name, value)

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
    def fromTime(cls, time):
        timeFrac = Fraction(time, cls.quarterTime * 4)
        exp = int(log(timeFrac, 2))
        value = 2 ** -exp
        tuplet = Tuplet.fromFraction(timeFrac * value)
        isDotted = isDoubleDotted = False
        if tuplet.times == 3:
            value *= int(log(tuplet.enters, 2))
            tuplet = Tuplet(1, 1)
            isDotted = True
        if not tuplet.isSupported():
            raise ValueError('cannot represent time {} as a Guitar Pro duration'.format(time))
        return Duration(value, isDotted, isDoubleDotted, tuplet)


@hashableAttrs
class TimeSignature(object):

    """A time signature."""

    numerator = attr.ib(default=4)
    denominator = attr.ib(default=attr.Factory(Duration))
    beams = attr.ib(default=attr.Factory(list))

    def __attrs_post_init__(self):
        if not self.beams:
            self.beams = [2, 2, 2, 2]


class TripletFeel(Enum):

    """An enumeration of different triplet feels."""

    #: No triplet feel.
    none = 0

    #: Eighth triplet feel.
    eighth = 1

    #: Sixteenth triplet feel.
    sixteenth = 2


@hashableAttrs(repr=False)
class MeasureHeader(object):

    """A measure header contains metadata for measures over multiple
    tracks."""

    number = attr.ib(default=1, hash=False, cmp=False)
    start = attr.ib(default=Duration.quarterTime, hash=False, cmp=False)
    hasDoubleBar = attr.ib(default=False)
    keySignature = attr.ib(default=KeySignature.CMajor)
    timeSignature = attr.ib(default=attr.Factory(TimeSignature))
    # TODO: Remove this attribute in next release
    tempo = attr.ib(default=attr.Factory(Tempo), hash=False, cmp=False)
    marker = attr.ib(default=None)
    isRepeatOpen = attr.ib(default=False)
    repeatAlternative = attr.ib(default=0)
    repeatClose = attr.ib(default=-1)
    tripletFeel = attr.ib(default=TripletFeel.none)
    direction = attr.ib(default=None)
    fromDirection = attr.ib(default=None)

    @property
    def hasMarker(self):
        return self.marker is not None

    @property
    def length(self):
        return self.timeSignature.numerator * self.timeSignature.denominator.time


@hashableAttrs
class Color(object):

    """An RGB Color."""

    r = attr.ib()
    g = attr.ib()
    b = attr.ib()
    a = attr.ib(default=1)


Color.black = Color(0, 0, 0)
Color.red = Color(255, 0, 0)


@hashableAttrs
class Marker(object):

    """A marker annotation for beats."""

    title = attr.ib(default='Section')
    color = attr.ib(default=Color.red)


@hashableAttrs
class TrackSettings(object):

    """Settings of the track."""

    tablature = attr.ib(default=True)
    notation = attr.ib(default=True)
    diagramsAreBelow = attr.ib(default=False)
    showRhythm = attr.ib(default=False)
    forceHorizontal = attr.ib(default=False)
    forceChannels = attr.ib(default=False)
    diagramList = attr.ib(default=True)
    diagramsInScore = attr.ib(default=False)
    autoLetRing = attr.ib(default=False)
    autoBrush = attr.ib(default=False)
    extendRhythmic = attr.ib(default=False)


class Accentuation(Enum):

    """Values of auto-accentuation on the beat found in track RSE
    settings."""

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


@hashableAttrs
class RSEInstrument(object):
    instrument = attr.ib(default=-1)
    unknown = attr.ib(default=1)
    soundBank = attr.ib(default=-1)
    effectNumber = attr.ib(default=-1)
    effectCategory = attr.ib(default='')
    effect = attr.ib(default='')


@hashableAttrs(repr=False)
class TrackRSE(object):
    instrument = attr.ib(default=attr.Factory(RSEInstrument))
    equalizer = attr.ib(default=attr.Factory(RSEEqualizer))
    humanize = attr.ib(default=0)
    autoAccentuation = attr.ib(default=Accentuation.none)

    def __attrs_post_init__(self):
        if not self.equalizer.knobs:
            self.equalizer.knobs = [0.0] * 3


@hashableAttrs(repr=False)
class Track(object):

    """A track contains multiple measures."""

    song = attr.ib(hash=False, cmp=False, repr=False)
    number = attr.ib(default=1, hash=False, cmp=False)
    fretCount = attr.ib(default=24)
    offset = attr.ib(default=0)
    isPercussionTrack = attr.ib(default=False)
    is12StringedGuitarTrack = attr.ib(default=False)
    isBanjoTrack = attr.ib(default=False)
    isVisible = attr.ib(default=True)
    isSolo = attr.ib(default=False)
    isMute = attr.ib(default=False)
    indicateTuning = attr.ib(default=False)
    name = attr.ib(default='Track 1')
    measures = attr.ib(default=None)
    strings = attr.ib(default=None)
    port = attr.ib(default=1)
    channel = attr.ib(default=attr.Factory(MidiChannel))
    color = attr.ib(default=Color.red)
    settings = attr.ib(default=attr.Factory(TrackSettings))
    useRSE = attr.ib(default=False)
    rse = attr.ib(default=attr.Factory(TrackRSE))

    def __attrs_post_init__(self):
        if self.strings is None:
            self.strings = [GuitarString(n, v)
                            for n, v in [(1, 64), (2, 59), (3, 55),
                                         (4, 50), (5, 45), (6, 40)]]
        if self.measures is None:
            self.measures = [Measure(self, header) for header in self.song.measureHeaders]


@hashableAttrs
class GuitarString(object):

    """A guitar string with a special tuning."""

    number = attr.ib()
    value = attr.ib()

    def __str__(self):
        notes = 'C C# D D# E F F# G G# A A# B'.split()
        octave, semitone = divmod(self.value, 12)
        return '{note}{octave}'.format(note=notes[semitone], octave=octave)


class MeasureClef(Enum):

    """An enumeration of available clefs."""

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


@hashableAttrs(repr=False)
class Measure(object):

    """A measure contains multiple voices of beats."""

    track = attr.ib(hash=False, cmp=False, repr=False)
    header = attr.ib(hash=False, cmp=False, repr=False)
    clef = attr.ib(default=MeasureClef.treble)
    voices = attr.ib(default=None)
    lineBreak = attr.ib(default=LineBreak.none)

    maxVoices = 2

    def __attrs_post_init__(self):
        if self.voices is None:
            self.voices = []
            for _ in range(self.maxVoices):
                voice = Voice(self)
                self.voices.append(voice)

    @property
    def isEmpty(self):
        return all(voice.isEmpty for voice in self.voices)

    @property
    def end(self):
        return self.start + self.length

    def _promote_header_attr(name):
        def fget(self):
            return getattr(self.header, name)

        def fset(self, value):
            setattr(self.header, name, value)

        return property(fget, fset)

    number = _promote_header_attr('number')
    keySignature = _promote_header_attr('keySignature')
    repeatClose = _promote_header_attr('repeatClose')
    start = _promote_header_attr('start')
    length = _promote_header_attr('length')
    tempo = _promote_header_attr('tempo')
    timeSignature = _promote_header_attr('timeSignature')
    isRepeatOpen = _promote_header_attr('isRepeatOpen')
    tripletFeel = _promote_header_attr('tripletFeel')
    hasMarker = _promote_header_attr('hasMarker')
    marker = _promote_header_attr('marker')

    del _promote_header_attr


class VoiceDirection(Enum):

    """Voice directions indicating the direction of beams."""

    none = 0
    up = 1
    down = 2


@hashableAttrs(repr=False)
class Voice(object):

    """A voice contains multiple beats."""

    measure = attr.ib(hash=False, cmp=False, repr=False)
    beats = attr.ib(default=attr.Factory(list))
    direction = attr.ib(default=VoiceDirection.none)

    @property
    def isEmpty(self):
        return len(self.beats) == 0


class BeatStrokeDirection(Enum):

    """All beat stroke directions."""

    none = 0
    up = 1
    down = 2


@hashableAttrs
class BeatStroke(object):

    """A stroke effect for beats."""

    direction = attr.ib(default=BeatStrokeDirection.none)
    value = attr.ib(default=0)

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


@hashableAttrs
class BeatEffect(object):

    """This class contains all beat effects."""

    stroke = attr.ib(default=attr.Factory(BeatStroke))
    hasRasgueado = attr.ib(default=False)
    pickStroke = attr.ib(default=BeatStrokeDirection.none)
    chord = attr.ib(default=None)
    fadeIn = attr.ib(default=False)
    tremoloBar = attr.ib(default=None)
    mixTableChange = attr.ib(default=None)
    slapEffect = attr.ib(default=SlapEffect.none)
    vibrato = attr.ib(default=None)

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


@hashableAttrs
class BeatDisplay(object):

    """Parameters of beat display."""

    breakBeam = attr.ib(default=False)
    forceBeam = attr.ib(default=False)
    beamDirection = attr.ib(default=VoiceDirection.none)
    tupletBracket = attr.ib(default=TupletBracket.none)
    breakSecondary = attr.ib(default=0)
    breakSecondaryTuplet = attr.ib(default=False)
    forceBracket = attr.ib(default=False)


class Octave(Enum):

    """Octave signs."""

    none = 0
    ottava = 1
    quindicesima = 2
    ottavaBassa = 3
    quindicesimaBassa = 4


class BeatStatus(Enum):
    empty = 0
    normal = 1
    rest = 2


@hashableAttrs(repr=False)
class Beat(object):

    """A beat contains multiple notes."""

    voice = attr.ib(hash=False, cmp=False, repr=False)
    notes = attr.ib(default=attr.Factory(list))
    duration = attr.ib(default=attr.Factory(Duration))
    text = attr.ib(default=None)
    start = attr.ib(default=None, hash=False, cmp=False)
    effect = attr.ib(default=attr.Factory(BeatEffect))
    index = attr.ib(default=None)
    octave = attr.ib(default=Octave.none)
    display = attr.ib(default=attr.Factory(BeatDisplay))
    status = attr.ib(default=BeatStatus.empty)

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


@hashableAttrs
class HarmonicEffect(object):

    """A harmonic note effect."""

    type = attr.ib(init=False)


@hashableAttrs
class NaturalHarmonic(HarmonicEffect):
    def __attrs_post_init__(self):
        self.type = 1


@hashableAttrs
class ArtificialHarmonic(HarmonicEffect):
    pitch = attr.ib(default=None)
    octave = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.type = 2


@hashableAttrs
class TappedHarmonic(HarmonicEffect):
    fret = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.type = 3


@hashableAttrs
class PinchHarmonic(HarmonicEffect):
    def __attrs_post_init__(self):
        self.type = 4


@hashableAttrs
class SemiHarmonic(HarmonicEffect):
    def __attrs_post_init__(self):
        self.type = 5


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


class Velocities(object):

    """A collection of velocities / dynamics."""
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


@hashableAttrs
class GraceEffect(object):

    """A grace note effect."""

    duration = attr.ib(default=1)
    fret = attr.ib(default=0)
    isDead = attr.ib(default=False)
    isOnBeat = attr.ib(default=False)
    transition = attr.ib(default=GraceEffectTransition.none)
    velocity = attr.ib(default=Velocities.default)

    @property
    def durationTime(self):
        """Get the duration of the effect."""
        return int(Duration.quarterTime / 16 * self.duration)


@hashableAttrs
class TrillEffect(object):

    """A trill effect."""

    fret = attr.ib(default=0)
    duration = attr.ib(default=attr.Factory(Duration))


@hashableAttrs
class TremoloPickingEffect(object):

    """A tremolo picking effect."""

    duration = attr.ib(default=attr.Factory(Duration))


class SlideType(Enum):

    """An enumeration of all supported slide types."""
    intoFromAbove = -2
    intoFromBelow = -1
    none = 0
    shiftSlideTo = 1
    legatoSlideTo = 2
    outDownwards = 3
    outUpwards = 4


class Fingering(Enum):

    """Left and right hand fingering used in tabs and chord diagram
    editor."""

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


@hashableAttrs(repr=False)
class NoteEffect(object):

    """Contains all effects which can be applied to one note."""

    accentuatedNote = attr.ib(default=False)
    bend = attr.ib(default=None)
    ghostNote = attr.ib(default=False)
    grace = attr.ib(default=None)
    hammer = attr.ib(default=False)
    harmonic = attr.ib(default=None)
    heavyAccentuatedNote = attr.ib(default=False)
    leftHandFinger = attr.ib(default=Fingering.open)
    letRing = attr.ib(default=False)
    palmMute = attr.ib(default=False)
    rightHandFinger = attr.ib(default=Fingering.open)
    slides = attr.ib(default=attr.Factory(list))
    staccato = attr.ib(default=False)
    tremoloPicking = attr.ib(default=None)
    trill = attr.ib(default=None)
    vibrato = attr.ib(default=False)

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
        return (self.leftHandFinger.value > -1 or
                self.rightHandFinger.value > -1)

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


@hashableAttrs
class Note(object):

    """Describes a single note."""

    beat = attr.ib(hash=False, cmp=False, repr=False)
    value = attr.ib(default=0)
    velocity = attr.ib(default=Velocities.default)
    string = attr.ib(default=0)
    effect = attr.ib(default=attr.Factory(NoteEffect))
    durationPercent = attr.ib(default=1.0)
    swapAccidentals = attr.ib(default=False)
    type = attr.ib(default=NoteType.rest)

    @property
    def realValue(self):
        return self.value + self.beat.voice.measure.track.strings[self.string - 1].value


@hashableAttrs
class Chord(object):

    """A chord annotation for beats."""

    length = attr.ib()
    sharp = attr.ib(default=None)
    root = attr.ib(default=None)
    type = attr.ib(default=None)
    extension = attr.ib(default=None)
    bass = attr.ib(default=None)
    tonality = attr.ib(default=None)
    add = attr.ib(default=None)
    name = attr.ib(default='')
    fifth = attr.ib(default=None)
    ninth = attr.ib(default=None)
    eleventh = attr.ib(default=None)
    firstFret = attr.ib(default=None)
    strings = attr.ib(default=attr.Factory(list))
    barres = attr.ib(default=attr.Factory(list))
    omissions = attr.ib(default=attr.Factory(list))
    fingerings = attr.ib(default=attr.Factory(list))
    show = attr.ib(default=None)
    newFormat = attr.ib(default=None)

    def __attrs_post_init__(self):
        self.strings = [-1] * self.length

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


@hashableAttrs
class Barre(object):

    """A single barre.

    :param start: first string from the bottom of the barre.
    :param end: last string on the top of the barre.

    """
    fret = attr.ib()
    start = attr.ib(default=0)
    end = attr.ib(default=0)

    @property
    def range(self):
        return self.start, self.end


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


@hashableAttrs
class PitchClass(object):

    """A pitch class.

    Constructor provides several overloads. Each overload provides
    keyword argument *intonation* that may be either "sharp" or "flat".

    First of overloads is (tone, accidental):

    :param tone: integer of whole-tone.
    :param accidental: flat (-1), none (0) or sharp (1).

    >>> p = PitchClass(4, -1)
    >>> p
    PitchClass(just=4, accidental=-1, value=3, intonation='flat')
    >>> print(p)
    Eb
    >>> p = PitchClass(4, -1, intonation='sharp')
    >>> p
    PitchClass(just=4, accidental=-1, value=3, intonation='sharp')
    >>> print(p)
    D#

    Second, semitone number can be directly passed to constructor:

    :param semitone: integer of semitone.

    >>> p = PitchClass(3)
    >>> print(p)
    Eb
    >>> p = PitchClass(3, intonation='sharp')
    >>> print(p)
    D#

    And last, but not least, note name:

    :param name: string representing note.

    >>> p = PitchClass('D#')
    >>> print(p)
    D#

    """
    just = attr.ib()
    accidental = attr.ib(default=None)
    value = attr.ib(default=None)
    intonation = attr.ib(default=None)

    _notes = {
        'sharp': 'C C# D D# E F F# G G# A A# B'.split(),
        'flat': 'C Db D Eb E F Gb G Ab A Bb B'.split(),
    }

    def __attrs_post_init__(self):
        if self.accidental is None:
            if isinstance(self.just, string_types):
                # Assume string input
                string = self.just
                try:
                    value = self._notes['sharp'].index(string)
                except ValueError:
                    value = self._notes['flat'].index(string)
            elif isinstance(self.just, int):
                value = self.just % 12
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
        else:
            pitch, accidental = self.just, self.accidental

        self.just = pitch % 12
        self.accidental = accidental
        self.value = self.just + accidental
        if self.intonation is None:
            if accidental == -1:
                self.intonation = 'flat'
            else:
                self.intonation = 'sharp'

    def __str__(self):
        return self._notes[self.intonation][self.value]


@hashableAttrs
class BeatText(object):

    """A text annotation for beats."""

    value = attr.ib(default='')


@hashableAttrs
class MixTableItem(object):

    """A mix table item describes a mix parameter, e.g. volume or
    reverb."""

    value = attr.ib(default=0)
    duration = attr.ib(default=0)
    allTracks = attr.ib(default=False)


@hashableAttrs
class WahEffect(object):
    value = attr.ib(default=-1)
    display = attr.ib(default=False)

    @value.validator
    def checkValue(self, attrib, value):
        if not -2 <= value <= 100:
            raise ValueError('value must be in range from -2 to 100')

    def isOff(self):
        return self.value == WahEffect.off.value

    def isNone(self):
        return self.value == WahEffect.none.value

    def isOn(self):
        return 0 <= self.value <= 100


WahEffect.off = WahEffect(-2)
WahEffect.none = WahEffect(-1)


@hashableAttrs
class MixTableChange(object):

    """A MixTableChange describes a change in mix parameters."""

    instrument = attr.ib(default=None)
    rse = attr.ib(default=None)
    volume = attr.ib(default=None)
    balance = attr.ib(default=None)
    chorus = attr.ib(default=None)
    reverb = attr.ib(default=None)
    phaser = attr.ib(default=None)
    tremolo = attr.ib(default=None)
    tempoName = attr.ib(default='')
    tempo = attr.ib(default=None)
    hideTempo = attr.ib(default=True)
    wah = attr.ib(default=None)
    useRSE = attr.ib(default=False)
    rse = attr.ib(default=attr.Factory(RSEInstrument))

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

    # Tremolo Bar
    # ===========

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


@hashableAttrs
class BendPoint(object):

    """A single point within the BendEffect."""

    position = attr.ib(default=0)
    value = attr.ib(default=None)
    vibrato = attr.ib(default=False)

    def getTime(self, duration):
        """Gets the exact time when the point need to be played (MIDI).

        :param duration: the full duration of the effect.

        """
        return int(duration * self.position / BendEffect.maxPosition)


@hashableAttrs
class BendEffect(object):

    """This effect is used to describe string bends and tremolo bars."""

    type = attr.ib(default=BendType.none)
    value = attr.ib(default=0)
    points = attr.ib(default=attr.Factory(list))

    #: The note offset per bend point offset.
    semitoneLength = 1

    #: The max position of the bend points (x axis)
    maxPosition = 12

    #: The max value of the bend points (y axis)
    maxValue = semitoneLength * 12
