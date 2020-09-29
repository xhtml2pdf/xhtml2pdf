
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
    fontBold = os.path.join(tests_folder, 'samples', 'font', 'Microsoft YaHei Bold.ttf')
    fontRegular = os.path.join(tests_folder, 'samples', 'font', 'Microsoft YaHei.ttf')

    HTML_CONTENT = """
    
    <html>
    <head>
    <title></title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <style type="text/css">

    @font-face {
        font-family: MYB;
        src: url('./samples/font/Microsoft YaHei Bold.ttf')
    }

    @font-face {
        font-family: '#MY';
        src: url('./samples/font/Microsoft YaHei.ttf')
    }

    .regular{
    font-family: '#MY';
    }   

    .mybold{
    font-family: MYB;
    }

    </style>
    </head>

    <body>
    <span class="regular">Regular font type</span>
    <p class="mybold">Bold font type</p>

    </body>
    </html>
    """

    def test_check_updated_face_name(self):

        """
        this function help us to check is the font-family value on the pdf and
        the font-family from html element are same.
        """

        html = self.HTML_CONTENT

        result = BytesIO()
        pdf = pisaDocument(BytesIO(html.encode('utf-8')), result)

        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(html)
        spanElement= document.getElementsByTagName("span")[0]
        spanElement = CSSDOMElementInterface(spanElement)
        attr_name = "font-family"
        rules = pdf.cssCascade.findCSSRulesFor(spanElement, attr_name)

        font_family = rules[0][1].get('font-family').strip('#')
        font_pdf = pdf.fontList.get('my').upper()
        if hasattr(font_pdf,'upper'):
            font_pdf.upper()

        self.assertEqual(font_family,font_pdf)



