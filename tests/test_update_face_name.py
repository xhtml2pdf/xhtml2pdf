#-*- coding: utf-8 -*-
from __future__ import unicode_literals
from io import BytesIO
import html5lib
import unittest
from xhtml2pdf.document import pisaDocument
from xhtml2pdf.w3c.cssDOMElementInterface import CSSDOMElementInterface
import os

__doc__ = """
        ttf_with_same_face_name provides us auxiliary functions to check 
        the correct way to choose the font style when we use a ttf file with the same face name.
        it always takes the last one @font-face font-family for all the text so to avoid this issue
        we have to add a "#" in the begin of the font-family value
        """


class ttf_with_same_face_name(unittest.TestCase):

    tests_folder = os.path.dirname(os.path.realpath(__file__))
    ttf_pathR = os.path.join(tests_folder, 'samples', 'font', 'Microsoft YaHei.ttf')
    ttf_pathB = os.path.join(tests_folder, 'samples', 'font', 'Microsoft YaHei.ttf')

    ffR = "@font-face {{font-family: '#MY';src: url(\'{ttf}\');}}".format(ttf=ttf_pathR)
    ffB = "@font-face {{font-family: MYB;src: url(\'{ttf}\');}}".format(ttf=ttf_pathB)
    regular = ".regular{font-family:'#MY';}"
    bold = ".mybold{font-family:MYB;}"

    HTML_CONTENT = u"""
                        <html>
                        <title></title>
                        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                        <style type="text/css">
                
                        {ffr}
                
                        {ffb}
                
                        {myB}
                
                        {my}
                
                        </style>
                        </head>

                        <body>

                        <span class="regular">Regular font type</span>
                        <span class="mybold">Bold font type</span>

                        </body>
                        </html>
                    """

    html = HTML_CONTENT.format(ffr=ffR, ffb=ffB, my=regular, myB=bold)

    def test_check_updated_face_name(self):

        """
        this function help us to check is the font-family value on the pdf and
        the font-family from html element are same.
        """
        result = BytesIO()

        pdf = pisaDocument(BytesIO(self.html.encode('utf-8')),result)

        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(self.html)
        spanElement= document.getElementsByTagName("span")[0]
        spanElement = CSSDOMElementInterface(spanElement)
        attr_name = "font-family"
        rules = pdf.cssCascade.findCSSRulesFor(spanElement, attr_name)

        font_family = rules[0][1].get('font-family').strip('#')
        font_pdf = pdf.fontList.get('my')

        if isinstance(font_pdf, str):
            font_pdf = font_pdf.upper()

        self.assertEqual(font_family,font_pdf)



