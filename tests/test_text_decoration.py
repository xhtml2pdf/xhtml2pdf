"""text-decoration: where underline, line-through and overline are drawn."""

from __future__ import annotations

import io
import re
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.reportlab_paragraph import OVERLINE_RISE

LINE = re.compile(r"([\d.-]+) ([\d.-]+) m ([\d.-]+) ([\d.-]+) l S")
BASELINE = re.compile(r"1 0 0 1 [\d.-]+ ([\d.-]+) Tm")
STROKE = re.compile(r"([\d.]+) ([\d.]+) ([\d.]+) RG")


def page_stream(html: str) -> str:
    out = io.BytesIO()
    result = pisa.CreatePDF(html, dest=out)
    assert not result.err
    page = PdfReader(io.BytesIO(out.getvalue())).pages[0]
    return page.get_contents().get_data().decode("latin-1")


def first(pattern: re.Pattern[str], stream: str) -> re.Match[str]:
    match = pattern.search(stream)
    assert match is not None, pattern.pattern
    return match


def lines(stream: str) -> list[float]:
    """The height of each horizontal line drawn, in stream order."""
    return [float(m.group(2)) for m in LINE.finditer(stream)]


class TextDecorationTest(TestCase):
    FONT_SIZE = 10.0

    def decorated(self, decoration: str) -> tuple[list[float], float]:
        stream = page_stream(
            f'<p style="font-size: {self.FONT_SIZE}pt; text-decoration: {decoration}">'
            "Decorated text</p>"
        )
        baseline = float(first(BASELINE, stream).group(1))
        return lines(stream), baseline

    def test_each_decoration_has_its_own_height(self) -> None:
        expected = {
            "underline": -1.5 * self.FONT_SIZE * 0.125,
            "line-through": 2 * self.FONT_SIZE * 0.125,
            "overline": OVERLINE_RISE * self.FONT_SIZE,
        }
        for decoration, offset in expected.items():
            with self.subTest(decoration=decoration):
                (height,), baseline = self.decorated(decoration)
                self.assertAlmostEqual(baseline + offset, height, places=2)

    def test_the_three_together(self) -> None:
        drawn, baseline = self.decorated("underline line-through overline")

        self.assertEqual(3, len(drawn))
        below, middle, above = sorted(drawn)
        self.assertLess(below, baseline)
        self.assertLess(baseline, middle)
        self.assertLess(middle, above)

    def test_none_takes_an_inherited_overline_off(self) -> None:
        stream = page_stream(
            '<p style="text-decoration: overline">'
            '<span style="text-decoration: none">plain</span></p>'
        )

        self.assertEqual([], lines(stream))

    def test_an_overline_follows_its_span(self) -> None:
        stream = page_stream(
            "<p>plain <span style='text-decoration: overline; color: #ff0000;"
            " font-size: 20pt'>big</span> plain</p>"
        )

        (height,) = lines(stream)
        before = stream[: first(LINE, stream).start()]
        self.assertEqual(("1", "0", "0"), STROKE.findall(before)[-1])
        baseline = float(first(BASELINE, stream).group(1))
        self.assertAlmostEqual(baseline + OVERLINE_RISE * 20, height, places=2)
