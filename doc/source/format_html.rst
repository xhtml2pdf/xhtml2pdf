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

.. code::

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

Using Grid System
-------------------------------------


Grid system is a new Xhtml2Pdf functionality which allows to generate a content structure for a PDF file. This new
arrangement of content is based on rows and columns.
The grid system structure that Xhtml2Pdf can interpret are ``Bootstrap 4`` and ``Bulma.io``.
The specific classes of CSS framework are:

=============       =========       ======================
CSS Framework       Row Class       Columns Class
=============       =========       ======================
Boostrap 4             row          col-sm-x (x=1,2...12)
Bulma.io             columns        is-x (x=1,2...12)
=============       =========       ======================

Thus, we can use the CSS framework that we feel more comfortable with.

Along with the previuos introduccion, we would like to explain the scope of this method in the following examples:

Example 1: Working simple columns.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: html

    <html>
    <head>
    <meta charset="UTF-8">
    <title>Title</title>
    <style>
    @page{
        size: letter;
        }
    </style>
    </head>
    <body>
    <div class="row" style="text-align: center">
        <div class="col-sm-6" style="background-color: #99CC66">col-6</div>
        <div class="col-sm-6">col-6</div>
    </div>
    <div class="row" style="text-align: center">
        <div class="col-sm-4" style="background-color: aquamarine">
            col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur
            adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet
            consectetur.
        </div>
        <div class="col-sm-8" style="background-color: blueviolet">
            col- 8 Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur
            adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet,
            consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit
            amet, consectetur adipiscing elitv.
        </div>
    </div>
    </body>
    </html>

Example 2: Working columns into columns.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In this example, is shown how to divide a column into more columns. Before showing you the example 2, please
take into consideration the following points:

* Add ``coltype="parent"`` attribute to the column you want to divide.
* Add ``rowtype=child`` to the row you have added in the ``parent column``.
* Add ``coltype=child`` to the columns that belong to ``children rows``.
* It is imperative to add  the custom tag ``<pdf: netxframe name="" />`` right after adding the ``child column``.

.. code:: html

    <html>
    <head>
    <meta charset="UTF-8">
    <title>Title</title>
    <style>
    @page{
        size: letter;
    }
    </style>
    </head>
    <body>
        <div class="columns" style="text-align: center">
            <!-- we must add coltype="parent" attr -->
            <div class="is-6" coltype="parent" style="background-color: #99CC66">
                <!-- we must add rowtype="child" attr -->
                <div class="columns" rowtype="child">
                <!-- we must add custom tag <pdf:nextframe name="" /> -->
                <pdf:nextframe name="" />
                    <!-- we must add coltype="child" attr -->
                    <div class="is-4" coltype="child" style="background-color: #FFBBBB">col-4</div>
                    <div class="is-8" coltype="child" style="background-color: #336699">col-8</div>
                </div>
            </div>
            <div class="is-6">col-6</div>
        </div>
        <div class="columns" style="text-align: center">
            <div class="is-4" style="background-color: aqua">
                col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut
                labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi
                ut aliquip exea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
                cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa
                qui officia deserunt mollit anim id est laborum.
            </div>
            <div class="is-4" style="background-color: crimson">
                col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut
                labore et dolore magna aliqua consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore
                et dolore magna aliqua.
            </div>
            <div class="is-4" style="background-color: green">
                col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elit ut labore et dolore magna aliqua.
                Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
                consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
                pariatur.
            </div>
        </div>
    </body>
    </html>

.. note:: The grid system classes used in this example are from Bulma.io


Example 3: Working grid system along to normal document system.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In this third example, is shown how to work a pdf file with grid template along with a simple template which uses a
block system.
Before showing you the example 3, please
take into consideration the following point:

* To change from grid template to simple template and vice versa in the end of each content use:

.. code:: html

    <!-- simple template to grid template -->
    <pdf:nexttemplate name="id0" />
    <pdf:nextframe name="" />

    <!-- grid template to simple template -->
    <pdf:nexttemplate name="body" />
    <pdf:nextframe name="" />

Full code
^^^^^^^^^

.. code:: html

    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <title>Title</title>
    <style>
    @page body{
        size: letter;
        @frame header_frame {
            -pdf-frame-content: header_content;
            left: 50pt; width: 512pt; top: 50pt; height: 40pt;
        }
        @frame content_frame {
            left: 50pt; width: 512pt; top: 90pt; height: 632pt;
        }
        @frame footer_frame {
            -pdf-frame-content: footer_content;
            left: 50pt; width: 512pt; top: 772pt; height: 20pt;
        }
    }
    </style>
    </head>
    <body>
    <div id="header_content">Grid Experiment</div>
    <p>NO GRID</p>
    <img width="30px" height="30px" src="img/beach.jpg">
    <div id="footer_content">(c) - page <pdf:pagenumber>
        of <pdf:pagecount>
    </div>

    <pdf:nexttemplate name="id0" />
    <pdf:nextframe name="" />

    <div class="row" style="text-align: center">
        <div class="col-sm-6" coltype="parent" style="background-color: #99CC66">
            <div class="row" rowtype="child">
                <pdf:nextframe name="" />
                <div class="col-sm-4" coltype="child" style="background-color: #FFBBBB">col-4</div>
                <div class="col-sm-8" coltype="child" style="background-color: #336699">col-8</div>
            </div>
        </div>
        <div class="col-sm-6">col-6</div>
    </div>
    <div class="row" style="text-align: center">
        <div class="col-sm-4" style="background-color: aqua">
            col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elit.
        </div>
        <div class="col-sm-4" style="background-color: crimson">
            col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et
            dolore magna aliqua consectetur adipiscing elit, sed do eiusmod tempor incididunt.
        </div>
        <div class="is-4" style="background-color: green">
            col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elit ut labore et dolore magna aliqua. Ut enim ad
            minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
        </div>
    </div>
    <div class="row" style="text-align: center">
        <div class="col-sm-4" style="background-color: aquamarine">
           col-4 Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet
        </div>
        <div class="col-sm-8" style="background-color: blueviolet;">
            col-8 Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur
            adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet,
            consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit
            amet, consectetur adipiscing elitv.
        </div>
    </div>

    <pdf:nexttemplate name="body" />
    <pdf:nextframe name="" />
    <div><p>NO GRID</p></div>
    </body>
    </html>

.. note:: In the example above, we used an image inside a column.

.. warning::

     This functionality is still in a developing process, some bugs may show up while you are working with it.

    ::

        * To avoid errors in the grid template structure, don't add images and text together.
        * Try to not add a long paragraph in columns that are less wider than 5.
        * When a paragraph is longer than the available page height, by default the grid system will do a page
         break, and take the whole row that contains the mentioned paragraph. A Force text split will be needed to
         avoid wasting space on the pages.
        * For now the columns resulting from a column split cannot be splinted in more columns.

