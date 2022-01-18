# -*- coding: utf-8 -*-
import io
from unittest import TestCase

from PyPDF3 import PdfFileReader
from reportlab.pdfbase import _cidfontdata

from xhtml2pdf.document import pisaDocument
from xhtml2pdf.util import get_default_asian_font

__doc__ = """
        AsianFontSupportTests provides us auxiliary functions to check 
        the correct operation of Asian fonts included in Report Lab.

        Adobe asian language pack in Report Lab:
        
        Simplified Chinese = ['STSong-Light']
        Tradicional Chinese = ['MSung-Light']
        Japanese = ['HeiseiMin-W3', 'HeiseiKakuGo-W5']
        Korean = ['HYSMyeongJo-Medium','HYGothic-Medium']
    """


class AsianFontSupportTests(TestCase):
    HTML_CONTENT = u"""
    <html>
    <head>
    <title></title>
     <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <style type="text/css">

    .chs { font-family: STSong-Light }
    .cht { font-family: MSung-Light }
    
    .jpn1 { font-family: HeiseiMin-W3 }
    .jpn2 { font-family: HeiseiKakuGo-W5 }
    
     .kor1 { font-family: HYSMyeongJo-Medium }
     .kor2 { font-family: HYGothic-Medium }

    </style>
    </head>

    <body>
    
    <p> I ate dinner. We had a three-course meal. Brad came to dinner with us. He loves fish tacos.
        In the end, we all felt like we ate too much. We all agreed; it was a magnificent evening.
        I hope that, when I've built up my savings, I'll be able to travel to Mexico.
        Wouldn't it be lovely to enjoy a week soaking up the culture? Oh, how I'd love to go!
        Of all the places to travel, Mexico is at the top of my list. Would you like to travel with me?
        Isn't language learning fun? There is so much to understand. I love learning!
        Sentences come in many shapes and sizes. Nothing beats a complete sentence.
        Once you know all the elements, it's not difficult to pull together a sentence.
    </p>
    <p class="chs"> 我吃过晚餐了。 我们吃了三道菜。 布拉德和我们一起吃饭。 他爱炸玉米饼。 最后，我们所有人都觉得自己吃得太多。
                    我们都同意； 那是一个宏伟的夜晚。 我希望，当我积累了积蓄之后，就能去墨西哥旅行。 享受一周的文化吸收会不会很可爱？
                    哦，我多么想去！ 在所有旅行的地方中，墨西哥在我的列表中排名第一。 你想和我一起旅行吗？ 语言学习不是很有趣吗？
                    有很多要理解的。 我喜欢学习！ 句子有多种形状和大小。 没有什么能说完整的句子了。
                    一旦了解了所有要素，将句子拼凑起来就很容易了。
    </p>             
    <p class="cht"> 我吃過晚餐了。 我們吃了三道菜。 布拉德和我們一起吃飯。 他愛炸玉米餅。 最後，我們所有人都覺得自己吃得太多。
                    我們都同意； 那是一個宏偉的夜晚。 我希望，當我積累了積蓄之後，就能去墨西哥旅行。 享受一周的文化吸收會不會很可愛？
                    哦，我多麼想去！ 在所有旅行的地方中，墨西哥在我的列表中排名第一。 你想和我一起旅行嗎？ 語言學習不是很有趣嗎？
                    有很多要理解的。 我喜歡學習！ 句子有多種形狀和大小。 沒有什麼能說完整的句子了。
                    一旦了解了所有要素，將句子拼湊起來就很容易了。
    </p>
    
    <p class="jpn1">私は夕食を食べました。 3コースの食事をしました。 ブラッドは私たちと一緒に夕食に来ました。 彼は魚のタコスが大好きです。
                    結局、私たちは皆、食べ過ぎたように感じました。 私たちは皆同意しました。 素晴らしい夜でした。
                    貯金が貯まったら、メキシコに旅行できるようになることを願っています。 文化に浸る一週間を楽しむのは素敵ではないでしょうか？
                    ああ、どうやって行きたいの！ 旅行するすべての場所の中で、メキシコは私のリストの一番上にあります。 私と一緒に旅行しませんか？
                    言語学習は楽しいものではありませんか？ 理解することがたくさんあります。 私は学ぶのが大好きです！
                    文章にはさまざまな形やサイズがあります。 完全な文に勝るものはありません。
                    すべての要素を理解したら、文をまとめるのは難しくありません。
    </p>
    <p class="jpn2">私は夕食を食べました。 3コースの食事をしました。 ブラッドは私たちと一緒に夕食に来ました。 彼は魚のタコスが大好きです。
                    結局、私たちは皆、食べ過ぎたように感じました。 私たちは皆同意しました。 素晴らしい夜でした。
                    貯金が貯まったら、メキシコに旅行できるようになることを願っています。 文化に浸る一週間を楽しむのは素敵ではないでしょうか？
                    ああ、どうやって行きたいの！ 旅行するすべての場所の中で、メキシコは私のリストの一番上にあります。 私と一緒に旅行しませんか？
                    言語学習は楽しいものではありませんか？ 理解することがたくさんあります。 私は学ぶのが大好きです！
                    文章にはさまざまな形やサイズがあります。 完全な文に勝るものはありません。
                    すべての要素を理解したら、文をまとめるのは難しくありません。
    </p>
    <p class="kor1">나는 저녁을 먹었다. 3 코스 식사를했습니다. 브래드는 우리와 함께 저녁을 먹으러 왔습니다. 그는 생선 타코를 좋아합니다.
                    결국 우리 모두는 너무 많이 먹는 것 같았습니다. 우리 모두 동의했습니다. 멋진 저녁이었습니다.
                    저축을 마쳤을 때 멕시코로 여행 할 수 있기를 바랍니다. 문화에 흠뻑 젖어 일주일을 즐기는 것이 멋지지 않을까요? 오,
                    내가 얼마나 가고 싶어요! 여행 할 모든 장소 중에서 멕시코가 내 목록의 맨 위에 있습니다. 나와 함께 여행 하시겠습니까?
                    언어 학습이 재미 있지 않나요? 이해할 것이 너무 많습니다. 나는 배우는 것을 좋아합니다!
                    문장은 다양한 모양과 크기로 제공됩니다. 완전한 문장을 능가하는 것은 없습니다.
                    모든 요소를 알고 나면 한 문장을 모으는 것이 어렵지 않습니다.
    </p>
    <p class="kor2">나는 저녁을 먹었다. 3 코스 식사를했습니다. 브래드는 우리와 함께 저녁을 먹으러 왔습니다. 그는 생선 타코를 좋아합니다.
                    결국 우리 모두는 너무 많이 먹는 것 같았습니다. 우리 모두 동의했습니다. 멋진 저녁이었습니다.
                    저축을 마쳤을 때 멕시코로 여행 할 수 있기를 바랍니다. 문화에 흠뻑 젖어 일주일을 즐기는 것이 멋지지 않을까요? 오,
                    내가 얼마나 가고 싶어요! 여행 할 모든 장소 중에서 멕시코가 내 목록의 맨 위에 있습니다. 나와 함께 여행 하시겠습니까?
                    언어 학습이 재미 있지 않나요? 이해할 것이 너무 많습니다. 나는 배우는 것을 좋아합니다!
                    문장은 다양한 모양과 크기로 제공됩니다. 완전한 문장을 능가하는 것은 없습니다.
                    모든 요소를 알고 나면 한 문장을 모으는 것이 어렵지 않습니다.
    </p>
    </body>
    </html>
    """

    def test_asian_font_in_pdf(self):
        """
            Tests if the asian fonts used in the CSS property "font-family"
            are correctly embeded in the pdf result.
        """

        # Read the embeded fonts from the finished pdf file
        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(
                src=self.HTML_CONTENT,
                dest=pdf_file)
            pdf_file.seek(0)
            pdf_content = PdfFileReader(pdf_file)
            pdf_fonts = read_fonts_from_pdf(pdf_content)

        # Read the fonts from the html content
        html_fonts = []
        for css_class in pisa_doc.css[0].values():
            for html_font_family in css_class.values():
                html_fonts.append(html_font_family)

        # Test, if all of the font-families from the html are also in the pdf file
        self.assertTrue(pdf_fonts.issuperset(html_fonts), 'Not all asian fonts detected in the PDF file!')

    def test_get_default_asian_font(self):
        """ Tests if we can successfully extract the default asian fonts """

        DEFAULT_ASIAN_FONT = get_default_asian_font()

        # Test, if is dict
        self.assertIsInstance(DEFAULT_ASIAN_FONT, dict, 'get_default_asian_font not returning a dict!')
        # Test, if dict is not empty
        self.assertNotEqual(DEFAULT_ASIAN_FONT, {}, 'get_default_asian_font return an empty dict!')

    def test_asian_reportlab_fonts(self):
        """ Tests the asian font list that we're getting from reportlab
            If there is an Error here, ReportLab probably has changed/added new asian fonts
        """

        reference = {'HeiseiMin-W3': ('jpn', 'UniJIS-UCS2-H'), 'HeiseiKakuGo-W5': ('jpn', 'UniJIS-UCS2-H'),
                     'STSong-Light': ('chs', 'UniGB-UCS2-H'), 'MSung-Light': ('cht', 'UniGB-UCS2-H'),
                     'HYSMyeongJo-Medium': ('kor', 'UniKS-UCS2-H'), 'HYGothic-Medium': ('kor', 'UniKS-UCS2-H')}

        reportlab_fonts = _cidfontdata.defaultUnicodeEncodings

        # Test if equal to reference
        self.assertEqual(reference, reportlab_fonts, 'New asian fonts added or changed by ReportLab !')


def get_fonts_from_page(obj, fnt):
    for k in obj:
        if '/BaseFont' in obj[k]:
            fnt.add(str(obj[k]['/BaseFont'])[1:])
    return fnt


def read_fonts_from_pdf(pdf):
    fonts = set()

    for page in pdf.pages:
        obj = page.getObject()
        fonts = get_fonts_from_page(obj['/Resources']['/Font'], fonts)

    return fonts
