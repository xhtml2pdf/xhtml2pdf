from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from pypdf import PdfReader

from xhtml2pdf.document import pisaDocument

if TYPE_CHECKING:
    from pypdf.generic import DictionaryObject


def test_font_face_names_retain_distinct_styles() -> None:
    font_directory: Final = Path(__file__).parent / "samples" / "font" / "Noto_Sans"
    styles: Final = ("Regular", "Bold", "Italic", "BoldItalic")
    source: Final = (
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
    output: Final = BytesIO()
    pisaDocument(source, dest=output)
    assert {
        str(cast("DictionaryObject", font.get_object())["/BaseFont"]).split("+")[-1]
        for page in PdfReader(output).pages
        for font in cast(
            "DictionaryObject", cast("DictionaryObject", page["/Resources"])["/Font"]
        ).values()
        if "+" in str(cast("DictionaryObject", font.get_object())["/BaseFont"])
    } == {"NotoSans", "NotoSans-Bold", "NotoSans-Italic", "NotoSans-BoldItalic"}
