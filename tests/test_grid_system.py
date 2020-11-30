# -*- coding: utf-8 -*-
import io
import os
from unittest import TestCase
from PyPDF2 import PdfFileReader
from xhtml2pdf.document import pisaDocument

__doc__ = """
        GridSystemTests provides us auxiliary functions to check 
        the correct work of the system grid, which handle the content position
        according to the columns positioning.
        """


class GridSystemTest(TestCase):
    tests_folder = os.path.dirname(os.path.realpath(__file__))
    img_path = os.path.join(tests_folder, 'samples', 'img', 'beach.jpg')

    tag_img_one = "<img width =30px height=30px src =\'{img}\'".format(img=img_path)
    tag_img_two = "<img width=200px height=100px src =\'{img}\'".format(img=img_path)
    body_page_template = "@page body{size: letter;@frame header_frame{-pdf-frame-content: header_content;" \
                        "left: 50pt; width: 512pt; top: 50pt; height: 40pt;}@frame content_frame{" \
                        "left: 50pt; width: 512pt; top: 90pt; height: 632pt;}@frame footer_frame{" \
                        "-pdf-frame-content: footer_content; left: 50pt; width: 512pt; top: 772pt; height: 20pt;}}"

    HTML_CONTENT = u"""
       <html>
        <head>
    <title>Title</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
</head>
<style>
       {body_page_template}
</style>
<body>

    <div id="header_content">Grid Experiment</div>
    <p>NO GRID</p>
    {{tag_img_one}}
    <div id="footer_content">(c) - page <pdf:pagenumber>
        of <pdf:pagecount>
    </div>
    
    <pdf:nexttemplate name="id0" />
    <pdf:nextframe name="" />
    
    <div class="row" style="text-align: center">
    <div class="col-sm-6" coltype="parent" style="background-color: #99CC66">
    <div class="row" rowtype="child">
        <pdf:nextframe name="" />
        <div class="col-sm-4" coltype="child" style="background-color: #FFBBBB">rosa col-4</div>
        <div class="col-sm-8" coltype="child" style="background-color: #336699">azul col-8
        </div>
        </div>
        </div>
        <div class="col-sm-6">blanco cols-6</div>
    </div>
    <div class="row" style="text-align: center">
        <div class="col-sm-4" style="background-color: aqua">
            Celeste orem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore
            et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip
            exea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu
            fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt
            mollit anim id est laborum.
        </div>
        <div class="col-sm-4" style="background-color: crimson">
            Rojo Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et
            dolore magna aliqua consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna
            aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
            consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
            pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id
            est laborum consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
            Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
            Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est
            laborum consectetur adipiscing elit.
        </div>
        <div class="is-4" style="background-color: green">
            Verde Lorem ipsum dolor sit amet, consectetur adipiscing elit ut labore et dolore magna aliqua. Ut enim ad
            minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute
            irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint
            occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum Verde Lorem
            ipsum dolor sit amet, consectetur adipiscing elit ut labore et dolore magna aliqua. Ut enim ad minim veniam,
            quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in
            reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat
            cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum Verde Lorem ipsum
            dolor sit amet, consectetur adipiscing elit ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
            nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in
            reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat
            cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
            quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in
            reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat
            cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum Verde Lorem ipsum
            dolor sit amet, consectetur adipiscing elit ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
            nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in
            reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat
            cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
        </div>
        </div>
    </div>
    <div class="row" style="text-align: center">
        <div class="col-sm-4" style="background-color: aquamarine">
            {{tag_img_two}}
        </div>
        <div class="col-sm-8" style="background-color: blueviolet">
            Morado Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur
            adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet,
            consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit
            amet, consectetur adipiscing elitv.
        </div>
    </div>
    
    <pdf:nexttemplate name="body" />
    <pdf:nextframe name="" />
    <div><p>NO GRID</p></div>
        </body>
        </html>
    """

    html = HTML_CONTENT.format(body_page_template=body_page_template, tag_img_one=tag_img_one,
                                    tag_img_two=tag_img_two)

    def test_checking_content_in_context_as_frag_inCol(self):
        """
            this function is used to check if the text from pdf_file in page 2 is the one that should be
             according the grid system result form the html source
        """
        text = """{tag_img_two}
            Morado Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit
            amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv
            Lorem ipsum dolor sit amet, consectetur adipiscing elitv Lorem ipsum dolor sit amet,
            consectetur adipiscing elitv Lorem ipsum dolor sit amet, consectetur adipiscing elitv."""
        text = text.replace('\n            ','')

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=self.html,
            dest=pdf_file)
            pdf_file.seek(0)
            pdf_content = PdfFileReader(pdf_file)

            page_two_text = pdf_content.getPage(2).extractText()
            page_two_text = page_two_text.replace('\n','')

        self.assertEquals(text, page_two_text)