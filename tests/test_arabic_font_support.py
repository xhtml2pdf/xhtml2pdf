# -*- coding: utf-8 -*-
import os
from io import BytesIO

import html5lib
from unittest import TestCase
from xhtml2pdf.document import pisaDocument

__doc__ = """
        ArabicFontSupportTests provides us auxiliary functions to check 
        the correct operation of arabic fonts.
        """


class ArabicFontSupportTests(TestCase):
    tests_folder = os.path.dirname(os.path.realpath(__file__))
    ttf_pathD = os.path.join(tests_folder, 'samples', 'font', 'DejaVuSans.ttf')

    ffD = "@font-face {{font-family: DejaVuSans;src: url(\'{ttf}\');}}".format(ttf=ttf_pathD)
    bod = ".body{font-family:DejaVuSans;background-color: red;}"
    pExtra = "p.extra {background-color: yellow;line-height: 200%;}"
    div = "div {background-color: orange;}"
    tab = "table {border: 2px solid black;}"
    h1 = "h1 {page-break-before: always;}"
    tr = "tr {background-color:red;}"

    HTML_CONTENT = u"""
    <html>
    <head>
    <title></title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>

    <style type="text/css">
        {ffd}
        {bod}
        {pEx}
        {div}
        {tab}
        {h1}
        {tr} 
    </style>
    </head>

    <body>
    <div>
        <pdf:language name="arabic"/>
        <span>رقم الغرفة:</span>
    </div>

    Test
    <p>
    Block 1
    <br>
    New Line
    <br><br>
      And another one!
    <p class="extra">
    Block 2
    
    <div style="page-break-after: always;">
        DIV 1 BEGIN
    
        <div class="extra">
            INNERDIV A
    
            <p style="background-color: blue;">
            INNERP
    
        </div>
    
        DIV 1 END
    </div>
    
    (NEW PAGE?) AFTERDIV
    
    <h1>Heading 1(NEW PAGE?)</h1>
    
    AFTERH1
    
    <table>
        <tr>
            <td>رقم الغرفة:</td>
            <td>Upper right</td>
        </tr>
        <tr>
            <td>Lower left</td>
            <td>
    
    <table>
        <tr>
            <td>xxx left</td>
            <td>yyy right</td>
        </tr>
        <tr>
            <td>xxx left</td>
            <td>yyy right</td>
        </tr>
    </table>
    
            </td>
        </tr>
    </table>
    
    <p>
    END
    </p>
    </body>
    </html>
    """

    html = HTML_CONTENT.format(ffd=ffD, bod=bod, pEx=pExtra, div=div, tab=tab, h1=h1, tr=tr)

    def test_arabic_check_pdf_language_tag(self):
        """
            this function is used to check if the "Custom Tag" <pdf:language/>
            is located in the document through asssertNotEqual()
        """

        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(self.html)
        tag_element = document.getElementsByTagName("pdf:language")
        self.assertNotEqual(tag_element, [])

    def test_arabic_check_language_in_pdf(self):
        """
            this function is used to check if the "attr language" is
            is located in the pdf result.
        """

        source = BytesIO(self.html.encode('utf-8'))
        destination = BytesIO()
        pdf = pisaDocument(source, destination)

        self.assertTrue(hasattr(pdf, 'language'), '<pdf:language> not found in the resulting PDF!')
        self.assertEqual(pdf.language, 'arabic', 'language "arabic" not detected in <pdf:language>!')
