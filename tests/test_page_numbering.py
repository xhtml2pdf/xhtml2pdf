"""Page numbers and counts, in the static frames and in the flow."""

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


class PageCountInTheFlowTest(TestCase):
    def test_the_first_page_has_the_whole_count(self) -> None:
        texts = page_texts("<p>count <pdf:pagecount/></p>" + FILLER)
        self.assertGreater(len(texts), 1)
        self.assertIn(f"count {len(texts)}", texts[0])
