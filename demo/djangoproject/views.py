# coding: utf-8

import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.contrib.staticfiles import finders

try:  # python2 and python3
    from .utils import extract_request_variables
except:
    from utils import extract_request_variables


def index(request):
    return render(request, "index.html")


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
        sUrl = settings.STATIC_URL  # Typically /static/
        sRoot = settings.STATIC_ROOT  # Typically /home/userX/project_static/
        mUrl = settings.MEDIA_URL  # Typically /media/
        mRoot = settings.MEDIA_ROOT  # Typically /home/userX/project_static/media/

        if uri.startswith(mUrl):
            path = os.path.join(mRoot, uri.replace(mUrl, ""))
        elif uri.startswith(sUrl):
            path = os.path.join(sRoot, uri.replace(sUrl, ""))
        else:
            return uri

    # make sure that file exists
    if not os.path.isfile(path):
        raise Exception("media URI must start with %s or %s" % (sUrl, mUrl))
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
                "We had some errors with code %s <pre>%s</pre>" % (pisaStatus.err, html)
            )
    return response
