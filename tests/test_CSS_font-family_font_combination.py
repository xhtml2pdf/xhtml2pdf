# -*- coding: utf-8 -*-
import io
from unittest import TestCase
import unittest
import os
from xhtml2pdf.document import pisaDocument

__doc__ = """
        FontFamilyCombination provides us auxiliary functions to check
        the correct operation code that check one we have one or more font-name in CSS font-family.
    """

class FontFamilyCombination(TestCase):


    tests_folder = os.path.dirname(os.path.realpath(__file__))
    fRegular_path = os.path.join(tests_folder, 'samples', 'font', 'Noto_Sans', 'NotoSans-Regular.ttf')
    fBold_path = os.path.join(tests_folder, 'samples', 'font', 'Noto_Sans', 'NotoSans-Bold.ttf')

    FFRegular = "@font-face {{font-family: '#Noto_Regular','Times New Roman'; src: url(\'{ttf}\');}}".format(ttf=fRegular_path)
    FFBold = "@font-face {{font-family: Noto_Bold; src: url(\'{ttf}\');}}".format(ttf=fBold_path)

    fRegular = ".fRegular{font-family: '#Noto_Regular', 'Times New Roman';}"
    fBold = ".fBold{font-family: Noto_Bold;}"

    pisa_doc = None

    #TRUE IF WE USE MORE THAN ONE FONT-NAME AS FAMILY-NAME VALUE
    values = True

    HTML_CONTENT = u"""
       <html>
       <head>
       <title></title>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
       <style type="text/css">

        {FFBold}

        {FFRegular}

        {fRegular}

        {fBold}

        </style>
        </head>

        <body>
        <span class="fRegular">Regular font type</span>
        <span class="fBold">Bold font type</span>
        </html>

       """

    def setUp(self):
        #Setting values that to be used in the following methods
        html = self.HTML_CONTENT.format(FFBold=self.FFBold, FFRegular=self.FFRegular,
                                        fRegular=self.fRegular, fBold=self.fBold)
        with io.BytesIO() as pdf_file:
            self.pisa_doc = pisaDocument(src=html,
                                    dest=pdf_file)


    def test_check_more_than_one_fontName(self):
        """
        this function help us to check is the font-family contain a font-name list.
        """
        fonts = []
        for css_class in self.pisa_doc.css[0].values():
            for font in css_class.values():
                fonts.append(font)
        for font in fonts:
            if isinstance(font,list):
                result = font
                break
        #here we are checking if fonts in pdf-doc contain a font-name list
        self.assertIsInstance(result,list)

    @unittest.skipIf(values == True,'"test_check_only_one_fontName" just need to run if font-family only have one font-name')
    def test_check_only_one_fontName(self):
        """
        this function help us to check is the font-family contain only one font-name .
        """
        fonts = []
        result = False
        for css_class in self.pisa_doc.css[0].values():
            for font in css_class.values():
                fonts.append(font)
        for font in fonts:
            if not isinstance(font, list):
                result = True
            else:
                result = False
                break
        #here we are checking if all objects in fonts list are str, the result have to be True
        self.assertTrue(result)
