import guitarpro
import os

def main(source):
    print "Filtering...\n"
    for dirpath, dirs, files in os.walk(source):
    	for file in files:
            try:
                guitarProPath = os.path.join(dirpath, file)
                tab = guitarpro.parse(guitarProPath)
                for track in tab.tracks:
                    if not track.isPercussionTrack:
                        if len(track.strings) == 5:
                            print guitarProPath
            except:
                pass
    print "\nDone!"

if __name__ == '__main__':
    import argparse
    description = "List guitar pro files containing 5 string bass track."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('source',
                        metavar='SOURCE',
                        help='path to the source tabs folder')
    args = parser.parse_args()
    kwargs = dict(args._get_kwargs())
    main(**kwargs)
