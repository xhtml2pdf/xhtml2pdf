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
    border-bottom-left-radius, border-bottom-right-radius
    border-left-color, border-left-style, border-left-width
    border-right-color, border-right-style, border-right-width
    border-top-color, border-top-style, border-top-width
    border-top-left-radius, border-top-right-radius
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
``border-radius``, ``border-style``, ``border-width``, ``border-top`` (and
its three siblings), ``flex``, ``flex-flow``, ``font``, ``gap``, ``list-style``,
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
-  ``align-items`` and ``align-self: baseline`` line the items up on
   their first baseline: the first line of the item's first paragraph,
   or, through a nested container, of its first item. A table or an
   image has no baseline and is aligned by its bottom edge, which is
   what the specification synthesises. ``last baseline`` is drawn as
   ``flex-end``.
-  A percentage ``gap`` resolves against the container's own content box
   in that gap's axis: ``column-gap`` against the width, ``row-gap``
   against the height. A container that takes its content's height has no
   definite height to resolve against, and there a percentage ``row-gap``
   is zero, as the specification says.
-  ``align-content`` only acts when the container's ``height`` is a
   length, which is what makes its cross size definite; in a row without
   one it does nothing, as the specification says.
-  A ``flex-direction: column`` container without a ``height`` never
   wraps and never distributes free space: its height is its content's.
-  A container that does not fit the room left on a page is cut where
   the page ends, through the flex line and the items the cut falls in,
   as a browser fragments it: each item goes on at the top of the next
   page with no edge at the cut (``box-decoration-break: slice``), and an
   item whose content cannot break there -- a one-line paragraph, an
   image -- moves whole. A line with nothing to show above the cut moves
   whole too, so a row of tiles still breaks between its lines. The
   continuation keeps the widths of the cut line when the next frame is
   as wide as the one it left; a declared ``height`` is shared between
   the two parts, and ``align-content`` places the remaining lines in
   what is left of it; ``wrap-reverse`` continues at the cross start. A
   line that no frame can hold and that cannot be cut is shrunk to fit.
-  Within a container the text direction of the document decides where
   the row starts: a ``dir="rtl"`` document lays ``row`` out from the
   right. The direction is read from ``dir`` on ``<html>``, ``<body>``,
   ``<div>`` or ``<p>``. Bear in mind that ``dir="rtl"`` reverses the
   characters of a run rather than applying the Unicode bidirectional
   algorithm, so Latin text in a right-to-left document comes out
   backwards; ``<pdf:language name="arabic"/>`` reshapes properly.

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

-  The box's baseline is the baseline of its last line of text, as in a
   browser; a box that holds no text -- a table, an image -- hangs from
   its bottom margin edge.
-  ``top`` and ``bottom`` align the box with the edges of the line box,
   ``text-top`` and ``text-bottom`` with the edges of the parent's
   content area, so the four coincide only when nothing else on the line
   is taller. The line box here is the one ReportLab builds from the
   font metrics of the line's fragments; it does not carry the half
   leading CSS puts above and below the content area, so a box on
   ``top`` sits a little lower than a browser puts it, by the same
   amount as the first line of a block.
-  A box wider than the line is laid out again to fit the line rather
   than overflowing it, and is never broken across lines.
-  A flex container inside an inline block takes the whole width of the
   box, which is the way to write ``display: inline-flex``: an inline
   block around a ``display: flex`` element.
-  An inline block does not work as a list marker.

.. _inline-box:

Inline boxes
------------

An inline element -- a ``<span>``, an ``<a>``, a ``<b>`` -- with
``padding``, a ``border``, a ``background-image`` or a ``margin-left``/
``margin-right`` of its own is drawn as a box around its text, in the
line, the way a browser draws it: the padding and the border widen the
line, the box is painted under the text, and a box cut by a line break
or a page break goes on from the start of the next line with no edge at
the cut (``box-decoration-break: slice``). A ``background-color`` alone
is still painted behind each word, as before, unless the element has a
``border-radius`` too: then it is one rounded box, like a pill badge.

Differences from a browser:

-  Vertical padding and borders do not change the height of the line, as
   CSS 2.1 section 10.8 says; a tall padding overlaps the lines above
   and below.
-  ``margin-top`` and ``margin-bottom`` do nothing on an inline element,
   as in a browser.

.. _border-radius:

Rounded corners
---------------

``border-radius`` rounds the corners of a box: one to four values, top-left
clockwise, and after a ``/`` one to four vertical radii for elliptical
corners; or ``border-top-left-radius`` and its siblings, one value or two.
A percentage is of the box's width across and of its height down, so
``50%`` makes a circle of a square and an ellipse of anything else. Radii
too large for their side shrink together until they fit, as the
specification says. The background and its image are clipped to the
curve; the border follows it, with an inner curve smaller by the border
width, so a border wider than its radius is square inside, and a thick
side tapers into a thin one through the corner. It applies to:

-  blocks with text, flex containers and flex items, inline blocks and
   inline boxes;
-  images, which it clips;
-  tables and table cells, drawn as with ``border-collapse: separate``: a
   browser ignores the radius of a collapsed table, and xhtml2pdf's
   ``cellspacing="0"`` is what ``border-spacing: 0`` lays out there.

Differences from a browser:

-  A ``<div>`` that holds other blocks has no box of its own: each block
   inside it paints its border and background, so a radius on the
   ``<div>`` rounds nothing. A ``display: flex; flex-direction: column``
   container around the blocks is one box, and rounds as expected.
-  An image's radius only clips it; an image draws no border or
   background of its own.
-  Like a straight border, a rounded one is centred on the edge of the
   box, so it sits half its width further out than in a browser.
-  The point where two sides of different colours or styles meet is on
   the line from the outer corner to the inner one, as in a browser; a
   dashed or dotted side is stroked along the middle of the border and
   meets its neighbour half way round the corner.
-  A block split between pages is rounded at both ends of each part
   (``box-decoration-break: clone``). A flex container or item, an inline
   box and a table are square at the cut (``slice``), as in a browser.
-  In a table, a rounded cell draws its own border, and the grid line of
   the neighbour it shares an edge with gives way to it. A corner cell's
   background is not clipped by a rounded table, as a browser does not
   clip it either. A radius on a ``<tr>`` is ignored, as browsers do.
-  The radius is not inherited, as CSS says; ``inherit`` takes the
   parent's, for the shorthand and each corner.

Selectors
---------

Type, class, id, descendant, child (``>``), adjacent sibling (``+``),
general sibling (``~``), grouping, attribute selectors and namespaces are
supported, along with the structural pseudo-classes ``:first-child``,
``:last-child``, ``:only-child``, ``:only-of-type``, ``:first-of-type``,
``:last-of-type``, ``:empty``, ``:root`` and the ``:nth-child()``,
``:nth-last-child()``, ``:nth-of-type()`` and ``:nth-last-of-type()``
functions.

From Selectors Level 4: ``:not()`` with a list of selectors, ``:is()``,
``:where()``, ``:has()`` (``p:has(> img)``, ``h2:has(+ p)``),
``:nth-child(2 of .x)`` and ``:nth-last-child()`` with ``of``, the ``i``
and ``s`` flags of an attribute selector (``[type=text i]``), ``:lang()``,
``:dir()``, ``:scope``, ``:link``, ``:any-link``, and the form states
``:checked``, ``:default``, ``:disabled``, ``:enabled``, ``:required``,
``:optional``, ``:read-only``, ``:read-write`` and ``:placeholder-shown``,
read from the document as written. As in a browser, HTML's ``type``,
``lang``, ``dir``, ``rel`` and the other attributes it lists compare
ignoring case on HTML elements, unless the selector says ``s``. Any other
pseudo-class, such as ``:hover``, parses and matches nothing.

The form states select for styling only: ``disabled`` and ``readonly`` do
not make the field in the PDF read-only, and a reader can still fill it
in. ``dir="auto"`` matches neither ``:dir(ltr)`` nor ``:dir(rtl)``, and for
layout the element keeps the direction it inherits: the direction of its
text is not worked out.

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
