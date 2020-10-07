# -*- coding: utf-8 -*-
import os
import io

import html5lib
from unittest import TestCase
from xhtml2pdf.document import pisaDocument

__doc__ = """
        RightToLeftFontSupportTests provides us auxiliary functions to check 
        the correct operation of writings from right to left, like Arabic,
        Farsi/Persion, Hebrew, Pashto, Urdu and Sindhi.
        """


class RightToLeftFontSupportTests(TestCase):
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
        </style>
        </head>
        
        <body>
        <pdf:language name="right-to-left"/>
        <p>The following lines are in Hebrew, Arabic, Farsi/Persian, Urdu, Pashto and Sindhi.<br>
        All of them are written from right to left.<br>
        There is an English sentence (from left to right) to show the difference.<br>
        If everything works as expected, the numbers 3 and 10 should change position in the right-to-left writings.
        </p>
        
        <div>                
            <span class="Arabic_R">
            Hello. I have 3 children and 10 cats. That's awesome!
            <br>
            <!-- Hebrew-->
            שלום. יש לי 3 ילדים ו -10 חתולים. זה מגניב!
            <br>
             <!-- Arabic -->
            مرحبا. لدي 3 طفلاً و 10 قطة. هذا رائع!
            <br>
             <!-- Farsi/Persian -->
            سلام. من 3 فرزند و 10 گربه دارم. عالی است!
            <br>
             <!-- Urdu -->
            ہیلو. میرے 3 بچے اور 10 بلیاں ہیں۔ یہ تو زبردست ہے!
            <br>
            <!-- Pashto -->
            سلام. زه 3 ماشومان او 10 پیشوګانې لرم. دا په زړه پوری دی!
            <br>
            <!-- Sindhi -->
            سلام. مون وٽ 3 ٻار ۽ 10 ٻچا آهن. اهو خوفناڪ آهي!
            <br>
            </span>
        </div><br><br>
        <p>This is to test different font-weights on Arabic writing.
        Regular, Medium, Bold, SemiBold and Variable.</p>
        <span class="Arabic_R">
        مرحبا. لدي 3 طفلاً و 10 قطة. هذا رائع!
        </span><br>
        <span class="Arabic_M">
        مرحبا. لدي 3 طفلاً و 10 قطة. هذا رائع!
        </span><br>
        <span class="Arabic_B">
        مرحبا. لدي 3 طفلاً و 10 قطة. هذا رائع!
        </span><br>
        <span class="Arabic_SB">
        مرحبا. لدي 3 طفلاً و 10 قطة. هذا رائع!
        </span><br>
        <span class="Arabic_V">
        مرحبا. لدي 3 طفلاً و 10 قطة. هذا رائع!
        </span></body>
        </html>
    """

    html = HTML_CONTENT.format(ff_R=ff_R, ff_M=ff_M, ff_B=ff_B, ff_SB=ff_SB, ff_V=ff_V,
                               css_R=css_R, css_M=css_M, css_B=css_B, css_SB=css_SB, css_V=css_V)

    def test_check_pdf_language_tag(self):
        """
            this function is used to check if the "Custom Tag" <pdf:language/>
            is located in the document through asssertNotEqual()
        """

        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(self.html)
        tag_element = document.getElementsByTagName("pdf:language")
        self.assertNotEqual(tag_element, [])

    def test_check_language_name_in_pdf(self):
        """
            Tests if the attribute 'language' is located in the pisaDocument.
            Tests if 'right-to-left' is the value of the 'language' attribute.
        """

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=io.StringIO(self.html),
                                    dest=pdf_file)

            self.assertTrue(hasattr(pisa_doc, 'language'), '<pdf:language> not found in the resulting PDF!')
            self.assertEqual(pisa_doc.language, 'right-to-left', '"right-to-left" not detected in <pdf:language>!')
