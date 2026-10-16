"""
Each document draws with the fonts it declares, whatever others in the
process declare.

Two documents may name a font-family the same and embed different files,
one after the other or at the same time in different threads: each gets
its own files, regular, bold and italic.
"""

import hashlib
import io
import threading
from pathlib import Path
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.config.resources import ResourceAccessPolicy

FONTS = Path(__file__).parent / "samples" / "font"
NOTO = {
    ("normal", "normal"): FONTS / "Noto_Sans" / "NotoSans-Regular.ttf",
    ("bold", "normal"): FONTS / "Noto_Sans" / "NotoSans-Bold.ttf",
    ("normal", "italic"): FONTS / "Noto_Sans" / "NotoSans-Italic.ttf",
}
MARKAZI = {
    ("normal", "normal"): FONTS / "Arabic_font" / "MarkaziText-Regular.ttf",
    ("bold", "normal"): FONTS / "Arabic_font" / "MarkaziText-Bold.ttf",
}
POLICY = ResourceAccessPolicy(allow_local_outside_base=True)


def render(faces: dict) -> set[tuple[str, str]]:
    """The embedded fonts of the document: (name, digest of the file)."""
    css = "".join(
        f"@font-face {{ font-family: Shared; font-weight: {weight};"
        f' font-style: {style}; src: url("{path}"); }}'
        for (weight, style), path in faces.items()
    )
    html = (
        f"<html><head><style>{css} body {{ font-family: Shared }}</style></head>"
        "<body><p>plain <b>bold</b> <i>italic</i></p></body></html>"
    )
    output = io.BytesIO()
    result = pisa.CreatePDF(html, dest=output, resource_policy=POLICY)
    assert not result.err
    embedded = set()
    for page in PdfReader(io.BytesIO(output.getvalue())).pages:
        for font in page["/Resources"]["/Font"].values():
            font = font.get_object()
            descriptor = font.get("/FontDescriptor")
            if descriptor is None:
                continue
            data = descriptor.get_object()["/FontFile2"].get_object().get_data()
            name = str(font["/BaseFont"]).split("+")[-1]
            embedded.add((name, hashlib.md5(data).hexdigest()))
    return embedded


class FontIsolationTest(TestCase):
    def test_a_second_document_embeds_its_own_file_for_the_same_family(self) -> None:
        noto = render(NOTO)
        markazi = render(MARKAZI)
        self.assertEqual(
            {"NotoSans", "NotoSans-Bold", "NotoSans-Italic"}, {name for name, _ in noto}
        )
        self.assertEqual(
            {"MarkaziText-Regular", "MarkaziText-Bold"}, {name for name, _ in markazi}
        )

    def test_documents_rendered_at_once_in_threads_keep_their_fonts(self) -> None:
        expected = {"noto": render(NOTO), "markazi": render(MARKAZI)}
        found: list[tuple[str, set]] = []

        def work(kind: str) -> None:
            faces = NOTO if kind == "noto" else MARKAZI
            found.extend((kind, render(faces)) for _ in range(3))

        threads = [
            threading.Thread(target=work, args=("noto" if n % 2 else "markazi",))
            for n in range(6)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(18, len(found))
        for kind, embedded in found:
            self.assertEqual(expected[kind], embedded, kind)
