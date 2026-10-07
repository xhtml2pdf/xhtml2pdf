import os

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import get_template

from xhtml2pdf import pisa

from .utils import extract_request_variables


def index(request):
    return render(request, "index.html")


def url_prefix(url):
    # Projects made with Django 4 or later set STATIC_URL = "static/", without
    # the leading slash; {% static %} still writes "/static/...".
    return "/" + url.lstrip("/")


def link_callback(uri, _rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those
    resources.
    """
    if uri.startswith(("http://", "https://", "data:")):
        return uri

    static_url = url_prefix(settings.STATIC_URL)
    media_url = url_prefix(settings.MEDIA_URL)

    if uri.startswith(media_url):
        path = os.path.join(settings.MEDIA_ROOT, uri.removeprefix(media_url))
    elif uri.startswith(static_url):
        name = uri.removeprefix(static_url)
        # finders.find wants the name below STATIC_URL, not the URL: given
        # "/static/logo.png" it raises SuspiciousFileOperation.
        path = finders.find(name) or os.path.join(settings.STATIC_ROOT, name)
    elif not os.path.isabs(uri):
        # A bare "logo.png" would be looked for in the working directory of
        # the server process, which is rarely the project.
        path = os.path.join(settings.BASE_DIR, uri)
    else:
        return uri

    if not os.path.isfile(path):
        msg = f"{uri!r} was resolved to {path}, which does not exist"
        raise FileNotFoundError(msg)
    return path


def render_pdf(request):
    template_path = "user_printer.html"
    context = extract_request_variables(request)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="report.pdf"'

    template = get_template(template_path)
    html = template.render(context)
    if request.POST.get("show_html", ""):
        response["Content-Type"] = "application/text"
        response["Content-Disposition"] = 'attachment; filename="report.txt"'
        response.write(html)
    else:
        pisaStatus = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
        if pisaStatus.err:
            return HttpResponse(
                f"We had some errors with code {pisaStatus.err} <pre>{html}</pre>"
            )
    return response
