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

To allow URL references to be resolved using Django's :setting:`STATIC_URL`
and :setting:`MEDIA_URL` settings, xhtml2pdf allows users to specify
a ``link_callback`` parameter to point to a function that converts relative URLs
to absolute system paths.

The callback is called as ``link_callback(uri, rel)`` for every image,
stylesheet, font and background in the document. ``uri`` is the reference as
it is written in the HTML, ``rel`` the directory it would otherwise be resolved
against: the directory of the document, or the current working directory when
the source is an HTML string, as it is in a Django view. Whatever the callback
returns is used instead of ``uri``; returning ``uri`` itself leaves it alone.

.. code:: python

    import os
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.http import HttpResponse
    from django.template.loader import get_template
    from xhtml2pdf import pisa


    def url_prefix(url):
        # Projects made with Django 4 or later set STATIC_URL = "static/",
        # without the leading slash; {% static %} still writes "/static/...".
        return "/" + url.lstrip("/")


    def link_callback(uri, rel):
        """
        Convert HTML URIs to absolute system paths so xhtml2pdf can access those
        resources
        """
        if uri.startswith(("http://", "https://", "data:")):
            return uri

        static_url = url_prefix(settings.STATIC_URL)  # Usually /static/
        media_url = url_prefix(settings.MEDIA_URL)    # Usually /media/

        if uri.startswith(media_url):
            path = os.path.join(settings.MEDIA_ROOT, uri.removeprefix(media_url))
        elif uri.startswith(static_url):
            name = uri.removeprefix(static_url)
            # finders.find wants the name below STATIC_URL, not the URL: given
            # "/static/logo.png" it raises SuspiciousFileOperation. It also
            # looks in each app's static/ directory, which is where the file
            # is before collectstatic has copied it to STATIC_ROOT.
            path = finders.find(name) or os.path.join(settings.STATIC_ROOT, name)
        elif not os.path.isabs(uri):
            # A bare "logo.png" would be looked for in `rel`, the working
            # directory of the server process, which is rarely the project.
            path = os.path.join(settings.BASE_DIR, uri)
        else:
            return uri

        if not os.path.isfile(path):
            raise FileNotFoundError(f"{uri!r} was resolved to {path}, which does not exist")
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

.. warning::

   Since 0.2.19 this example needs one more argument. ``STATIC_ROOT`` and
   ``MEDIA_ROOT`` are outside the directory of the document being rendered, so
   the resource policy refuses what the callback resolves and every image is
   dropped. Name those directories -- and, if the callback also returns files
   from the apps' ``static/`` directories or from ``BASE_DIR``, those too:

   .. code:: python

       from pathlib import Path

       from xhtml2pdf.config.resources import ResourceAccessPolicy

       POLICY = ResourceAccessPolicy(
           base_dir=Path(settings.STATIC_ROOT),
           extra_roots=(Path(settings.MEDIA_ROOT),),
       )

       pisa_status = pisa.CreatePDF(
           html,
           dest=response,
           link_callback=link_callback,
           resource_policy=POLICY,
       )

   A view that renders a template containing anything a user wrote is the case
   the policy exists for; see :doc:`security` before widening it.

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

Demonstration
-------------

.. include:: /_generated/advanced-usage.rst
