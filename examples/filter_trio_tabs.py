from __future__ import print_function

import os
import fnmatch

import guitarpro


def main(source):
    print("Filtering...\n")
    supportedExtensions = '*.gp[345]'

    for dirpath, dirs, files in os.walk(source):
        for file in fnmatch.filter(files, supportedExtensions):
            guitarProPath = os.path.join(dirpath, file)
            try:
                tab = guitarpro.parse(guitarProPath)
            except guitarpro.GPException as exc:
                print("###This is not a supported Guitar Pro file:", guitarProPath, ":", exc)
            else:
                if isABassGuitarDrumsFile(tab):
                    print(guitarProPath)
    print("\nDone!")


def isABassGuitarDrumsFile(tab):
    drumsOK = bassOK = guitarOK = False

    if len(tab.tracks) == 3:
        for track in tab.tracks:
            if not track.isPercussionTrack:
                if len(track.strings) <= 5:
                    bassOK = True
                else:
                    guitarOK = True
            else:
                drumsOK = True

    return drumsOK and bassOK and guitarOK


if __name__ == '__main__':
    import argparse
    description = ("List Guitar Pro files containing three tracks: "
                   "bass, guitar and drums.")
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('source',
                        metavar='SOURCE',
                        help='path to the source tabs folder')
    args = parser.parse_args()
    kwargs = dict(args._get_kwargs())
    main(**kwargs)
