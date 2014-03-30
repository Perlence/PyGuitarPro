from os import path

import guitarpro
import tests


def main():
    for test in tests.TESTS:
        filepath = path.join(tests.LOCATION, test)
        song = guitarpro.parse(filepath)
        tests.product(test, song)


if __name__ == '__main__':
    main()
