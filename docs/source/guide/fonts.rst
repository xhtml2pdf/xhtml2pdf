==================
Working with fonts
==================

Working with fonts is very similar to normal CSS. To assign a font to an
element, put its name in the ``font-family`` property:

.. code:: html

   <style>
   p { font-family: STSong-Light }
   </style>

Default fonts
-------------

By default, there is just a certain set of fonts available for PDF. Here is the
complete list of those that ``xhtml2pdf`` "knows" about, together with their
alias names:

-  **Times-Roman**: *Times New Roman*, *Times*, *Georgia*, serif
-  **Helvetica**: *Arial*, *Verdana*, *Geneva*, *sansserif*, *sans*
-  **Courier**: *Courier New*, *monospace*, *monospaced*, *mono*
-  **ZapfDingbats**
-  **Symbol**

The names are case-insensitive.

A family the document embeds with ``@font-face`` wins over the alias of the
same name: declaring ``@font-face { font-family: Arial; }`` gives you your
file, not Helvetica. A name of its own is still clearer to read.

If a ``font-family`` names nothing this document knows -- a misspelling, a
system font that was never embedded, or a ``@font-face`` whose ``src`` could
not be read -- the text is drawn in Helvetica and a warning says so, naming
every family it tried. Before, that substitution was silent, and a missing
font and a missing glyph looked exactly alike.

Asian (CJK) fonts
^^^^^^^^^^^^^^^^^

Some Asian fonts are available by default for PDF. The names are
case-insensitive.

Simplified Chinese
""""""""""""""""""

-  **STSong-Light**

Traditional Chinese
"""""""""""""""""""

-  **MSung-Light**

Japanese
""""""""

-  **HeiseiMin-W3**
-  **HeiseiKakuGo-W5**

Korean
""""""

-  **HYSMyeongJo-Medium**
-  **HYGothic-Medium**

RTL (Arabic, Hebrew, Persian, etc.) fonts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using a language with right-to-left writing, you need to specify the
language name in the ``<pdf:language name=""/>`` custom tag. This is necessary
to ensure the correct direction is applied.

For right-to-left languages, the following values are supported and tested:

- ``name="arabic"``
- ``name="hebrew"``
- ``name="persian"``
- ``name="urdu"``
- ``name="pashto"``
- ``name="sindhi"``

Usage example:

.. code:: html

   <pdf:language name="arabic"/>

   <p>بعض النصوص العربية هنا</p>
   <p>Some English text here</p>

Naming a right-to-left language makes the rest of the element it is in right
to left, the same as ``dir="rtl"`` on that element. Declared just inside
``<body>`` it covers the document; declared inside a ``<div>`` it stops at the
``</div>``, and ``<pdf:language name=""/>`` ends it earlier still. Either
one turns three things around: the text runs through the Unicode
bidirectional algorithm, so the Arabic letters read right to left while Latin
words inside them keep their own direction; paragraphs are aligned to the
right unless ``text-align`` says otherwise; and a table's columns are laid out
from the right, so the first ``<td>`` of a row is its rightmost cell.

.. note::
    A right-to-left document needs an embedded font. The base-14 families
    (*Helvetica*, *Times-Roman*, *Courier*) have no Arabic or Hebrew glyphs
    at all, so the text comes out as boxes whatever the direction is, and a
    warning says which characters were lost. `Markazi Text
    <https://fonts.google.com/specimen/Markazi+Text>`_ is one that works.

.. note::
    Arabic letters are joined by choosing the contextual form of each one,
    because ReportLab does no shaping of its own. A font built for OpenType
    shaping carries the plain Arabic block and no presentation forms, and for
    those the letters are left unjoined rather than replaced by boxes.




Using Custom Fonts
------------------

You may also embed a new font by using the ``@font-face``
keyword in CSS like this:

::

    @font-face {
      font-family: Example, "Example Font";
      src: url('example.ttf');
    }

.. note::
    A ``font-family`` list is matched per character, the way CSS says: each
    character is drawn by the first family on the list that has a glyph for
    it. So ``font-family: Helvetica, MySans`` draws the Latin text in
    Helvetica and reaches ``MySans`` only for the characters Helvetica has
    no glyph for.

    A character no family on the list has comes out blank or as a box, and a
    warning names the character and every family that was tried. There is no
    hidden system font behind the list: if a script is not showing up, embed
    a font that covers it and put it on the list.

The ``font-family`` property defines the names under which the embedded
font will be known. ``src`` defines the place of the fonts source file.
This can be a TrueType font or a Postscript font. The file name of the
first has to end with ``.ttf`` the latter with one of ``.pfb`` or
``.afm``. For Postscript fonts pass just one filename like
``<name>``\ ``.afm`` or ``<name>``\ ``.pfb``, the missing one will be
calculated automatically.

To define other shapes you can do the following:

::

    /* Normal */
    @font-face {
       font-family: DejaMono;
       src: url('font/DejaVuSansMono.ttf');
    }

    /* Bold */
    @font-face {
       font-family: DejaMono;
       src: url('font/DejaVuSansMono-Bold.ttf');
       font-weight: bold;
    }

    /* Italic */
    @font-face {
       font-family: DejaMono;
       src: url('font/DejaVuSansMono-Oblique.ttf');
       font-style: italic;
    }

    /* Bold and italic */
    @font-face {
       font-family: DejaMono;
       src: url('font/DejaVuSansMono-BoldOblique.ttf');
       font-weight: bold;
       font-style: italic;
    }


Using TFF files with the same face-name
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In specific situations we have to use .ttf files with the same face name,
but working with these kind of files makes us deal with some issues. To
avoid it you have to add ``#`` at the beginning of the ``font-family name``.
Please check the following example:

::

    /* put in quotes and add # at the beginning */
    @font-face {
        font-family: '#MY';
        src: url('font/Microsoft YaHei.ttf')
    }

Demonstration
-------------

.. include:: /_generated/guide-fonts.rst
