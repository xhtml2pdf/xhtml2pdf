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

The Arabic letters will render from right to left, while all other Latin letters will keep their left-to-right direction.

.. warning::
    Right now it seems like right-to-left support isn't there for default font
    families (for example, *Times-Roman*). We're working on fixing this.
    You can make it work by using the ``@font-face`` tag in the CSS definition
    and defining a custom font. You will need a custom font file. For example,
    `Markazi Text <https://fonts.google.com/specimen/Markazi+Text>`_ seems to
    work.




Using Custom Fonts
------------------

You may also embed a new font by using the ``@font-face``
keyword in CSS like this:

::

    @font-face {
      font-family: Example, "Example Font";
      src: url('example.ttf');
    }

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
