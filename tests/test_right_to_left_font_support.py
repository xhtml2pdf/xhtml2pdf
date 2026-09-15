import io
import os
from pathlib import Path
from unittest import TestCase

import html5lib
from pypdf import PdfReader

from xhtml2pdf.document import pisaDocument, pisaStory


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
        This function is used to check if the "Custom Tag" <pdf:language/>
        is located in the HTML file through assertNotEqual()
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


class RightToLeftLayoutTests(TestCase):
    """
    What a right-to-left document actually comes out as.

    The tests above check that <pdf:language> was stored on the context;
    none of them looks at the page. Three things were wrong behind that:
    <pdf:language name="arabic"/> set the reshaper going and nothing else,
    so paragraphs were still laid out left to right with the table columns
    beside them in left-to-right order; dir="rtl" reversed each fragment
    with str[::-1], which turned "and Latin text" into "dna nitaL txet";
    and a document declaring both had its text put through the whole of it
    twice.
    """

    FONT = (
        Path(__file__).parent
        / "samples"
        / "font"
        / "Arabic_font"
        / "MarkaziText-Regular.ttf"
    )
    ARABIC = "تقرير"
    TABLE = "<table><tr><td>One</td><td>Two</td><td>Three</td></tr></table>"

    def story_text(self, body: str, *, rtl: str = "") -> str:
        """
        The text of every fragment, as the paragraph will draw it.

        Not PdfReader.extract_text: pypdf runs its own bidirectional pass
        over what it finds, so it hands back something in logical order that
        says nothing about what was drawn. The fragments are what was drawn.
        """
        context = pisaStory(self.document(body, rtl=rtl).encode())
        return " ".join(
            frag.text
            for flowable in context.story
            for frag in getattr(flowable, "frags", None) or []
            if isinstance(frag.text, str)
        )

    def document(self, body: str, *, rtl: str = "") -> str:
        css = f"@font-face {{ font-family: Markazi; src: url('{self.FONT}'); }}"
        attribute = ' dir="rtl"' if rtl == "attribute" else ""
        tag = '<pdf:language name="arabic"/>' if rtl == "tag" else ""
        return (
            f"<html{attribute}>"
            f'<head><meta charset="utf-8"><style>{css}'
            f"body {{ font-family: Markazi; }}</style></head><body>"
            f"{tag}{body}</body></html>"
        )

    def render(self, body: str, *, rtl: str = "") -> str:
        output = io.BytesIO()
        pisaDocument(self.document(body, rtl=rtl).encode(), output)
        return PdfReader(io.BytesIO(output.getvalue())).pages[0].extract_text()

    def test_latin_text_is_not_reversed(self) -> None:
        for rtl in ("tag", "attribute"):
            with self.subTest(rtl=rtl):
                self.assertIn(
                    "and Latin text",
                    self.story_text(f"<p>{self.ARABIC} and Latin text</p>", rtl=rtl),
                )

    def test_the_language_tag_turns_the_document_round(self) -> None:
        text = self.render(self.TABLE, rtl="tag")

        self.assertLess(
            text.index("Three"), text.index("One"), f"columns not mirrored: {text!r}"
        )

    def test_the_dir_attribute_turns_the_document_round(self) -> None:
        text = self.render(self.TABLE, rtl="attribute")

        self.assertLess(text.index("Three"), text.index("One"), text)

    def test_a_left_to_right_document_is_untouched(self) -> None:
        text = self.render(self.TABLE)

        self.assertLess(text.index("One"), text.index("Three"), text)

    def test_declaring_both_is_not_done_twice(self) -> None:
        # The reshaper ran in addFrag and again over the accumulated text in
        # addPara, which put a NUL into the middle of an Arabic paragraph.
        css = f"@font-face {{ font-family: Markazi; src: url('{self.FONT}'); }}"
        html = (
            f'<html dir="rtl"><head><meta charset="utf-8"><style>{css}'
            f"body {{ font-family: Markazi; }}</style></head><body>"
            f'<pdf:language name="arabic"/><p>{self.ARABIC} and Latin</p>'
            f"</body></html>"
        )
        context = pisaStory(html.encode())
        text = " ".join(
            frag.text
            for flowable in context.story
            for frag in getattr(flowable, "frags", None) or []
            if isinstance(frag.text, str)
        )

        self.assertNotIn("\x00", text)
        self.assertIn("and Latin", text)

    def test_the_language_name_is_not_case_sensitive(self) -> None:
        css = f"@font-face {{ font-family: Markazi; src: url('{self.FONT}'); }}"
        html = (
            f'<html><head><meta charset="utf-8"><style>{css}'
            f"body {{ font-family: Markazi; }}</style></head><body>"
            f'<pdf:language name="Arabic"/>{self.TABLE}</body></html>'
        )
        output = io.BytesIO()
        context = pisaDocument(html.encode(), output)
        text = PdfReader(io.BytesIO(output.getvalue())).pages[0].extract_text()

        self.assertTrue(context.is_rtl)
        self.assertLess(text.index("Three"), text.index("One"), text)

    def test_the_arabic_is_put_in_visual_order(self) -> None:
        # get_display returns the order the characters are drawn in, so the
        # Arabic ends up after the Latin on the line -- which is where a
        # right-to-left line puts what was written first.
        text = self.story_text(f"<p>{self.ARABIC} and Latin</p>", rtl="tag")

        # The Arabic was written first, so on a right-to-left line it is
        # drawn last -- the Latin comes out at the start of the run.
        self.assertTrue(text.strip().startswith("and Latin"), repr(text))
