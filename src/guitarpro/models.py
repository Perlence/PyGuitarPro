from collections.abc import Callable
from enum import Enum, IntEnum
from fractions import Fraction
from functools import partial
from math import log
from typing import Any, Optional, TypeVar, Union, overload

import attr

__all__ = [
    'GPException', 'RepeatGroup', 'Clipboard', 'KeySignature', 'Song',
    'LyricLine', 'Lyrics', 'Point', 'Padding', 'HeaderFooterElements',
    'PageSetup', 'MidiChannel', 'DirectionSign', 'Tuplet', 'Duration',
    'TimeSignature', 'TripletFeel', 'MeasureHeader', 'Color', 'Marker',
    'TrackSettings', 'Track', 'GuitarString', 'MeasureClef', 'LineBreak',
    'Measure', 'VoiceDirection', 'Voice', 'BeatStrokeDirection', 'BeatStroke',
    'SlapEffect', 'BeatEffect', 'TupletBracket', 'BeatDisplay', 'Octave',
    'BeatStatus', 'Beat', 'HarmonicEffect', 'NaturalHarmonic',
    'ArtificialHarmonic', 'TappedHarmonic', 'PinchHarmonic', 'SemiHarmonic',
    'GraceEffectTransition', 'Velocities', 'GraceEffect', 'TrillEffect',
    'TremoloPickingEffect', 'SlideType', 'Fingering', 'NoteEffect', 'NoteType',
    'Note', 'Chord', 'ChordType', 'Barre', 'ChordAlteration', 'ChordExtension',
    'PitchClass', 'MixTableItem', 'WahEffect', 'MixTableChange',
    'BendType', 'BendPoint', 'BendEffect', 'RSEMasterEffect', 'RSEEqualizer',
    'Accentuation', 'RSEInstrument', 'TrackRSE',
]


class GPException(Exception):
    pass


class LenientEnum(Enum):
    """Enum subclass that doesn't have invalid members."""

    @classmethod
    def _missing_(cls, value):
        pseudoMember = object.__new__(cls)
        pseudoMember._name_ = 'unknown'
        pseudoMember._value_ = value
        return pseudoMember

    def __eq__(self, other):
        if (self.__class__ is other.__class__ and
                self._name_ == other._name_ == 'unknown'):
            return self._value_ == other._value_
        return super().__eq__(other)

    def __hash__(self):
        if self._name_ == 'unknown':
            return hash(self._value_)
        return hash(self._name_)


_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)


def __dataclass_transform__(
    *,
    eq_default: bool = True,
    order_default: bool = False,
    kw_only_default: bool = False,
    field_descriptors: tuple[Union[type, Callable[..., Any]], ...] = (()),
) -> Callable[[_T], _T]:
    return lambda a: a


@overload
@__dataclass_transform__(order_default=True, field_descriptors=(attr.attrib, attr.field))
def hashableAttrs(cls: _C, *, repr: bool = ...) -> _C: ...
@overload
@__dataclass_transform__(order_default=True, field_descriptors=(attr.attrib, attr.field))
def hashableAttrs(cls: None = ..., *, repr: bool = ...) -> Callable[[_C], _C]: ...
def hashableAttrs(cls=None, *, repr=True):  # noqa: E302
    """A fully hashable attrs decorator.

    Converts unhashable attributes, e.g. lists, to hashable ones, e.g.
    tuples.
    """
    if cls is None:
        return partial(hashableAttrs, repr=repr)

    decorated = attr.s(cls, hash=True, repr=repr, auto_attribs=True)
    origHash = decorated.__hash__

    def hash_(self):
        toEvolve = {}
        for field in attr.fields(self.__class__):
            value = getattr(self, field.name)
            if isinstance(value, (list, set)):
                newValue = tuple(value)
                toEvolve[field.name] = newValue
        newSelf = attr.evolve(self, **toEvolve)
        return origHash(newSelf)

    decorated.__hash__ = hash_
    return decorated


@hashableAttrs
class RepeatGroup:
    """This class can store the information about a group of measures
    which are repeated.
    """

    measureHeaders: list['MeasureHeader'] = attr.Factory(list)
    closings: list['MeasureHeader'] = attr.Factory(list)
    openings: list['MeasureHeader'] = attr.Factory(list)
    isClosed: bool = False

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
class Clipboard:
    startMeasure: int = 1
    stopMeasure: int = 1
    startTrack: int = 1
    stopTrack: int = 1
    startBeat: int = 1
    stopBeat: int = 1
    subBarCopy: bool = False


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
class LyricLine:
    """A lyrics line."""

    startingMeasure: int = 1
    lyrics: str = ''


@hashableAttrs(repr=False)
class Lyrics:
    """A collection of lyrics lines for a track."""

    trackChoice: int = 0
    lines: list[LyricLine] = attr.Factory(lambda: [LyricLine() for _ in range(Lyrics.maxLineCount)])

    maxLineCount = 5

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
class Point:
    """A point construct using integer coordinates."""

    x: int
    y: int


@hashableAttrs
class Padding:
    """A padding construct."""

    right: int
    top: int
    left: int
    bottom: int


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
class PageSetup:
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

    pageSize: Point = Point(210, 297)
    pageMargin: Padding = Padding(10, 15, 10, 10)
    scoreSizeProportion: float = 1.0
    headerAndFooter: HeaderFooterElements = HeaderFooterElements.all
    title: str = '%title%'
    subtitle: str = '%subtitle%'
    artist: str = '%artist%'
    album: str = '%album%'
    words: str = 'Words by %words%'
    music: str = 'Music by %music%'
    wordsAndMusic: str = 'Words & Music by %WORDSMUSIC%'
    copyright: str = 'Copyright %copyright%\nAll Rights Reserved - International Copyright Secured'
    pageNumber: str = 'Page %N%/%P%'


@hashableAttrs
class RSEEqualizer:
    """Equalizer found in master effect and track effect.

    Attribute :attr:`RSEEqualizer.knobs` is a list of values in range
    from -6.0 to 5.9. Master effect has 10 knobs, track effect has 3
    knobs. Gain is a value in range from -6.0 to 5.9 which can be found
    in both master and track effects and is named as "PRE" in Guitar Pro
    5.
    """

    knobs: list[float] = attr.Factory(list)
    gain: float = attr.ib(default=0.0)


@hashableAttrs
class RSEMasterEffect:
    """Master effect as seen in "Score information"."""

    volume: float = 0
    reverb: float = 0
    equalizer: RSEEqualizer = attr.Factory(RSEEqualizer)

    def __attrs_post_init__(self):
        if not self.equalizer.knobs:
            self.equalizer.knobs = [0.0] * 10


@hashableAttrs(repr=False)
class Song:
    """The top-level node of the song model.

    It contains basic information about the stored song.
    """

    # TODO: Store file format version here
    versionTuple: Optional[tuple[int, int, int]] = attr.ib(default=None, hash=False, eq=False)
    clipboard: Optional[Clipboard] = None
    title: str = ''
    subtitle: str = ''
    artist: str = ''
    album: str = ''
    words: str = ''
    music: str = ''
    copyright: str = ''
    tab: str = ''
    instructions: str = ''
    notice: list[str] = attr.Factory(list)
    lyrics: Lyrics = attr.Factory(Lyrics)
    pageSetup: PageSetup = attr.Factory(PageSetup)
    tempoName: str = 'Moderate'
    tempo: int = 120
    hideTempo: bool = False
    key: KeySignature = KeySignature.CMajor
    measureHeaders: list['MeasureHeader'] = attr.Factory(lambda: [MeasureHeader()])
    tracks: list['Track'] = attr.Factory(lambda self: [Track(self)], takes_self=True)
    masterEffect: RSEMasterEffect = attr.Factory(RSEMasterEffect)

    _currentRepeatGroup: RepeatGroup = attr.ib(default=attr.Factory(RepeatGroup), hash=False, eq=False, repr=False)

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
        header = MeasureHeader()
        self.measureHeaders.append(header)
        for track in self.tracks:
            measure = Measure(track, header)
            track.measures.append(measure)


@hashableAttrs
class MidiChannel:
    """A MIDI channel describes playing data for a track."""

    channel: int = 0
    effectChannel: int = 1
    instrument: int = 25
    volume: int = 104
    balance: int = 64
    chorus: int = 0
    reverb: int = 0
    phaser: int = 0
    tremolo: int = 0
    bank: int = 0

    DEFAULT_PERCUSSION_CHANNEL = 9

    @property
    def isPercussionChannel(self):
        return self.channel % 16 == self.DEFAULT_PERCUSSION_CHANNEL


@hashableAttrs
class DirectionSign:
    """A navigation sign like *Coda* or *Segno*."""

    # TODO: Consider making DirectionSign an Enum.
    name: str = ''


@hashableAttrs
class Tuplet:
    """A *n:m* tuplet."""

    enters: int = 1
    times: int = 1

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
        result = Fraction(time * self.times, self.enters)
        if result.denominator == 1:
            return result.numerator
        return result

    def isSupported(self):
        return (self.enters, self.times) in self.supportedTuplets

    @classmethod
    def fromFraction(cls, frac):
        return cls(frac.denominator, frac.numerator)


@hashableAttrs
class Duration:
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
    minTime = quarterTime * 4 // sixtyFourth * 2 // 3

    value: int = quarter
    isDotted: bool = False
    tuplet: Tuplet = attr.Factory(Tuplet)

    @property
    def time(self):
        result = self.quarterTime * 4 // self.value
        if self.isDotted:
            result += result // 2
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
        isDotted = False
        if not tuplet.isSupported():
            # Check if it's dotted
            timeFrac = Fraction(time, cls.quarterTime * 4) * Fraction(2, 3)
            exp = int(log(timeFrac, 2))
            value = 2 ** -exp
            tuplet = Tuplet.fromFraction(timeFrac * value)
            isDotted = True
        if not tuplet.isSupported():
            raise ValueError(f'cannot represent time {time} as a Guitar Pro duration')
        return Duration(value, isDotted, tuplet)


@hashableAttrs
class TimeSignature:
    """A time signature."""

    numerator: int = 4
    denominator: Duration = attr.Factory(Duration)
    beams: list[int] = attr.Factory(list)

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
class MeasureHeader:
    """A measure header contains metadata for measures over multiple
    tracks.
    """

    number: int = attr.ib(default=1, hash=False, eq=False)
    start: int = attr.ib(default=Duration.quarterTime, hash=False, eq=False)
    hasDoubleBar: bool = False
    keySignature: KeySignature = KeySignature.CMajor
    timeSignature: TimeSignature = attr.Factory(TimeSignature)
    marker: Optional['Marker'] = None
    isRepeatOpen: bool = False
    repeatAlternative: int = 0
    repeatClose: int = -1
    tripletFeel: TripletFeel = TripletFeel.none
    direction: Optional[DirectionSign] = None
    fromDirection: Optional[DirectionSign] = None

    @property
    def length(self):
        return self.timeSignature.numerator * self.timeSignature.denominator.time

    @property
    def end(self):
        return self.start + self.length


@hashableAttrs
class Color:
    """An RGB Color."""

    r: int
    g: int
    b: int


Color.black = Color(0, 0, 0)
Color.red = Color(255, 0, 0)


@hashableAttrs
class Marker:
    """A marker annotation for beats."""

    title: str = 'Section'
    color: Color = Color.red


@hashableAttrs
class TrackSettings:
    """Settings of the track."""

    tablature: bool = True
    notation: bool = True
    diagramsAreBelow: bool = False
    showRhythm: bool = False
    forceHorizontal: bool = False
    forceChannels: bool = False
    diagramList: bool = True
    diagramsInScore: bool = False
    autoLetRing: bool = False
    autoBrush: bool = False
    extendRhythmic: bool = False


class Accentuation(Enum):
    """Values of auto-accentuation on the beat found in track RSE
    settings.
    """

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
class RSEInstrument:
    instrument: int = -1
    unknown: int = -1
    soundBank: int = -1
    effectNumber: int = -1
    effectCategory: str = ''
    effect: str = ''


@hashableAttrs(repr=False)
class TrackRSE:
    instrument: RSEInstrument = attr.Factory(RSEInstrument)
    equalizer: RSEEqualizer = attr.Factory(RSEEqualizer)
    humanize: int = 0
    autoAccentuation: Accentuation = Accentuation.none

    def __attrs_post_init__(self):
        if not self.equalizer.knobs:
            self.equalizer.knobs = [0.0] * 3


@hashableAttrs(repr=False)
class Track:
    """A track contains multiple measures."""

    song: Song = attr.ib(hash=False, eq=False, repr=False)
    number: int = attr.ib(default=1, hash=False, eq=False)
    fretCount: int = 24
    offset: int = 0
    isPercussionTrack: bool = False
    is12StringedGuitarTrack: bool = False
    isBanjoTrack: bool = False
    isVisible: bool = True
    isSolo: bool = False
    isMute: bool = False
    indicateTuning: bool = False
    name: str = 'Track 1'
    measures: list['Measure'] = attr.Factory(lambda self: [Measure(self, header)
                                                           for header in self.song.measureHeaders],
                                             takes_self=True)
    strings: list['GuitarString'] = attr.Factory(lambda: [GuitarString(n, v)
                                                          for n, v in [(1, 64), (2, 59), (3, 55),
                                                                       (4, 50), (5, 45), (6, 40)]])
    port: int = 1
    channel: MidiChannel = attr.Factory(MidiChannel)
    color: Color = Color.red
    settings: TrackSettings = attr.Factory(TrackSettings)
    useRSE: bool = False
    rse: TrackRSE = attr.Factory(TrackRSE)


@hashableAttrs
class GuitarString:
    """A guitar string with a special tuning."""

    number: int
    value: int

    def __str__(self):
        notes = 'C C# D D# E F F# G G# A A# B'.split()
        octave, semitone = divmod(self.value, 12)
        return f'{notes[semitone]}{octave-1}'


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
class Measure:
    """A measure contains multiple voices of beats."""

    track: Track = attr.ib(hash=False, eq=False, repr=False)
    header: MeasureHeader = attr.ib(hash=False, eq=False, repr=False)
    clef: MeasureClef = MeasureClef.treble
    voices: list['Voice'] = attr.Factory(lambda self: [Voice(self) for _ in range(self.maxVoices)], takes_self=True)
    lineBreak: LineBreak = LineBreak.none

    maxVoices = 2

    @property
    def isEmpty(self):
        return all(voice.isEmpty for voice in self.voices)

    def _promoteHeaderAttr(name):
        def fget(self):
            return getattr(self.header, name)

        def fset(self, value):
            setattr(self.header, name, value)

        return property(fget, fset)

    number = _promoteHeaderAttr('number')
    keySignature = _promoteHeaderAttr('keySignature')
    repeatClose = _promoteHeaderAttr('repeatClose')
    start = _promoteHeaderAttr('start')
    end = _promoteHeaderAttr('end')
    length = _promoteHeaderAttr('length')
    timeSignature = _promoteHeaderAttr('timeSignature')
    isRepeatOpen = _promoteHeaderAttr('isRepeatOpen')
    tripletFeel = _promoteHeaderAttr('tripletFeel')
    marker = _promoteHeaderAttr('marker')

    del _promoteHeaderAttr


class VoiceDirection(Enum):
    """Voice directions indicating the direction of beams."""

    none = 0
    up = 1
    down = 2


@hashableAttrs(repr=False)
class Voice:
    """A voice contains multiple beats."""

    measure: Measure = attr.ib(hash=False, eq=False, repr=False)
    beats: list['Beat'] = attr.Factory(list)
    direction: VoiceDirection = VoiceDirection.none

    @property
    def isEmpty(self):
        return len(self.beats) == 0


class BeatStrokeDirection(Enum):
    """All beat stroke directions."""

    none = 0
    up = 1
    down = 2


@hashableAttrs
class BeatStroke:
    """A stroke effect for beats."""

    direction: BeatStrokeDirection = BeatStrokeDirection.none
    value: int = 0

    def swapDirection(self):
        if self.direction == BeatStrokeDirection.up:
            return attr.evolve(self, direction=BeatStrokeDirection.down)
        elif self.direction == BeatStrokeDirection.down:
            return attr.evolve(self, direction=BeatStrokeDirection.up)
        return self


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
class BeatEffect:
    """This class contains all beat effects."""

    stroke: BeatStroke = attr.Factory(BeatStroke)
    hasRasgueado: bool = False
    pickStroke: BeatStrokeDirection = BeatStrokeDirection.none
    chord: Optional['Chord'] = None
    fadeIn: bool = False
    tremoloBar: Optional['BendEffect'] = None
    mixTableChange: Optional['MixTableChange'] = None
    slapEffect: SlapEffect = SlapEffect.none
    vibrato: bool = False

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
class BeatDisplay:
    """Parameters of beat display."""

    breakBeam: bool = False
    forceBeam: bool = False
    beamDirection: VoiceDirection = VoiceDirection.none
    tupletBracket: TupletBracket = TupletBracket.none
    breakSecondary: int = 0
    breakSecondaryTuplet: bool = False
    forceBracket: bool = False


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
class Beat:
    """A beat contains multiple notes."""

    voice: Voice = attr.ib(hash=False, eq=False, repr=False)
    notes: list['Note'] = attr.Factory(list)
    duration: Duration = attr.Factory(Duration)
    text: Optional[str] = None
    start: Optional[int] = attr.ib(default=None, hash=False, eq=False)
    effect: BeatEffect = attr.Factory(BeatEffect)
    octave: Octave = Octave.none
    display: BeatDisplay = attr.Factory(BeatDisplay)
    status: BeatStatus = BeatStatus.empty

    @property
    def startInMeasure(self):
        offset = self.start - self.voice.measure.start
        return offset

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
class HarmonicEffect:
    """A harmonic note effect."""

    type: int = attr.ib(init=False)


@hashableAttrs
class NaturalHarmonic(HarmonicEffect):
    def __attrs_post_init__(self):
        self.type = 1


@hashableAttrs
class ArtificialHarmonic(HarmonicEffect):
    pitch: Optional['PitchClass'] = None
    octave: Optional[int] = None

    def __attrs_post_init__(self):
        self.type = 2


@hashableAttrs
class TappedHarmonic(HarmonicEffect):
    fret: Optional[int] = None

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


class Velocities:
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
class GraceEffect:
    """A grace note effect."""

    duration: int = 32
    fret: int = 0
    isDead: bool = False
    isOnBeat: bool = False
    transition: GraceEffectTransition = GraceEffectTransition.none
    velocity: int = Velocities.default

    @property
    def durationTime(self):
        """Get the duration of the effect."""
        return Duration.quarterTime * 4 // self.duration


@hashableAttrs
class TrillEffect:
    """A trill effect."""

    fret: int = 0
    duration: Duration = attr.Factory(Duration)


@hashableAttrs
class TremoloPickingEffect:
    """A tremolo picking effect."""

    duration: Duration = attr.Factory(Duration)


class SlideType(Enum):
    """An enumeration of all supported slide types."""

    intoFromAbove = -2
    intoFromBelow = -1
    none = 0
    shiftSlideTo = 1
    legatoSlideTo = 2
    outDownwards = 3
    outUpwards = 4


class Fingering(LenientEnum):
    """Left and right hand fingering used in tabs and chord diagram
    editor.
    """

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
class NoteEffect:
    """Contains all effects which can be applied to one note."""

    accentuatedNote: bool = False
    bend: Optional['BendEffect'] = None
    ghostNote: bool = False
    grace: Optional[GraceEffect] = None
    hammer: bool = False
    harmonic: Optional[HarmonicEffect] = None
    heavyAccentuatedNote: bool = False
    leftHandFinger: Fingering = Fingering.open
    letRing: bool = False
    palmMute: bool = False
    rightHandFinger: Fingering = Fingering.open
    slides: list[SlideType] = attr.Factory(list)
    staccato: bool = False
    tremoloPicking: Optional[TremoloPickingEffect] = None
    trill: Optional[TrillEffect] = None
    vibrato: bool = False

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


class NoteType(LenientEnum):
    rest = 0
    normal = 1
    tie = 2
    dead = 3


@hashableAttrs
class Note:
    """Describes a single note."""

    beat: Beat = attr.ib(hash=False, eq=False, repr=False)
    value: int = 0
    velocity: int = Velocities.default
    string: int = 0
    effect: NoteEffect = attr.Factory(NoteEffect)
    durationPercent: float = 1.0
    swapAccidentals: bool = False
    type: NoteType = NoteType.rest

    @property
    def realValue(self):
        return self.value + self.beat.voice.measure.track.strings[self.string - 1].value


@hashableAttrs
class Chord:
    """A chord annotation for beats."""

    length: int
    sharp: Optional[bool] = None
    root: Optional['PitchClass'] = None
    type: Optional['ChordType'] = None
    extension: Optional['ChordExtension'] = None
    bass: Optional['PitchClass'] = None
    tonality: Optional['ChordAlteration'] = None
    add: Optional[bool] = None
    name: str = ''
    fifth: Optional['ChordAlteration'] = None
    ninth: Optional['ChordAlteration'] = None
    eleventh: Optional['ChordAlteration'] = None
    firstFret: Optional[int] = None
    strings: list[int] = attr.Factory(lambda self: [-1] * self.length, takes_self=True)
    barres: list['Barre'] = attr.Factory(list)
    omissions: list[bool] = attr.Factory(list)
    fingerings: list[Fingering] = attr.Factory(list)
    show: Optional[bool] = None
    newFormat: Optional[bool] = None

    @property
    def notes(self):
        return [string for string in self.strings if string >= 0]


class ChordType(LenientEnum):
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
class Barre:
    """A single barre.

    :param start: first string from the bottom of the barre.
    :param end: last string on the top of the barre.
    """

    fret: int
    start: int = 0
    end: int = 0

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


class ChordExtension(LenientEnum):
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
class PitchClass:
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

    just: Union[str, int]
    accidental: Optional[int] = None
    value: Optional[int] = None
    intonation: Optional[str] = None

    _notes = {
        'sharp': 'C C# D D# E F F# G G# A A# B'.split(),
        'flat': 'C Db D Eb E F Gb G Ab A Bb B'.split(),
    }

    def __attrs_post_init__(self):
        if self.accidental is None:
            if isinstance(self.just, str):
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
class MixTableItem:
    """A mix table item describes a mix parameter, e.g. volume or
    reverb.
    """

    value: int = 0
    duration: int = 0
    allTracks: bool = False


@hashableAttrs
class WahEffect:
    value: int = attr.ib(default=-1)
    display: bool = False

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
class MixTableChange:
    """A MixTableChange describes a change in mix parameters."""

    instrument: Optional[MixTableItem] = None
    rse: RSEInstrument = attr.Factory(RSEInstrument)
    volume: Optional[MixTableItem] = None
    balance: Optional[MixTableItem] = None
    chorus: Optional[MixTableItem] = None
    reverb: Optional[MixTableItem] = None
    phaser: Optional[MixTableItem] = None
    tremolo: Optional[MixTableItem] = None
    tempoName: str = ''
    tempo: Optional[MixTableItem] = None
    hideTempo: bool = True
    wah: Optional[WahEffect] = None
    useRSE: bool = False

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
class BendPoint:
    """A single point within the BendEffect."""

    position: int = 0
    value: int = 0
    vibrato: bool = False

    def getTime(self, duration):
        """Gets the exact time when the point need to be played (MIDI).

        :param duration: the full duration of the effect.
        """

        return int(duration * self.position / BendEffect.maxPosition)


@hashableAttrs
class BendEffect:
    """This effect is used to describe string bends and tremolo bars."""

    type: BendType = BendType.none
    value: int = 0
    points: list[BendPoint] = attr.Factory(list)

    #: The note offset per bend point offset.
    semitoneLength = 1

    #: The max position of the bend points (x axis)
    maxPosition = 12

    #: The max value of the bend points (y axis)
    maxValue = semitoneLength * 12
