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
            except guitarpro.GPException as exception:
                print("###This is not a supported GuitarPro file:", guitarProPath, ":", exception)
            else:
                for track in tab.tracks:
                    if not track.isPercussionTrack:
                        if len(track.strings) == 5:
                            print(guitarProPath)
    print("\nDone!")


if __name__ == '__main__':
    import argparse
    description = "List Guitar Pro files containing 5 string bass track."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('source',
                        metavar='SOURCE',
                        help='path to the source tabs folder')
    args = parser.parse_args()
    kwargs = dict(args._get_kwargs())
    main(**kwargs)
