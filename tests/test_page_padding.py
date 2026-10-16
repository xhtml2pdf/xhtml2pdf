"""
The padding of <html> and <body> is room around the page content, once.

The side padding indents everything inside, tables in the page's flow
included, and the top padding is room above the first block. No paragraph
inside draws it again.
"""

from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa


def runs(body: str, body_style: str) -> dict[str, tuple[float, float]]:
    """The (x, distance down from the top) of each run of text, by its text."""
    html = (
        "<html><head><style>@page { size: a4; margin: 1cm }"
        f" body {{ font-size: 11pt; line-height: 15pt; {body_style} }}"
        " p { margin: 0 }</style></head><body>" + body + "</body></html>"
    )
    output = BytesIO()
    result = pisa.CreatePDF(html, dest=output)
    assert not result.err
    page = PdfReader(BytesIO(output.getvalue())).pages[0]
    height = float(page.mediabox.height)
    found: dict[str, tuple[float, float]] = {}

    def visit(text, cm, tm, _font, _size) -> None:
        if text.strip():
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            found[text.strip()] = (round(x, 1), round(height - y, 1))

    page.extract_text(visitor_text=visit)
    return found


class PagePaddingTest(TestCase):
    def test_paragraphs_are_one_line_apart(self) -> None:
        found = runs("<p>one</p><p>two</p><p>three</p>", "padding: 20pt")
        self.assertEqual(15, round(found["two"][1] - found["one"][1], 1))
        self.assertEqual(15, round(found["three"][1] - found["two"][1], 1))

    def test_the_padding_moves_the_content_in_and_down(self) -> None:
        plain = runs("<p>one</p>", "")
        padded = runs("<p>one</p>", "padding: 10pt 0 0 30pt")
        self.assertAlmostEqual(plain["one"][0] + 30, padded["one"][0], places=1)
        self.assertAlmostEqual(plain["one"][1] + 10, padded["one"][1], places=1)

    def test_a_table_is_indented_by_it_and_a_nested_one_is_not_again(self) -> None:
        found = runs(
            "<table><tr><td>outer</td><td>"
            "<table><tr><td>inner</td></tr></table></td></tr></table>",
            "padding: 0 0 0 30pt",
        )
        plain = runs(
            "<table><tr><td>outer</td><td>"
            "<table><tr><td>inner</td></tr></table></td></tr></table>",
            "padding: 0",
        )
        self.assertAlmostEqual(plain["outer"][0] + 30, found["outer"][0], places=1)
        # The inner table sits in its cell, which the padding has moved and
        # narrowed: it starts no further left than the cell does.
        self.assertGreater(found["inner"][0], found["outer"][0])

    def test_the_bottom_padding_adds_no_page(self) -> None:
        html = (
            "<html><head><style>@page { size: a4; margin: 1cm }"
            " body { font-size: 11pt; line-height: 15pt; padding-bottom: 300pt }"
            " p { margin: 0 }</style></head><body>"
            + "".join(f"<p>line {n}</p>" for n in range(50))
            + "</body></html>"
        )
        output = BytesIO()
        pisa.CreatePDF(html, dest=output)
        self.assertEqual(1, len(PdfReader(BytesIO(output.getvalue())).pages))
