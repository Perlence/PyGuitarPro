from __future__ import print_function

from os import path

import guitarpro


def unfold_tracknumber(tracknumber, tracks):
    """Substitute '*' with all track numbers except for percussion
    tracks."""
    if tracknumber == '*':
        for number, track in enumerate(tracks, start=1):
            if not track.isPercussionTrack:
                yield number
    else:
        yield tracknumber


def process(track, measure, voice, beat, note, semitone, stringmap):
    if (1 << (note.string - 1) & stringmap and
            not (note.type == guitarpro.NoteType.dead or
                 note.type == guitarpro.NoteType.tie)):
        note.value += semitone
        capped = max(0, min(track.fretCount, note.value))
        if note.value != capped:
            print("Warning on track %d '%s', measure %d" % (track.number, track.name, measure.number))
            note.type = guitarpro.NoteType.dead
            note.value = capped
    return note


def transpose(track, semitone, stringmap):
    for measure in track.measures:
        for voice in measure.voices:
            for beat in voice.beats:
                for note in beat.notes:
                    note = process(track, measure, voice, beat, note, semitone, stringmap)


def main(source, dest, tracks, semitones, stringmaps):
    if tracks is None:
        tracks = ['*']
    if stringmaps is None:
        stringmaps = [0x7f] * len(tracks)
    song = guitarpro.parse(source)
    for number, semitone, stringmap in zip(tracks, semitones, stringmaps):
        for number in unfold_tracknumber(number, song.tracks):
            track = song.tracks[number - 1]
            transpose(track, semitone, stringmap)
    if dest is None:
        dest = '%s-transposed%s' % path.splitext(source)
    guitarpro.write(song, dest)


if __name__ == '__main__':
    import argparse

    def bitarray(string):
        return int(string, base=2)

    def tracknumber(string):
        if string == '*':
            return string
        else:
            return int(string)

    description = """
        Transpose tracks of GP tab by N semitones.
        Multiple '--track' and '--by' arguments can be specified.
        """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('source',
                        metavar='SOURCE',
                        help='path to the source tab')
    parser.add_argument('dest',
                        metavar='DEST', nargs='?',
                        help='path to the processed tab')
    parser.add_argument('-t', '--track',
                        metavar='NUMBER', type=tracknumber, dest='tracks',
                        action='append',
                        help='number of the track to transpose')
    parser.add_argument('-b', '--by',
                        metavar='N', type=int, required=True, dest='semitones',
                        action='append',
                        help='transpose by N steps')
    parser.add_argument('-s', '--stringmap',
                        metavar='BITARRAY', type=bitarray, dest='stringmaps',
                        action='append',
                        help='bit array where ones represent strings that '
                             'should be transposed, e.g. `100000` will '
                             'transpose only 6th string')
    args = parser.parse_args()
    kwargs = dict(args._get_kwargs())
    main(**kwargs)
