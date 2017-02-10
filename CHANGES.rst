Changelog
=========

Version 0.3
-----------

- Removed ``Note.deadNote`` attribute.
- Fixed track order changes.
- Removed attribute ``Marker.measureHeader``.
- Provided better default values for some models.
- Implemented clipboard files handling.
- Replaced ``GPObject`` with `attrs <https://attrs.readthedocs.io>`_ class decorator.
- Reimplemented version handling. Keyword ``version`` of functions ``parse`` and ``write`` expects a version tuple.
- Moved class ``GPFileBase`` to module ``guitarpro.iobase``, and renamed module ``guitarpro.base`` to
  ``guitarpro.models``.
- Exported all models alongside with functions ``parse`` and ``write`` from ``guitarpro`` module.
  Now they can be accessed as ``guitarpro.Song``, for example.
- Swapped beat stroke directions. Downstroke is represented by ``BeatStrokeDirection.down`` and upstroke is represented
  by ``BeatStrokeDirection.up``.
- Resolved #1. Now it's easier to create a tab from scratch.

Minor changes:

- Replaced nosetest with pytest.


Version 0.2.2
-------------

- Fixed `NoteType` enumeration.
- Included examples into sdist.
- Create ``tests.OUTPUT`` directory before running tests.
- Type coercion before writing data (fixes py3k compatibility).


Version 0.2.1
-------------

- Converted Markdown docs to reST docs.
- Added ``MANIFEST.in``.


Version 0.2
-----------

- Added Python 3 compatibility.
- Added documentation.
- Added support for RSE.
- Added automated tests using ``nose``.
- Fixed harmonics conversion.
- Converted some classes to ``Enum`` subclasses.
- Added support for chord diagrams.
- Added generic arguments to ``GPObject.__init__``.
- Cleaned up the code.


Version 0.1
-----------

First public release.

.. vim: tw=120 cc=121
