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
from xhtml2pdf.util import NO_RADIUS
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

    def test_the_box_is_rounded_and_its_content_is_not(self) -> None:
        (para,) = _paragraphs(
            f"<p>a <span style='{BOX}; border-radius: 6pt'>X</span></p>"
        )
        (box,) = _boxes(para)
        self.assertEqual((6, 6), box.flowable.style.borderTopLeftRadius.resolve(40, 40))
        inner = box.flowable.content[0]
        self.assertIs(NO_RADIUS, inner.style.borderTopLeftRadius)

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


class InlineBlockBaselineTest(TestCase):
    """vertical-align: baseline is the box's last line, not its bottom edge."""

    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    def test_a_baseline_box_sits_on_its_last_lines_baseline(self) -> None:
        (para,) = _paragraphs(
            "<p>x <span style='display:inline-block; padding-bottom: 5pt'>text"
            "</span> y</p>"
        )
        (box,) = _boxes(para)
        self.assertEqual("baseline", box.valign)
        para.wrapOn(self.canv, 400, 800)
        self.assertEqual("baseline", box.declared_valign)
        # Bottom padding plus the last line's descent, below the baseline.
        self.assertLess(box.valign, -5)
        self.assertGreater(box.valign, -5 - 10)
        self.assertAlmostEqual(-box.flowable.last_baseline, box.valign)

    def test_a_box_of_two_lines_hangs_by_its_last(self) -> None:
        one = _paragraphs("<p>x <span style='display:inline-block'>a</span> y</p>")[0]
        two = _paragraphs(
            "<p>x <span style='display:inline-block'>a<br/>b</span> y</p>"
        )[0]
        for para in (one, two):
            para.wrapOn(self.canv, 400, 800)
        # The same distance from the bottom, whatever is above the last line.
        self.assertAlmostEqual(_boxes(one)[0].valign, _boxes(two)[0].valign)
        self.assertGreater(_boxes(two)[0].height, _boxes(one)[0].height)

    def test_a_box_without_a_baseline_keeps_its_bottom_on_the_baseline(self) -> None:
        # A table has no baseline of its own (only paragraphs do), so the
        # box hangs from its bottom margin edge, as before.
        (para,) = _paragraphs(
            "<p>x <span style='display:inline-block'><table><tr><td>t</td></tr>"
            "</table></span> y</p>"
        )
        para.wrapOn(self.canv, 400, 800)
        (box,) = _boxes(para)
        self.assertEqual("baseline", box.valign)

    def test_vertical_align_bottom_is_left_alone(self) -> None:
        (para,) = _paragraphs(
            "<p>x <span style='display:inline-block; vertical-align: bottom'>text"
            "</span> y</p>"
        )
        para.wrapOn(self.canv, 400, 800)
        self.assertEqual("bottom", _boxes(para)[0].valign)

    def test_the_box_is_measured_again_on_a_second_wrap_without_drift(self) -> None:
        (para,) = _paragraphs(
            "<p>x <span style='display:inline-block; padding-bottom: 5pt'>text"
            "</span> y</p>"
        )
        para.wrapOn(self.canv, 400, 800)
        first = _boxes(para)[0].valign
        para.wrapOn(self.canv, 400, 800)
        self.assertEqual(first, _boxes(para)[0].valign)

    def test_the_lines_descent_grows_to_hold_the_box(self) -> None:
        plain = _paragraphs("<p>x y</p>")[0]
        boxed = _paragraphs(
            "<p>x <span style='display:inline-block; padding-bottom: 12pt'>text"
            "</span> y</p>"
        )[0]
        for para in (plain, boxed):
            para.wrapOn(self.canv, 400, 800)
        self.assertGreater(boxed.height, plain.height + 10)


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

        def spy(h, va, font_size, *line):
            seen.append((h, va))
            return original(h, va, font_size, *line)

        with patch.object(reportlab_paragraph, "imgVRange", spy):
            para.wrapOn(self.canv, 400, 800)
        self.assertIn("middle", [va for _h, va in seen])
        self.assertTrue(all(h > 30 for h, _va in seen))

    def test_top_and_bottom_align_to_the_line_box_not_the_font(self) -> None:
        # CSS 2.1 10.8.1: text-top and text-bottom align with the parent's
        # content area, top and bottom with the whole line box, which is
        # taller as soon as something else on the line is. The line box is
        # only known once the line is assembled, so the four coincide while
        # measuring and part company when the line is drawn.
        from xhtml2pdf.reportlab_paragraph import imgVRange

        measuring = {
            va: imgVRange(8, va, 10)
            for va in ("top", "text-top", "bottom", "text-bottom")
        }
        self.assertEqual(measuring["top"], measuring["text-top"])
        self.assertEqual(measuring["bottom"], measuring["text-bottom"])

        # A line whose tallest fragment reaches 30pt above and 7pt below.
        drawing = {
            va: imgVRange(8, va, 10, 30, -7)
            for va in ("top", "text-top", "bottom", "text-bottom")
        }
        # top puts the box's own top at the line's top; text-top leaves it at
        # the font's ascent, well below that.
        self.assertEqual(30, drawing["top"][1])
        self.assertEqual(10, drawing["text-top"][1])
        # bottom puts the box's bottom at the line's bottom; text-bottom
        # leaves it at the font's descent.
        self.assertEqual(-7, drawing["bottom"][0])
        self.assertAlmostEqual(-2, drawing["text-bottom"][0])
        # baseline and middle do not look at the line box at all.
        self.assertEqual(
            imgVRange(8, "baseline", 10), imgVRange(8, "baseline", 10, 30, -7)
        )

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
