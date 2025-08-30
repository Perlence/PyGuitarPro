Guitar Pro File Format
======================


Basic Guitar Pro 3–5 types
--------------------------

.. _byte:

Byte
^^^^

Values of type :ref:`byte` are stored in 1 byte.


.. _signed-byte:

Signed byte
^^^^^^^^^^^

Values of type :ref:`signed-byte` are stored in 1 byte.


.. _bool:

Bool
^^^^

Values of type :ref:`bool` are stored in 1 byte.


.. _short:

Short
^^^^^

Values of type :ref:`short` are stored in 2 little-endian bytes.


.. _int:

Int
^^^

Values of type :ref:`int` are stored in 4 little-endian bytes.


.. _float:

Float
^^^^^

Values of type :ref:`float` are stored in 4 little-endian bytes.


.. _double:

Double
^^^^^^

Values of type :ref:`double` are stored in 8 little-endian bytes.


.. _byte-size-string:

ByteSizeString
^^^^^^^^^^^^^^

Values of type :ref:`byte-size-string` are represented by length of the string (1 :ref:`byte`) followed by characters
encoded in an 8-bit charset.


.. _int-size-string:

IntSizeString
^^^^^^^^^^^^^

Values of type :ref:`int-size-string` are represented by length of the string (1 :ref:`int`) followed by characters
encoded in an 8-bit charset.


.. _int-byte-size-string:

IntByteSizeString
^^^^^^^^^^^^^^^^^

Values of type :ref:`int-byte-size-string` are represented by an :ref:`int` holding length of the string increased by 1,
a :ref:`byte` holding length of the string and finally followed by characters encoded in an 8-bit charset.


Guitar Pro 3 format
-------------------


.. automodule:: guitarpro.gp3
   :members:


Guitar Pro 4 format
-------------------

.. automodule:: guitarpro.gp4
   :members:


Guitar Pro 5 format
-------------------

.. automodule:: guitarpro.gp5
   :members:

.. vim: tw=120 cc=121
