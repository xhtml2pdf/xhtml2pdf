"""
Choosing a font, and saying so when the choice was not the one asked for.

Most of what gets reported as a font bug is not a wrong glyph but a silent
substitution: a family nobody registered, a @font-face whose file never
arrived, a name that also means one of the base-14 faces. The document comes
out in Helvetica and nothing in the log connects the two. These tests pin
both halves -- which face is actually used, and that the substitution is
announced.
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa

SAMPLES = Path(__file__).parent / "samples"
FONT = SAMPLES / "font" / "Noto_Sans" / "NotoSans-Regular.ttf"

#: Characters no base-14 face has, which is what the reports were about.
CZECH = "ěščřž"


def render(html: str) -> bytes:
    output = BytesIO()
    pisa.CreatePDF(html, dest=output)
    return output.getvalue()


def base_fonts(pdf: bytes) -> set[str]:
    """The /BaseFont of every font the document actually uses."""
    reader = PdfReader(BytesIO(pdf))
    return {
        str(font.get_object().get("/BaseFont", "?"))
        for page in reader.pages
        for font in (page.get("/Resources", {}).get("/Font", {}) or {}).values()
    }


def document(family: str, *, src: str | Path | None = None, text: str = CZECH) -> str:
    face = f'@font-face {{ font-family: {family}; src: url("{src}"); }}' if src else ""
    return (
        f'<html><head><meta charset="utf-8"><style>{face}'
        f"* {{ font-family: {family}; }}</style></head>"
        f"<body>{text}</body></html>"
    )


class EmbeddedFontBeatsABuiltInAliasTest(TestCase):
    """
    A family the document embeds is the one it gets, alias or not.

    `arial`, `verdana`, `georgia`, `sans`, `serif` and `mono` are all names
    the library maps to a base-14 face. Naming one in @font-face is a thing
    people do -- it is what the Czech report did -- and the embedded file has
    to win, because it is the more specific thing the author said.
    """

    def assert_embedded(self, family: str) -> None:
        fonts = base_fonts(render(document(family, src=FONT)))
        self.assertTrue(
            any("NotoSans" in name for name in fonts),
            f"{family}: expected the embedded face, got {sorted(fonts)}",
        )

    def test_arial(self) -> None:
        self.assert_embedded("Arial")

    def test_verdana(self) -> None:
        self.assert_embedded("Verdana")

    def test_the_generic_families(self) -> None:
        for family in ("sans", "serif", "mono"):
            with self.subTest(family=family):
                self.assert_embedded(family)

    def test_the_text_survives(self) -> None:
        pdf = render(document("Arial", src=FONT))
        self.assertIn(CZECH, PdfReader(BytesIO(pdf)).pages[0].extract_text())


class SubstitutionIsAnnouncedTest(TestCase):
    """Each way of ending up with a font nobody asked for says so."""

    def warnings(self, html: str) -> list[str]:
        with self.assertLogs("xhtml2pdf", level=logging.WARNING) as caught:
            render(html)
        return caught.output

    def test_an_unknown_family_is_reported(self) -> None:
        messages = self.warnings(document("Calibri", text="x"))

        self.assertTrue(
            any("calibri" in m.lower() and "helvetica" in m.lower() for m in messages),
            messages,
        )

    def test_an_unknown_family_is_reported_once(self) -> None:
        paragraphs = "".join(
            f'<p style="font-family: Calibri">{n}</p>' for n in range(5)
        )
        messages = [
            m
            for m in self.warnings(f"<html><body>{paragraphs}</body></html>")
            if "calibri" in m.lower()
        ]

        self.assertEqual(1, len(messages), messages)

    def test_a_font_face_that_cannot_be_read_is_reported(self) -> None:
        messages = self.warnings(document("Missing", src="/no/such/font.ttf", text="x"))

        self.assertTrue(
            any("@font-face" in m and "font.ttf" in m for m in messages), messages
        )

    def test_a_known_family_says_nothing(self) -> None:
        with self.assertNoLogs("xhtml2pdf", level=logging.WARNING):
            render(document("Helvetica", text="x"))

    def test_an_embedded_family_says_nothing(self) -> None:
        with self.assertNoLogs("xhtml2pdf", level=logging.WARNING):
            render(document("Embedded", src=FONT))
