# ruff: noqa: RUF001
import io
import os
from unittest import TestCase

import html5lib

from xhtml2pdf.document import pisaDocument


class RightToLeftFontSupportTests(TestCase):
    """
    RightToLeftFontSupportTests provides us auxiliary functions to check
    the correct operation of the Arabic writing from right to left.
    """

    tests_folder = os.path.dirname(os.path.realpath(__file__))
    ttf_pathR = os.path.join(
        tests_folder, "samples", "font", "Arabic_font", "MarkaziText-Regular.ttf"
    )
    ttf_pathM = os.path.join(
        tests_folder, "samples", "font", "Arabic_font", "MarkaziText-Medium.ttf"
    )
    ttf_pathB = os.path.join(
        tests_folder, "samples", "font", "Arabic_font", "MarkaziText-Bold.ttf"
    )
    ttf_pathSB = os.path.join(
        tests_folder, "samples", "font", "Arabic_font", "MarkaziText-SemiBold.ttf"
    )
    ttf_pathV = os.path.join(
        tests_folder,
        "samples",
        "font",
        "Arabic_font",
        "MarkaziText-VariableFont_wght.ttf",
    )

    ff_R = f"@font-face {{font-family: Regular; src: url('{ttf_pathR}');}}"
    ff_M = f"@font-face {{font-family: Medium; src: url('{ttf_pathM}');}}"
    ff_B = f"@font-face {{font-family: Bold; src: url('{ttf_pathB}');}}"
    ff_SB = f"@font-face {{font-family: SemiBold; src: url('{ttf_pathSB}');}}"
    ff_V = f"@font-face {{font-family: Variable; src: url('{ttf_pathV}');}}"

    HTML_CONTENT: str = """
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

            .RegularClass {{ font-family: Regular }}
            .MediumClass {{ font-family: Medium }}
            .BoldClass {{ font-family: Bold }}
            .SemiBoldClass {{ font-family: SemiBold }}
            .VariableClass {{ font-family: Variable }}
        </style>
        </head>

        <body>
        <p>
        The following lines are in Arabic/Hebrew/Persian etc., written from right to left.<br>
        There is an English sentence (from left to right) to show the difference.<br>
        If everything works as expected, the numbers 3 and 10 should change position<br>
        in the Arabic/Hebrew/Persian etc. sentences.<br><br>

        We're also testing different font-weights:<br>
        Regular, Medium, Bold, SemiBold and Variable
        </p>

        {language_tag}

        <br><br>
        <span class="RegularClass">
        Hello. I have 3 children and 10 cats. That's awesome!<br>
        <br>
        {text}
        </span><br>
        <span class="MediumClass">
        {text}
        </span><br>
        <span class="BoldClass">
        {text}
        </span><br>
        <span class="SemiBoldClass">
        {text}
        </span><br>
        <span class="VariableClass">
        {text}
        </span></body>
        </html>
    """

    def test_pdf_language_tag_in_html(self) -> None:
        """
        this function is used to check if the "Custom Tag" <pdf:language/>
        is located in the HTML file through asssertNotEqual()
        """
        text = ""
        language_tag = '<pdf:language name=""/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(html)
        tag_element = document.getElementsByTagName("pdf:language")
        self.assertNotEqual(tag_element, [])

    def test_language_attribute_in_pisaDocument(self) -> None:
        """Tests if the attribute 'language' is located in the pisaDocument."""
        text = ""
        language_tag = '<pdf:language name=""/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=html, dest=pdf_file)

            self.assertTrue(
                hasattr(pisa_doc, "language"),
                "<pdf:language> not found in the resulting PDF!",
            )

    def test_arabic_in_pdf_language(self) -> None:
        """Tests if 'arabic' is the value of the 'language' attribute."""
        text = "مرحبا. لدي 3 طفلاً و 10 قطة. هذا رائع!"
        language_tag = '<pdf:language name="arabic"/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=html, dest=pdf_file)

            self.assertEqual(
                pisa_doc.language, "arabic", '"arabic" not detected in <pdf:language>!'
            )

    def test_hebrew_in_pdf_language(self) -> None:
        """Tests if 'hebrew' is the value of the 'language' attribute."""
        text = "שלום. יש לי 3 ילדים ו -10 חתולים. זה מגניב!"
        language_tag = '<pdf:language name="hebrew"/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=html, dest=pdf_file)

            self.assertEqual(
                pisa_doc.language, "hebrew", '"hebrew" not detected in <pdf:language>!'
            )

    def test_persian_in_pdf_language(self) -> None:
        """Tests if 'persian' is the value of the 'language' attribute."""
        text = "سلام. من 3 فرزند و 10 گربه دارم. عالی است!"
        language_tag = '<pdf:language name="persian"/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=html, dest=pdf_file)

            self.assertEqual(
                pisa_doc.language,
                "persian",
                '"persian" not detected in <pdf:language>!',
            )

    def test_urdu_in_pdf_language(self) -> None:
        """Tests if 'urdu' is the value of the 'language' attribute."""
        text = "ہیلو. میرے 3 بچے اور 10 بلیاں ہیں۔ یہ تو زبردست ہے!"
        language_tag = '<pdf:language name="urdu"/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=html, dest=pdf_file)

            self.assertEqual(
                pisa_doc.language, "urdu", '"urdu" not detected in <pdf:language>!'
            )

    def test_pashto_in_pdf_language(self) -> None:
        """Tests if 'pashto' is the value of the 'language' attribute."""
        text = "سلام. زه 3 ماشومان او 10 پیشوګانې لرم. دا په زړه پوری دی!"
        language_tag = '<pdf:language name="pashto"/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=html, dest=pdf_file)

            self.assertEqual(
                pisa_doc.language, "pashto", '"pashto" not detected in <pdf:language>!'
            )

    def test_sindhi_in_pdf_language(self) -> None:
        """Tests if 'sindhi' is the value of the 'language' attribute."""
        text = "سلام. مون وٽ 3 ٻار ۽ 10 ٻچا آهن. اهو خوفناڪ آهي!"
        language_tag = '<pdf:language name="sindhi"/>'

        html = self.HTML_CONTENT.format(
            ff_R=self.ff_R,
            ff_M=self.ff_M,
            ff_B=self.ff_B,
            ff_SB=self.ff_SB,
            ff_V=self.ff_V,
            text=text,
            language_tag=language_tag,
        )

        with io.BytesIO() as pdf_file:
            pisa_doc = pisaDocument(src=html, dest=pdf_file)

            self.assertEqual(
                pisa_doc.language, "sindhi", '"sindhi" not detected in <pdf:language>!'
            )
