"""
-pdf-frame-pages: the pages a static frame is painted on.

`last` paints it on the last page only, a signature block or a closing
footer; `not-last` on every page but that one; `all`, the default, on
every page.
"""

from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa


def page_texts(paragraphs: int, pages: str = "last") -> list[str]:
    html = (
        "<html><head><style>@page { size: a5; margin: 1cm 1cm 3cm 1cm;"
        f" @frame closing {{ -pdf-frame-content: closing; -pdf-frame-pages: {pages};"
        " left: 1cm; width: 10cm; bottom: 0.5cm; height: 2cm; }"
        " @frame number { -pdf-frame-content: number;"
        " left: 11cm; width: 3cm; bottom: 0.5cm; height: 1cm; } }"
        "</style></head><body>"
        "<div id='closing'>CLOSING</div><div id='number'>page <pdf:pagenumber/></div>"
        + "".join(f"<p>Paragraph {n}.</p>" for n in range(paragraphs))
        + "</body></html>"
    )
    output = BytesIO()
    result = pisa.CreatePDF(html, dest=output)
    assert not result.err
    return [page.extract_text() for page in PdfReader(BytesIO(output.getvalue())).pages]


class FramePagesTest(TestCase):
    def test_last_paints_the_frame_on_the_last_page_only(self) -> None:
        texts = page_texts(60)
        self.assertGreater(len(texts), 2)
        self.assertEqual(
            [False] * (len(texts) - 1) + [True], ["CLOSING" in t for t in texts]
        )

    def test_not_last_paints_it_on_every_page_but_the_last(self) -> None:
        texts = page_texts(60, "not-last")
        self.assertEqual(
            [True] * (len(texts) - 1) + [False], ["CLOSING" in t for t in texts]
        )

    def test_a_single_page_is_the_last(self) -> None:
        (text,) = page_texts(2)
        self.assertIn("CLOSING", text)

    def test_the_other_static_frames_are_on_every_page(self) -> None:
        texts = page_texts(60)
        for number, text in enumerate(texts, 1):
            self.assertIn(f"page {number}", text)

    def test_an_unknown_value_paints_it_on_every_page(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING") as logged:
            texts = page_texts(60, "sometimes")
        self.assertTrue(all("CLOSING" in t for t in texts))
        self.assertTrue(any("-pdf-frame-pages" in line for line in logged.output))
