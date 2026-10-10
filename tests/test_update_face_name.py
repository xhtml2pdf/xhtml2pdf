import io
import os
from unittest import TestCase
from uuid import uuid4

from reportlab.pdfbase import ttfonts

from xhtml2pdf.document import pisaDocument


class EmbeddedFontIsBuiltOnce(TestCase):
    """
    ReportLab keeps the first dynamic font registered under a name, so a
    second document asking for the same @font-face used to read and parse the
    whole file again only for pdfmetrics.registerFont to discard the result.
    """

    ttf_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "samples",
        "font",
        "Noto_Sans",
        "NotoSans-Regular.ttf",
    )

    @staticmethod
    def _render(family: str) -> int:
        """Render one document, and return how many TTFont objects it built."""
        built = []
        original = ttfonts.TTFont.__init__

        def counted(self, *args, **kwargs):
            built.append(args[0] if args else None)
            return original(self, *args, **kwargs)

        html = (
            "<html><head><style>"
            f"@font-face {{font-family: {family};"
            f" src: url('{EmbeddedFontIsBuiltOnce.ttf_path}');}}"
            f"body {{font-family: {family};}}"
            "</style></head><body>text</body></html>"
        )
        ttfonts.TTFont.__init__ = counted
        try:
            with io.BytesIO() as output:
                pisaDocument(html, output)
        finally:
            ttfonts.TTFont.__init__ = original
        return len(built)

    def test_the_second_document_reuses_the_registered_font(self) -> None:
        # A name of its own: pdfmetrics' registry is global and outlives a
        # document, so a family another test embedded would already be there.
        family = f"Probe{uuid4().hex}"
        self.assertEqual(1, self._render(family))
        self.assertEqual(0, self._render(family))

    def test_a_different_family_is_still_built(self) -> None:
        self.assertEqual(1, self._render(f"Probe{uuid4().hex}"))
        self.assertEqual(1, self._render(f"Probe{uuid4().hex}"))
