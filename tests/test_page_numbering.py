"""
Page numbers: <pdf:resetpagenumber> and the numbers written in the flow.

<pdf:resetpagenumber value="n"/> numbers the page it falls on n and the
pages after it on from there, in the static frames, in <pdf:pagenumber>
in the flow and in the table of contents. <pdf:pagecount> stays the
number of pages in the document.
"""

from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa

FILLER = "".join(f"<p>Paragraph {n}</p>" for n in range(40))


def page_texts(body: str) -> list[str]:
    html = (
        "<html><head><style>@page { size: a6; margin: 1cm 1cm 2cm 1cm;"
        " @frame footer { -pdf-frame-content: footer;"
        " left: 1cm; width: 8cm; bottom: 0.5cm; height: 1cm; } }"
        " h1 { -pdf-outline: true }</style></head><body>"
        "<div id='footer'>footer <pdf:pagenumber/> of <pdf:pagecount/></div>"
        + body
        + "</body></html>"
    )
    output = BytesIO()
    result = pisa.CreatePDF(html, dest=output)
    assert not result.err
    return [page.extract_text() for page in PdfReader(BytesIO(output.getvalue())).pages]


class ResetPageNumberTest(TestCase):
    BODY = (
        "<h1>Cover</h1><pdf:toc/>"
        "<pdf:nextpage/><pdf:resetpagenumber value='1'/>"
        "<h1>Chapter one</h1><p>flow <pdf:pagenumber/></p>"
        + FILLER
        + "<h1>Chapter two</h1>"
    )

    def test_the_static_frames_count_from_the_reset(self) -> None:
        texts = page_texts(self.BODY)
        footers = [line for t in texts for line in t.splitlines() if "footer" in line]
        total = len(texts)
        self.assertEqual(
            [f"footer 1 of {total}"]
            + [f"footer {n} of {total}" for n in range(1, total)],
            footers,
        )

    def test_a_page_number_in_the_flow_counts_from_the_reset(self) -> None:
        texts = page_texts(self.BODY)
        self.assertIn("flow 1", texts[1])

    def test_the_table_of_contents_counts_from_the_reset(self) -> None:
        texts = page_texts(self.BODY)
        # The physical page n + 1 is numbered n after the reset on page 2.
        chapter_two = next(
            n for n, t in enumerate(texts) if n > 0 and "Chapter two" in t
        )
        toc = texts[0].split("Chapter one", 1)[1]
        self.assertIn(str(chapter_two), toc)
        self.assertNotIn(str(chapter_two + 1), toc)

    def test_a_reset_to_another_value(self) -> None:
        texts = page_texts(
            "<p>a</p><pdf:nextpage/><pdf:resetpagenumber value='10'/><p>b</p>"
        )
        self.assertIn("footer 10 of 2", texts[1])


class PageCountInTheFlowTest(TestCase):
    def test_the_first_page_has_the_whole_count(self) -> None:
        texts = page_texts("<p>count <pdf:pagecount/></p>" + FILLER)
        self.assertGreater(len(texts), 1)
        self.assertIn(f"count {len(texts)}", texts[0])
