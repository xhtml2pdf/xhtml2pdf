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
            print("An error occurred!")

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
