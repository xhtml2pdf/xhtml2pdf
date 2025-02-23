Reference
==========

Outlines/ Bookmarks
-------------------

PDF supports outlines (Adobe calls them "bookmarks"). By default
``xhtml2pdf`` defines the ``<h1>`` to ``<h6>`` tags to be shown in the
outline. But you can specify exactly for every tag which outline
behaviour it should have. Therefore you may want to use the following
vendor specific styles:

- ``-pdf-outline``
    set it to "true" if the block element should appear in the outline
- ``-pdf-outline-level``
   set the value starting with "0" for the level on which the outline
   should appear. Missing predecessors are inserted automatically with
   the same name as the current outline
- ``-pdf-outline-open``
  set to "true" if the outline should be shown uncollapsed

Example:

::

    h1 {
      -pdf-outline: true;  -pdf-level: 0;
      -pdf-open: false;
    }

Table of Contents
-----------------

It is possible to automatically generate a Table of Contents (TOC) with
``xhtml2pdf``. By default all headings from ``<h1>`` to ``<h6>`` will be
inserted into that TOC. But you may change that behaviour by setting the
CSS property ``-pdf-outline`` to ``true`` or ``false``. To generate the
TOC simply insert ``<pdf:toc />`` into your document. You then may
modify the look of it by defining styles for the ``pdf:toc`` tag and the
classes ``pdftoc.pdftoclevel0`` to ``pdftoc.pdftoclevel5``. Here is a
simple example for a nice looking CSS:

::

    pdftoc {
        color: #666;
    }
    pdftoc.pdftoclevel0 {
        font-weight: bold;
        margin-top: 0.5em;
    }
    pdftoc.pdftoclevel1 {
        margin-left: 1em;
    }
    pdftoc.pdftoclevel2 {
        margin-left: 2em;
        font-style: italic;
    }

Tables
------

Tables are supported but may behave a little different to the way you
might expect them to do. These restriction are due to the underlying
table mechanism of ReportLab.

-  The main restriction is that table cells that are longer than one
   page lead to an error
-  Tables can not float left or right and can not be inlined

Long cells
----------

``xhtml2pdf`` is not able to split table cells that are larger than the available
space. To work around it you may define what should happen in this case.
The ``-pdf-keep-in-frame-mode`` can be one of: "error", "overflow",
"shrink", "truncate", where "shrink" is the default value.

::

    table {    -pdf-keep-in-frame-mode: shrink;}

Cell widths
-----------

The table renderer is not able to adjust the width of the table
automatically. Therefore you should explicitly set the width of the
table and to the table rows or cells.

Headers
-------

It is possible to repeat table rows if a page break occurs within a
table. The number of repeated rows is passed in the property
``repeat``. Example:

::

    <table repeat="1">
      <tr><th>Column 1</th><th>...</th></tr>
      ...
    </table>

Borders
-------

Borders are supported. Use corresponding CSS styles.

Images
------

Size
----

By default JPG images are supported. If the Python Imaging Library (PIL)
is installed the file types supported by it are available too. As
mapping pixels to points is not trivial the images may appear bigger in
the PDF as in the browser. To adjust this you may want to use the
``zoom`` style. Here is a small example:

::

    img { zoom: 80%; }

Position/ floating
------------------

Since Reportlab Toolkit does not yet support the use of images within
paragraphs, images are always rendered in a separate paragraph.
Therefore floating is not available yet.

Barcodes
--------

You can embed barcodes automatically in a document. Various barcode
formats are supported through the ``type`` property. If you want the
original barcode text to be appeared on the document, simply add
``humanreadable="1"``, otherwise simply omit this property. Some barcode
formats have a checksum as an option and it will be on by default, set
``checksum="0"`` to override.
Alignment
is achieved through ``align`` property and available values are any of
``"baseline", "top", "middle", "bottom"`` whereas default is
``baseline``. Finally, bar width and height can be controlled through
``barwidth`` and ``barheight`` properties respectively.

::

    <pdf:barcode value="BARCODE TEXT COMES HERE" type="code128" humanreadable="1" align="right" />

Custom Tags
-----------

``xhtml2pdf`` provides some custom tags. They are all prefixed by the
namespace identifier ``pdf:``. As the HTML5 parser used by xhtml2pdf
does not know about these specific tags it may be confused if they are
without a block. To avoid problems you may condsider surrounding them
by ``<div>`` tags, like this:

::

    <div>
       <pdf:toc />
    </div>
