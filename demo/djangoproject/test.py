# encoding: utf-8


'''
Created on 22/11/2016

@author: luisza
'''
from __future__ import unicode_literals
from django.test import TestCase, RequestFactory
try:  # python2 and python3
    from .utils import extract_request_variables
    from .views import render_pdf
except:
    from utils import extract_request_variables
    from views import render_pdf


class Djxhtml2pfdTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_var_empty(self):
        request = self.factory.post('/download', data={})

        data = extract_request_variables(request)

        default_data = {
            'pagesize': 'letter portrait',
            'data': '',
            'page_orientation': 'portrait',
            'page_size': 'letter',
            'example_number': '1',
            'border':  ''
        }

        self.assertDictEqual(data, default_data, msg="No default data")

    def test_reder_data_as_html(self):
        request = self.factory.post(
            '/download', data={'data': '{% lorem 1 p %}'})

        data = extract_request_variables(request)

        self.assertIn(
            'Lorem ipsum dolor sit amet', data['data'], msg="Not rendering data as html")

    def test_render_pfd(self):
        for x in range(1, 4):
            for y in ['application/pdf', 'application/text']:
                data = {'example_number': '%d' % (x),
                        'data': '{% lorem 1 p %}'}
                if y == 'application/text':
                    data['show_html'] = '1'
                request = self.factory.post(
                    '/download', data=data)

                response = render_pdf(request)
                self.assertEqual(
                    response['Content-Type'], y,
                    msg="Render %s example %d" % (y, x))
