"""
display: inline-block -- a box that is one word of the line it sits in.

The paragraph carries it the way it carries an inline image, as a cbDefn;
what is checked here is that the parser builds that frag, that the fork of
Paragraph measures and draws it in the line, and that nothing about the
surrounding paragraph is lost on the way.
"""

import io
import re
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf import pisa
from xhtml2pdf.builders.flex import FlexContainer, InlineBox
from xhtml2pdf.document import pisaStory
from xhtml2pdf.reportlab_paragraph import _getFragWords
from xhtml2pdf.xhtml2pdf_reportlab import PmlInput, PmlParagraph

BOX = "display:inline-block; width:40pt; padding:2pt; border:1pt solid #000"


def _paragraphs(html: str) -> list[PmlParagraph]:
    context = pisaStory(html)
    assert context.err == 0
    return [f for f in context.story if isinstance(f, PmlParagraph)]


def _boxes(paragraph: PmlParagraph) -> list:
    return [
        f.cbDefn
        for f in paragraph.frags
        if getattr(getattr(f, "cbDefn", None), "kind", None) == "box"
    ]


class InlineBlockParsingTest(TestCase):
    def test_it_is_one_frag_of_its_paragraph(self) -> None:
        (para,) = _paragraphs(f"<p>a <span style='{BOX}'>X</span> b</p>")
        (box,) = _boxes(para)
        self.assertIsInstance(box.flowable, InlineBox)
        # 40 of content, 2 of padding and 1 of border each side.
        self.assertAlmostEqual(46, box.width)
        self.assertEqual(box.width, box.flowable.width)

    def test_the_text_around_it_stays_in_the_same_paragraph(self) -> None:
        (para,) = _paragraphs(f"<p>a <span style='{BOX}'>X</span> b</p>")
        texts = [f.text for f in para.frags if f.text.strip()]
        self.assertEqual(["a", "b"], [t.strip() for t in texts])
        self.assertIn("a", para.text)
        self.assertIn("b", para.text)

    def test_the_box_paints_its_own_box_and_its_content_does_not(self) -> None:
        (para,) = _paragraphs(
            f"<p>a <span style='{BOX}; background-color: #eee'>X</span></p>"
        )
        (box,) = _boxes(para)
        style = box.flowable.style
        self.assertEqual(2, style.paddingLeft)
        self.assertEqual("solid", style.borderLeftStyle)
        self.assertIsNotNone(style.backColor)
        inner = box.flowable.content[0]
        self.assertEqual(0, inner.style.paddingLeft)
        self.assertIsNone(inner.style.backColor)

    def test_getFragWords_treats_it_as_one_atom(self) -> None:
        (para,) = _paragraphs(f"<p>a <span style='{BOX}'>X Y</span> b</p>")
        (box,) = _boxes(para)
        atoms = [w for w in _getFragWords(para.frags) if w[0] == box.width]
        self.assertEqual(1, len(atoms))

    def test_vertical_align_is_read(self) -> None:
        (para,) = _paragraphs(
            f"<p>a <span style='{BOX}; vertical-align: middle'>X</span></p>"
        )
        self.assertEqual("middle", _boxes(para)[0].valign)

    def test_a_box_alone_still_makes_a_paragraph(self) -> None:
        (para,) = _paragraphs(f"<div><span style='{BOX}'>X</span></div>")
        self.assertEqual(1, len(_boxes(para)))

    def test_an_empty_box_is_nothing(self) -> None:
        (para,) = _paragraphs(f"<p>a <span style='{BOX}'> </span> b</p>")
        self.assertEqual([], _boxes(para))

    def test_a_flex_container_inside_an_inline_block(self) -> None:
        (para,) = _paragraphs(
            f"<p>a <span style='{BOX}'><span style='display:flex'>"
            "<span>1</span><span>2</span></span></span> b</p>"
        )
        (box,) = _boxes(para)
        self.assertIsInstance(box.flowable.content[0], FlexContainer)

    def test_inside_a_flex_container_it_is_an_item(self) -> None:
        context = pisaStory(
            "<div style='display:flex'><span style='display:inline-block'>a</span>"
            "<div>b</div></div>"
        )
        container = next(f for f in context.story if isinstance(f, FlexContainer))
        self.assertEqual(2, len(container.items))

    def test_an_input_does_not_break_the_line(self) -> None:
        (para,) = _paragraphs("<p>Name: <input type='text' name='n'/> end</p>")
        (box,) = _boxes(para)
        self.assertIsInstance(box.flowable.content[0], PmlInput)
        self.assertIn("Name:", para.text)
        self.assertIn("end", para.text)


class InlineBlockLayoutTest(TestCase):
    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    def test_the_box_advances_the_line(self) -> None:
        (para,) = _paragraphs(f"<p>aaaa <span style='{BOX}'>X</span> bbbb</p>")
        drawn: list[tuple[float, float]] = []

        def record(_self, _canvas, x, y, _sW=0):
            drawn.append((x, y))

        with patch.object(InlineBox, "drawOn", record):
            para.wrapOn(self.canv, 400, 800)
            para.drawOn(self.canv, 0, 0)
        (position,) = drawn
        # After "aaaa ", not at the line's start.
        self.assertGreater(position[0], 15)
        self.assertLess(position[0], 40)

    def test_vertical_align_reaches_the_line_layout(self) -> None:
        # imgVRange is what places an inline image against the baseline; the
        # box goes through the same call with the same vocabulary.
        from xhtml2pdf import reportlab_paragraph

        (para,) = _paragraphs(
            f"<p>a <span style='{BOX}; height: 30pt; vertical-align: middle'>X</span></p>"
        )
        seen = []
        original = reportlab_paragraph.imgVRange

        def spy(h, va, font_size):
            seen.append((h, va))
            return original(h, va, font_size)

        with patch.object(reportlab_paragraph, "imgVRange", spy):
            para.wrapOn(self.canv, 400, 800)
        self.assertIn("middle", [va for _h, va in seen])
        self.assertTrue(all(h > 30 for h, _va in seen))

    def test_a_box_wider_than_the_frame_is_laid_out_to_fit(self) -> None:
        (para,) = _paragraphs(
            "<p><span style='display:inline-block; width: 2000pt'>wide</span></p>"
        )
        (box,) = _boxes(para)
        self.assertGreater(box.width, 300)
        para.wrapOn(self.canv, 300, 800)
        self.assertLessEqual(box.width, 300)

    def test_a_percentage_width_resolves_against_the_line(self) -> None:
        (para,) = _paragraphs(
            "<p><span style='display:inline-block; width: 50%'>half</span></p>"
        )
        (box,) = _boxes(para)
        para.wrapOn(self.canv, 300, 800)
        self.assertAlmostEqual(150, box.width)

    def test_the_line_is_as_tall_as_the_box(self) -> None:
        (short,) = _paragraphs("<p>a</p>")
        (tall,) = _paragraphs(
            f"<p>a <span style='{BOX}; height: 50pt; vertical-align: baseline'>X</span></p>"
        )
        short.wrapOn(self.canv, 400, 800)
        tall.wrapOn(self.canv, 400, 800)
        self.assertGreater(tall.height, short.height + 40)


class InlineBlockRenderTest(TestCase):
    @staticmethod
    def _render(html: str):
        out = io.BytesIO()
        result = pisa.CreatePDF(html, dest=out)
        assert not result.err
        return PdfReader(io.BytesIO(out.getvalue())).pages[0]

    def test_the_pdf_has_no_nested_text_object(self) -> None:
        # The guard for the one hazard of drawing inside _putFragLine: a BT
        # inside a BT is not a PDF. PDFTextObject buffers, so it never is.
        page = self._render(
            f"<p>a <span style='{BOX}'>X</span> b <span style='{BOX}'>"
            "<span style='display:flex'><span>1</span><span>2</span></span></span> c</p>"
        )
        content = page.get_contents().get_data().decode("latin-1")
        depth = 0
        for token in re.findall(r"\b(BT|ET)\b", content):
            depth += 1 if token == "BT" else -1
            self.assertLessEqual(depth, 1)
        self.assertEqual(0, depth)

    def test_the_text_inside_and_around_the_box_is_all_there(self) -> None:
        page = self._render(f"<p>ALPHA <span style='{BOX}'>BETA</span> GAMMA</p>")
        text = page.extract_text()
        for word in ("ALPHA", "BETA", "GAMMA"):
            self.assertIn(word, text)

    def test_the_box_text_is_written_between_its_neighbours(self) -> None:
        # The paragraph's text object used to be written whole at the end of
        # the paragraph, after everything drawn inside the line, so a box's
        # text came first in the stream and text extraction read it first.
        page = self._render(f"<p>ALPHA <span style='{BOX}'>BETA</span> GAMMA</p>")
        content = page.get_contents().get_data().decode("latin-1")
        shown = [t for t in re.findall(r"\((.*?)\)\s*Tj", content) if t.strip()]
        order = [next(w for w in ("ALPHA", "BETA", "GAMMA") if w in t) for t in shown]
        self.assertEqual(["ALPHA", "BETA", "GAMMA"], order)

    def test_form_controls_share_the_line(self) -> None:
        page = self._render(
            "<p>Name: <input type='text' name='n'/> Pick: <select name='s'>"
            "<option value='a' selected='selected'>A</option></select> end</p>"
        )
        runs = []

        def visitor(text, cm, tm, _font, _size) -> None:
            if text.strip():
                runs.append((text.strip(), round(cm[5] + tm[5], 1)))

        page.extract_text(visitor_text=visitor)
        # The line is several runs, one on each side of a control, and they
        # all sit on the same baseline.
        self.assertEqual(1, len({y for _text, y in runs}))
        joined = " ".join(text for text, _y in runs)
        self.assertTrue(joined.startswith("Name:"))
        self.assertTrue(joined.endswith("end"))
