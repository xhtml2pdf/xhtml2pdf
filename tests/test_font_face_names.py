from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf.document import pisaDocument

if TYPE_CHECKING:
    from pypdf.generic import DictionaryObject


class FontFaceNameTests(TestCase):
    def test_font_face_names_retain_distinct_styles(self) -> None:
        font_directory = Path(__file__).parent / "samples" / "font" / "Noto_Sans"
        styles = ("Regular", "Bold", "Italic", "BoldItalic")
        source = (
            "<style>"
            + "".join(
                f"@font-face {{font-family: Noto_{style}; "
                f"src: url('{font_directory / f'NotoSans-{style}.ttf'}');}}"
                for style in styles
            )
            + f"@font-face{{font-family:Noto_Regular_Minified;src:url('{font_directory / 'NotoSans-Regular.ttf'}');}}"
            + "</style><p style='font-family:Noto_Regular_Minified'>Regular minified</p>"
            + "".join(
                f'<p style="font-family:Noto_{style}">{style}</p>' for style in styles
            )
        )
        output = BytesIO()
        pisaDocument(source, dest=output)
        self.assertEqual(
            {"NotoSans", "NotoSans-Bold", "NotoSans-Italic", "NotoSans-BoldItalic"},
            {
                str(cast("DictionaryObject", font.get_object())["/BaseFont"]).split(
                    "+"
                )[-1]
                for page in PdfReader(output).pages
                for font in cast(
                    "DictionaryObject",
                    cast("DictionaryObject", page["/Resources"])["/Font"],
                ).values()
                if "+" in str(cast("DictionaryObject", font.get_object())["/BaseFont"])
            },
        )
