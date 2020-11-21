PyGuitarPro
===========

.. image:: https://img.shields.io/pypi/v/pyguitarpro.svg?style=flat
   :alt: PyPI Package latest release
   :target: https://pypi.org/project/PyGuitarPro/


Introduction
------------

PyGuitarPro is a package to read, write and manipulate GP3, GP4 and GP5 files. Initially PyGuitarPro is a Python port
of `AlphaTab <https://www.alphatab.net/>`_ which is a Haxe port of `TuxGuitar <https://tuxguitar.herac.com.ar/>`_.

This package helps you achieve several goals you might find yourself yearning to do in a day-to-day tabber life:

- transpose a track without messing the fingering.

- add first string to the track without messing the fingering.

- map percussion notes to different values.

Reading ``.gp*`` files is as easy as:

.. code-block:: python

   import guitarpro
   curl = guitarpro.parse('Mastodon - Curl of the Burl.gp5')

Writing ``.gp*`` files isn't that hard as well:

.. code-block:: python

   guitarpro.write(curl, 'Mastodon - Curl of the Burl 2.gp5')

All objects representing GP entities are hashable and comparable. This gives the great opportunity to apply *diff*
algorithm to tabs, or even *diff3* algorithm to merge tablatures.

To anyone wanting to create their the best guitar tablature editor in Python this package will be the good thing to
start with.


Examples
--------

Several usage examples are included in the ``/examples`` folder. Please feel free to add your own examples, or improve
on some of the existing ones, and then submit them via pull request.

To run one of the examples in your local environment, simply:

.. code-block:: sh

   cd pyguitarpro
   python examples/transpose.py --help


Installation
------------

Install PyGuitarPro from PyPI:

.. code-block:: sh

   pip install PyGuitarPro

To install development version of PyGuitarPro:

.. code-block:: sh

   git clone https://github.com/Perlence/PyGuitarPro.git
   cd pyguitarpro
   pip install -e .


Documentation
-------------

Package documentation is located at `Read the Docs <https://pyguitarpro.readthedocs.io/>`_.


Licensing
---------

Please see the file called ``LICENSE``.

.. vim: tw=120 cc=121
