**********
Quickstart
**********

Install
=======

**Prerequisites:** Python v3.8 or newer

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
            print("An error occured!")

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
