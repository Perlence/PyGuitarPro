from setuptools import setup, find_packages

# http://bugs.python.org/issue15881
try:
    import multiprocessing
except ImportError:
    pass

install_requires = [
    'six',
    'enum34',
]

tests_require = [
    'nose',
]

try:
    import argparse
except ImportError:
    install_requires.append('argparse')

setup(
    name='PyGuitarPro',
    description='Read, write, and manipulate GP3, GP4 and GP5 files.',
    version='0.2.2',
    author='Sviatoslav Abakumov',
    author_email='dust.harvesting@gmail.com',
    url='https://bitbucket.org/Perlence/pyguitarpro/',
    platforms=['Windows', 'POSIX', 'Unix', 'MacOS X'],
    license='zlib/libpng',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    test_suite='nose.collector',
    install_requires=install_requires,
    tests_require=tests_require,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: zlib/libpng License',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        'Topic :: Artistic Software',
        'Topic :: Multimedia :: Sound/Audio',
    ],
)
