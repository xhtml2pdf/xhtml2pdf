"""Where a paragraph's text sits in its lines: CSS half-leading."""

from __future__ import annotations

import io
from itertools import pairwise
from unittest import TestCase

from pypdf import PdfReader
from reportlab.pdfbase.pdfmetrics import getAscentDescent

from xhtml2pdf import pisa
from xhtml2pdf.document import pisaStory
from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph

FONT_SIZE = 10.0
#: Top of the default frame: a 1cm page margin.
FRAME_TOP = 28.3465


def first_paragraph(html: str) -> PmlParagraph:
    story = pisaStory(html).story
    para = next(f for f in story if isinstance(f, PmlParagraph))
    para.wrap(400, 800)
    return para


def baselines(html: str) -> list[float]:
    """Distance from the top of the page to each baseline, in stream order."""
    out = io.BytesIO()
    result = pisa.CreatePDF(html, dest=out)
    assert not result.err
    page = PdfReader(io.BytesIO(out.getvalue())).pages[0]
    height = float(page.mediabox.height)
    found: list[float] = []

    def visit(text, cm, tm, _font, _size) -> None:
        if text.strip():
            found.append(round(height - (tm[5] * cm[3] + cm[5]), 3))

    page.extract_text(visitor_text=visit)
    return found


class HalfLeadingTest(TestCase):
    @staticmethod
    def expected_first_baseline(leading: float) -> float:
        ascent, descent = getAscentDescent("Helvetica", FONT_SIZE)
        return ascent + (leading - (ascent - descent)) / 2

    def test_the_leading_is_shared_above_and_below(self) -> None:
        for line_height, leading in (("150%", 15.0), ("100%", 10.0), ("200%", 20.0)):
            with self.subTest(line_height=line_height):
                para = first_paragraph(
                    f'<p style="font-size: {FONT_SIZE}pt; line-height: {line_height}">'
                    "one line</p>"
                )
                self.assertAlmostEqual(
                    self.expected_first_baseline(leading),
                    para._firstBaseline(),
                    places=3,
                )

    def test_plain_lines_keep_their_height(self) -> None:
        para = first_paragraph(
            f'<p style="font-size: {FONT_SIZE}pt; line-height: 150%">'
            + "word " * 300
            + "</p>"
        )
        lines = len(para.blPara.lines)
        self.assertGreater(lines, 1)
        self.assertAlmostEqual(lines * 15.0, para.height, places=3)

    def test_lines_step_by_the_leading(self) -> None:
        found = baselines(
            f'<p style="font-size: {FONT_SIZE}pt; line-height: 150%">'
            + "word " * 300
            + "</p>"
        )
        steps = {round(b - a, 3) for a, b in pairwise(found)}
        self.assertEqual({15.0}, steps)

    def test_a_bigger_font_still_grows_its_line(self) -> None:
        plain = first_paragraph(f'<p style="font-size: {FONT_SIZE}pt">x</p>')
        mixed = first_paragraph(
            f'<p style="font-size: {FONT_SIZE}pt">x <span style="font-size: 30pt">'
            "BIG</span> x</p>"
        )
        self.assertGreater(mixed.height, plain.height)
        big_ascent = getAscentDescent("Helvetica", 30)[0]
        self.assertGreaterEqual(mixed._firstBaseline(), big_ascent)

    def test_the_drawn_text_is_where_the_paragraph_says(self) -> None:
        html = (
            '<div style="font-size: 10pt; line-height: 150%">'
            "<p style='margin: 0'>first</p></div>"
        )
        para = first_paragraph(html)
        top = baselines(html)[0]
        self.assertAlmostEqual(FRAME_TOP + para._firstBaseline(), top, places=2)
