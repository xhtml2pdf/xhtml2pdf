Reference
==========

Supported @page properties and values
--------------------------------------------

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
-----------------------------

Valid @frame properties.

::

    bottom, top, height
    left, right, width
    margin, margin-bottom, margin-left, margin-right, margin-top

To avoid unexpected results, please only specify
two out of three bottom/top/height properties, and
two out of three left/right/width properties per @frame object.

Supported CSS properties
----------------------------

xhtml2pdf supports the following standard CSS properties

::

    background-color
    border-bottom-color, border-bottom-style, border-bottom-width
    border-left-color, border-left-style, border-left-width
    border-right-color, border-right-style, border-right-width
    border-top-color, border-top-style, border-top-width
    colordisplay
    font-family, font-size, font-style, font-weight
    height
    line-height, list-style-type
    margin-bottom, margin-left, margin-right, margin-top
    padding-bottom, padding-left, padding-right, padding-top
    page-break-after, page-break-before
    size
    text-align, text-decoration, text-indent
    vertical-align
    white-space
    width
    zoom

xhtml2pdf adds the following vendor-specific properties:

::

     -pdf-frame-border
     -pdf-frame-break
     -pdf-frame-content
     -pdf-keep-with-next
     -pdf-next-page
     -pdf-outline
     -pdf-outline-level
     -pdf-outline-open
     -pdf-page-break

@page background-image
--------------------------

To add a watermark to the PDF, use the ``background-image`` property to specify
a background image

::

    @page {
        background-image: url('/path/to/pdf-background.jpg');
    }


Create PDF
-------------

The main function of xhtml2pdf is called CreatePDF(). It offers the
following arguments in this order:

-  **src**: The source to be parsed. This can be a file handle or a
   ``String`` - or even better - a ``Unicode`` object.
-  **dest**: The destination for the resulting PDF. This has to be a
   file object wich will not be closed by ``CreatePDF``. (XXX allow file
   name?)
-  **path**: The original file path or URL. This is needed to calculate
   relative paths of images and style sheets. (XXX calculate
   automatically from src?)
-  **link\_callback**: Handler for special file paths (see below).
-  **debug**: \*\* DEPRECATED \*\*
-  **show\_error\_as\_pdf**: Boolean that indicates that the errors will
   be dumped into a PDF. This is usefull if that is the only way to show
   the errors like in simple web applications.
-  **default\_css**: Here you can pass a default CSS definition in as a
   ``String``. If set to ``None`` the predefined CSS of xhtml2pdf is
   used.
-  **xhtml**: Boolean to force parsing the source as XHTML. By default
   the HTML5 parser tries to guess this.
-  **encoding**: The encoding name of the source. By default this is
   guessed by the HTML5 parser. But HTML with no meta information this
   may not work an then this argument is helpfull.

Link callback
-------------

Images, backgrounds and stylesheets are loaded form an HTML document.
Normaly ``xhtml2pdf`` expects these files to be found on the local drive.
They may also be referenced relative to the original document. But the
programmer might want to load form different kind of sources like the
Internet via HTTP requests or from a database or anything else.
Therefore you may define a ``link_callback`` that handles these reuests.

XXX

Web applications
----------------

XXX

Defaults
--------

-  The name of the first layout template is ``body``, but you better
   leave the name empty for defining the default template (XXX May be
   changed in the future!)


Fonts
--------

By default there is just a certain set of fonts available for PDF. Here
is the complete list - and their repective alias names - ``xhtml2pdf``
knows by default (the names are not case sensitive):

-  **Times-Roman**: Times New Roman, Times, Georgia, serif
-  **Helvetica**: Arial, Verdana, Geneva, sansserif, sans
-  **Courier**: Courier New, monospace, monospaced, mono
-  **ZapfDingbats**
-  **Symbol**

But you may also embed new font faces by using the ``@font-face``
keyword in CSS like this:

::

    @font-face {
      font-family: Example, "Example Font";
      src: url(example.ttf);
    }

The ``font-family`` property defines the names under which the embedded
font will be known. ``src`` defines the place of the fonts source file.
This can be a TrueType font or a Postscript font. The file name of the
first has to end with ``.ttf`` the latter with one of ``.pfb`` or
``.afm``. For Postscript font pass just one filename like
``<name>``\ ``.afm`` or ``<name>``\ ``.pfb``, the missing one will be
calculated automatically.

To define other shapes you may do like this:

::

    /* Normal */
    @font-face {
       font-family: DejaMono;
       src: url(font/DejaVuSansMono.ttf);
    }

    /* Bold */
    @font-face {
       font-family: DejaMono;
       src: url(font/DejaVuSansMono-Bold.ttf);
       font-weight: bold;
    }

    /* Italic */
    @font-face {
       font-family: DejaMono;
       src: url(font/DejaVuSansMono-Oblique.ttf);
       font-style: italic;
    }

    /* Bold and italic */
    @font-face {
       font-family: DejaMono;
       src: url(font/DejaVuSansMono-BoldOblique.ttf);
       font-weight: bold;
       font-style: italic;
    }

Outlines/ Bookmarks
------------------------

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
---------------------

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
--------

Tables are supported but may behave a little different to the way you
might expect them to do. These restriction are due to the underlying
table mechanism of ReportLab.

-  The main restriction is that table cells that are longer than one
   page lead to an error
-  Tables can not float left or right and can not be inlined

Long cells
------------

``xhtml2pdf`` is not able to split table cells that are larger than the available
space. To work around it you may define what should happen in this case.
The ``-pdf-keep-in-frame-mode`` can be one of: "error", "overflow",
"shrink", "truncate", where "shrink" is the default value.

::

    table {    -pdf-keep-in-frame-mode: shrink;}

Cell widths
------------

The table renderer is not able to adjust the width of the table
automatically. Therefore you should explicitly set the width of the
table and to the table rows or cells.

Headers
--------

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
--------

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
paragraphs, images are always rendered in a seperate paragraph.
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
--------------

``xhtml2pdf`` provides some custom tags. They are all prefixed by the
namespace identifier ``pdf:``. As the HTML5 parser used by xhtml2pdf
does not know about these specific tags it may be confused if they are
without a block. To avoid problems you may condsider sourrounding them
by ``<div>`` tags, like this:

::

    <div>
       <pdf:toc />
    </div>

Tag-Definitions
---------------

pdf:barcode
~~~~~~~~~~~

Creates a barcode.

pdf:pagenumber
~~~~~~~~~~~~~~

Prints current page number. The argument "example" defines the space the
page number will require e.g. "00".

pdf:pagecount
~~~~~~~~~~~~~~

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


