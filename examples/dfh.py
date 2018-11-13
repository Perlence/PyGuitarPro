from os import path
try:
    from itertools import izip
except ImportError:
    izip = zip

import guitarpro


MAPPING = {
    22: 42,
    23: 42,
    24: 46,
    25: 46,
    26: 46,
    27: 52,
    28: 49,
    29: 52,
    30: 56,
    31: 57,
    32: 57,
    33: 38,
    54: 49,
    58: 57,
}


def main(source, dest=None, tracks=None):
    song = guitarpro.parse(source)

    if tracks is None:
        # Process all percussion tracks.
        tracks = (track for track in song.tracks if track.isPercussionTrack)
    else:
        # Get tracks by track numbers.
        tracks = (song.tracks[n] for n in tracks)

    for track in tracks:
        # Map values to Genaral MIDI.
        for measure in track.measures:
            for voice in measure.voices:
                for beat in voice.beats:
                    for note in beat.notes:
                        note.value = MAPPING.get(note.value, note.value)

        # Extend note durations to remove rests in-between.
        voiceparts = izip(*(measure.voices for measure in track.measures))
        for measures in voiceparts:
            for measure in measures:
                last = None
                newbeats = []
                for beat in measure.beats:
                    if beat.notes:
                        last = beat
                    elif last is not None:
                        try:
                            newduration = guitarpro.Duration.fromTime(last.duration.time + beat.duration.time)
                        except ValueError:
                            last = beat
                        else:
                            last.duration = newduration
                            continue
                    newbeats.append(beat)
                measure.beats = newbeats

    if dest is None:
        dest = '%s-generalized%s' % path.splitext(source)
    guitarpro.write(song, dest)


if __name__ == '__main__':
    import argparse

    description = """
        Replace Drumkit from Hell specific values to General MIDI ones and
        remove rests by extending beats.
        """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('source',
                        metavar='SOURCE',
                        help='path to the source tab')
    parser.add_argument('dest',
                        metavar='DEST', nargs='?',
                        help='path to the processed tab')
    parser.add_argument('-t', '--track',
                        metavar='NUMBER', type=int, dest='tracks',
                        action='append',
                        help='zero-based number of the track to transpose')
    args = parser.parse_args()
    kwargs = dict(args._get_kwargs())
    main(**kwargs)
