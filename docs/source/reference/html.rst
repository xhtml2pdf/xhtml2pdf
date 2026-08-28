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

These are read straight out of the @page or @frame rule, not through the
property whitelist below, so they only mean anything inside one.

To avoid unexpected results, please only specify
two out of three bottom/top/height properties, and
two out of three left/right/width properties per @frame object.

Supported CSS properties
------------------------

xhtml2pdf supports the following standard CSS properties

::

    background-color
    background-image, background-position, background-repeat
    border-bottom-color, border-bottom-style, border-bottom-width
    border-left-color, border-left-style, border-left-width
    border-right-color, border-right-style, border-right-width
    border-top-color, border-top-style, border-top-width
    color
    display
    font-family, font-size, font-style, font-weight
    height
    letter-spacing, word-spacing
    line-height
    list-style-image, list-style-type
    margin-bottom, margin-left, margin-right, margin-top
    padding-bottom, padding-left, padding-right, padding-top
    page-break-after, page-break-before
    text-align, text-decoration, text-indent, text-transform
    vertical-align
    white-space
    width
    zoom

The shorthands ``background``, ``border``, ``border-color``,
``border-style``, ``border-width``, ``border-top`` (and its three
siblings), ``font``, ``list-style``, ``margin`` and ``padding`` are
expanded into the properties above.

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

Creates a Table of Contents.

pdf:language
~~~~~~~~~~~~

Used for languages with right-to-left writing like Arabic, Hebrew, Persion etc. Right-to-left writing can be defined by passing the name via the ``name=""`` property.

::

    <pdf:language name="arabic"/>

Demonstration
-------------

.. include:: /_generated/reference-html.rst
