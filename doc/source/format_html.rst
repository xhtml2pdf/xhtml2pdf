Working with HTML 
===================

PDF vs. HTML
------------------

Before we discuss how to define page layouts with xhtml2pdf style sheets, it helps
to understand some of the inherent differences between PDF and HTML.

PDF is specifically designed around pages of a specific width and height.
PDF page elements (such as paragraphs, tables and images) are positioned
at absolute (X,Y) coordinates.

.. note:: 

    While true PDF files use (0,0) to denote the bottom left of a page,
    xhtml2pdf uses (0,0) to denote the top left of a page, partly to
    maintain similarity with the HTML coordinate system.

HTML, by itself, does not have the concept of pagination or of pages with a
specific width and height. An HTML page can be as wide as your browser width
(and even wider), and it can be as long as the page content itself.
HTML page elements are positioned in
relationship to each other and may change when the browser window is resized.

In order to bridge the differences between HTML and PDFs, xhtml2pdf
makes use of the concept of **Pages** and **Frames**. Pages define the
size, orientation and margins of pages. Frames are rectangular regions
with in each page.

The **Frame location is specified in absolute (X,Y) coordinates**,
while the **Frame content is used to flow HTML content using the
relative positioning rules of HTML**.
This is the essence from which the power of xhtml2pdf stems.

HTML content will start printing in the first available content frame. Once the first
frame is filled up, the content will continue to print in the next
frame, and the next, and so on, until the entire HTML content has been printed.

Defining Page Layouts
-----------------------

xhtml2pdf facilitates the conversion of HTML content into a PDF document by flowing
the continuous HTML content through one or more pages using Pages and Frames.
A page represents a page layout within a PDF document.
A Frame represents a rectangular region within a page through which the HTML
content will flow.

Pages
^^^^^^^

The **@page** object defines a **Page template** by defining the properties of a page,
such as page type (letter or A4), page orientation (portrait or landscape), and page margins.
The @page definition follows the style sheet convention of ordinary CSS style sheets:

.. code:: html

    <style>
        @page {
            size: letter landscape;
            margin: 2cm;
        }
    </style>

Frames
^^^^^^^

The **@frame** object defines the position and size of rectangular region within a page.
A @page object can hold one or more @frame objects.
The @frame definition follows the style sheet convention of ordinary CSS style sheets:

Here's a definition of a page template with one Content Frame.
It makes use of the Letter page size of 612pt x 792pt.

.. code:: html

    <style>
        @page {
            size: letter portrait;
            @frame content_frame {
                left: 50pt;
                width: 512pt;
                top: 50pt;
                height: 692pt;
                -pdf-frame-border: 1;    /* for debugging the layout */
            }
        }
    </style>

This will result in the following page layout:

::

         +-page----------------+
         |                     |
         |  +-content_frame-+  |
         |  |               |  |
         |  |               |  |
         |  |               |  |
         |  |               |  |
         |  +---------------+  |
         |                     |
         +---------------------+


.. note:: To visualize the page layout you are defining, add the ``-pdf-frame-border: 1;``
         property to your each of your @frame objects.

Static frames vs Content frames
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
xhtml2pdf uses the concept of **Static Frames** to define content that remains the same
across different pages (like headers and footers), and uses **Content Frames**
to position the to-be-converted HTML content.

Static Frames are defined through use of the @frame property ``-pdf-frame-content``.
Regular HTML content will not flow through Static Frames.

Content Frames are @frame objects without this property defined. Regular HTML
content will flow through Content Frames.

Example with 2 Static Frames and 1 Content Frame
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: html

    <html>
    <head>
    <style>
        @page {
            size: a4 portrait;
            @frame header_frame {           /* Static Frame */
                -pdf-frame-content: header_content;
                left: 50pt; width: 512pt; top: 50pt; height: 40pt; 
            }
            @frame content_frame {          /* Content Frame */
                left: 50pt; width: 512pt; top: 90pt; height: 632pt;
            }
            @frame footer_frame {           /* Another static Frame */
                -pdf-frame-content: footer_content;
                left: 50pt; width: 512pt; top: 772pt; height: 20pt; 
            }
        } 
    </style>
    </head>

    <body>
        <!-- Content for Static Frame 'header_frame' -->
        <div id="header_content">Lyrics-R-Us</div>
        
        <!-- Content for Static Frame 'footer_frame' -->
        <div id="footer_content">(c) - page <pdf:pagenumber>
            of <pdf:pagecount>
        </div>
        
        <!-- HTML Content -->
        To PDF or not to PDF
    </body>
    </html>

In the example above, the vendor-specific tags ``<pdf:pagenumber>`` and ``<pdf:pagecount>``
are used to display page numbers and the total page count. This example will produce the 
following PDF Document:

::

         +-page------------------+
         | +-header_frame------+ |
         | | Lyrics-R-Us       | |
         | +-------------------+ |
         | +-content_frame-----+ |
         | | To PDF or not to  | |
         | | PDF               | |
         | |                   | |
         | |                   | |
         | +-------------------+ |
         | +-footer_frame------+ |
         | | (c) - page 1 of 1 | |
         | +-------------------+ |
         +-----------------------+

::

    # Developer's note:
    # To avoid a problem where duplicate numbers are printed, 
    # make sure that these tags are immediately followed by a newline.


Flowing HTML content through Content Frames
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Content frames are used to position the HTML content across multiple pages.
HTML content will start printing in the first available Content Frame. Once the first
frame is filled up, the content will continue to print in the next
frame, and the next, and so on, until the entire HTML content has been printed.
This concept is illustrated by the example below.

Example page template with a header, two columns, and a footer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: html

    <html>
    <head>
    <style>
        @page {
            size: letter portrait;
            @frame header_frame {           /* Static frame */
                -pdf-frame-content: header_content;
                left: 50pt; width: 512pt; top: 50pt; height: 40pt; 
            }
            @frame col1_frame {             /* Content frame 1 */
                left: 44pt; width: 245pt; top: 90pt; height: 632pt;
            }
            @frame col2_frame {             /* Content frame 2 */
                left: 323pt; width: 245pt; top: 90pt; height: 632pt;
            } 
            @frame footer_frame {           /* Static frame */
                -pdf-frame-content: footer_content;
                left: 50pt; width: 512pt; top: 772pt; height: 20pt; 
            }
        } 
    </style>
    <head>
    <body>
        <div id="header_content">Lyrics-R-Us</div>
        <div id="footer_content">(c) - page <pdf:pagenumber>
            of <pdf:pagecount>
        </div>
        <p>Old MacDonald had a farm. EIEIO.</p>
        <p>And on that farm he had a cow. EIEIO.</p>
        <p>With a moo-moo here, and a moo-moo there.</p>
        <p>Here a moo, there a moo, everywhere a moo-moo.</p>
    </body>
    </html>

The HTML content will flow from Page1.Col1 to Page1.Col2 to Page2.Col1, etc.
Here's what the resulting PDF document could look like:

::

         +-------------------------------+    +-------------------------------+
         | Lyrics-R-Us                   |    | Lyrics-R-Us                   |
         |                               |    |                               |
         | Old MacDonald   farm he had a |    | a moo-moo       everywhere a  |
         | had a farm.     cow. EIEIO.   |    | there.          moo-moo.      |
         | EIEIO.          With a moo-   |    | Here a moo,                   |
         | and on that     moo here, and |    | there a moo,                  |
         |                               |    |                               |
         | (c) - page 1 of 2             |    | (c) - page 2 of 2             |
         +-------------------------------+    +-------------------------------+


Advanced concepts
===================

Keeping text and tables together
-------------------------------------

You can prevent a block of text from being split across separate frames through the use of the
vendor-specific ``-pdf-keep-with-next`` property.

Here's an example where paragraphs and tables are kept together until a 'separator paragraph'
appears in the HTML content flow.

.. code:: html

    <style>
        table { -pdf-keep-with-next: true; }
        p { margin: 0; -pdf-keep-with-next: true; }
        p.separator { -pdf-keep-with-next: false; font-size: 6pt; }
    </style>
      ...
    <body>
        <p>Keep these lines</p>    
        <table><tr><td>And this table</td></tr></table>
        <p>together in one frame</p>
    
        <p class="separator">&nbsp;<p>

        <p>Keep these sets of lines</p>
        <p>may appear in a different frame</p>
        <p class="separator">&nbsp;<p>
    </body>

Named Page templates
------------------------

Page templates can be named by providing the name after the @page keyword

.. code:: html

    @page my_page {
        margin: 40pt;
    }


Switching between multiple Page templates
----------------------------------------------

PDF documents sometimes requires a different page layout across different sections
of the document. xhtml2pdf allows you to define multiple @page templates
and a way to switch between them using the vendor-specific tag ``<pdf:nexttemplate>``.

As an illustration, consider the following example for a title page with
large 5cm margins and regular pages with regular 2cm margins.

.. code:: html

    <html>
    <head>
    <style>
        @page title_template { margin: 5cm; }
        @page regular_template { margin: 2cm; }
    </style>
    </head>
    
    <body>    
        <h1>Title Page</h1>
        This is a title page with a large 5cm margin.
    
        <!-- switch page templates -->
        <pdf:nexttemplate name="regular_template" />
    
        <h1>Chapter 1</h1>
        This is a regular page with a regular 2cm margin.    
    </body>
    </html>

