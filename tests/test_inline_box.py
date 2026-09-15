"""
display: inline with a box of its own: padding, borders, a background.

The paragraph carries the element's edges as two marker frags; the fork of
Paragraph turns the stretch between them into a box on every line it
touches. Checked here: that the parser builds the markers, that the line
breaker counts their padding, and that the box is painted where the text is.
"""

import io
import re
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from pypdf import PdfReader
from reportlab.lib.abag import ABag
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf import pisa, reportlab_paragraph
from xhtml2pdf.builders.flex import BoxStyle, inline_box_markers
from xhtml2pdf.document import pisaStory
from xhtml2pdf.reportlab_paragraph import Paragraph, _getFragWords
from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph

BOX = "padding: 3pt 6pt; border: 1pt solid #cc0000; background-color: #ffeeee"


def _paragraph(html: str) -> PmlParagraph:
    context = pisaStory(html)
    assert context.err == 0
    return next(f for f in context.story if isinstance(f, PmlParagraph))


def _markers(paragraph) -> list:
    return [
        f.cbDefn
        for f in paragraph.frags
        if getattr(getattr(f, "cbDefn", None), "kind", None) == "inlineBox"
    ]


class InlineBoxParsingTest(TestCase):
    def test_a_span_with_a_box_gets_an_open_and_a_close_marker(self) -> None:
        para = _paragraph(f"<p>a <span style='{BOX}'>b</span> c</p>")
        edges = [m.edge for m in _markers(para)]
        self.assertEqual(["open", "close"], edges)

    def test_a_plain_span_gets_none(self) -> None:
        para = _paragraph(
            "<p>a <span style='color: red; font-weight: bold'>b</span> c</p>"
        )
        self.assertEqual([], _markers(para))

    def test_a_background_colour_alone_is_not_a_box(self) -> None:
        # That keeps going through the per-frag background, as before.
        para = _paragraph("<p>a <span style='background-color: #eee'>b</span> c</p>")
        self.assertEqual([], _markers(para))
        inner = next(f for f in para.frags if f.text == "b")
        self.assertIsNotNone(inner.backColor)

    def test_a_box_with_nothing_to_draw_is_not_a_box(self) -> None:
        # A reset such as `* { padding: 0 }` declares the properties without
        # giving the element anything to paint; its text keeps painting its
        # own background, as before.
        para = _paragraph(
            "<p>a <span style='padding: 0; border: 0; margin: 0 0; "
            "background-color: #eee'>b</span> c</p>"
        )
        self.assertEqual([], _markers(para))
        inner = next(f for f in para.frags if f.text == "b")
        self.assertIsNotNone(inner.backColor)
        self.assertEqual(0, inner.paddingLeft)

    def test_a_block_property_that_is_not_the_box_stays_off_the_frag(self) -> None:
        # text-indent and the vertical margins travel with padding in the
        # block groups; an inline element's frag must not pick them up.
        para = _paragraph(
            "<p>a <span style='padding: 2pt; text-indent: 30pt; margin-top: 9pt'>b"
            "</span> c</p>"
        )
        self.assertEqual(2, len(_markers(para)))
        outer = next(f for f in para.frags if f.text == "a ")
        inner = next(f for f in para.frags if f.text == "b")
        for name in ("firstLineIndent", "spaceBefore"):
            self.assertEqual(getattr(outer, name, 0), getattr(inner, name, 0), name)

    def test_the_markers_carry_the_box_and_the_text_does_not(self) -> None:
        para = _paragraph(f"<p>a <span style='{BOX}'>b</span> c</p>")
        opener, closer = _markers(para)
        self.assertIs(opener.style, closer.style)
        self.assertEqual(3.0, opener.style.paddingTop)
        self.assertEqual("solid", opener.style.borderLeftStyle)
        self.assertIsNotNone(opener.style.backColor)
        # padding-left 6 + border-left 1; padding-right 6 + border-right 1.
        self.assertEqual(7.0, opener.advance)
        self.assertEqual(7.0, closer.advance)
        inner = next(f for f in para.frags if f.text == "b")
        self.assertEqual(0, inner.paddingLeft)
        self.assertIsNone(inner.backColor)

    def test_side_margins_advance_the_line_outside_the_box(self) -> None:
        para = _paragraph(
            "<p>a <span style='padding: 0 2pt; margin-left: 5pt; margin-right: 4pt'>b</span> c</p>"
        )
        opener, closer = _markers(para)
        self.assertEqual((7.0, 5.0), (opener.advance, opener.inset))
        self.assertEqual((6.0, 4.0), (closer.advance, closer.inset))

    def test_nested_boxes_nest(self) -> None:
        para = _paragraph(
            f"<p><span style='{BOX}'>a <span style='padding: 1pt'>b</span> c</span></p>"
        )
        self.assertEqual(
            ["open", "open", "close", "close"], [m.edge for m in _markers(para)]
        )


class _LineFixture(TestCase):
    """The fork of Paragraph, fed markers by hand."""

    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())
        self.style = ParagraphStyle("t", fontName="Helvetica", fontSize=10, leading=12)
        # The fork reads these off every style; xhtml2pdf's frags carry them.
        self.style.letterSpacing = "normal"
        self.style.wordSpacing = "normal"

    def _frags(self, before: str, inside: str, after: str, box: BoxStyle):
        para = Paragraph(before + inside + after, self.style)
        base = para.frags[0]
        opener, closer = inline_box_markers(base, box)
        frags = []
        for text in (before,):
            f = base.clone()
            f.text = text
            frags.append(f)
        frags.append(opener)
        f = base.clone()
        f.text = inside
        frags.extend((f, closer))
        f = base.clone()
        f.text = after
        frags.append(f)
        para.frags = frags
        return para

    def _spans(self, para, width):
        spans = []
        original = reportlab_paragraph._do_post_text

        def spy(tx):
            spans.extend(tx.XtraState.inlineBoxSpans)
            original(tx)

        with patch.object(reportlab_paragraph, "_do_post_text", spy):
            para.wrapOn(self.canv, width, 800)
            para.drawOn(self.canv, 0, 0)
        return spans


class InlineBoxLineTest(_LineFixture):
    def test_getFragWords_counts_the_padding_in_the_word(self) -> None:
        box = BoxStyle(paddingLeft=6, paddingRight=6)
        para = self._frags("aa ", "bb", " cc", box)
        words = _getFragWords(para.frags)
        # "bb" with its two edges: one word, 12 wider than the text.
        # The fork's splitter hands the words over as bytes.
        boxed = next(w for w in words if any(t in {"bb", b"bb"} for _f, t in w[1:]))
        from reportlab.pdfbase.pdfmetrics import stringWidth

        self.assertAlmostEqual(stringWidth("bb", "Helvetica", 10) + 12, boxed[0])
        self.assertEqual(3, len(words))

    def test_a_box_on_one_line_is_one_span_with_both_edges(self) -> None:
        box = BoxStyle(paddingLeft=6, paddingRight=6)
        para = self._frags("aa ", "bb", " cc", box)
        (span,) = self._spans(para, 400)
        x1, x2, style, first, last = span
        self.assertIs(box, style)
        self.assertTrue(first)
        self.assertTrue(last)
        self.assertGreater(x1, 10)
        self.assertGreater(x2 - x1, 12)

    def test_a_box_across_two_lines_is_two_spans_cut_at_the_break(self) -> None:
        box = BoxStyle(paddingLeft=2, paddingRight=2)
        inside = " ".join(["word"] * 30)
        para = self._frags("start ", inside, " end", box)
        spans = self._spans(para, 120)
        self.assertGreater(len(spans), 1)
        self.assertEqual((True, False), (spans[0][3], spans[0][4]))
        self.assertEqual((False, True), (spans[-1][3], spans[-1][4]))
        for x1, x2, _s, first, _last in spans[1:]:
            self.assertFalse(first)
            self.assertLess(x1, x2)
            self.assertLessEqual(x1, 2 + 1e-6)  # continues from the line's start

    def test_the_cut_edges_are_not_stroked(self) -> None:
        box = BoxStyle(
            paddingLeft=2,
            paddingRight=2,
            borderLeftStyle="solid",
            borderLeftWidth=1,
            borderRightStyle="solid",
            borderRightWidth=1,
        )
        inside = " ".join(["word"] * 30)
        para = self._frags("start ", inside, " end", box)
        calls = []
        with patch.object(
            reportlab_paragraph,
            "drawBoxBorders",
            lambda *_a, **k: calls.append(k["sides"]),
        ):
            para.wrapOn(self.canv, 120, 800)
            para.drawOn(self.canv, 0, 0)
        self.assertIn("Left", calls[0])
        self.assertNotIn("Right", calls[0])
        self.assertNotIn("Left", calls[-1])
        self.assertIn("Right", calls[-1])
        for sides in calls[1:-1]:
            self.assertNotIn("Left", sides)
            self.assertNotIn("Right", sides)

    def test_the_box_wraps_the_lines_ascent_and_descent(self) -> None:
        box = BoxStyle(paddingTop=3, paddingBottom=4, backColor="#eee")
        para = self._frags("aa ", "bb", " cc", box)
        rects = []
        with patch.object(
            reportlab_paragraph,
            "drawBoxBackground",
            lambda _c, x, y, w, h, _s: rects.append((x, y, w, h)),
        ):
            para.wrapOn(self.canv, 400, 800)
            para.drawOn(self.canv, 0, 0)
        (rect,) = rects
        _x, y, _w, h = rect
        # ascent + descent of a 10pt Helvetica line (0.718 + 0.207 of the
        # size, 9.25) plus 7 of padding.
        self.assertGreater(h, 9 + 7)
        self.assertLess(h, 10 + 7)
        self.assertLess(y, 0)  # the descent and bottom padding go below the baseline


def _marker_kinds(frags) -> list:
    return [
        (f.cbDefn.edge, getattr(f.cbDefn, "continued", False))
        for f in frags
        if getattr(getattr(f, "cbDefn", None), "kind", None) == "inlineBox"
    ]


class InlineBoxSplitTest(_LineFixture):
    """A box open where the paragraph is cut between pages."""

    WORDS = " ".join(["word"] * 30)

    def _cut(self, para, height=37):
        # leading 12: 37 of room holds three lines.
        para.wrapOn(self.canv, 120, 800)
        head, tail = para.split(120, height)
        return head, tail

    def test_a_box_open_at_the_cut_is_reopened_in_the_tail(self) -> None:
        box = BoxStyle(paddingLeft=2, paddingRight=2)
        head, tail = self._cut(self._frags("start ", self.WORDS, " end", box))
        first = tail.frags[0].cbDefn
        self.assertEqual(
            ("inlineBox", "open", True), (first.kind, first.edge, first.continued)
        )
        self.assertEqual((0.0, 0.0), (first.advance, first.inset))
        self.assertIs(box, first.style)
        head_spans = self._spans(head, 120)
        tail_spans = self._spans(tail, 120)
        self.assertEqual((True, False), (head_spans[0][3], head_spans[0][4]))
        self.assertEqual((False, False), (head_spans[-1][3], head_spans[-1][4]))
        self.assertEqual((False, False), (tail_spans[0][3], tail_spans[0][4]))
        self.assertEqual((False, True), (tail_spans[-1][3], tail_spans[-1][4]))

    def test_a_box_closed_before_the_cut_is_not_reopened(self) -> None:
        box = BoxStyle(paddingLeft=2, paddingRight=2)
        _head, tail = self._cut(self._frags("a ", "b", " " + self.WORDS, box))
        self.assertEqual([], _marker_kinds(tail.frags))

    def test_nested_boxes_are_reopened_outermost_first(self) -> None:
        outer = BoxStyle(paddingLeft=1, paddingRight=1)
        inner = BoxStyle(paddingLeft=2, paddingRight=2)
        para = Paragraph("x", self.style)
        base = para.frags[0]
        open_outer, close_outer = inline_box_markers(base, outer)
        open_inner, close_inner = inline_box_markers(base, inner)
        text = base.clone()
        text.text = self.WORDS
        para.frags = [open_outer, open_inner, text, close_inner, close_outer]
        _head, tail = self._cut(para)
        self.assertEqual(
            [("open", True), ("open", True), ("close", False), ("close", False)],
            _marker_kinds(tail.frags),
        )
        self.assertIs(outer, tail.frags[0].cbDefn.style)
        self.assertIs(inner, tail.frags[1].cbDefn.style)

    def test_the_continued_marker_survives_a_second_split(self) -> None:
        box = BoxStyle(paddingLeft=2, paddingRight=2)
        _head, tail = self._cut(self._frags("start ", self.WORDS, " end", box))
        tail.wrapOn(self.canv, 120, 800)
        _middle, last = tail.split(120, 25)
        self.assertEqual([("open", True), ("close", False)], _marker_kinds(last.frags))

    def test_the_reopened_box_has_no_left_edge_at_the_top_of_the_tail(self) -> None:
        box = BoxStyle(
            paddingLeft=2,
            paddingRight=2,
            borderLeftStyle="solid",
            borderLeftWidth=1,
            borderRightStyle="solid",
            borderRightWidth=1,
        )
        _head, tail = self._cut(self._frags("start ", self.WORDS, " end", box))
        calls = []
        with patch.object(
            reportlab_paragraph,
            "drawBoxBorders",
            lambda *_a, **k: calls.append(k["sides"]),
        ):
            tail.wrapOn(self.canv, 120, 800)
            tail.drawOn(self.canv, 0, 0)
        self.assertNotIn("Left", calls[0])
        self.assertIn("Right", calls[-1])

    def test_the_first_page_keeps_its_open_marker(self) -> None:
        # The tail's marker is a new one; the head still carries its own,
        # with the edge and the padding it opened with.
        box = BoxStyle(paddingLeft=2, paddingRight=2)
        head, tail = self._cut(self._frags("start ", self.WORDS, " end", box))
        (opener,) = [f for f in head.frags if _marker_kinds([f])]
        self.assertEqual(2.0, opener.cbDefn.advance)
        self.assertIsNot(opener.cbDefn, tail.frags[0].cbDefn)

    def test_a_single_frag_paragraph_splits_as_before(self) -> None:
        para = Paragraph(self.WORDS, self.style)
        para.wrapOn(self.canv, 120, 800)
        _head, tail = para.split(120, 37)
        self.assertEqual([], _marker_kinds(tail.frags))
        # The simple path: one frag carrying its words, no text.
        self.assertEqual(0, para.blPara.kind)
        tail.wrapOn(self.canv, 120, 800)
        self.assertGreater(len(tail.blPara.lines), 0)


class InlineBoxRenderTest(TestCase):
    @staticmethod
    def _render(html: str):
        out = io.BytesIO()
        result = pisa.CreatePDF(html, dest=out)
        assert not result.err
        return PdfReader(io.BytesIO(out.getvalue())).pages[0]

    def test_padding_widens_the_line_by_the_padding(self) -> None:
        # Through the parser: the markers reach the line breaker with their
        # advance, so the line is 38 wider with 20pt of padding a side than
        # with 1pt.
        narrow = _paragraph("<p>a <span style='padding: 0 1pt'>b</span> c</p>")
        wide = _paragraph("<p>a <span style='padding: 0 20pt'>b</span> c</p>")

        def line_width(para):
            return sum(word[0] for word in _getFragWords(para.frags))

        self.assertAlmostEqual(38, line_width(wide) - line_width(narrow))

    def test_the_text_is_all_there_and_in_order(self) -> None:
        page = self._render(f"<p>ALPHA <span style='{BOX}'>BETA</span> GAMMA</p>")
        text = page.extract_text()
        self.assertLess(text.index("ALPHA"), text.index("BETA"))
        self.assertLess(text.index("BETA"), text.index("GAMMA"))

    def test_no_nested_text_object(self) -> None:
        page = self._render(f"<p>a <span style='{BOX}'>b</span> c</p>")
        content = page.get_contents().get_data().decode("latin-1")
        depth = 0
        for token in re.findall(r"\b(BT|ET)\b", content):
            depth += 1 if token == "BT" else -1
            self.assertLessEqual(depth, 1)
        self.assertEqual(0, depth)

    def test_a_box_alone_in_a_paragraph_renders(self) -> None:
        page = self._render(f"<p><span style='{BOX}'>only</span></p>")
        self.assertIn("only", page.extract_text())


class MarkerHelperTest(TestCase):
    def test_markers_keep_their_cbDefn_and_carry_no_text(self) -> None:
        style = BoxStyle(
            paddingLeft=1, paddingRight=2, borderRightStyle="solid", borderRightWidth=3
        )
        frag = ABag(text="x", fontName="Helvetica", fontSize=10)
        frag.clone = lambda: ABag(**frag.__dict__)
        opener, closer = inline_box_markers(frag, style, (4, 5))
        self.assertEqual("", opener.text)
        self.assertEqual(
            ("open", 5.0, 4),
            (opener.cbDefn.edge, opener.cbDefn.advance, opener.cbDefn.inset),
        )
        self.assertEqual(
            ("close", 10.0, 5),
            (closer.cbDefn.edge, closer.cbDefn.advance, closer.cbDefn.inset),
        )
