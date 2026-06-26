Quickstart
==========

After the package has been installed, it's ready for hacking.

Reading ``.gp*`` files is as easy as:

.. code-block:: python

   import guitarpro
   demo = guitarpro.parse('Demo v5.gp5')

Writing ``.gp*`` files isn't that hard as well:

.. code-block:: python

   guitarpro.write(demo, 'Demo v5 2.gp5')

All objects representing GP entities are hashable and comparable. This gives the great opportunity to apply *diff*
algorithm to tabs, or even *diff3* algorithm to merge tablatures.

The package is also designed to convert tablatures between formats. To do this, simply change extension of the output
file according to your desired format:

.. code-block:: python

   guitarpro.write(demo, 'Demo v5.gp4')

Functions :func:`guitarpro.parse` and :func:`guitarpro.write` support not only filenames, but also file-like object:

.. code-block:: python

   from urllib.request import urlopen
   with urlopen('https://github.com/Perlence/PyGuitarPro/raw/master/tests/Demo%20v5.gp5') as stream:
       demo = guitarpro.parse(stream)

.. note::

   PyGuitarPro reads and writes GP3, GP4, GP5 files, as well as GP6 (``.gpx``) and GP7 (``.gp``) files. GP6/GP7
   support covers the core musical content (song info, tracks, tunings, measures, voices, beats, durations and
   notes) but not yet every advanced effect. Write the GP6/GP7 formats by passing ``version=(6, 0, 0)`` or
   ``version=(7, 0, 0)`` to :func:`guitarpro.write`, or by using a ``.gpx`` / ``.gp`` file extension.

.. vim: tw=120 cc=121
