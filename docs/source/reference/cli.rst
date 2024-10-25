======================
Command-line interface
======================

.. program:: xhtml2pdf

.. hint:: At any time, run ``xhtml2pdf --help`` to get help.


Basic usage
-----------

To generate a PDF document from an HTML file called ``source.html`` call:

.. code:: shell

    xhtml2pdf source.html # will create source.pdf


Source
^^^^^^

.. option:: source

   The source HTML file, or ``-``, if you want to read it from stdin. Can also
   be a URL to a webpage.

.. code:: shell

    some-script-that-outputs-html | xhtml2pdf - output.pdf

When using a URL, don't forget to quote it, when needed:

.. code:: shell

    xhtml2pdf "https://en.wikipedia.org/w/index.php?title=PDF&oldid=1183757701" output.pdf


Destination
^^^^^^^^^^^

.. option:: [destination]

   The destination PDF document. If omitted, it will be derived from the
   :option:`source`. Use ``-`` to redirect the PDF file to stdout. Can also
   be a URL to a webpage.

.. important:: Make sure that the destination file is not already opened by
               another application (like Acrobat Reader)


Options
-------

Input
^^^^^

.. option:: --base <path>, -b <path>

   Specify a base path. You should set this when the source HTML is supplied via
   stdin, as there is no other way to resolve relative hyperlinks.

.. option:: --encoding <encoding>

   The character encoding of the source HTML file. If left empty, this will be
   inferred from the HTML ``<meta charset>`` value.

.. option:: --html

   Parse the source document as HTML (default).

.. option:: --xml, --xhtml, -x

   Parse the source document as XHTML. This is set automatically if the source file
   name ends with ".xml"

HTTP Options
""""""""""""

These are used when the source is a webpage.

.. option:: --http_nosslcheck

   Do not check the website's SSL certificate.

.. option:: --http_timeout

   equivalent to ``timeout`` in :py:class:`http.client.HTTPSConnection`

.. option:: --http_source_address

   equivalent to ``source_address`` in :py:class:`http.client.HTTPSConnection`

.. option:: --http_key_file

   :deprecated: Removed in Python 3.12 and not used anymore.

.. option:: --http_cert_file

   :deprecated: Removed in Python 3.12 and not used anymore.

Styling
^^^^^^^

.. option:: --css <file>, -c <file>

   Path to default CSS file. It will be applied to the generated document. If
   omitted, a reasonable default will be used.

.. option:: --css-dump

   Output default CSS file.

When generating the HTML output, ``xhtml2pdf`` uses an internal default CSS
definition (otherwise all tags would look the same). To get an impression of
what it looks like, run:

.. code:: shell

    xhtml2pdf --css-dump > xhtml2pdf-default.css

Output
^^^^^^

.. option:: --start-viewer, -s

   Start the default PDF viewer after conversion.

.. option:: --quiet, -q

   Show no messages.

.. option:: --warn, -w

   Show warnings.

.. option:: --debug, -d

   Show debugging information.
