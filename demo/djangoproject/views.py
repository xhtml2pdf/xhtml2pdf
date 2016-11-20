# coding: utf-8

import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.template import Context, Template
from django.template.loader import get_template, render_to_string
from xhtml2pdf import pisa


def index(request):
    return render(request, 'index.html')


def extract_request_variables(request):

    page_size = request.POST.get('page_size', 'letter')
    page_orientation = request.POST.get('page_orientation', 'portrait')

    pagesize = "%s %s" % (
        page_size, page_orientation
    )

    template = Template(request.POST.get('data', ''))
    data = template.render(Context({}))
    return {
        'pagesize': pagesize,
        'data': data,
        'page_orientation': page_orientation,
        'page_size': page_size,
        'example_number': request.POST.get("example_number", '1'),
        'border': request.POST.get('border', '')
    }


def render_pdf(request):

    template_path = 'user_printer.html'
    context = extract_request_variables(request)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'

    template = get_template(template_path)
    html = template.render(Context(context))
    if request.POST.get('show_html', ''):
        response.content_type = 'application/text'
        response['Content-Disposition'] = 'attachment; filename="report.txt"'
        response.write(html)
    else:
        pisaStatus = pisa.CreatePDF(html, dest=response)
        if pisaStatus.err:
            return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response
