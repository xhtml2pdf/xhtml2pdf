========
HTML API
========

Supported @page properties and values
-------------------------------------

Valid @page properties:

::

    background-image
    size
    margin, margin-bottom, margin-left, margin-right, margin-top

Valid size syntax and values:

::

    Syntax: @page { size: <type> <orientation>; }

    Where <type> is one of:
    a0 .. a6
    b0 .. b6
    elevenseventeen
    legal
    letter

    And <orientation> is one of:
    landscape
    portrait

    Defaults to:
    size: a4 portrait;

Supported @frame properties:
----------------------------

Valid @frame properties.

::

    bottom, top, height
    left, right, width
    margin, margin-bottom, margin-left, margin-right, margin-top
    padding, padding-bottom, padding-left, padding-right, padding-top
    border-bottom-color, border-bottom-width
    border-left-color, border-left-width
    border-right-color, border-right-width
    border-top-color, border-top-width
    background-image
    -pdf-frame-border, -pdf-frame-box, -pdf-frame-content
    -pdf-keep-in-frame-mode

These are read straight out of the @page or @frame rule, not through the
property whitelist below, so they only mean anything inside one.

``-pdf-keep-in-frame-mode`` only applies to a static frame, i.e. one that
declares ``-pdf-frame-content``. It says what to do with content taller than
the frame, which has nowhere else to go: ``shrink`` (the default) scales the
whole frame down to fit, ``truncate`` clips it at the boundary, ``overflow``
draws past it, and ``error`` leaves the frame unpainted. Any of them logs a
warning naming the frame -- the real fix is a taller ``height``.

To avoid unexpected results, please only specify
two out of three bottom/top/height properties, and
two out of three left/right/width properties per @frame object.

Supported CSS properties
------------------------

xhtml2pdf supports the following standard CSS properties

::

    align-content, align-items, align-self
    background-color
    background-image, background-position, background-repeat
    border-bottom-color, border-bottom-style, border-bottom-width
    border-left-color, border-left-style, border-left-width
    border-right-color, border-right-style, border-right-width
    border-top-color, border-top-style, border-top-width
    color
    column-gap, row-gap
    display
    flex-basis, flex-direction, flex-grow, flex-shrink, flex-wrap
    font-family, font-size, font-style, font-weight
    height
    justify-content
    letter-spacing, word-spacing
    line-height
    list-style-image, list-style-type
    margin-bottom, margin-left, margin-right, margin-top
    max-height, max-width, min-height, min-width
    order
    padding-bottom, padding-left, padding-right, padding-top
    page-break-after, page-break-before
    text-align, text-decoration, text-indent, text-transform
    vertical-align
    white-space
    width
    zoom

The shorthands ``background``, ``border``, ``border-color``,
``border-style``, ``border-width``, ``border-top`` (and its three
siblings), ``flex``, ``flex-flow``, ``font``, ``gap``, ``list-style``,
``margin`` and ``padding`` are expanded into the properties above.

A property that is not on this list is parsed and then ignored. Each
document logs the ones its stylesheet declares, by name, at warning
level, so a rule that does nothing says so rather than looking broken.

Known limitations of the properties above:

-  ``border-style``: ``groove``, ``ridge``, ``inset`` and ``outset`` are
   drawn as a solid line. ``dashed``, ``dotted`` and ``double`` are drawn
   as themselves.
-  ``list-style-type``: ``circle`` draws a filled bullet, because no font
   in the base-14 set has a hollow circle.
-  ``text-decoration``: ``overline`` is not drawn.
-  ``white-space``: ``pre-wrap`` keeps its spaces unbreakable, so a line
   will not wrap inside a run of them.
-  ``width`` and ``height`` apply to images, table cells and barcodes
   only, not to blocks.
-  ``display``: ``block``, ``inline``, ``inline-block``, ``flex`` and
   ``none`` are laid out as such; ``inline-flex`` is laid out as
   ``flex``, block-level (see :ref:`inline-block` for how to get an
   inline one); ``table``, ``list-item``, ``flow-root``, ``grid`` and the
   ``table-*`` values as ``block``. A table is a table because it is a
   ``<table>``, and a list item because it is an ``<li>``, whatever
   ``display`` says. Any other value is reported once and treated as
   ``inline``.
-  ``min-width``, ``max-width``, ``min-height`` and ``max-height`` apply
   to flex items only. See :ref:`flexbox` for what a flex container
   supports.

.. _flexbox:

Flexbox
-------

``display: flex`` lays the element's children out as flex items, in a row
or a column, following CSS Flexible Box Layout Module Level 1. The
container is one box the width of its frame; each child is one item,
sized by ``flex-basis``, ``width``/``height``, ``min-``/``max-`` and its
content, then grown or shrunk by ``flex-grow`` and ``flex-shrink`` to fill
the line. ``flex-direction``, ``flex-wrap``, ``justify-content``,
``align-items``, ``align-self``, ``align-content``, ``gap``, ``order``
and ``margin: auto`` on the items behave as in a browser, with these
differences:

-  ``inline-flex`` is laid out as ``flex``: a container always takes the
   full width of its frame.
-  ``align-items: baseline`` is drawn as ``flex-start``.
-  ``align-content`` only acts when the container's ``height`` is a
   length, which is what makes its cross size definite; in a row without
   one it does nothing, as the specification says.
-  A ``flex-direction: column`` container without a ``height`` never
   wraps and never distributes free space: its height is its content's.
-  A container is not split inside an item. One that does not fit the
   room left in a frame moves to the next; one taller than a whole frame
   is shrunk to fit.
-  Within a container the text direction of the document decides where
   the row starts: a ``dir="rtl"`` document lays ``row`` out from the
   right.

.. _inline-block:

Inline blocks
-------------

``display: inline-block`` makes the element a box that sits in the line
of text around it, as one unbreakable word: it has its own ``width``,
``height``, ``padding``, ``border`` and ``background``, its content is
laid out inside it, and ``vertical-align`` places it against the line
the way it places an inline image (``baseline``, ``top``, ``middle``,
``bottom``, ``text-top``, ``text-bottom``, ``super``, ``sub`` or a
length). Without a ``width`` it is as wide as its content, up to the
room the line has. Form controls (``<input>``, ``<select>``,
``<textarea>``) are inline blocks by default, so they no longer stand on
a line of their own.

Differences from a browser:

-  The box's baseline is its bottom margin edge, not the baseline of its
   last line of text; ``vertical-align: middle`` is the value to reach
   for when the box holds text.
-  A box wider than the line is laid out again to fit the line rather
   than overflowing it, and is never broken across lines.
-  A flex container inside an inline block takes the whole width of the
   box, which is the way to write ``display: inline-flex``: an inline
   block around a ``display: flex`` element.
-  An inline block does not work as a list marker.

Selectors
---------

Type, class, id, descendant, child (``>``), adjacent sibling (``+``),
general sibling (``~``), grouping, attribute selectors and namespaces are
supported, along with the structural pseudo-classes ``:first-child``,
``:last-child``, ``:only-child``, ``:only-of-type``, ``:first-of-type``,
``:last-of-type``, ``:empty``, ``:root`` and the ``:nth-child()``,
``:nth-last-child()``, ``:nth-of-type()`` and ``:nth-last-of-type()``
functions. Any other pseudo-class parses and matches nothing.

``@media`` is honoured for the media *types* ``all``, ``print`` and
``pdf``; a media query's conditions are ignored, so ``@media
(max-width: 500px)`` applies unconditionally.

xhtml2pdf adds the following vendor-specific properties:

::

     -pdf-frame-break
     -pdf-keep-in-frame-max-height
     -pdf-keep-in-frame-max-width
     -pdf-keep-in-frame-mode
     -pdf-keep-with-next
     -pdf-line-spacing
     -pdf-next-page
     -pdf-outline
     -pdf-outline-level
     -pdf-outline-open
     -pdf-page-break
     -pdf-toc-leader
     -pdf-toc-name
     -pdf-word-wrap

Defaults
--------

-  The name of the first layout template is ``body``, but you better
   leave the name empty for defining the default template (XXX May be
   changed in the future!)

Tag-Definitions
---------------

pdf:barcode
~~~~~~~~~~~

Creates a barcode.

A barcode is an inline fragment and the line does not reserve its full height,
so the paragraph below it will overlap. The reliable way to give one room is a
table cell with a declared ``height``.

``barwidth`` has a floor of 0.0075 inch, 0.19 mm (0.264 mm for EAN): asking for
a narrower module does not make the symbol smaller. Shorten what is encoded
instead.

pdf:pagenumber
~~~~~~~~~~~~~~

Prints current page number. The argument ``example`` defines the space the
page number will require, e.g. ``"00"``: it is what the line is measured with
until the number is known. It is only read when it is written down, and it is
what stays on the page in the one place a page number cannot resolve, inside a
table cell.

pdf:pagecount
~~~~~~~~~~~~~

Prints total page count.

pdf:nexttemplate
~~~~~~~~~~~~~~~~

Defines the template to be used on the next page. The name of the
template is passed via the ``name`` property and refers to a
``@page templateName`` style definition:

::

    <pdf:nexttemplate name="templateName">

pdf:nextpage
~~~~~~~~~~~~

Create a new page after this position.

pdf:nextframe
~~~~~~~~~~~~~

Jump to next unused frame on the same page or to the first on a new
page. You may not jump to a named frame.

pdf:spacer
~~~~~~~~~~

Creates an object of a specific size.

pdf:toc
~~~~~~~

Creates a Table of Contents. Entries come from the headings, whose page
numbers are set flush right; the page number links to the heading it names.

``-pdf-toc-leader`` fills the gap between an entry and its page number. Give
it one of the names below, or any other string to repeat as it is:

=============  ==============================================
``none``       no fill; the page number is still flush right
``space``      spaces, so copied text keeps the two apart
``dots``       ``.``
``dashes``     ``-``
``line``       ``_``, which joins up into a continuous rule
``"· "``       any other pattern, repeated as written
=============  ==============================================

The default is ``none``. ``<pdf:toc leader="dots" />`` sets it for the whole
table; a ``.pdftoclevelN`` rule sets it for one level and wins over the
attribute. A level that declares nothing keeps what the level before it had,
as with every other property of a table of contents.

::

    <style>
        pdftoc.pdftoclevel0 { -pdf-toc-leader: dots; font-weight: bold; }
        pdftoc.pdftoclevel1 { -pdf-toc-leader: dots; }
    </style>
    <pdf:toc />

Several tables of contents
^^^^^^^^^^^^^^^^^^^^^^^^^^

Name a table of contents with ``name=""`` and it takes only the entries that
ask for it by that name with ``-pdf-toc-name``. A document can have as many as
it needs -- a list of figures, a list of tables -- each with its own fill and
its own typography::

    <style>
        p.figcaption { -pdf-outline: true; -pdf-outline-level: 0;
                       -pdf-toc-name: figures; }
        pdftoc.idx-figures.pdftoclevel0 { -pdf-toc-leader: dashes; }
    </style>

    <pdf:toc leader="dots" />
    <pdf:toc name="figures" />

An entry belongs to exactly one table of contents: the one it names, or the
unnamed one when it names none. So a figure caption listed among the figures
does not also appear in the general contents, which is what a document with
both usually wants.

A named table of contents also carries the class ``idx-`` plus its name, which
is how a stylesheet reaches one of several: ``pdftoc.idx-figures.pdftoclevel0``.
The plain ``pdftoc.pdftoclevelN`` rules still apply to every one of them, and
the classes written on the tag itself are kept, so ``<pdf:toc class="compact">``
can be styled with ``pdftoc.compact.pdftoclevel0``.

The name is matched case-insensitively and trimmed, so ``name="Figures"`` and
``-pdf-toc-name: figures`` do meet. A second ``<pdf:toc>`` under a name
already used is ignored with a warning, and so is an entry naming a table of
contents the document never declares -- though that entry still gets its
bookmark and its link destination.

Three limits worth knowing:

* ``-pdf-outline: true`` is what makes something an entry at all;
  ``-pdf-toc-name`` only says which table of contents it goes to. An element
  that is not an outline entry is not an entry.
* Only paragraphs become entries. An image or a table never does, so a list of
  figures is built from the **caption**, which is a ``<p>``.
* Like ``-pdf-outline``, ``-pdf-toc-name`` inherits, so setting it on a
  wrapping ``<div>`` routes every outline entry inside it.

A ``<pdf:toc>`` inside a ``<pdf:frame static>`` or a table cell produces
nothing: only the top level of the document is searched for the tables of
contents to fill.

pdf:language
~~~~~~~~~~~~

Turns on right-to-left shaping. Pass the language through ``name=""``:

::

    <pdf:language name="arabic"/>

The names that mean right-to-left are ``arabic``, ``hebrew``, ``persian``,
``pashto``, ``sindhi`` and ``urdu``. Any other name is read as a language tag
and sets the document language instead, as described below.

The document language
---------------------

The language a document declares is written to the PDF catalog as ``/Lang``,
which is where a screen reader and a PDF/UA checker read it from. Declare it
the way you would in HTML::

    <html lang="es-CR">

or, in the ``<pdf:*>`` dialect::

    <pdf:language name="fr"/>

The value is a BCP 47 tag and is written through unchanged. If a document
gives both, the last one parsed wins -- ``<pdf:language>`` in the head comes
after ``<html>``, so it is the one that counts.

A document that declares nothing gets no ``/Lang`` entry. The six
right-to-left names listed under ``pdf:language`` are not language tags, so
``<pdf:language name="arabic"/>`` shapes the text without setting one; write
``<html lang="ar">`` as well when you want both.

Demonstration
-------------

.. include:: /_generated/reference-html.rst
