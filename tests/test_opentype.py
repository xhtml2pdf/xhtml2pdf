"""OpenType (CFF), WOFF and WOFF2 fonts in @font-face, through fontTools."""

from __future__ import annotations

import base64
import io
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import TestCase, mock, skipUnless

import pypdf

from xhtml2pdf.document import pisaDocument

try:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.ttLib import TTFont
except ImportError:  # pragma: no cover
    FontBuilder = None

try:
    import brotli
except ImportError:  # pragma: no cover
    brotli = None

TTF = Path(__file__).parent / "samples" / "font" / "Noto_Sans" / "NotoSans-Regular.ttf"


def cff_font(family: str = "Square") -> bytes:
    """An OpenType font with PostScript outlines and one glyph, "A", a square."""
    builder = FontBuilder(1000, isTTF=False)
    builder.setupGlyphOrder([".notdef", "A"])
    builder.setupCharacterMap({ord("A"): "A"})
    charstrings = {}
    for name in (".notdef", "A"):
        pen = T2CharStringPen(600, None)
        if name == "A":
            pen.moveTo((100, 0))
            pen.lineTo((500, 0))
            pen.curveTo((550, 200), (550, 500), (500, 700))
            pen.lineTo((100, 700))
            pen.closePath()
        charstrings[name] = pen.getCharString()
    builder.setupCFF(family, {"FullName": family}, charstrings, {})
    builder.setupHorizontalMetrics({".notdef": (600, 0), "A": (600, 100)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": family, "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    out = io.BytesIO()
    builder.save(out)
    return out.getvalue()


def wrapped(data: bytes, flavor: str) -> bytes:
    font = TTFont(io.BytesIO(data))
    font.flavor = flavor
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def data_uri(data: bytes, mimetype: str) -> str:
    return f"data:{mimetype};base64,{base64.b64encode(data).decode()}"


def render(src: str, path: str = "") -> pypdf.PdfReader:
    html = (
        f"<style>@font-face {{ font-family: Test; src: {src} }}"
        " p { font-family: Test }</style><p>AAA</p>"
    )
    out = io.BytesIO()
    pisaDocument(html, dest=out, path=path)
    return pypdf.PdfReader(io.BytesIO(out.getvalue()))


def embedded_fonts(reader: pypdf.PdfReader) -> dict[str, bool]:
    fonts = {}
    for font in reader.pages[0]["/Resources"]["/Font"].values():
        font = font.get_object()
        descriptor = font.get("/FontDescriptor")
        fonts[str(font["/BaseFont"])] = descriptor is not None and (
            "/FontFile2" in descriptor.get_object()
        )
    return fonts


def text_font(reader: pypdf.PdfReader) -> str:
    """The base font of the face that sets the paragraph."""
    names = {
        str(name): str(font.get_object()["/BaseFont"])
        for name, font in reader.pages[0]["/Resources"]["/Font"].items()
    }
    stream = reader.pages[0].get_contents().get_data().decode("latin-1")
    used = [name for name in names if f"{name} " in stream and name != "/F1"]
    return names[used[-1]]


@skipUnless(FontBuilder is not None, "needs fontTools (the fonts extra)")
class OpenTypeFontTestCase(TestCase):
    def assertEmbedded(self, reader: pypdf.PdfReader, family: str) -> None:
        font = text_font(reader)
        self.assertIn(family, font)
        self.assertTrue(embedded_fonts(reader)[font], font)

    def test_cff_font_from_a_file(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        font = Path(directory.name) / "square.otf"
        font.write_bytes(cff_font())
        document = Path(directory.name) / "document.html"
        self.assertEmbedded(render("url(square.otf)", str(document)), "Square")

    def test_cff_font_from_a_data_uri(self) -> None:
        reader = render(f"url({data_uri(cff_font(), 'font/otf')})")
        self.assertEmbedded(reader, "Square")

    def test_woff_with_cff_outlines(self) -> None:
        reader = render(f"url({data_uri(wrapped(cff_font(), 'woff'), 'font/woff')})")
        self.assertEmbedded(reader, "Square")

    @skipUnless(brotli is not None, "WOFF2 needs brotli")
    def test_woff2_with_truetype_outlines(self) -> None:
        woff2 = wrapped(TTF.read_bytes(), "woff2")
        reader = render(f"url({data_uri(woff2, 'font/woff2')}) format('woff2')")
        self.assertEmbedded(reader, "NotoSans")

    def test_the_glyph_keeps_its_shape(self) -> None:
        """The converted outline stays within a font unit of the original."""
        from xhtml2pdf.opentype import to_truetype

        converted = TTFont(io.BytesIO(to_truetype(cff_font())))
        self.assertIn("glyf", converted)
        self.assertNotIn("CFF ", converted)
        glyph = converted["glyf"]["A"]
        glyph.recalcBounds(converted["glyf"])
        self.assertEqual(
            (100, 0, 538, 700), (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
        )

    def test_truetype_in_an_otf_file_is_not_converted(self) -> None:
        from xhtml2pdf.opentype import needs_conversion, to_truetype

        data = TTF.read_bytes()
        self.assertFalse(needs_conversion(data))
        self.assertIs(data, to_truetype(data))

    def test_the_first_source_that_loads_wins(self) -> None:
        """A later url() is a fallback, not a second embed of the family."""
        src = (
            f"url({data_uri(cff_font(), 'font/otf')}) format('opentype'),"
            f" url({TTF.as_posix()})"
        )
        with self.assertNoLogs("xhtml2pdf.context", level="WARNING"):
            reader = render(src)
        self.assertEmbedded(reader, "Square")

    def test_an_unreadable_font_falls_back_to_the_next_source(self) -> None:
        src = (
            f"url({data_uri(b'wOF2 not a font', 'font/woff2')}), url({TTF.as_posix()})"
        )
        with self.assertLogs("xhtml2pdf.context", level="WARNING") as logs:
            reader = render(src)
        self.assertTrue(any("Cannot embed the font" in line for line in logs.output))
        self.assertEmbedded(reader, "NotoSans")

    def test_a_damaged_cff_table_falls_back_to_the_next_source(self) -> None:
        """The CFF table is read only once a glyph is drawn from it."""
        data = bytearray(cff_font("Damaged"))
        table = TTFont(io.BytesIO(bytes(data))).reader.tables["CFF "]
        data[table.offset + 4 : table.offset + table.length] = b"\xff" * (
            table.length - 4
        )
        src = f"url({data_uri(bytes(data), 'font/otf')}), url({TTF.as_posix()})"
        with self.assertLogs("xhtml2pdf.context", level="WARNING") as logs:
            reader = render(src)
        self.assertTrue(any("Cannot embed the font" in line for line in logs.output))
        self.assertEmbedded(reader, "NotoSans")

    def test_a_font_converts_to_the_same_bytes_every_time(self) -> None:
        """The same source font is registered once, under one digest."""
        from xhtml2pdf import opentype

        data = cff_font("Stable")
        converted = []
        for now in (3_000_000_000, 3_000_000_001):
            opentype._cache.clear()
            with mock.patch(
                "fontTools.ttLib.tables._h_e_a_d.timestampNow", return_value=now
            ):
                converted.append(opentype.to_truetype(data))
        self.assertEqual(converted[0], converted[1])


class WithoutFontToolsTest(TestCase):
    def test_a_cff_font_asks_for_the_extra(self) -> None:
        if FontBuilder is None:
            self.skipTest("needs fontTools to build the test font")
        script = textwrap.dedent(
            f"""
            import io, logging, sys
            sys.modules["fontTools"] = None
            logging.basicConfig(level=logging.WARNING, stream=sys.stdout)
            from xhtml2pdf.document import pisaDocument
            pisaDocument({render_html(data_uri(cff_font(), 'font/otf'))!r}, dest=io.BytesIO())
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertIn("xhtml2pdf[fonts]", result.stdout, result.stderr)


def render_html(uri: str) -> str:
    return (
        f"<style>@font-face {{ font-family: Test; src: url({uri}) }}"
        " p { font-family: Test }</style><p>AAA</p>"
    )
