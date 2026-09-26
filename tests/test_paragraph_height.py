"""
A paragraph takes the height it is drawn with.

With a TTF taller than 1.2em -- Noto Sans is 1.362em, ascent 1.069 and
descent 0.293 -- and a line-height over 1.2, Paragraph.wrap and split
measured each line as max(ascent - descent, leading) while _putFragLine drew
it as max(5/6 leading, ascent) + max(1/6 leading, descent), about a point
more. The paragraph was drawn taller than it said it was: the next block ran
over its last lines, and a paragraph split at a page overran the margin.
"""

import logging
from io import BytesIO
from itertools import pairwise
from pathlib import Path
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa

FONT = Path(__file__).parent / "samples" / "font" / "Noto_Sans" / "NotoSans-Regular.ttf"
#: Noto Sans's descent, in em.
DESCENT = 0.293
FONT_SIZE = 9.4


def baselines(html: str) -> list[list[tuple[float, str]]]:
    """Per page, the baseline and the start of each run of text, top down."""
    output = BytesIO()
    pisa.CreatePDF(html, dest=output)
    pages = []
    for page in PdfReader(BytesIO(output.getvalue())).pages:
        found: list[tuple[float, str]] = []

        def visit(text, cm, tm, _font, _size, found=found) -> None:
            if text.strip():
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                found.append((round(y, 2), text.strip()))

        page.extract_text(visitor_text=visit)
        pages.append(found)
    return pages


def document(body: str, line_height: str = "1.35") -> str:
    return (
        f'<html><head><style>@font-face {{ font-family: T; src: url("{FONT}"); }}'
        "@page { size: a4; margin: 2cm }"
        f"body {{ font-family: T; font-size: {FONT_SIZE}pt;"
        f" line-height: {line_height} }}"
        "p { margin: 0 }</style></head><body>" + body + "</body></html>"
    )


TEXT = " ".join(f"Line{i} filler words to wrap." for i in range(30))


class ParagraphHeightTest(TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_the_next_block_starts_where_the_paragraph_ends(self) -> None:
        # With no margins the step from the paragraph's last line to the next
        # block's first is the step between any two of its lines. It used to
        # be a point short for each line of the paragraph.
        for line_height in ("1.2", "1.35", "1.5"):
            with self.subTest(line_height=line_height):
                (page,) = baselines(document(f"<p>{TEXT}</p><p>NEXT</p>", line_height))
                self.assertEqual("NEXT", page[-1][1])
                steps = [a[0] - b[0] for a, b in pairwise(page)]
                for step in steps[1:]:
                    self.assertAlmostEqual(steps[0], step, delta=0.05)

    def test_a_split_paragraph_stays_inside_the_page_margin(self) -> None:
        # The part split() kept on the first page is drawn to its measured
        # height, so its last line's descent ends above the 2cm margin.
        pages = baselines(document(f"<p>{TEXT * 12}</p>"))
        self.assertGreater(len(pages), 1)
        bottom_margin = 2 / 2.54 * 72
        last_baseline = pages[0][-1][0]
        self.assertGreaterEqual(
            last_baseline - DESCENT * FONT_SIZE, bottom_margin - 0.01
        )
