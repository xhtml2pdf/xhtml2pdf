import io
import logging
import os
from pathlib import Path
from typing import ClassVar
from unittest import TestCase

import html5lib
from pypdf import PdfReader

from xhtml2pdf.bidi import get_display
from xhtml2pdf.document import pisaDocument, pisaStory
from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph


def drawn_lines(paragraph, width: float = 400) -> list[str]:
    """The text of each line of `paragraph` in the order it is drawn."""
    paragraph.wrap(width, 100000)
    lines = []
    for line in paragraph.displayLines():
        words = getattr(line, "words", None)
        if words is None:
            lines.append(" ".join(line[1]))
        else:
            lines.append(
                "".join(w.text for w in words if not hasattr(w, "cbDefn") and w.text)
            )
    return lines


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
        The text of every fragment, in logical order: the order it was written.

        The fragments keep it that way; a line is put in the order it is
        drawn only when it is drawn -- see drawn_lines.
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

    def test_dir_auto_keeps_the_inherited_direction_without_a_warning(self) -> None:
        # dir="auto" is valid HTML; it used to be reported as a wrong value.
        # The direction of the text is not worked out, so it inherits.
        table = f'<div dir="auto">{self.TABLE}</div>'
        with self.assertNoLogs("xhtml2pdf", level=logging.WARNING):
            text = self.render(table, rtl="attribute")
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
        pisaDocument(html.encode(), output)
        text = PdfReader(io.BytesIO(output.getvalue())).pages[0].extract_text()

        self.assertLess(text.index("Three"), text.index("One"), text)

    def test_a_direction_declared_inside_the_document_ends_with_it(self) -> None:
        # dir was one value for the whole document, set by whichever element
        # declared it last and never put back, so a single <p dir="rtl"> left
        # every table after it with its columns reversed.
        text = self.render(f'<p dir="rtl">{self.ARABIC}</p><p>after.</p>{self.TABLE}')

        self.assertLess(text.index("One"), text.index("Three"), text)
        self.assertIn("after.", text)

    def test_the_language_tag_can_be_turned_off_again(self) -> None:
        # <pdf:language name=""/> is how a document says it is done with the
        # language, and it has to put the direction back with it.
        text = self.render(
            f'<pdf:language name="arabic"/><p>{self.ARABIC}</p>'
            f'<pdf:language name=""/><p>after.</p>{self.TABLE}'
        )

        self.assertLess(text.index("One"), text.index("Three"), text)
        self.assertIn("after.", text)

    def drawn_lines(self, body: str, *, rtl: str = "", width: float = 400) -> list:
        """
        The lines of the first paragraph, as the text of each is drawn.

        Not PdfReader.extract_text: pypdf runs its own bidirectional pass
        over what it finds, so it hands back something in logical order that
        says nothing about what was drawn.
        """
        context = pisaStory(self.document(body, rtl=rtl).encode())
        paragraph = next(f for f in context.story if isinstance(f, PmlParagraph))
        return drawn_lines(paragraph, width)

    def test_the_text_keeps_the_order_it_was_written_in(self) -> None:
        text = self.story_text(f"<p>{self.ARABIC} and Latin</p>", rtl="tag")

        self.assertTrue(text.strip().endswith("and Latin"), repr(text))

    def test_the_arabic_is_drawn_after_the_latin(self) -> None:
        # The Arabic was written first, so on a right-to-left line it is
        # drawn last -- the Latin comes out at the start of the run.
        (line,) = self.drawn_lines(f"<p>{self.ARABIC} and Latin</p>", rtl="tag")

        self.assertTrue(line.startswith("and Latin"), repr(line))


class LineByLineBidiTests(TestCase):
    """
    A line is put in the order it is drawn in as a whole, once broken.

    Not frag by frag: an entity or a <b> in the middle of a right-to-left
    sentence splits it into frags that are still ordered as one. Not the
    paragraph at once either: its first line holds its first words.
    """

    FONT = (
        Path(__file__).parent.parent
        / "manual_test"
        / "font"
        / "dejavu"
        / "DejaVuSans.ttf"
    )
    WORDS: ClassVar[list[str]] = [c * 3 for c in "אבגדהוזחטיכלמנסעפצקרשת"]

    def paragraphs(self, body: str, *, direction: str = "rtl") -> list:
        css = f"@font-face {{ font-family: D; src: url('{self.FONT}'); }}"
        html = (
            f'<html dir="{direction}"><head><meta charset="utf-8"><style>{css}'
            f"body {{ font-family: D; font-size: 20pt }}</style></head>"
            f"<body>{body}</body></html>"
        )
        context = pisaStory(html.encode())
        return [f for f in context.story if isinstance(f, PmlParagraph)]

    def lines(self, body: str, *, direction: str = "rtl", width: float = 400) -> list:
        return drawn_lines(self.paragraphs(body, direction=direction)[0], width)

    def test_an_entity_does_not_split_the_sentence(self) -> None:
        for dash in ("&mdash;", "<b>—</b>", "—"):
            with self.subTest(dash=dash):
                (line,) = self.lines(f"<p>אאא בבב {dash} גגג דדד</p>")
                self.assertEqual(get_display("אאא בבב — גגג דדד", "R"), line)

    def test_the_first_line_holds_the_first_words(self) -> None:
        lines = self.lines(f"<p>{' '.join(self.WORDS)}</p>", width=230)

        self.assertGreater(len(lines), 2)
        # Drawn right to left: the first word ends the first line.
        self.assertTrue(lines[0].endswith(self.WORDS[0]), lines)
        self.assertTrue(lines[-1].startswith(self.WORDS[-1]), lines)
        drawn = [w for line in lines for w in reversed(line.split())]
        self.assertEqual(self.WORDS, drawn)

    def test_a_bracket_is_mirrored_across_frags(self) -> None:
        (line,) = self.lines("<p>אאא (<b>בבב</b>) גגג</p>")

        self.assertEqual(get_display("אאא (בבב) גגג", "R"), line)

    def test_latin_in_a_right_to_left_line_reads_left_to_right(self) -> None:
        (line,) = self.lines("<p>אאא and Latin בבב</p>")

        self.assertEqual("בבב and Latin אאא", line)

    def test_a_hebrew_word_in_a_left_to_right_paragraph(self) -> None:
        (line,) = self.lines("<p>Latin עברית text</p>", direction="ltr")

        self.assertEqual("Latin תירבע text", line)

    def test_a_left_to_right_paragraph_keeps_its_own_lines(self) -> None:
        (paragraph,) = self.paragraphs("<p>Only Latin text.</p>", direction="ltr")
        paragraph.wrap(400, 1000)

        self.assertIs(paragraph.blPara.lines, paragraph.displayLines())

    def test_a_paragraph_after_a_right_to_left_one_is_left_to_right(self) -> None:
        first, after = self.paragraphs(
            '<p dir="rtl">אאא</p><p>after.</p>', direction="ltr"
        )

        self.assertEqual(("rtl", "ltr"), (first.dir, after.dir))
        self.assertEqual(["after."], drawn_lines(after))

    def test_justified_lines_keep_their_spaces(self) -> None:
        (paragraph,) = self.paragraphs(
            f'<p style="text-align: justify">{" ".join(self.WORDS)}</p>'
        )
        paragraph.wrap(230, 1000)
        for logical, visual in zip(
            paragraph.blPara.lines, paragraph.displayLines(), strict=True
        ):
            count = lambda line: sum(  # noqa: E731
                w.text.count(" ") for w in getattr(line, "words", ()) if w.text
            )
            self.assertEqual(count(logical), count(visual))
            self.assertEqual(logical.extraSpace, visual.extraSpace)

    def test_a_paragraph_split_between_pages_stays_right_to_left(self) -> None:
        (paragraph,) = self.paragraphs(f"<p>{' '.join(self.WORDS)}</p>")
        paragraph.wrap(230, 1000)
        head, tail = paragraph.split(230, 60)

        self.assertEqual(("rtl", "rtl"), (head.dir, tail.dir))
        drawn = [
            w
            for part in (head, tail)
            for line in drawn_lines(part, 230)
            for w in reversed(line.split())
        ]
        self.assertEqual(self.WORDS, drawn)

    def test_an_inline_box_in_a_right_to_left_line(self) -> None:
        from unittest import mock

        from reportlab.pdfgen.canvas import Canvas

        from xhtml2pdf import reportlab_paragraph

        def spans(width: float) -> list:
            (paragraph,) = self.paragraphs(
                "<p>אאא <span style='background-color: #ff0000; padding: 0 4pt'>"
                f"{' '.join(self.WORDS[1:8])}</span> תתת</p>"
            )
            found = []
            original = reportlab_paragraph._do_post_text

            def spy(tx):
                found.extend(tx.XtraState.inlineBoxSpans)
                original(tx)

            with mock.patch.object(reportlab_paragraph, "_do_post_text", spy):
                paragraph.wrapOn(Canvas(io.BytesIO()), width, 1000)
                paragraph.drawOn(Canvas(io.BytesIO()), 0, 0)
            return found

        (one,) = spans(1000)
        x1, x2, _style, first, last = one
        self.assertLess(x1, x2)
        self.assertEqual((True, True), (first, last))

        # Over two lines the box starts on the right of the first and ends
        # on the left of the second: each line has one edge.
        edges = [(first, last) for _x1, _x2, _s, first, last in spans(250)]
        self.assertEqual([(False, True), (True, False)], edges)
