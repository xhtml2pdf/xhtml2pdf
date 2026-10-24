"""Output meant for a print shop: CMYK colour, bleed and crop marks, PDF/X."""

from __future__ import annotations

import io
import re
from pathlib import Path
from unittest import TestCase

import pypdf
from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm

from xhtml2pdf.document import pisaDocument
from xhtml2pdf.util import getColor
from xhtml2pdf.w3c.css import CSSTerminalFunction

IMAGE = (Path(__file__).parent / "samples" / "img" / "denker.png").as_posix()


def render(html: str, **kwargs) -> pypdf.PdfReader:
    out = io.BytesIO()
    result = pisaDocument(html, dest=out, **kwargs)
    assert not result.err, result.log
    return pypdf.PdfReader(io.BytesIO(out.getvalue()))


def numbers(pattern: str | re.Pattern, text: str) -> list[float]:
    """The groups of the first match of `pattern` in `text`, as numbers."""
    match = re.search(pattern, text)
    assert match is not None, text
    return [float(group) for group in match.groups()]


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


def boxes(page: pypdf.PageObject) -> dict[str, list[float]]:
    found = {}
    for name in ("/MediaBox", "/BleedBox", "/TrimBox"):
        if name in page:
            found[name[1:]] = [round(float(v), 2) for v in page[name]]
    return found


A6 = (297.64, 419.53)
SLUG = 12 * mm

#: The first translation in a content stream, as reportlab or pypdf writes it.
TRANSLATION = re.compile(r"1 0(?:\.0)? 0(?:\.0)? 1 (-?[\d.]+) (-?[\d.]+) cm")


class BleedAndMarksTestCase(TestCase):
    def test_no_bleed_leaves_the_page_alone(self) -> None:
        reader = render("<style>@page { size: a6 }</style><p>x</p>")
        self.assertEqual({"MediaBox": [0, 0, *A6]}, boxes(reader.pages[0]))

    def test_bleed_grows_the_page_around_the_trim(self) -> None:
        reader = render("<style>@page { size: a6; bleed: 10pt }</style><p>x</p>")
        width, height = A6
        self.assertEqual(
            {
                "MediaBox": [0, 0, width + 20, height + 20],
                "BleedBox": [0, 0, width + 20, height + 20],
                "TrimBox": [10, 10, width + 10, height + 10],
            },
            boxes(reader.pages[0]),
        )
        # Moved, not scaled.
        self.assertEqual(
            [10, 10], numbers(TRANSLATION, content(reader).split("ET", 1)[1])
        )

    def assertBox(self, expected, found) -> None:
        for want, got in zip(expected, found, strict=True):
            self.assertAlmostEqual(want, got, delta=0.02)

    def test_marks_sit_in_a_slug_outside_an_auto_bleed(self) -> None:
        reader = render("<style>@page { size: a6; marks: crop cross }</style><p>x</p>")
        width, height = A6
        offset = 6 + SLUG
        found = boxes(reader.pages[0])
        self.assertBox(
            [offset, offset, offset + width, offset + height], found["TrimBox"]
        )
        self.assertBox(
            [offset - 6, offset - 6, offset + width + 6, offset + height + 6],
            found["BleedBox"],
        )
        self.assertBox(
            [0, 0, width + 2 * offset, height + 2 * offset], found["MediaBox"]
        )
        # Registration colour, so every plate shows the marks.
        self.assertIn("1 1 1 1 K", content(reader))

    def test_marks_none_and_unknown_values(self) -> None:
        reader = render("<style>@page { size: a6; marks: none }</style><p>x</p>")
        self.assertNotIn("TrimBox", boxes(reader.pages[0]))
        with self.assertLogs("xhtml2pdf.builders.printmarks", level="WARNING"):
            render("<style>@page { size: a6; marks: crop stars }</style><p>x</p>")

    def test_each_template_has_its_own_bleed(self) -> None:
        reader = render(
            "<style>@page { size: a6 }"
            " @page cover { size: a5; bleed: 3mm }</style>"
            "<pdf:nexttemplate name='cover'/><pdf:nextpage/><p>cover</p>"
            "<pdf:nexttemplate name='body'/><pdf:nextpage/><p>body</p>"
        )
        # The first page is the body's; nexttemplate applies from the next.
        first, cover, body = reader.pages
        self.assertEqual({"MediaBox": [0, 0, *A6]}, boxes(first))
        self.assertAlmostEqual(3 * mm, boxes(cover)["TrimBox"][0], delta=0.01)
        self.assertEqual({"MediaBox": [0, 0, *A6]}, boxes(body))

    def test_body_background_reaches_into_the_bleed(self) -> None:
        reader = render(
            "<style>@page { size: a6; bleed: 10pt }"
            " body { background-color: cmyk(0, 0.1, 0.2, 0) }</style><p>x</p>"
        )
        width, height = A6
        rect = numbers(
            r"n (-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+) re f", content(reader)
        )
        self.assertBox([-10, -10, width + 20, height + 20], rect)

    def test_page_background_image_reaches_into_the_bleed(self) -> None:
        reader = render(
            "<style>@page { size: a6; bleed: 10pt; marks: crop;"
            f" background-image: url({IMAGE}) }}</style><p>x</p>"
        )
        # The background, as wide as the trim and its bleed, starts at the
        # edge of the bleed, which is the slug from the corner of the page.
        self.assertBox([SLUG, SLUG], numbers(TRANSLATION, content(reader)))

    def test_link_destinations_move_with_the_content(self) -> None:
        html = (
            "<style>@page {{ size: a6; margin: 0; {} }}</style>"
            "<a href='#t'>go</a><pdf:nextpage/><p><a name='t'>target</a></p>"
        )
        plain = render(html.format(""))
        marked = render(html.format("bleed: 10pt"))

        def destination(reader):
            link = reader.pages[0]["/Annots"][0].get_object()
            return [float(v) for v in link["/Dest"][2:4]]

        left, top = destination(plain)
        self.assertEqual([left + 10, top + 10], destination(marked))
