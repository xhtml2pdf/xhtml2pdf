"""Output meant for a print shop: CMYK colour, bleed and crop marks, PDF/X."""

from __future__ import annotations

import io
from unittest import TestCase

import pypdf
from reportlab.lib.colors import CMYKColor

from xhtml2pdf.document import pisaDocument
from xhtml2pdf.util import getColor
from xhtml2pdf.w3c.css import CSSTerminalFunction


def render(html: str, **kwargs) -> pypdf.PdfReader:
    out = io.BytesIO()
    result = pisaDocument(html, dest=out, **kwargs)
    assert not result.err, result.log
    return pypdf.PdfReader(io.BytesIO(out.getvalue()))


def content(reader: pypdf.PdfReader, page: int = 0) -> str:
    return reader.pages[page].get_contents().get_data().decode("latin-1")


class CMYKColorTestCase(TestCase):
    def test_device_cmyk_space_separated(self) -> None:
        self.assertEqual(getColor("device-cmyk(0 1 1 0)"), CMYKColor(0, 1, 1, 0))

    def test_cmyk_with_commas_and_percentages(self) -> None:
        self.assertEqual(getColor("cmyk(10%, 0, 0, 100%)"), CMYKColor(0.1, 0, 0, 1))

    def test_alpha_after_a_slash_or_as_a_fifth_argument(self) -> None:
        self.assertEqual(getColor("device-cmyk(0 1 1 0 / 0.5)").alpha, 0.5)
        self.assertEqual(getColor("cmyk(0, 1, 1, 0, 0.25)").alpha, 0.25)

    def test_function_object_from_the_parser(self) -> None:
        """`device-cmyk(0 1 1 0 / 50%)` reaches getColor as this object."""
        function = CSSTerminalFunction(
            "device-cmyk", ["0", "1", "1", "op('0', '/', ('50', '%'))"]
        )
        self.assertEqual(getColor(function), CMYKColor(0, 1, 1, 0, alpha=0.5))

    def test_wrong_number_of_inks_gives_the_default(self) -> None:
        with self.assertLogs("xhtml2pdf.util", level="WARNING"):
            self.assertEqual(getColor("device-cmyk(0 1)", "no"), "no")

    def test_out_of_range_inks_are_clamped(self) -> None:
        self.assertEqual(getColor("cmyk(2, -1, 0, 0)"), CMYKColor(1, 0, 0, 0))

    def test_css_and_attribute_colours_are_drawn_in_device_cmyk(self) -> None:
        reader = render(
            "<p style='color: device-cmyk(0 1 1 0)'>css</p>"
            "<p style='background-color: cmyk(1, 0, 0, 0)'>background</p>"
            "<p><font color='cmyk(0,0,1,0)'>attribute</font></p>"
        )
        stream = content(reader)
        self.assertIn("0 1 1 0 k", stream)
        self.assertIn("1 0 0 0 k", stream)
        self.assertIn("0 0 1 0 k", stream)
