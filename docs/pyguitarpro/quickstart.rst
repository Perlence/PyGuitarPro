Quickstart
==========

After the package has been installed, it's ready for hacking.

Reading ``.gp*`` files is as easy as::

    import guitarpro
    curl = guitarpro.parse('Mastodon - Curl of the Burl.gp5')

Writing ``.gp*`` files isn't that hard as well::

    guitarpro.write(curl, 'Mastodon - Curl of the Burl 2.gp5')

All objects representing GP entities are *hashable*, so they can be easily
stored in a `dict` and *compared*. This gives us the great opportunity to
apply *diff* algorithm to tabs, or even *diff3* algorithm to merge tablatures.

The package is also designed to convert tablatures between formats. To
do this, simply change extension of the output file according to your desired
format::

    guitarpro.write(curl, 'Mastodon - Curl of the Burl.gp4')

Functions :func:`guitarpro.parse` and :func:`guitarpro.write` support not only
filenames, but also file-like object::

    import urllib2
    stream = urllib2.urlopen('https://bitbucket.org/Perlence/pyguitarpro/src/develop/tests/Mastodon - Curl of the Burl.gp5')
    curl = guitarpro.parse(stream)

.. note::

    PyGuitarPro supports only GP3, GP4 and GP5 files. Support for GPX (Guitar
    Pro 6) files is planned for the next release.
