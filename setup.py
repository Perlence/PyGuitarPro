from setuptools import setup, find_packages

setup(
    name='PyGuitarPro',
    description='Read, write, and manipulate GP3, GP4 and GP5 files.',
    version='0.1',
    author='Sviatoslav Abakumov',
    author_email='dust.harvesting@gmail.com',
    url='https://bitbucket.org/Perlence/pyguitarpro/',
    platforms=['Windows', 'POSIX', 'Unix', 'MacOS X'],
    license='zlib/libpng',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers'.
        'License :: OSI Approved :: zlib/libpng License',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Artistic Software',
        'Topic :: Multimedia :: Sound/Audio',
    ],
)
