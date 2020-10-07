# -*- coding: utf-8 -*-
import os
import io

import html5lib
from unittest import TestCase
from xhtml2pdf.document import pisaDocument

__doc__ = """
        ArabicFontSupportTests provides us auxiliary functions to check 
        the correct operation of arabic fonts.
        """


class ArabicFontSupportTests(TestCase):
    tests_folder = os.path.dirname(os.path.realpath(__file__))
    ttf_pathR = os.path.join(tests_folder, 'samples', 'font', 'Arabic_font', 'MarkaziText-Regular.ttf')
    ttf_pathM = os.path.join(tests_folder, 'samples', 'font', 'Arabic_font', 'MarkaziText-Medium.ttf')
    ttf_pathB = os.path.join(tests_folder, 'samples', 'font', 'Arabic_font', 'MarkaziText-Bold.ttf')
    ttf_pathSB = os.path.join(tests_folder, 'samples', 'font', 'Arabic_font', 'MarkaziText-SemiBold.ttf')
    ttf_pathV = os.path.join(tests_folder, 'samples', 'font', 'Arabic_font', 'MarkaziText-VariableFont_wght.ttf')

    ff_R = "@font-face {{font-family: Arabic_R; src: url(\'{ttf}\');}}".format(ttf=ttf_pathR)
    ff_M = "@font-face {{font-family: Arabic_M; src: url(\'{ttf}\');}}".format(ttf=ttf_pathM)
    ff_B = "@font-face {{font-family: Arabic_B; src: url(\'{ttf}\');}}".format(ttf=ttf_pathB)
    ff_SB = "@font-face {{font-family: Arabic_SB; src: url(\'{ttf}\');}}".format(ttf=ttf_pathSB)
    ff_V = "@font-face {{font-family: Arabic_V; src: url(\'{ttf}\');}}".format(ttf=ttf_pathV)

    css_R = ".Arabic_R { font-family: Arabic_R }"
    css_M = ".Arabic_M { font-family: Arabic_M }"
    css_B = ".Arabic_B { font-family: Arabic_B }"
    css_SB = ".Arabic_SB { font-family: Arabic_SB }"
    css_V = ".Arabic_V { font-family: Arabic_V }"
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
                        {ff_R}
                        {ff_M}
                        {ff_B}
                        {ff_SB}
                        {ff_V}
                        
                        {css_R}
                        {css_M}
                        {css_B}
                        {css_SB}
                        {css_V}
                         
                        {pEx}
                        {div}
                        {tab}
                        {h1}
                        {tr} 
                    </style>
                    </head>
                    
                    <body>
                    <pdf:language name="arabic"/>
                    <div>
                        <span class="Arabic_R">رقم الغرفة:</span>
                        <span class="Arabic_M">رقم الغرفة:</span>
                        <span class="Arabic_B">رقم الغرفة:</span>
                    </div>
                    
                    Test
                    <p>Block 1</p>
                    <br>
                    New Line
                    <br><br>
                    And another one!
                    <p class="extra">Block 2</p>
                    
                    <div style="page-break-after: always;">
                        DIV 1 BEGIN
                    
                        <div class="extra">
                            INNERDIV A
                        <p style="background-color: blue;">INNERP</p>
                        </div>
                    
                        DIV 1 END
                    </div>
                    
                    (NEW PAGE?) AFTERDIV
                    
                    <h1>Heading 1(NEW PAGE?)</h1>
                    
                    AFTERH1
                    
                    <table>
                        <tr>
                            <td class="Arabic_SB">رقم الغرفة:</td>
                            <td class="Arabic_V">رقم الغرفة:</td>
                            <td>Upper right</td>
                        </tr>
                        <tr>
                            <td>Lower left</td>
                            <td>Test</td>
                            <td>Test</td>
                        </tr>
                    </table>
                    <table>
                        <tr>
                            <td>xxx left</td>
                            <td>yyy right</td>
                            <td>yyy right</td>
                        </tr>
                        <tr>
                            <td>xxx left</td>
                            <td>yyy right</td>
                            <td>yyy right</td>
                        </tr>
                    </table>
                    
                    <p>
                    END
                    </p>
                    </body>
                    </html>
    """

    html = HTML_CONTENT.format(ff_R=ff_R, ff_M=ff_M, ff_B=ff_B, ff_SB=ff_SB, ff_V=ff_V,
                               css_R=css_R, css_M=css_M, css_B=css_B, css_SB=css_SB, css_V=css_V,
                               pEx=pExtra, div=div, tab=tab, h1=h1, tr=tr)

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

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=io.StringIO(self.html),
                                    dest=pdf_file)

            self.assertTrue(hasattr(pisa_doc, 'language'), '<pdf:language> not found in the resulting PDF!')
            self.assertEqual(pisa_doc.language, 'arabic', 'language "arabic" not detected in <pdf:language>!')
