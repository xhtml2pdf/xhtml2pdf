"""Output meant for a print shop: CMYK colour, bleed and crop marks, PDF/X."""

from __future__ import annotations

import io
import re
from pathlib import Path
from unittest import TestCase
from xml.dom import minidom

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

    def test_cmyk_in_the_background_shorthand(self) -> None:
        reader = render(
            "<div style='background: cmyk(1 0 0 0)'>div</div>"
            "<table><tr><td style='background: device-cmyk(0 .5 0 0)'>td</td>"
            "</tr></table>"
        )
        stream = content(reader)
        self.assertIn("1 0 0 0 k", stream)
        self.assertIn("0 .5 0 0 k", stream)


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

    def test_a_positioned_page_background_is_placed_from_the_trim(self) -> None:
        html = (
            "<style>@page {{ size: a6; {} background-image: url({});"
            " background-object-position: 20pt 30pt; background-width: 50pt;"
            " background-height: 40pt }}</style><p>x</p>"
        )
        image = re.compile(r"50 0 0 40 (-?[\d.]+) (-?[\d.]+) cm")
        plain = numbers(image, content(render(html.format("", IMAGE))))
        bled = numbers(image, content(render(html.format("bleed: 10pt;", IMAGE))))
        self.assertEqual([20, 30], plain)
        # The backdrop it is drawn on starts at the edge of the bleed.
        self.assertEqual([30, 40], bled)

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


FONT = Path(__file__).parent / "samples" / "font" / "Noto_Sans" / "NotoSans-Regular.ttf"


def fake_profile(space: bytes = b"CMYK", device_class: bytes = b"prtr") -> bytes:
    """An ICC header with an empty tag table: enough for the output intent."""
    header = bytearray(132)
    header[0:4] = (132).to_bytes(4, "big")
    header[12:16] = device_class
    header[16:20] = space
    header[20:24] = b"Lab "
    header[36:40] = b"acsp"
    return bytes(header)


PDFX = {"profile": fake_profile(), "condition": "FOGRA39", "info": "Coated FOGRA39"}


def undefined_fonts(stream, resources, reader: pypdf.PdfReader) -> list[str]:
    """The fonts a content stream, or a form it draws, selects without having."""
    resources = resources.get_object()
    fonts = resources.get("/Font")
    known = set(fonts.get_object()) if fonts is not None else set()
    missing = [
        str(operands[0])
        for operands, operator in pypdf.generic.ContentStream(stream, reader).operations
        if operator == b"Tf" and str(operands[0]) not in known
    ]
    xobjects = resources.get("/XObject")
    for xobj in xobjects.get_object().values() if xobjects is not None else []:
        xobj = xobj.get_object()
        if xobj.get("/Subtype") == "/Form":
            missing += undefined_fonts(xobj, xobj.get("/Resources", resources), reader)
    return missing


def embedded(body: str, css: str = "") -> str:
    """A document whose text is all set in an embedded TrueType face."""
    return (
        f"<style>@font-face {{ font-family: Noto; src: url({FONT.as_posix()}) }}"
        f" body {{ font-family: Noto }} {css}</style>{body}"
    )


class PDFXTestCase(TestCase):
    @staticmethod
    def render_pdfx(html: str) -> tuple[bytes, pypdf.PdfReader]:
        out = io.BytesIO()
        pisaDocument(html, dest=out, pdfx=PDFX)
        data = out.getvalue()
        return data, pypdf.PdfReader(io.BytesIO(data))

    def test_output_intent_metadata_and_version(self) -> None:
        data, reader = self.render_pdfx(
            embedded("<title>Brochure</title><p>text</p>", "@page { size: a6 }")
        )
        self.assertTrue(data.startswith(b"%PDF-1.6"))
        root = reader.trailer["/Root"]
        (intent,) = root["/OutputIntents"]
        intent = intent.get_object()
        self.assertEqual("/GTS_PDFX", intent["/S"])
        self.assertEqual("FOGRA39", intent["/OutputConditionIdentifier"])
        self.assertEqual("Coated FOGRA39", intent["/Info"])
        profile = intent["/DestOutputProfile"].get_object()
        self.assertEqual(4, profile["/N"])
        self.assertEqual(fake_profile(), profile.get_data())

        self.assertEqual("PDF/X-4", reader.metadata["/GTS_PDFXVersion"])
        xmp = root["/Metadata"].get_object().get_data().decode("utf-8")
        self.assertIn("<pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>", xmp)
        self.assertIn(">Brochure</rdf:li>", xmp)
        self.assertEqual("Brochure", reader.xmp_metadata.dc_title["x-default"])
        self.assertIn("<xmpMM:RenditionClass>default</xmpMM:RenditionClass>", xmp)

    def test_xmp_dates_repeat_the_info_dates(self) -> None:
        _, reader = self.render_pdfx(embedded("<p>text</p>"))
        created = reader.metadata["/CreationDate"]  # D:YYYYMMDDHHmmSS+hh'mm'
        xmp = reader.trailer["/Root"]["/Metadata"].get_object().get_data().decode()
        iso = (
            f"{created[2:6]}-{created[6:8]}-{created[8:10]}"
            f"T{created[10:12]}:{created[12:14]}:{created[14:16]}"
        )
        self.assertIn(f"<xmp:CreateDate>{iso}", xmp)

    def test_every_page_has_a_trim_box_and_managed_rgb(self) -> None:
        _, reader = self.render_pdfx(
            embedded("<p style='color: #c00'>red</p><pdf:nextpage/><p>two</p>")
        )
        for page in reader.pages:
            self.assertIn("/TrimBox", page)
            spaces = page["/Resources"]["/ColorSpace"]
            space, profile = spaces["/DefaultRGB"]
            self.assertEqual("/ICCBased", space)
            self.assertEqual(3, profile.get_object()["/N"])

    def test_neutral_rgb_is_drawn_in_gray(self) -> None:
        _, reader = self.render_pdfx(embedded("<p style='color: #000'>black</p>"))
        stream = content(reader)
        self.assertNotIn("0 0 0 rg", stream)
        self.assertRegex(stream, r"\b0(?:\.0)? g\b")

    def test_fonts_that_draw_nothing_are_taken_out(self) -> None:
        """Reportlab selects Helvetica at the top of every page."""
        _, reader = self.render_pdfx(embedded("<p>text</p>"))
        fonts = reader.pages[0]["/Resources"]["/Font"]
        names = {str(font.get_object()["/BaseFont"]) for font in fonts.values()}
        self.assertFalse({name for name in names if "Helvetica" in name})
        self.assertTrue(any("NotoSans" in name for name in names))

    def assert_fonts_defined(self, reader: pypdf.PdfReader) -> None:
        self.assertGreater(len(reader.pages), 1)
        for number, page in enumerate(reader.pages, 1):
            self.assertEqual(
                [],
                undefined_fonts(page.get_contents(), page["/Resources"], reader),
                f"page {number}",
            )

    def test_every_page_keeps_the_fonts_it_selects(self) -> None:
        """Every Tf on every page names a font of the /Font dictionary they share."""
        _, reader = self.render_pdfx(
            embedded("<p>one</p><pdf:nextpage/><p>two</p><pdf:nextpage/><p>3</p>")
        )
        self.assert_fonts_defined(reader)

    def test_every_page_keeps_the_fonts_it_selects_under_a_background(self) -> None:
        """
        A merged page background, which brings a renamed Helvetica of its own,
        leaves every Tf naming a font of the page.
        """
        with self.assertLogs("xhtml2pdf.builders.preflight", level="WARNING"):
            _, reader = self.render_pdfx(
                embedded(
                    "<p>one</p><pdf:nextpage/><p>two</p>",
                    f"@page {{ size: a6; background-image: url({IMAGE}) }}",
                )
            )
        self.assert_fonts_defined(reader)

    def test_a_form_written_through_ascii85_is_rewritten(self) -> None:
        """A box under the flow is a form; reportlab encodes it ASCII85 + Flate."""
        _, reader = self.render_pdfx(
            embedded(
                "<p>flowing</p><div style='position: absolute; top: 0;"
                " z-index: -1; color: #000'>under</div>"
            )
        )
        page = reader.pages[0]
        self.assertEqual(
            [], undefined_fonts(page.get_contents(), page["/Resources"], reader)
        )
        (form,) = page["/Resources"]["/XObject"].values()
        stream = form.get_object().get_data().decode("latin-1")
        self.assertNotIn("0 0 0 rg", stream)

    def test_control_characters_in_the_title_leave_the_xmp_well_formed(self) -> None:
        _, reader = self.render_pdfx(
            embedded("<title>A &amp; B &lt;c&gt; \x01\x07é</title><p>text</p>")
        )
        xmp = reader.trailer["/Root"]["/Metadata"].get_object().get_data()
        minidom.parseString(xmp)
        self.assertEqual("A & B <c> é", reader.xmp_metadata.dc_title["x-default"])

    def test_text_in_a_font_that_is_not_embedded_is_an_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Helvetica"):
            pisaDocument("<p>plain</p>", dest=io.BytesIO(), pdfx=PDFX)

    def test_links_are_left_out(self) -> None:
        _, reader = self.render_pdfx(embedded("<a href='https://example.com'>site</a>"))
        self.assertNotIn("/Annots", reader.pages[0])

    def test_bleed_and_marks_are_kept(self) -> None:
        _, reader = self.render_pdfx(
            embedded("<p>text</p>", "@page { size: a6; marks: crop }")
        )
        self.assertIn("/BleedBox", reader.pages[0])
        self.assertAlmostEqual(6 + SLUG, float(reader.pages[0].trimbox[0]), delta=0.01)

    def test_unusable_arguments(self) -> None:
        cases = [
            ({"condition": "FOGRA39"}, "profile"),
            ({"profile": fake_profile(space=b"RGB ")}, "CMYK"),
            ({"profile": fake_profile(device_class=b"mntr")}, "output"),
            ({"profile": b"not a profile"}, "not an ICC profile"),
            ({"profile": fake_profile()}, "condition"),
        ]
        for pdfx, message in cases:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                pisaDocument("<p>x</p>", dest=io.BytesIO(), pdfx=pdfx)

    def test_pdfx_and_encryption_cannot_be_combined(self) -> None:
        with self.assertRaisesRegex(ValueError, "encrypt"):
            pisaDocument("<p>x</p>", dest=io.BytesIO(), pdfx=PDFX, encrypt="secret")

    def test_pdfx_and_signature_cannot_be_combined(self) -> None:
        with self.assertRaisesRegex(ValueError, "signature"):
            pisaDocument(
                "<p>x</p>", dest=io.BytesIO(), pdfx=PDFX, signature={"cert": "x"}
            )

    def test_a_document_without_a_title_is_reported(self) -> None:
        with self.assertLogs("xhtml2pdf.builders.pdfx", level="WARNING") as logs:
            self.render_pdfx(embedded("<p>text</p>"))
        self.assertTrue(any("<title>" in line for line in logs.output))
        with self.assertNoLogs("xhtml2pdf.builders.pdfx", level="WARNING"):
            self.render_pdfx(embedded("<title>Brochure</title><p>text</p>"))


class PrintWarningTestCase(TestCase):
    def test_a_coarse_image_on_a_page_with_bleed_is_reported(self) -> None:
        html = f"<style>@page {{ bleed: 3mm }}</style><img src='{IMAGE}' width='200'>"
        with self.assertLogs("xhtml2pdf.builders.preflight", level="WARNING") as logs:
            render(html)
        self.assertTrue(any("ppi" in line for line in logs.output))

    def test_text_in_base_fonts_on_a_page_with_bleed_is_reported(self) -> None:
        with self.assertLogs("xhtml2pdf.builders.preflight", level="WARNING") as logs:
            render("<style>@page { bleed: 3mm }</style><p>text</p>")
        self.assertTrue(any("Helvetica" in line for line in logs.output))

    def test_nothing_is_reported_without_bleed_or_marks(self) -> None:
        with self.assertNoLogs("xhtml2pdf.builders.preflight", level="WARNING"):
            render(f"<p>text</p><img src='{IMAGE}' width='200'>")
