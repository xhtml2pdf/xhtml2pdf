import io
import os
from unittest import TestCase

import html5lib

from xhtml2pdf.document import pisaDocument
from xhtml2pdf.w3c.cssDOMElementInterface import CSSDOMElementInterface


class TTFWithSameFaceName(TestCase):
    """
    TTFWithSameFaceName provides us auxiliary functions to check
    the correct way to choose the font style when we use a ttf file with the same face name.
    it always takes the last one @font-face font-family for all the text so to avoid this issue
    we have to add a "#" in the begin of the font-family value
    """

    tests_folder = os.path.dirname(os.path.realpath(__file__))
    ttf_pathR = os.path.join(
        tests_folder, "samples", "font", "Noto_Sans", "NotoSans-Regular.ttf"
    )
    ttf_pathB = os.path.join(
        tests_folder, "samples", "font", "Noto_Sans", "NotoSans-Bold.ttf"
    )
    ttf_pathI = os.path.join(
        tests_folder, "samples", "font", "Noto_Sans", "NotoSans-Italic.ttf"
    )
    ttf_pathBI = os.path.join(
        tests_folder, "samples", "font", "Noto_Sans", "NotoSans-BoldItalic.ttf"
    )

    ff_R = f"@font-face {{font-family: Noto_Regular; src: url('{ttf_pathR}');}}"
    ff_RM = (
        f"@font-face{{font-family: Noto_Regular_Minified; src: url('{ttf_pathR}');}}"
    )
    ff_B = f"@font-face {{font-family: Noto_Bold; src: url('{ttf_pathB}');}}"
    ff_I = f"@font-face {{font-family: Noto_Italic; src: url('{ttf_pathI}');}}"
    ff_BI = f"@font-face {{font-family: Noto_BoldItalic; src: url('{ttf_pathBI}');}}"

    css_R: str = ".classRegular{font-family: Noto_Regular;}"
    css_RM: str = ".classRegularMinified{font-family: Noto_Regular_Minified;}"
    css_B: str = ".classBold{font-family: Noto_Bold;}"
    css_I: str = ".classItalic{font-family: Noto_Italic;}"
    css_BI: str = ".classBoldItalic{font-family: Noto_BoldItalic;}"

    HTML_CONTENT: str = """
                        <html>
                        <title></title>
                        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                        <style type="text/css">

                        {ff_R}
                        {ff_RM}
                        {ff_B}
                        {ff_I}
                        {ff_BI}

                        {css_R}
                        {css_RM}
                        {css_B}
                        {css_I}
                        {css_BI}

                        </style>
                        </head>

                        <body>

                        <span class="classRegular">My custom regular font type</span>
                        <span class="classRegularMinified">My custom regular minified font type</span>
                        <span class="classBold">My custom bold font type</span>
                        <span class="classItalic">My custom italic font type</span>
                        <span class="classBoldItalic">My custom bold-italic font type</span>

                        </body>
                        </html>
                    """

    html = HTML_CONTENT.format(
        ff_R=ff_R,
        ff_RM=ff_RM,
        ff_B=ff_B,
        ff_I=ff_I,
        ff_BI=ff_BI,
        css_R=css_R,
        css_RM=css_RM,
        css_B=css_B,
        css_I=css_I,
        css_BI=css_BI,
    )

    def test_check_updated_face_name(self) -> None:
        """
        this function help us to check is the font-family value on the pdf and
        the font-family from html element are same.
        """
        # Create the pisaDocument in memory from the HTML
        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=self.html, dest=pdf_file)

        # Parse HTML
        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(self.html)

        for spanElement in document.getElementsByTagName("span"):
            spanElement = CSSDOMElementInterface(spanElement)
            rules = pisa_doc.cssCascade.findCSSRulesFor(spanElement, "font-family")
            font_family_html = rules[0][1].get("font-family").lower()

            # Test if font-family of custom @font-face was added to the pisaDocument
            self.assertIsNotNone(pisa_doc.fontList.get(font_family_html))
