"""<pdf:insertpdf>: the pages of another PDF inside the document (#551)."""

from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
from unittest import TestCase

from pypdf import PdfReader
from reportlab.lib.pagesizes import A5, landscape
from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf import pisa
from xhtml2pdf.builders.inserts import parse_pages
from xhtml2pdf.config.resources import ResourceAccessPolicy


def source_pdf(path: Path) -> None:
    """Three pages saying "Source page N", the third one A5 landscape."""
    canvas = Canvas(str(path))
    for number in range(1, 4):
        if number == 3:
            canvas.setPageSize(landscape(A5))
        canvas.drawString(72, 300, f"Source page {number}")
        canvas.showPage()
    canvas.save()


class InsertPdfTest(TestCase):
    directory: tempfile.TemporaryDirectory
    base: Path
    policy: ResourceAccessPolicy

    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.base = Path(cls.directory.name)
        source_pdf(cls.base / "source.pdf")
        cls.policy = ResourceAccessPolicy(base_dir=cls.base)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def render(self, body: str, head: str = "", policy=None) -> PdfReader:
        html = f"<html><head>{head}</head><body>{body}</body></html>"
        output = io.BytesIO()
        pisa.CreatePDF(
            html,
            dest=output,
            path=str(self.base / "doc.html"),
            resource_policy=policy or self.policy,
            raise_exception=True,
        )
        return PdfReader(output)

    @staticmethod
    def texts(reader: PdfReader) -> list[str]:
        return [page.extract_text().strip() for page in reader.pages]

    def test_the_pages_go_where_the_tag_is(self) -> None:
        reader = self.render(
            '<p>before</p><pdf:insertpdf src="source.pdf"/><p>after</p>'
        )

        self.assertEqual(
            ["before", "Source page 1", "Source page 2", "Source page 3", "after"],
            self.texts(reader),
        )

    def test_pages_picks_and_orders_them(self) -> None:
        reader = self.render('<p>a</p><pdf:insertpdf src="source.pdf" pages="3,1"/>')

        self.assertEqual(["a", "Source page 3", "Source page 1"], self.texts(reader))

    def test_no_empty_page_at_either_end(self) -> None:
        reader = self.render('<pdf:insertpdf src="source.pdf" pages="2"/>')

        self.assertEqual(["Source page 2"], self.texts(reader))

    def test_inserted_pages_are_numbered_and_counted(self) -> None:
        reader = self.render(
            '<p>first of <pdf:pagecount/></p><pdf:insertpdf src="source.pdf"/>'
            "<p>page <pdf:pagenumber/></p>"
        )

        self.assertEqual("first of 5", self.texts(reader)[0])
        self.assertEqual("page 5", self.texts(reader)[-1])

    def test_a_page_keeps_its_own_size(self) -> None:
        reader = self.render('<p>a</p><pdf:insertpdf src="source.pdf" pages="3"/>')
        box = reader.pages[1].mediabox

        self.assertEqual(
            [round(v) for v in landscape(A5)], [round(box.width), round(box.height)]
        )

    def test_nothing_of_the_document_is_drawn_on_it(self) -> None:
        head = (
            "<style>@page { background-image: url(source.pdf);"
            " @frame footer { -pdf-frame-content: foot; bottom: 1cm;"
            " height: 1cm; left: 2cm; width: 10cm } }</style>"
        )
        reader = self.render(
            '<div id="foot">footer</div><p>a</p>'
            '<pdf:insertpdf src="source.pdf" pages="2"/>',
            head,
        )

        self.assertIn("footer", self.texts(reader)[0])
        self.assertEqual("Source page 2", self.texts(reader)[1])

    def test_a_missing_file_inserts_nothing(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING"):
            reader = self.render('<p>a</p><pdf:insertpdf src="missing.pdf"/>')

        self.assertEqual(["a"], self.texts(reader))

    def test_an_inline_pdf_follows_the_pdf_background_policy(self) -> None:
        data = base64.b64encode((self.base / "source.pdf").read_bytes()).decode()
        body = f'<p>a</p><pdf:insertpdf src="data:application/pdf;base64,{data}"/>'
        strict = ResourceAccessPolicy(
            base_dir=self.base, allow_remote_pdf_backgrounds=False
        )

        self.assertEqual(4, len(self.render(body).pages))
        with self.assertLogs("xhtml2pdf", level="WARNING") as logs:
            self.assertEqual(1, len(self.render(body, policy=strict).pages))
        self.assertTrue(any("PDF to insert" in line for line in logs.output))

    def test_it_cannot_be_used_with_encryption(self) -> None:
        """An owner password alone would be silently lost on the way."""
        from reportlab.lib.pdfencrypt import StandardEncryption

        for encrypt in ("user", StandardEncryption("", ownerPassword="owner")):
            with self.subTest(encrypt=encrypt), self.assertRaises(ValueError):
                pisa.CreatePDF(
                    '<p>a</p><pdf:insertpdf src="source.pdf"/>',
                    dest=io.BytesIO(),
                    path=str(self.base / "doc.html"),
                    resource_policy=self.policy,
                    encrypt=encrypt,
                )


class ParsePagesTest(TestCase):
    def test_every_page_by_default(self) -> None:
        self.assertEqual([0, 1, 2], parse_pages("", 3))

    def test_pages_and_ranges(self) -> None:
        self.assertEqual([0, 2, 3, 4], parse_pages("1, 3-5", 5))

    def test_open_ranges(self) -> None:
        self.assertEqual([0, 1, 3, 4], parse_pages("-2,4-", 5))

    def test_a_page_it_does_not_have_is_left_out(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING"):
            self.assertEqual([1], parse_pages("2, 7, x", 3))
