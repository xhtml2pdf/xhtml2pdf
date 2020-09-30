#-*- coding: utf-8 -*-
from io import BytesIO
from copy import copy
import unittest
import reportlab
from xhtml2pdf.document import pisaDocument
from reportlab.pdfbase import pdfmetrics,_cidfontdata
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


__doc__ = """
        asian_font_support_tests provides us auxiliary functions to check 
        the correct operation of Asian fonts included in Report Lab.

        Adobe asian language pack in Report Lab:
        
        Chinese= ['STSong-Light'] # to do
        Tradiciona Chinese = ['MSung-Light']  #, 'MHei-Medium'] # to do
        Japanese= ['HeiseiMin-W3', 'HeiseiKakuGo-W5']
        korean = ['HYSMyeongJo-Medium','HYGothic-Medium']
    """

class asian_font_support_tests(unittest.TestCase):

    HTML_CONTENT = u"""
    <html>
    <head>
    <title></title>
     <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <style type="text/css">

    .jap{
        font-family: HeiseiMin-W3;
    }
    
    .kor{
        font-family: HYSMyeongJo-Medium;
    }


    </style>
    </head>

    <body>
    
    <p class="jap">目提要四部類敘</p>
    <p class="kor">모든 사람은 교육을 받을 권리를 가진다</p>
    <p class= "jap">円鬱イ</p>
    
    </body>
    </html>
    """

    def get_default_asian_font(self):

        lower_font_list = []
        upper_font_list = []

        list = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
        list = list.keys()

        for font in list:
            upper_font_list.append(font)
            lower_font_list.append(font.lower())
        default_asian_font = {lower_font_list[i]: upper_font_list[i] for i in range(len(lower_font_list))}

        return default_asian_font

    def set_asian_fonts(self,fontname):
        list = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
        list = list.keys()
        if fontname in list:
            pdfmetrics.registerFont(UnicodeCIDFont(fontname))

    def test_asian_font_int_pdf(self):

        """
            This function check if asian fonts used in font-family are in
            the pdf result.

            ASIAN_FONT_LIST_USED a dict that contain all fonts used in the style
            real_asian_font a dict that contain all fonts in the pdf result
            (validated through assertDictEqual() have to be equals)
        """

        ASIAN_FONT_LIST_USED = {'heiseimin-w3' : 'HeiseiMin-W3',
                                'hysmyeongjo-medium' : 'HYSMyeongJo-Medium'}

        html = self.HTML_CONTENT
        real_asian_font = {}
        result = BytesIO()
        pdf = pisaDocument(BytesIO(html.encode('utf-8')), result)

        for font in ASIAN_FONT_LIST_USED:
            font_value = ASIAN_FONT_LIST_USED.get(font)
            if font_value == pdf.getFontName(font):
                real_asian_font[font] = font_value

        self.assertDictEqual(ASIAN_FONT_LIST_USED,real_asian_font)

    def test_copy_font_list_cid(self):
        try:
            DEFAULT_ASIAN_FONT = self.get_default_asian_font()
        except:
            DEFAULT_ASIAN_FONT = {}

        self.assertNotEqual(DEFAULT_ASIAN_FONT,{})

    def test_copy_font_list_cid_fail(self):
        try:
            DEFAULT_ASIAN_FONT = self.get_default_asian_fon()
        except:
            DEFAULT_ASIAN_FONT = {}

        self.assertEqual(DEFAULT_ASIAN_FONT,{})

    def test_copy_default_asian_font(self):
        font = "heiseimin-w3"
        DEFAULT_ASIAN_FONT = {"heiseimin-w3": "HeiseiMin-W3"}
        if font in DEFAULT_ASIAN_FONT:
            font = DEFAULT_ASIAN_FONT.get(font)

        self.assertEquals(font,"HeiseiMin-W3")

    def test_copy_default_asian_font_fail(self):
        font = "heiseimin-w"
        DEFAULT_ASIAN_FONT = {"heiseimin-w3": "HeiseiMin-W3"}
        if DEFAULT_ASIAN_FONT != {} and font in DEFAULT_ASIAN_FONT:
            font = DEFAULT_ASIAN_FONT.get(font)
        else:
            print("font-family value not in DEFAULT_ASIAN_FONT")
        self.assertNotEqual(font,"HeiseiMin-W3")

    def test_set_asian_fonts(self):
        result = "OK"
        font = "HeiseiMin-W3"
        try:
            list = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
            list = list.keys()
            if font in list:
                pdfmetrics.registerFont(UnicodeCIDFont(font))
        except:
            result = "Fail"
        self.assertEqual(result,"OK")

    def test_set_asian_fonts_fail(self):
        result = "OK"
        font = "HeiseiMin-W3"
        try:
            list = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncoding)
            list = list.keys()
            if font in list:
                pdfmetrics.registerFont(UnicodeCIDFont(font))
        except Exception as e:
            result = "False"
            print(e)
        self.assertNotEqual(result,"OK")

    def test_get_default_asian_font(self):
        lower_font_list = []
        upper_font_list = []
        try:
            list = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
            list = list.keys()

            for font in list:
                upper_font_list.append(font)
                lower_font_list.append(font.lower())
            default_asian_font = {lower_font_list[i]: upper_font_list[i] for i in range(len(lower_font_list))}
            return  default_asian_font
        except:
            default_asian_font = {}
            return default_asian_font
        self.assertNotEqual(default_asian_font,{})

    def test_get_default_asian_font_fail(self):
        lower_font_list = []
        upper_font_list = []
        try:
            list = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodin)
            list = list.keys()

            for font in list:
                upper_font_list.append(font)
                lower_font_list.append(font.lower())
            default_asian_font = {lower_font_list[i]: upper_font_list[i] for i in range(len(lower_font_list))}
            return  default_asian_font
        except:
            default_asian_font = {}
            return default_asian_font
        self.assertEqual(default_asian_font,{})








