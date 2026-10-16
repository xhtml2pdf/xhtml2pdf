"""
-pdf-frame-align: bottom puts a block at the foot of the frame it lands in.

A signature block or a closing note sits at the bottom of the last page
whatever the length of the content before it, and moves to the next page,
to its bottom, when it does not fit where it falls.
"""

from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa

#: A5 with 1cm margins: the frame's bottom edge, in points from the bottom.
FRAME_BOTTOM = 28.35


def pages(paragraphs: int, after: str = "", head: str = "") -> list[dict[str, float]]:
    """Per page, the baseline of each run of text, by its text."""
    html = (
        "<html><head><style>@page { size: a5; margin: 1cm }"
        " body { font-size: 10pt; line-height: 14pt } p { margin: 0 }"
        " .closing { -pdf-frame-align: bottom }</style></head><body>"
        + head
        + "".join(f"<p>Paragraph {n}</p>" for n in range(paragraphs))
        + "<div class='closing'><p>Signature</p><p>Name</p></div>"
        + after
        + "</body></html>"
    )
    output = BytesIO()
    result = pisa.CreatePDF(html, dest=output)
    assert not result.err
    found = []
    for page in PdfReader(BytesIO(output.getvalue())).pages:
        runs: dict[str, float] = {}

        def visit(text, cm, tm, _font, _size, runs=runs) -> None:
            if text.strip():
                runs[text.strip()] = tm[5] * cm[3] + cm[5]

        page.extract_text(visitor_text=visit)
        found.append(runs)
    return found


class FrameAlignBottomTest(TestCase):
    def test_the_block_sits_at_the_bottom_of_the_page(self) -> None:
        (page,) = pages(3)
        self.assertLess(page["Name"] - FRAME_BOTTOM, 14)
        self.assertAlmostEqual(14, page["Signature"] - page["Name"], places=1)
        self.assertGreater(page["Paragraph 2"] - page["Signature"], 300)

    def test_it_moves_to_the_bottom_of_the_next_page_when_it_does_not_fit(self) -> None:
        first, second = pages(40)
        self.assertNotIn("Signature", first)
        self.assertLess(second["Name"] - FRAME_BOTTOM, 14)

    def test_what_follows_it_starts_on_the_next_page(self) -> None:
        first, second = pages(3, after="<p>After</p>")
        self.assertIn("Signature", first)
        self.assertIn("After", second)

    def test_a_second_layout_pass_adds_no_page(self) -> None:
        found = pages(3, head="<p>Page <pdf:pagenumber/> of <pdf:pagecount/></p>")
        self.assertEqual(1, len(found))
        self.assertIn("Signature", found[0])
