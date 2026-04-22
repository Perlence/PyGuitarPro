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
    'TimeSignature', 'TripletFeel', 'MeasureHeader', 'Fermata', 'FermataType',
    'Color', 'Marker',
    'TrackSettings', 'Track', 'GuitarString', 'MeasureClef', 'LineBreak',
    'SimileMark',
    'Measure', 'VoiceDirection', 'Voice', 'BeatStrokeDirection', 'BeatStroke',
    'SlapEffect', 'FadeType', 'CrescendoType', 'GolpeType', 'WahPedal',
    'RasgueadoType', 'BarreShape', 'BeatBeamingMode',
    'SustainPedalMarker', 'SustainPedalMarkerType',
    'BackingTrack', 'SyncPointData',
    'MusicFontSymbol', 'TechniqueSymbolPlacement', 'PercussionArticulation',
    'BeatEffect', 'TupletBracket', 'BeatDisplay', 'Octave',
    'BeatStatus', 'Beat', 'HarmonicEffect', 'NaturalHarmonic',
    'ArtificialHarmonic', 'TappedHarmonic', 'PinchHarmonic', 'SemiHarmonic',
    'FeedbackHarmonic',
    'GraceEffectTransition', 'Velocities', 'GraceEffect', 'TrillEffect',
    'TremoloPickingEffect', 'SlideType', 'VibratoType', 'Fingering', 'NoteEffect', 'NoteType',
    'NoteAccidentalMode', 'NoteOrnament',
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
    #: GPIF ``<BackingTrack>`` — external audio playback companion.
    #: ``None`` when the score has no backing track, or when the
    #: backing track is remote / YouTube (alphaTab only decodes local
    #: backing tracks). Empty for GP3/4/5.
    backingTrack: Optional['BackingTrack'] = None
    #: GPIF ``<ScoreSystemsLayout>`` — score-wide bars-per-system list.
    #: Distinct from :attr:`Track.systemsLayout`, which is per-track.
    #: Empty list means "use defaults".
    systemsLayout: list[int] = attr.Factory(list)
    #: GPIF ``<ScoreSystemsDefaultLayout>`` — fallback bars-per-system
    #: used when :attr:`systemsLayout` runs out. Matches alphaTab's
    #: documented default of 4.
    defaultSystemsLayout: int = 4

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

    #: Breve / double-whole note — two whole notes long. GPIF-only
    #: (GP3/4/5 binary formats have no breve). Encoded with a sentinel
    #: negative value so the existing power-of-two ``value`` scheme
    #: for ``whole … 128th`` stays intact; ``time`` / ``fromTime`` check
    #: for this sentinel explicitly.
    doubleWhole = -2

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
        if self.value == self.doubleWhole:
            # Breve = 2 whole notes = 8 quarter-notes.
            result = self.quarterTime * 8
        else:
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
    """An enumeration of different triplet feels.

    Mirrors alphaTab's ``TripletFeel`` enum one-for-one (7 values).
    GP3/4/5 binary formats only distinguish none / triplet-8th /
    triplet-16th; the ``dotted*`` and ``scottish*`` variants are
    GPIF-only (GP6/7/8).
    """

    #: No triplet feel.
    none = 0

    #: Eighth triplet feel — play eighth-note pairs as quarter + eighth
    #: triplet (standard jazz swing).
    eighth = 1

    #: Sixteenth triplet feel.
    sixteenth = 2

    #: GPIF: eighth-note pairs play as dotted-eighth + sixteenth
    #: (double-dotted shuffle).
    dottedEighth = 3

    #: GPIF: sixteenth-note pairs play as dotted-sixteenth + 32nd.
    dottedSixteenth = 4

    #: GPIF: eighth-note pairs play as sixteenth + dotted-eighth
    #: ("Scotch snap" — short-long instead of long-short).
    scottishEighth = 5

    #: GPIF: sixteenth-note pairs play as 32nd + dotted-sixteenth.
    scottishSixteenth = 6


class FermataType(Enum):
    """Rendered fermata glyph — the GPIF format distinguishes three durations."""

    short = 0
    medium = 1
    long = 2


@hashableAttrs
class Fermata:
    """A fermata placed on a :class:`MeasureHeader`.

    Only the GPIF format (GP6/7/8) exposes fermatas as a dedicated
    structure; GP3/4/5 implied them via tempo changes. Multiple fermatas
    may appear in one bar.
    """

    type: FermataType = FermataType.short
    length: float = 0.0
    #: Offset from the start of the bar, in MIDI ticks (``quarterTime`` per
    #: quarter-note — matches alphaTab's conversion).
    offset: int = 0


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
    #: GPIF: fermatas placed within the bar, ordered by :attr:`Fermata.offset`.
    #: Empty for GP3/4/5 (format has no dedicated fermata element).
    fermatas: list[Fermata] = attr.Factory(list)
    #: GPIF ``<FreeTime>`` — cadenza / rubato / out-of-tempo bar. The
    #: renderer should replace the time signature with the "free time"
    #: annotation. Always ``False`` for GP3/4/5 (the binary formats
    #: have no equivalent marker).
    isFreeTime: bool = False
    #: GPIF ``<XProperty id="1124073984">`` — master-bar display scale.
    #: ``1.0`` means default size; smaller values shrink the bar on
    #: the page, larger values stretch it.
    displayScale: float = 1.0
    #: GPIF ``<XProperty id="1124139010">`` — note duration unit that
    #: the :attr:`beamingRuleGroups` entries count in. ``0`` means no
    #: custom beaming rule was set (use the time-signature default).
    beamingRuleDuration: int = 0
    #: GPIF ``<XProperty id="1124139264+n">`` — per-group size list that
    #: together with :attr:`beamingRuleDuration` describes how beams
    #: should cluster beats within the bar. Empty list means "use the
    #: time-signature default".
    beamingRuleGroups: list[int] = attr.Factory(list)
    #: GPIF ``<Automation><Type>SyncPoint>`` entries attached to this
    #: master-bar, linking bar positions to backing-track timestamps.
    #: Empty for non-audio scores and for GP3/4/5.
    syncPoints: 'list[SyncPointData]' = attr.Factory(list)

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


@hashableAttrs
class GpifSound:
    """A single GPIF ``<Sound>`` entry — one soundbank/MIDI program pair
    a track can play. GPIF tracks carry a list of these (e.g. clean +
    distortion channels with different MIDI programs or bank selects).

    Mirrors alphaTab's ``GpifSound`` one-for-one. ``bank`` is the combined
    14-bit value ``((MSB & 0x7f) << 7) | LSB`` — same formula as alphaTab
    and as MIDI's Bank Select (CC 0 / CC 32).
    """

    name: str = ''
    path: str = ''
    role: str = ''
    program: int = 0
    bank: int = 0


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
    #: Full list of GPIF ``<Sound>`` entries for this track. Populated
    #: by the GP7/GP8 reader; empty for GP3/4/5 (which don't expose this
    #: richer metadata). The first entry's MIDI program/bank is also
    #: mirrored onto ``channel.instrument``/``channel.bank`` for
    #: back-compat with code that only consults :class:`MidiChannel`.
    sounds: list['GpifSound'] = attr.Factory(list)
    #: GPIF ``<Instrument ref="...">`` — a soundbank identifier such as
    #: ``s-gtr6`` (6-string steel guitar), ``e-gtr6`` (6-string electric),
    #: ``e-bass4``, ``drmkt`` (drum kit), or a grand-staff variant
    #: ending in ``-gs`` / ``GrandStaff``. Empty string when the file
    #: doesn't carry this element (typical for GP7/GP8 exports, which
    #: put the instrument type in ``<InstrumentSet>`` instead; live for
    #: GP6-era GPIF files).
    instrumentRef: str = ''
    #: GPIF ``<SystemsLayout>`` — bars-per-system for this track, in
    #: score order. Empty list when the element isn't present.
    systemsLayout: list[int] = attr.Factory(list)
    #: GPIF ``<SystemsDefautLayout>`` (the typo is in the GPIF format
    #: itself) — default bars-per-system used when ``systemsLayout``
    #: runs out. Guitar Pro's own default is 4.
    defaultSystemsLayout: int = 4
    #: GPIF ``<NotationPatch><LineCount>`` — number of lines in the
    #: standard-notation staff (5 for standard, often 1 for percussion
    #: single-line cue). Default follows alphaTab's fallback of 5.
    staffLineCount: int = 5
    #: GPIF ``<Property name="Tuning"><Label>`` — human-readable tuning
    #: name such as ``"Drop D"`` or ``"Standard"``. Empty when the file
    #: doesn't annotate the tuning. Mirrors alphaTab's
    #: ``staff.stringTuning.name``.
    tuningName: str = ''
    #: GPIF ``<PartSounding><TranspositionPitch>`` — chromatic offset (in
    #: semitones) between written and sounding pitch for a transposing
    #: instrument (e.g. Bb trumpet = -2). Mirrors alphaTab's
    #: ``staff.displayTranspositionPitch``.
    transpositionPitch: int = 0
    #: GPIF ``<PartSounding><NominalKey>`` — the key the instrument is
    #: written in (e.g. ``"Bb"``, ``"Eb"``). Used by the renderer to
    #: transpose key signatures. Empty when not specified.
    nominalKey: str = ''
    #: GPIF percussion articulation table — one entry per drum-kit
    #: slot defined in ``<InstrumentSet><Elements>``. Populated only
    #: for percussion tracks; the later ``<NotationPatch>`` may update
    #: entries' :attr:`PercussionArticulation.staffLine`. Empty for
    #: pitched tracks.
    percussionArticulations: 'list[PercussionArticulation]' = attr.Factory(list)


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


class SimileMark(Enum):
    """Simile-mark annotation placed on a bar (GPIF format).

    A simile mark tells the performer to repeat the previous bar(s).
    Mirrors alphaTab's ``SimileMark`` enum.
    """

    #: No simile mark.
    none = 0
    #: Repeat the previous bar once.
    simple = 1
    #: First bar of a two-bar simile group.
    firstOfDouble = 2
    #: Second bar of a two-bar simile group.
    secondOfDouble = 3


@hashableAttrs(repr=False)
class Measure:
    """A measure contains multiple voices of beats."""

    track: Track = attr.ib(hash=False, eq=False, repr=False)
    header: MeasureHeader = attr.ib(hash=False, eq=False, repr=False)
    clef: MeasureClef = MeasureClef.treble
    voices: list['Voice'] = attr.Factory(lambda self: [Voice(self) for _ in range(self.maxVoices)], takes_self=True)
    lineBreak: LineBreak = LineBreak.none
    #: GPIF simile-mark annotation. None for GP3/4/5 (format has no
    #: equivalent element).
    simileMark: SimileMark = SimileMark.none
    #: GPIF ``<XProperty id="1124139520">`` — per-measure display scale
    #: (independent of :attr:`MeasureHeader.displayScale`, which is the
    #: master-bar / score-wide scale). ``1.0`` means default.
    displayScale: float = 1.0
    #: GPIF sustain-pedal markers within this bar, each with a
    #: ``ratioPosition`` in ``[0, 1]``. Empty for GP3/4/5 (no sub-bar
    #: pedal concept) and for GPIF bars without pedal automations.
    sustainPedals: 'list[SustainPedalMarker]' = attr.Factory(list)

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


class FadeType(Enum):
    """Beat-level fade effect.

    GP3/4/5 only encode fade-in, so those readers toggle :attr:`BeatEffect.fadeIn`.
    The GPIF format stores a richer ``<Fadding>`` element that distinguishes
    ``FadeIn``, ``FadeOut`` and ``VolumeSwell`` — mirrored here as
    :attr:`FadeType` and exposed as :attr:`BeatEffect.fade`.
    """

    none = 0
    fadeIn = 1
    fadeOut = 2
    volumeSwell = 3


class CrescendoType(Enum):
    """Beat-level hairpin direction.

    Mirrors alphaTab's ``CrescendoType``. Stored on :attr:`BeatEffect.crescendo`.
    """

    none = 0
    crescendo = 1
    decrescendo = 2


class GolpeType(Enum):
    """Flamenco "golpe" body-tap indication on a beat (GPIF format).

    Mirrors alphaTab's ``GolpeType``. Stored on :attr:`BeatEffect.golpe`.
    """

    none = 0
    finger = 1
    thumb = 2


class WahPedal(Enum):
    """GPIF wah-pedal state marker placed on a beat.

    Distinct from :class:`WahEffect` (GP5 mix-table entry with a numeric
    pedal position): the GPIF format stores a simple Open/Closed
    annotation on the beat. Mirrors alphaTab's ``WahPedal``.
    """

    none = 0
    open = 1
    closed = 2


class MusicFontSymbol(Enum):
    """Music-font glyph identifier used in GPIF notation patches.

    Mirrors alphaTab's ``MusicFontSymbol`` subset actually referenced
    inside ``<Noteheads>`` / ``<TechniqueSymbol>`` payloads. Extra
    values alphaTab defines but GPIF never emits aren't listed — when
    alphaTab's decoder encounters a token it doesn't know, it falls
    back to :attr:`none`, and so do we.

    The SMuFL / alphaTab enum names are preserved (CamelCase suffix
    after ``Notehead`` / ``Artic`` / ``Pict`` / ``Strings`` / ``Guitar``)
    so a reader can match on the exact strings GPIF stores.
    """

    none = 0
    # <Noteheads> glyphs
    noteheadDoubleWholeSquare = 1
    noteheadDoubleWhole = 2
    noteheadWhole = 3
    noteheadHalf = 4
    noteheadBlack = 5
    noteheadNull = 6
    noteheadXOrnate = 7
    noteheadTriangleUpWhole = 8
    noteheadTriangleUpHalf = 9
    noteheadTriangleUpBlack = 10
    noteheadDiamondBlackWide = 11
    noteheadDiamondWhite = 12
    noteheadDiamondWhiteWide = 13
    noteheadCircleX = 14
    noteheadCircleSlash = 15
    noteheadXBlack = 16
    noteheadXHalf = 17
    noteheadXWhole = 18
    noteheadHeavyX = 19
    noteheadHeavyXHat = 20
    noteheadParenthesis = 21
    # <TechniqueSymbol> glyphs
    pictEdgeOfCymbal = 100
    articStaccatoAbove = 101
    stringsUpBow = 102
    stringsDownBow = 103
    guitarGolpe = 104


class TechniqueSymbolPlacement(Enum):
    """Where the technique-symbol glyph is drawn relative to the note.

    Mirrors alphaTab's ``TechniqueSymbolPlacement`` enum.
    """

    outside = 0
    inside = 1
    above = 2
    below = 3


@hashableAttrs
class PercussionArticulation:
    """A single drum-kit articulation entry from GPIF.

    GPIF enumerates each way a drum or percussion instrument is
    struck (e.g. Snare "hit" / "rim" / "side stick") under
    ``<InstrumentSet><Elements><Element><Articulations><Articulation>``,
    and a later ``<NotationPatch>`` may override ``staffLine``.

    Mirrors alphaTab's ``InstrumentArticulation``. PyGuitarPro never
    synthesises audio, so these fields are preserved for round-trip
    and for consumers that do actually render drum staves (e.g. the
    future GP7/GP8 writer).
    """

    #: ``<Element><Name>`` — the kit slot (e.g. "Kick", "Snare", "Hihat").
    elementType: str = ''
    #: First integer of ``<InputMidiNumbers>`` — the incoming MIDI note
    #: for this articulation (used to dispatch on import).
    id: int = 0
    #: ``<OutputMidiNumber>`` — the MIDI note alphaSynth plays back.
    outputMidiNumber: int = -1
    #: ``<TechniqueSymbol>`` glyph identifier.
    techniqueSymbol: MusicFontSymbol = MusicFontSymbol.none
    #: ``<TechniquePlacement>`` — where the technique-symbol renders.
    techniqueSymbolPlacement: TechniqueSymbolPlacement = TechniqueSymbolPlacement.outside
    #: First entry of ``<Noteheads>`` — notehead for quarter and shorter.
    noteHeadDefault: MusicFontSymbol = MusicFontSymbol.none
    #: Second entry — notehead for half notes. Falls back to
    #: ``noteHeadDefault`` when the source token is "noteheadNone".
    noteHeadHalf: MusicFontSymbol = MusicFontSymbol.none
    #: Third entry — notehead for whole notes. Falls back to
    #: ``noteHeadDefault`` when the source token is "noteheadNone".
    noteHeadWhole: MusicFontSymbol = MusicFontSymbol.none
    #: ``<StaffLine>`` — vertical staff-line position (0 = middle line,
    #: negative = below, positive = above). NotationPatch entries
    #: override this value on a previously-seen articulation.
    staffLine: int = 0


@hashableAttrs
class BackingTrack:
    """GPIF ``<BackingTrack>`` — external audio file attached to the
    score for playback alongside (or instead of) the synthesized MIDI.

    Mirrors alphaTab's ``BackingTrack`` model. AlphaTab exposes only the
    raw audio bytes; PyGuitarPro additionally preserves a few of the
    GPIF metadata fields so a future writer can regenerate the same
    ``<BackingTrack>`` block.

    Only created when GPIF carries ``<Enabled>true</Enabled>`` and
    ``<Source>Local</Source>`` (the only backing-track source alphaTab
    currently supports — remote / YouTube links are not decoded).
    """

    name: str = ''
    shortName: str = ''
    #: Frame padding converted to milliseconds (GPIF stores it as an
    #: integer frame count at the alphaTab sample rate).
    paddingMs: float = 0.0
    #: AssetId referenced inside the ZIP; matches the id attribute on
    #: the ``<Asset id="...">`` child inside ``<Assets>``.
    assetId: str = ''
    #: GPIF ``<Asset><EmbeddedFilePath>`` — the raw-audio ZIP entry
    #: path (typically ``Content/Assets/<uuid>.ogg``). Preserved so a
    #: future writer can repair the ``<Asset>`` element and emit the
    #: audio payload back into the archive.
    embeddedFilePath: str = ''
    #: The audio payload itself — the raw bytes of the file at
    #: :attr:`embeddedFilePath`. ``None`` when the score has a
    #: ``<BackingTrack>`` reference but the ZIP doesn't actually
    #: contain the asset (edge case; alphaTab discards the whole
    #: BackingTrack in that case — we keep the metadata so the writer
    #: can at least regenerate the reference).
    rawAudioFile: Optional[bytes] = attr.ib(default=None, hash=False, eq=False, repr=False)


@hashableAttrs
class SyncPointData:
    """GPIF ``<Automation><Type>SyncPoint</Type>`` payload — links a
    bar position to an absolute timestamp in the backing track audio.

    Mirrors alphaTab's ``SyncPointData``. ``millisecondOffset`` is
    pre-adjusted for the backing track's ``FramePadding`` (subtracted
    as alphaTab does), so the value represents the point in the bar
    where the backing-track audio should reach.
    """

    barIndex: int = 0
    barOccurrence: int = 0
    millisecondOffset: float = 0.0


class SustainPedalMarkerType(Enum):
    """Sustain-pedal action at a given position in a bar.

    Mirrors alphaTab's ``SustainPedalMarkerType``. GP3/4/5 encode a
    sustain pedal as a single MIDI controller event; GPIF models
    explicit down / hold / up events with sub-bar positions to drive
    piano-style pedal rendering and playback.
    """

    #: Press the pedal from this point onward.
    down = 0
    #: Pedal stays held across this marker (used when a pedal is
    #: held for a whole bar).
    hold = 1
    #: Release the pedal at this point.
    up = 2


@hashableAttrs
class SustainPedalMarker:
    """A single sustain-pedal marker within a measure.

    GPIF attaches these via the track ``<Automations>`` list with
    ``<Type>SustainPedal</Type>``. Each marker carries:

    - ``ratioPosition`` — 0.0 … 1.0 fraction of the bar where the
      action occurs (0.0 = bar start, 0.5 = halfway, 1.0 = bar end);
    - ``type`` — down / hold / up (see :class:`SustainPedalMarkerType`).

    Mirrors alphaTab's ``SustainPedalMarker``. PyGuitarPro exposes them
    only on the GPIF reader (GP3/4/5 have no per-bar sub-position
    concept for sustain control).
    """

    ratioPosition: float = 0.0
    type: SustainPedalMarkerType = SustainPedalMarkerType.down


class BeatBeamingMode(Enum):
    """Explicit beaming override for a beat (GPIF XProperties).

    GPIF exposes two XProperties that collectively determine how the
    beat beams connect to neighbouring beats:

      - ``ForceMergeWithNext``  — force a beam to the next beat even
        if the rhythm would normally split.
      - ``ForceSplitToNext``    — force a split between this and the
        next beat.
      - ``ForceSplitOnSecondaryToNext`` — split only the secondary
        beams (8th-note stems stay joined, 16th-note tails separate).

    ``auto`` lets the renderer choose based on time-signature rules.
    Mirrors alphaTab's ``BeatBeamingMode`` enum.
    """

    auto = 0
    forceMergeWithNext = 1
    forceSplitToNext = 2
    forceSplitOnSecondaryToNext = 3


class BarreShape(Enum):
    """Beat-level barré indication.

    GPIF's ``<BarreFret>`` sets the fret; ``<BarreString>`` sets the
    shape (0 = full bar across all strings, 1 = half / partial). GP3/4/5
    encode barré only as part of the chord diagram, not per-beat.
    Mirrors alphaTab's ``BarreShape`` enum.
    """

    none = 0
    full = 1
    half = 2


class RasgueadoType(Enum):
    """Fingering pattern for a flamenco rasgueado strum.

    GPIF encodes the specific right-hand fingering pattern as an 18-value
    enum. GP3/4/5 only encode "has rasgueado" as a boolean
    (:attr:`BeatEffect.hasRasgueado`), so this enum is populated only by
    the GPIF reader. Names mirror alphaTab's ``Rasgueado`` enum:
    single-finger strokes (``ii``, ``mi``), triplet and anapaest
    variants of multi-finger combinations (``MiiTriplet``,
    ``MiiAnapaest`` = m-i-i), and longer patterns (``Ppp``, ``Amii``,
    ``Eamii``, ``Peami``).
    """

    none = 0
    ii = 1
    mi = 2
    miiTriplet = 3
    miiAnapaest = 4
    pmpTriplet = 5
    pmpAnapaest = 6
    peiTriplet = 7
    peiAnapaest = 8
    paiTriplet = 9
    paiAnapaest = 10
    amiTriplet = 11
    amiAnapaest = 12
    ppp = 13
    amii = 14
    amip = 15
    eami = 16
    eamii = 17
    peami = 18


@hashableAttrs
class BeatEffect:
    """This class contains all beat effects."""

    stroke: BeatStroke = attr.Factory(BeatStroke)
    #: GP3/4/5 encode rasgueado as a bare boolean. GPIF refines this into
    #: an 18-variant enum (:attr:`rasgueado`). ``hasRasgueado`` stays the
    #: canonical cross-version flag — it is kept ``True`` whenever
    #: ``rasgueado`` is anything other than :attr:`RasgueadoType.none`.
    hasRasgueado: bool = False
    #: GPIF rasgueado fingering pattern. Stays :attr:`RasgueadoType.none`
    #: for GP3/4/5 files (which can still set :attr:`hasRasgueado`).
    rasgueado: RasgueadoType = RasgueadoType.none
    pickStroke: BeatStrokeDirection = BeatStrokeDirection.none
    chord: Optional['Chord'] = None
    fadeIn: bool = False
    #: GPIF fade variant. ``fadeIn`` stays the canonical field for GP3/4/5
    #: compatibility; ``fade`` carries the full three-way distinction.
    fade: FadeType = FadeType.none
    tremoloBar: Optional['BendEffect'] = None
    mixTableChange: Optional['MixTableChange'] = None
    slapEffect: SlapEffect = SlapEffect.none
    vibrato: bool = False
    #: GPIF hairpin (crescendo / decrescendo) annotation.
    crescendo: CrescendoType = CrescendoType.none
    #: GPIF slashed-rhythm notation marker.
    slashed: bool = False
    #: GPIF "dead slap" guitar body slap marker.
    deadSlapped: bool = False
    #: GPIF flamenco "golpe" finger/thumb tap marker.
    golpe: GolpeType = GolpeType.none
    #: GPIF wah pedal state (Open / Closed). Independent of :class:`WahEffect`.
    wahPedal: WahPedal = WahPedal.none
    #: GPIF ``<BarreFret>`` — fret at which the beat is barred. ``0`` means
    #: no barre. GP3/4/5 carry barre info only on :class:`Chord`, not
    #: per-beat.
    barreFret: int = 0
    #: GPIF ``<BarreString>`` shape — :attr:`BarreShape.full` (all strings)
    #: or :attr:`BarreShape.half` (partial). :attr:`BarreShape.none`
    #: when no barre is active.
    barreShape: BarreShape = BarreShape.none

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
    #: GPIF backing-track synchronisation timestamp in milliseconds.
    #: ``None`` means no timer is displayed on this beat.
    timer: Optional[int] = None
    #: GPIF beat-level lyrics — one string per lyric line attached to
    #: this beat (GPIF supports multiple verses stacked on the same
    #: beat). Empty for GP3/4/5 (those formats attach lyrics to the
    #: track, not to individual beats; see :class:`LyricLine`).
    lyrics: list[str] = attr.Factory(list)
    #: GPIF ``<XProperty id="1124204546|1124204552|…">`` — explicit beaming
    #: override. ``auto`` means the renderer decides from the rhythm.
    beamingMode: BeatBeamingMode = BeatBeamingMode.auto
    #: GPIF ``<XProperty id="1124204545">`` — force the beam to flip
    #: direction (up / down) regardless of stem rules.
    invertBeamDirection: bool = False
    #: GPIF ``<XProperty id="687935489">`` — duration of a brush /
    #: arpeggio strum in MIDI ticks. ``0`` means no custom duration
    #: (the renderer / player uses its default).
    brushDuration: int = 0

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


@hashableAttrs
class FeedbackHarmonic(HarmonicEffect):
    """GPIF "feedback" harmonic — amp-feedback style harmonic sustain.

    Mirrors alphaTab's ``HarmonicType.Feedback``. Binary GP3/4/5 have
    no equivalent; only set by the GPIF (GP6/7/8) reader.
    """

    def __attrs_post_init__(self):
        self.type = 6


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
    #: Downward pick slide — introduced in Guitar Pro 7.
    pickSlideDown = 5
    #: Upward pick slide — introduced in Guitar Pro 7.
    pickSlideUp = 6


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


class VibratoType(Enum):
    """Vibrato intensity on a note.

    GP3/4/5 only encode a boolean "has vibrato"; the GPIF format
    introduces two intensity variants which alphaTab exposes via a
    ``VibratoType`` enum. PGP keeps :attr:`NoteEffect.vibrato` (bool)
    for legacy readers and adds :attr:`NoteEffect.vibratoType` for GPIF
    precision.
    """

    none = 0
    slight = 1
    wide = 2


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
    #: GPIF: the note is struck by the fretting hand (without picking).
    #: Rendered as a small circled "T" above the note.
    leftHandTapped: bool = False
    letRing: bool = False
    palmMute: bool = False
    rightHandFinger: Fingering = Fingering.open
    slides: list[SlideType] = attr.Factory(list)
    staccato: bool = False
    #: GPIF tenuto articulation — hold the note its full written value.
    #: Independent from :attr:`letRing`; corresponds to alphaTab's
    #: ``AccentuationType.Tenuto``.
    tenuto: bool = False
    tremoloPicking: Optional[TremoloPickingEffect] = None
    trill: Optional[TrillEffect] = None
    vibrato: bool = False
    #: GPIF vibrato intensity. `vibrato` stays the canonical bool for
    #: GP3/4/5; `vibratoType` carries the Slight/Wide distinction.
    vibratoType: VibratoType = VibratoType.none

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


class NoteOrnament(Enum):
    """Ornament symbol attached to a note (GPIF format).

    Mirrors alphaTab's ``NoteOrnament`` enum.
    """

    none = 0
    invertedTurn = 1
    turn = 2
    upperMordent = 3
    lowerMordent = 4


class NoteAccidentalMode(Enum):
    """How the accidental sign of a note is displayed.

    Mirrors alphaTab's ``NoteAccidentalMode``. The GPIF format stores
    the display choice separately from the pitch so that e.g. E♭ and
    D♯ can be distinguished in notation even though they sound the same.
    """

    #: Accidentals are calculated automatically from key signature.
    default = 0
    #: Force no accidental sign.
    forceNone = 1
    #: Force a natural sign (♮).
    forceNatural = 2
    #: Force a sharp sign (♯).
    forceSharp = 3
    #: Force a double-sharp sign (𝄪).
    forceDoubleSharp = 4
    #: Force a flat sign (♭).
    forceFlat = 5
    #: Force a double-flat sign (𝄫).
    forceDoubleFlat = 6


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
    #: GPIF: explicit choice how the accidental is rendered (e.g. E♭ vs D♯).
    accidentalMode: NoteAccidentalMode = NoteAccidentalMode.default
    #: GPIF percussion articulation index. ``-1`` means unset / pitched track.
    #: On percussion tracks, references an entry of the track's articulation
    #: list or a built-in articulation number.
    percussionArticulation: int = -1
    #: GPIF ornament glyph (turn / inverted turn / mordent variants).
    ornament: NoteOrnament = NoteOrnament.none
    #: Explicit request to display this note's string number beside it.
    #: GPIF marks this per note; older binary formats have no equivalent.
    showStringNumber: bool = False
    #: GPIF ``<Octave>`` — GP6-era pitch encoding, absolute octave number.
    #: Current GP7/GP8 exports encode pitch via :attr:`accidentalMode` +
    #: :attr:`value` instead, but GP6 files (and backwards-compatible
    #: exports from newer GP) may still carry this.
    octave: int = 0
    #: GPIF ``<Tone>`` — GP6-era pitch encoding, diatonic step within
    #: the octave (0=C, 1=D, 2=E, …, 6=B). ``-1`` means unset — the
    #: GP6→GP7 export pipeline may drop Tone while keeping Octave, so
    #: alphaTab treats encountering ``<Octave>`` alone as resetting
    #: tone to 0; PyGuitarPro's reader mirrors that behaviour.
    tone: int = -1

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
    #: GPIF ``<Property name="ShowName" value="true|false"/>`` — render
    #: the chord's name text above the diagram. Default ``True``
    #: matches alphaTab's ``Chord`` constructor.
    showName: bool = True
    #: GPIF ``<Property name="ShowFingering" value="true|false"/>`` —
    #: render finger numbers on the diagram.
    showFingering: bool = True

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
