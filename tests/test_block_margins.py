"""
The vertical margins of a block without padding, a border or a background.

Such a block draws nothing of its own: its top margin goes above the first
thing it holds and its bottom margin below the last, each collapsing with
the margin of that child and of the blocks around it, the larger one
winning (CSS 2.1, 8.3.1).
"""

from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa

#: Every line is this tall, so a gap between two baselines minus it is the
#: margin between their blocks.
LINE = 15.0


def baselines(body: str) -> dict[str, float]:
    """The baseline of each run of text, by its text, down from the top."""
    html = (
        "<html><head><style>body { font-size: 11pt; line-height: 15pt }"
        " p { margin: 0 }</style></head><body>" + body + "</body></html>"
    )
    output = BytesIO()
    result = pisa.CreatePDF(html, dest=output)
    assert not result.err
    found: dict[str, float] = {}

    def visit(text, cm, tm, _font, _size) -> None:
        if text.strip():
            found[text.strip()] = -(tm[4] * cm[1] + tm[5] * cm[3] + cm[5])

    PdfReader(BytesIO(output.getvalue())).pages[0].extract_text(visitor_text=visit)
    return found


class BlockMarginTest(TestCase):
    @staticmethod
    def gap(lines: dict[str, float], above: str, below: str) -> float:
        return round(lines[below] - lines[above] - LINE, 1)

    def test_the_margins_of_a_block_around_a_paragraph_without_margins(self) -> None:
        lines = baselines(
            "<div style='margin-bottom: 1in'><p>first</p></div>"
            "<p>second</p>"
            "<div style='margin-top: 1in'><p>third</p></div>"
        )
        self.assertEqual(72, self.gap(lines, "first", "second"))
        self.assertEqual(72, self.gap(lines, "second", "third"))

    def test_nested_top_margins_collapse_to_the_largest(self) -> None:
        lines = baselines(
            "<p>before</p>"
            "<div style='margin-top: 20pt'><div style='margin-top: 10pt'>"
            "<p style='margin-top: 5pt'>inside</p></div></div>"
        )
        self.assertEqual(20, self.gap(lines, "before", "inside"))

    def test_a_last_child_margin_larger_than_its_block_wins(self) -> None:
        lines = baselines(
            "<div style='margin-bottom: 30pt'><p style='margin-bottom: 40pt'>last</p>"
            "</div><p>after</p>"
        )
        self.assertEqual(40, self.gap(lines, "last", "after"))

    def test_the_text_of_a_block_takes_its_margins_once(self) -> None:
        lines = baselines(
            "<p>start</p>"
            "<div style='margin: 30pt 0 40pt 0'>leading"
            "<p style='margin: 5pt 0'>inner</p>trailing</div>"
            "<p>end</p>"
        )
        self.assertEqual(30, self.gap(lines, "start", "leading"))
        self.assertEqual(5, self.gap(lines, "leading", "inner"))
        self.assertEqual(5, self.gap(lines, "inner", "trailing"))
        self.assertEqual(40, self.gap(lines, "trailing", "end"))

    def test_a_child_does_not_inherit_the_margins_of_its_block(self) -> None:
        lines = baselines(
            "<div style='margin-bottom: 20pt'><div><p>one</p></div>"
            "<div><p>two</p></div></div><p>after</p>"
        )
        self.assertEqual(0, self.gap(lines, "one", "two"))
        self.assertEqual(20, self.gap(lines, "two", "after"))
