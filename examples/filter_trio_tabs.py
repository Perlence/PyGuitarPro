import guitarpro
import os

def main(source):
    print "Filtering...\n"
    for dirpath, dirs, files in os.walk(source):
    	for file in files:
            try:
                guitarProPath = os.path.join(dirpath, file)
                tab = guitarpro.parse(guitarProPath)
                if(isABassGuitarDrumsFile(tab)): print guitarProPath
            except:
                pass
    print "\nDone!"

def isABassGuitarDrumsFile(tab):
    if(len(tab.tracks)) == 3:
        drumsOK = False
        bassOK = False
        guitarOK = False
        for track in tab.tracks:
            if not track.isPercussionTrack:
                if len(track.strings) <= 5:
                    bassOK = True
                else:
                    guitarOK = True
            else:
                drumsOK = True

    if(drumsOK and bassOK and guitarOK):
        return True
    else:
        return False

if __name__ == '__main__':
    import argparse
    description = "List guitar pro files containing three tracks: bass, guitar and drums."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('source',
                        metavar='SOURCE',
                        help='path to the source tabs folder')
    args = parser.parse_args()
    kwargs = dict(args._get_kwargs())
    main(**kwargs)
