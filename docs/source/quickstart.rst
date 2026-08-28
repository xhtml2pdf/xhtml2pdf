**********
Quickstart
**********

Install
=======

**Prerequisites:** Python v3.10 or newer

This is a typical Python library and is installed using pip

.. code:: shell

    pip install xhtml2pdf


Use
===

Python
------

For basic PDF rendering, you'll mostly need to use the :py:func:`xhtml2pdf.pisa.CreatePDF`
function.

.. code:: python

    from xhtml2pdf import pisa

    # enable logging
    pisa.showLogging()

    html_source = "<html><body><p>To PDF or not to PDF</p></body></html>"

    with open("test.pdf", "w+b") as result_file:
        # convert HTML to PDF
        pisa_status = pisa.CreatePDF(
            html_source,       # page data
            dest=result_file,  # destination file
        )

        # Check for errors
        if pisa_status.err:
            print("An error occurred!")

A conversion that fails raises. Pass ``raise_exception=False`` to be handed the
status object with ``err`` set instead, or ``show_error_as_pdf=True`` to render
a PDF listing the errors and the warnings.

You can generate files in-memory by writing to :py:class:`io.BytesIO` or
:py:class:`io.StringIO` objects:

.. code:: python

    import io

    from xhtml2pdf import pisa

    output = io.BytesIO()

    pisa.CreatePDF(
        "<html><body><p>To PDF or not to PDF</p></body></html>",  # page data
        dest=output,                                              # destination "file"
    )

    # You can get the PDF file bytes with `.getbuffer()`
    print(len(output.getbuffer()))

Command-line
------------

You can convert HTML files to PDF documents from the command line:

.. code:: shell

    xhtml2pdf source.html output.pdf

The same tool is installed as ``pisa``, and the package can be run as a module:

.. code:: shell

    python -m xhtml2pdf source.html output.pdf

Read more in the :doc:`CLI reference <reference/cli>`.

Demonstration
=============

.. include:: /_generated/quickstart.rst
