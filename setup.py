from setuptools import setup, find_packages

# http://bugs.python.org/issue15881
try:
    import multiprocessing  # noqa
except ImportError:
    pass

setup_requires = ['pytest-runner']

install_requires = [
    'attrs>=17.1',
    'six',
    'enum34',
]

tests_require = [
    'pytest',
]

try:
    import argparse  # noqa
except ImportError:
    install_requires.append('argparse')

with open('README.rst') as fp:
    README = fp.read()

setup(
    name='PyGuitarPro',
    description='Read, write, and manipulate GP3, GP4 and GP5 files.',
    long_description=README,
    version='0.5',
    author='Sviatoslav Abakumov',
    author_email='dust.harvesting@gmail.com',
    url='https://github.com/Perlence/PyGuitarPro',
    platforms=['Windows', 'POSIX', 'Unix', 'MacOS X'],
    license='LGPL',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    setup_requires=setup_requires,
    install_requires=install_requires,
    tests_require=tests_require,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Artistic Software',
        'Topic :: Multimedia :: Sound/Audio',
    ],
)
