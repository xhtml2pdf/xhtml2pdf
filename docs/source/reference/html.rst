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

To avoid unexpected results, please only specify
two out of three bottom/top/height properties, and
two out of three left/right/width properties per @frame object.

Supported CSS properties
------------------------

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

pdf:pagenumber
~~~~~~~~~~~~~~

Prints current page number. The argument "example" defines the space the
page number will require e.g. "00".

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
