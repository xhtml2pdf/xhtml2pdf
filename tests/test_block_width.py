"""
The CSS width of a <div>, a <p> or any other block.

It is the width of the block's content box, a length or a share of the
block that contains it. An auto margin takes what the box leaves of the
line, so margin: 0 auto centres the block.
"""

from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf import pisa
from xhtml2pdf.builders.block import BlockBox
from xhtml2pdf.document import pisaStory

AVAIL = 500.0
TEXT = " ".join(f"word{n}" for n in range(60))


def box(html: str) -> BlockBox:
    """The block box the HTML makes, laid out AVAIL points wide."""
    context = pisaStory(html)
    assert context.err == 0
    (found,) = [f for f in context.story if isinstance(f, BlockBox)]
    found.wrapOn(Canvas(BytesIO()), AVAIL, 10000)
    return found


class BlockWidthTest(TestCase):
    def test_a_percentage_of_the_containing_block(self) -> None:
        found = box(f"<div style='width: 50%'>{TEXT}</div>")
        self.assertAlmostEqual(250, found._inner)
        self.assertAlmostEqual(0, found._left)

    def test_a_length(self) -> None:
        found = box(f"<p style='width: 200pt'>{TEXT}</p>")
        self.assertAlmostEqual(200, found._inner)

    def test_the_width_is_the_content_box(self) -> None:
        found = box(
            f"<div style='width: 200pt; padding: 10pt; border: 2pt solid'>{TEXT}</div>"
        )
        self.assertAlmostEqual(200, found._inner)
        self.assertAlmostEqual(AVAIL - 224, found._right)

    def test_auto_margins_centre_it(self) -> None:
        found = box(f"<div style='width: 300pt; margin: 0 auto'>{TEXT}</div>")
        self.assertAlmostEqual(100, found._left)
        self.assertAlmostEqual(100, found._right)

    def test_an_auto_left_margin_puts_it_on_the_right(self) -> None:
        found = box(f"<div style='width: 300pt; margin-left: auto'>{TEXT}</div>")
        self.assertAlmostEqual(200, found._left)

    def test_a_percentage_is_of_the_block_not_of_what_its_margin_leaves(self) -> None:
        found = box(f"<div style='width: 50%; margin-left: 20pt'>{TEXT}</div>")
        self.assertAlmostEqual(20, found._left)
        self.assertAlmostEqual(250, found._inner)

    def test_a_width_wider_than_the_line_is_held_to_it(self) -> None:
        found = box(f"<div style='width: 900pt'>{TEXT}</div>")
        self.assertAlmostEqual(AVAIL, found._inner)

    def test_the_text_wraps_at_the_width(self) -> None:
        def lines(style: str) -> int:
            output = BytesIO()
            result = pisa.CreatePDF(
                f"<html><body><div style='{style}'>{TEXT}</div></body></html>",
                dest=output,
            )
            self.assertEqual(0, result.err)
            heights: set[float] = set()

            def visit(text, cm, tm, _font, _size) -> None:
                if text.strip():
                    heights.add(round(tm[5] * cm[3] + cm[5], 1))

            PdfReader(BytesIO(output.getvalue())).pages[0].extract_text(
                visitor_text=visit
            )
            return len(heights)

        self.assertGreater(lines("width: 40%"), 2 * lines(""))
