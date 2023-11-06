**************
Advanced usage
**************

Usage in Python scripts
-----------------------

For basic PDF rendering, you'll need to use the :py:func:`xhtml2pdf.pisa.CreatePDF`
function. Here's an example script that will generate a ``test.pdf`` file with
the text "To PDF or not to PDF" in the top left of the page:

.. code:: python

    # import python module
    from xhtml2pdf import pisa

    # enable logging
    pisa.showLogging()

    # Define your page data
    source_html = "<html><body><p>To PDF or not to PDF</p></body></html>"

    # open output file for writing (truncated binary)
    with open("test.pdf", "w+b") as result_file:
        # convert HTML to PDF
        pisa_status = pisa.CreatePDF(
            source_html,       # the HTML to convert
            dest=result_file,  # file handle to receive result
        )

        if pisa_status.err:
            print("An error occured!")

You can generate files in-memory by writing to a :py:class:`io.StringIO` instance.

Usage in Django apps
--------------------

To allow URL references to be resolved using Django's :django:setting:`STATIC_URL`
and :django:setting:`MEDIA_URL` settings, xhtml2pdf allows users to specify
a ``link_callback`` parameter to point to a function that converts relative URLs
to absolute system paths.

.. code:: python

    import os
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.http import HttpResponse
    from django.template.loader import get_template
    from xhtml2pdf import pisa


    def link_callback(uri, rel):
        """
        Convert HTML URIs to absolute system paths so xhtml2pdf can access those
        resources
        """
        result = finders.find(uri)

        if result:
            if not isinstance(result, (list, tuple)):
                result = [result]
            result = list(os.path.realpath(path) for path in result)
            path = result[0]
        else:
            static_url = settings.STATIC_URL    # Usually /static/
            static_root = settings.STATIC_ROOT  # Usually /home/user/project_static/
            media_url = settings.MEDIA_URL      # Usually /media/
            media_root = settings.MEDIA_ROOT    # Usually /home/user/project_static/media/

            if uri.startswith(media_url):
                path = os.path.join(media_root, uri.replace(media_url, ""))
            elif uri.startswith(static_url):
                path = os.path.join(static_root, uri.replace(static_url, ""))
            else:
                return uri

        # make sure that file exists
        if not os.path.isfile(path):
            raise RuntimeError(
                f'media URI must start with {static_url} or {media_url}'
            )
        return path

Then, in your Django view:

.. code:: python

    def render_pdf_view(request):
        template_path = 'user_printer.html'
        context = {'myvar': 'this is your template context'}

        # Create a Django response object, and set content type to PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="report.pdf"'

        # find the template and render it.
        template = get_template(template_path)
        html = template.render(context)

        # create a pdf
        pisa_status = pisa.CreatePDF(
           html,
           dest=response,
           link_callback=link_callback,  # defined above
        )

        # if error then show some funny view
        if pisa_status.err:
           return HttpResponse('We had some errors <pre>' + html + '</pre>')

        return response

You can see it in action in :source:`demo/djangoproject` folder.

Usage as a command line tool
----------------------------

xhtml2pdf also provides a convenient tool that you can use to convert HTML files
to PDF documents using the command line.
In an environment where the package is installed, run:

.. code:: shell

    xhtml2pdf test.html

This basic command will convert the content of ``test.html`` to PDF and save it
to ``test.pdf``.

The ``-s``/``--start-viewer`` option can be used to start the default PDF viewer
after the conversion:

.. code:: shell

    xhtml2pdf -s test.html

Advanced CLI usage
^^^^^^^^^^^^^^^^^^

Use ``xhtml2pdf --help`` to get started.


Converting HTML data
""""""""""""""""""""

To generate a PDF from an HTML file called ``test.html`` call:

.. code:: shell

    xhtml2pdf -s test.html

The resulting PDF will be called ``test.pdf`` (if this file is locked
e.g. by the Adobe Reader, it will be called ``test-0.pdf`` and so on).
The ``-s`` option takes care that the PDF will be opened directly in the
Operating Systems default viewer.

To convert more than one file you may use wildcard patterns like ``*``
and ``?``:

.. code:: shell

    xhtml2pdf "test/test-*.html"

You may also directly access pages from the internet:

.. code:: shell

    xhtml2pdf -s http://www.xhtml2pdf.com/

Using special properties
""""""""""""""""""""""""

If the conversion doesn't work as expected some more information may be
usefull. You may turn on the output of warnings by adding ``-w`` or even
the debugging output by using ``-d``.

Another reason could be, that the parsing failed. Consider trying the
``-xhtml`` and ``-html`` options. ``xhtml2pdf`` uses the HTMLT5lib parser
that offers two internal parsing modes: one for HTML and one for XHTML.

When generating the HTML output ``xhtml2pdf`` uses an internal default CSS
definition (otherwise all tags would appear with no differences). To get
an impression of how this one looks like start ``xhtml2pdf`` like this:

.. code:: shell

    xhtml2pdf --css-dump > xhtml2pdf-default.css

The CSS will be dumped into the file ``xhtml2pdf-default.css``. You may
modify this or even take a totally self-defined one and hand it in by
using the ``-css`` option, e.g.:

.. code:: shell

    xhtml2pdf --css=xhtml2pdf-default.css test.html
