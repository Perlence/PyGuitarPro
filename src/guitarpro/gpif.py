"""Maps a Guitar Pro ``score.gpif`` XML document into the :class:`Song` model.

The GPIF format (used by GP6 and GP7) stores the score as a set of
cross-referenced lists -- ``MasterBars`` point at ``Bars`` by id, ``Bars``
point at ``Voices``, ``Voices`` point at ``Beats``, ``Beats`` point at
``Notes`` and ``Rhythms``.  This parser resolves those references and builds
the same object tree the binary readers produce.

The mapping covers the core musical content: song info, tracks and tunings,
master bars and time signatures, voices, beats, durations and notes.
Advanced effects are not yet translated.
"""
import xml.etree.ElementTree as ET

from . import models as gp

__all__ = ('GPIFParser', 'GPIFWriter')

# GPIF NoteValue -> Duration.value
_NOTE_VALUES = {
    'Whole': gp.Duration.whole,
    'Half': gp.Duration.half,
    'Quarter': gp.Duration.quarter,
    'Eighth': gp.Duration.eighth,
    '16th': gp.Duration.sixteenth,
    '32nd': gp.Duration.thirtySecond,
    '64th': gp.Duration.sixtyFourth,
    '128th': gp.Duration.hundredTwentyEighth,
}

# GPIF Dynamic -> velocity
_DYNAMICS = {
    'PPP': gp.Velocities.pianoPianissimo,
    'PP': gp.Velocities.pianissimo,
    'P': gp.Velocities.piano,
    'MP': gp.Velocities.mezzoPiano,
    'MF': gp.Velocities.mezzoForte,
    'F': gp.Velocities.forte,
    'FF': gp.Velocities.fortissimo,
    'FFF': gp.Velocities.forteFortissimo,
}

# Inverse lookups for writing.
_NOTE_VALUE_NAMES = {value: name for name, value in _NOTE_VALUES.items()}
_DYNAMIC_NAMES = {velocity: name for name, velocity in _DYNAMICS.items()}


class GPIFParser:
    def __init__(self, data, versionTuple=None):
        if isinstance(data, (bytes, bytearray)):
            self.root = ET.fromstring(data)
        else:
            self.root = ET.fromstring(data.encode() if isinstance(data, str) else data)
        self.versionTuple = versionTuple

    # -- helpers --------------------------------------------------------

    def _text(self, path, default=''):
        element = self.root.find(path)
        if element is not None and element.text is not None:
            return element.text.strip()
        return default

    @staticmethod
    def _index(elements):
        """Index a list of elements by their ``id`` attribute."""
        return {e.get('id'): e for e in elements}

    @staticmethod
    def _property(element, name):
        """Return the ``<Property name="...">`` child of *element*, or None."""
        if element is None:
            return None
        for prop in element.findall('./Properties/Property'):
            if prop.get('name') == name:
                return prop
        return None

    # -- entry point ----------------------------------------------------

    def readSong(self):
        root = self.root
        self.bars = self._index(root.findall('./Bars/Bar'))
        self.voices = self._index(root.findall('./Voices/Voice'))
        self.beats = self._index(root.findall('./Beats/Beat'))
        self.notes = self._index(root.findall('./Notes/Note'))
        self.rhythms = self._index(root.findall('./Rhythms/Rhythm'))

        song = gp.Song(versionTuple=self.versionTuple)
        self._readScoreInfo(song)
        self._readTempo(song)

        masterBars = root.findall('./MasterBars/MasterBar')
        self._readMeasureHeaders(song, masterBars)
        self._readTracks(song)
        self._readMeasures(song, masterBars)
        return song

    # -- score info -----------------------------------------------------

    def _readScoreInfo(self, song):
        song.title = self._text('./Score/Title')
        song.subtitle = self._text('./Score/SubTitle')
        song.artist = self._text('./Score/Artist')
        song.album = self._text('./Score/Album')
        song.words = self._text('./Score/Words')
        song.music = self._text('./Score/Music')
        song.copyright = self._text('./Score/Copyright')
        song.tab = self._text('./Score/Tabber')
        song.instructions = self._text('./Score/Instructions')
        notices = self._text('./Score/Notices')
        song.notice = notices.splitlines() if notices else []

    def _readTempo(self, song):
        for automation in self.root.findall('./MasterTrack/Automations/Automation'):
            if automation.findtext('Type') == 'Tempo':
                value = (automation.findtext('Value') or '').split()
                if value:
                    song.tempo = int(round(float(value[0])))
                break

    # -- measure headers ------------------------------------------------

    def _readMeasureHeaders(self, song, masterBars):
        song.measureHeaders = []
        for number, masterBar in enumerate(masterBars, start=1):
            header = gp.MeasureHeader(number=number)
            time = masterBar.findtext('Time')
            if time and '/' in time:
                numerator, denominator = time.split('/')
                header.timeSignature = gp.TimeSignature(
                    numerator=int(numerator),
                    denominator=gp.Duration(value=int(denominator)),
                )
            repeat = masterBar.find('Repeat')
            if repeat is not None:
                if repeat.get('start') == 'true':
                    header.isRepeatOpen = True
                if repeat.get('end') == 'true':
                    header.repeatClose = int(repeat.get('count', 0))
            song.addMeasureHeader(header)
        if not song.measureHeaders:
            song.measureHeaders = [gp.MeasureHeader()]

    # -- tracks ---------------------------------------------------------

    def _readTracks(self, song):
        trackElements = self.root.findall('./Tracks/Track')
        song.tracks = []
        for number, element in enumerate(trackElements, start=1):
            track = gp.Track(song, number=number)
            track.name = (element.findtext('Name') or '').strip() or track.name
            track.strings = self._readTuning(element)
            track.measures = []
            song.tracks.append(track)
        if not song.tracks:
            song.tracks = [gp.Track(song)]

    def _readTuning(self, trackElement):
        tuning = self._property(trackElement, 'Tuning')
        pitches = None
        if tuning is not None:
            text = tuning.findtext('Pitches')
            if text:
                pitches = [int(p) for p in text.split()]
        if not pitches:
            # Default standard 6-string tuning, low to high.
            pitches = [40, 45, 50, 55, 59, 64]
        # GPIF lists pitches low-to-high; GuitarString #1 is the highest.
        return [gp.GuitarString(number=i + 1, value=value)
                for i, value in enumerate(reversed(pitches))]

    # -- measures / voices / beats / notes ------------------------------

    def _readMeasures(self, song, masterBars):
        for trackIndex, track in enumerate(song.tracks):
            for header, masterBar in zip(song.measureHeaders, masterBars):
                measure = gp.Measure(track, header)
                measure.voices = []
                barIds = (masterBar.findtext('Bars') or '').split()
                barId = barIds[trackIndex] if trackIndex < len(barIds) else None
                bar = self.bars.get(barId)
                self._readVoices(measure, bar)
                track.measures.append(measure)

    def _readVoices(self, measure, bar):
        voiceIds = []
        if bar is not None:
            voiceIds = (bar.findtext('Voices') or '').split()
        start = measure.start
        for voiceId in voiceIds:
            if voiceId == '-1':
                continue
            voice = gp.Voice(measure)
            self._readBeats(voice, self.voices.get(voiceId), start)
            measure.voices.append(voice)
        # The model expects at least ``maxVoices`` voices per measure.
        while len(measure.voices) < gp.Measure.maxVoices:
            measure.voices.append(gp.Voice(measure))

    def _readBeats(self, voice, voiceElement, start):
        if voiceElement is None:
            return start
        for beatId in (voiceElement.findtext('Beats') or '').split():
            beatElement = self.beats.get(beatId)
            if beatElement is None:
                continue
            beat = gp.Beat(voice)
            beat.start = start
            beat.duration = self._readDuration(beatElement)
            self._readBeatNotes(beat, beatElement)
            beat.status = gp.BeatStatus.normal if beat.notes else gp.BeatStatus.rest
            voice.beats.append(beat)
            start += beat.duration.time
        return start

    def _readDuration(self, beatElement):
        rhythm = None
        ref = beatElement.find('Rhythm')
        if ref is not None:
            rhythm = self.rhythms.get(ref.get('ref'))
        duration = gp.Duration()
        if rhythm is None:
            return duration
        noteValue = rhythm.findtext('NoteValue')
        duration.value = _NOTE_VALUES.get(noteValue, gp.Duration.quarter)
        dots = rhythm.find('AugmentationDot')
        if dots is not None and int(dots.get('count', 0)) > 0:
            duration.isDotted = True
        tuplet = rhythm.find('PrimaryTuplet')
        if tuplet is not None:
            duration.tuplet = gp.Tuplet(
                enters=int(tuplet.get('num', 1)),
                times=int(tuplet.get('den', 1)),
            )
        return duration

    def _readBeatNotes(self, beat, beatElement):
        dynamic = beatElement.findtext('Dynamic')
        velocity = _DYNAMICS.get(dynamic, gp.Velocities.default)
        noteIds = beatElement.findtext('Notes')
        if not noteIds:
            return
        for noteId in noteIds.split():
            noteElement = self.notes.get(noteId)
            if noteElement is None:
                continue
            beat.notes.append(self._readNote(beat, noteElement, velocity))

    def _readNote(self, beat, noteElement, velocity):
        note = gp.Note(beat, velocity=velocity, type=gp.NoteType.normal)
        fret = self._property(noteElement, 'Fret')
        if fret is not None:
            note.value = int(fret.findtext('Fret') or 0)
        string = self._property(noteElement, 'String')
        if string is not None:
            # GPIF strings are 0-based from the highest; the model is 1-based.
            note.string = int(string.findtext('String') or 0) + 1
        if noteElement.find('Tie') is not None:
            note.type = gp.NoteType.tie
        return note


class GPIFWriter:
    """Serializes a :class:`Song` into a ``score.gpif`` XML document.

    The model is a tree (measure -> voice -> beat -> note) while GPIF stores
    flat, cross-referenced lists joined by ``id``.  This writer hoists beats,
    notes and rhythms into global tables, assigns ids and emits the reference
    strings the format expects.  It writes the same subset of the model that
    :class:`GPIFParser` reads back.
    """

    def __init__(self, song):
        self.song = song
        self.root = ET.Element('GPIF')
        # Global id counters and lists for the cross-referenced sections.
        self._bars = []
        self._voices = []
        self._beats = []
        self._notes = []
        self._rhythms = []
        # Deduplicate rhythms by (value, dotted, tuplet).
        self._rhythmIds = {}

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _sub(parent, tag, text=None, **attrib):
        element = ET.SubElement(parent, tag, {k: str(v) for k, v in attrib.items()})
        if text is not None:
            element.text = str(text)
        return element

    # -- entry point ----------------------------------------------------

    def write(self):
        self._sub(self.root, 'GPVersion', 6)
        self._writeScoreInfo()
        self._writeMasterTrack()
        self._writeTracks()
        self._writeMasterBars()
        self._writeCollections()
        return ET.tostring(self.root, encoding='UTF-8', xml_declaration=True)

    # -- score / master track ------------------------------------------

    def _writeScoreInfo(self):
        song = self.song
        score = self._sub(self.root, 'Score')
        self._sub(score, 'Title', song.title)
        self._sub(score, 'SubTitle', song.subtitle)
        self._sub(score, 'Artist', song.artist)
        self._sub(score, 'Album', song.album)
        self._sub(score, 'Words', song.words)
        self._sub(score, 'Music', song.music)
        self._sub(score, 'Copyright', song.copyright)
        self._sub(score, 'Tabber', song.tab)
        self._sub(score, 'Instructions', song.instructions)
        self._sub(score, 'Notices', '\n'.join(song.notice))

    def _writeMasterTrack(self):
        master = self._sub(self.root, 'MasterTrack')
        trackIds = ' '.join(str(i) for i in range(len(self.song.tracks)))
        self._sub(master, 'Tracks', trackIds)
        automations = self._sub(master, 'Automations')
        automation = self._sub(automations, 'Automation')
        self._sub(automation, 'Type', 'Tempo')
        self._sub(automation, 'Linear', 'true')
        self._sub(automation, 'Bar', 0)
        self._sub(automation, 'Position', 0)
        self._sub(automation, 'Visible', 'true')
        self._sub(automation, 'Value', f'{self.song.tempo} 2')

    # -- tracks ---------------------------------------------------------

    def _writeTracks(self):
        tracks = self._sub(self.root, 'Tracks')
        for index, track in enumerate(self.song.tracks):
            element = self._sub(tracks, 'Track', id=index)
            self._sub(element, 'Name', track.name)
            properties = self._sub(element, 'Properties')
            tuning = self._sub(properties, 'Property', name='Tuning')
            # The model orders strings high-to-low; GPIF lists pitches low-to-high.
            pitches = ' '.join(str(s.value) for s in reversed(track.strings))
            self._sub(tuning, 'Pitches', pitches)

    # -- master bars / bars / voices / beats / notes / rhythms ----------

    def _writeMasterBars(self):
        masterBars = self._sub(self.root, 'MasterBars')
        headers = self.song.measureHeaders
        for measureIndex, header in enumerate(headers):
            masterBar = self._sub(masterBars, 'MasterBar')
            self._sub(masterBar, 'Key')
            time = header.timeSignature
            self._sub(masterBar, 'Time', f'{time.numerator}/{time.denominator.value}')
            if header.isRepeatOpen or header.repeatClose >= 0:
                attrib = {}
                if header.isRepeatOpen:
                    attrib['start'] = 'true'
                if header.repeatClose >= 0:
                    attrib['end'] = 'true'
                    attrib['count'] = str(header.repeatClose)
                self._sub(masterBar, 'Repeat', **attrib)
            # One bar per track; every track has a measure per header.
            barIds = [self._writeBar(track.measures[measureIndex])
                      for track in self.song.tracks]
            self._sub(masterBar, 'Bars', ' '.join(str(i) for i in barIds))

    def _writeBar(self, measure):
        barId = len(self._bars)
        bar = ET.Element('Bar', id=str(barId))
        self._bars.append(bar)
        self._sub(bar, 'Clef', 'G2')
        # GPIF always reserves four voice slots; -1 marks an unused one.
        voiceIds = ['-1', '-1', '-1', '-1']
        slot = 0
        for voice in measure.voices:
            if slot >= 4:
                break
            if voice.beats:
                voiceIds[slot] = str(self._writeVoice(voice))
                slot += 1
        self._sub(bar, 'Voices', ' '.join(voiceIds))
        return barId

    def _writeVoice(self, voice):
        voiceId = len(self._voices)
        element = ET.Element('Voice', id=str(voiceId))
        self._voices.append(element)
        beatIds = [self._writeBeat(beat) for beat in voice.beats]
        self._sub(element, 'Beats', ' '.join(str(i) for i in beatIds))
        return voiceId

    def _writeBeat(self, beat):
        beatId = len(self._beats)
        element = ET.Element('Beat', id=str(beatId))
        self._beats.append(element)
        if beat.notes:
            velocity = beat.notes[0].velocity
            self._sub(element, 'Dynamic', _DYNAMIC_NAMES.get(velocity, 'F'))
        rhythmId = self._writeRhythm(beat.duration)
        self._sub(element, 'Rhythm', ref=rhythmId)
        if beat.notes:
            noteIds = [self._writeNote(note) for note in beat.notes]
            self._sub(element, 'Notes', ' '.join(str(i) for i in noteIds))
        return beatId

    def _writeNote(self, note):
        noteId = len(self._notes)
        element = ET.Element('Note', id=str(noteId))
        self._notes.append(element)
        properties = self._sub(element, 'Properties')
        fret = self._sub(properties, 'Property', name='Fret')
        self._sub(fret, 'Fret', note.value)
        string = self._sub(properties, 'Property', name='String')
        # The model is 1-based from the highest string; GPIF is 0-based.
        self._sub(string, 'String', note.string - 1)
        if note.type is gp.NoteType.tie:
            self._sub(element, 'Tie', origin='true')
        return noteId

    def _writeRhythm(self, duration):
        key = (duration.value, duration.isDotted,
               duration.tuplet.enters, duration.tuplet.times)
        if key in self._rhythmIds:
            return self._rhythmIds[key]
        rhythmId = len(self._rhythms)
        element = ET.Element('Rhythm', id=str(rhythmId))
        self._rhythms.append(element)
        self._sub(element, 'NoteValue', _NOTE_VALUE_NAMES.get(duration.value, 'Quarter'))
        if duration.isDotted:
            self._sub(element, 'AugmentationDot', count=1)
        if (duration.tuplet.enters, duration.tuplet.times) != (1, 1):
            self._sub(element, 'PrimaryTuplet',
                      num=duration.tuplet.enters, den=duration.tuplet.times)
        self._rhythmIds[key] = str(rhythmId)
        return str(rhythmId)

    def _writeCollections(self):
        for tag, elements in (('Bars', self._bars), ('Voices', self._voices),
                              ('Beats', self._beats), ('Notes', self._notes),
                              ('Rhythms', self._rhythms)):
            container = self._sub(self.root, tag)
            container.extend(elements)
