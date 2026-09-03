from __future__ import annotations

import io
from pathlib import Path
from typing import ClassVar
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf.document import pisaDocument
from xhtml2pdf.pdf import pisaPDF

from .httpserver import LocalServerMixin

SAMPLES = Path(__file__).parent / "samples"


def _render(text: str) -> bytes:
    """Render a one-page PDF whose only content is ``text``."""
    dest = io.BytesIO()
    pisaDocument(io.StringIO(f"<html><body><p>{text}</p></body></html>"), dest)
    return dest.getvalue()


class PisaPDFTest(TestCase):
    """``xhtml2pdf.pdf`` had no test coverage at all."""

    one: ClassVar[bytes]
    two: ClassVar[bytes]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.one = _render("one")
        cls.two = _render("two")

    @staticmethod
    def _pages(data: bytes) -> list[str]:
        return [
            page.extract_text().strip() for page in PdfReader(io.BytesIO(data)).pages
        ]

    def test_addFromString(self) -> None:
        """
        This raised TypeError on every call: getFile() takes no ``capacity``
        keyword, and the bytes it returns were appended without a BytesIO
        wrapper, which PdfReader cannot consume.
        """
        merger = pisaPDF()
        merger.addFromString(self.one)
        merger.addFromString(self.two)
        self.assertEqual(["one", "two"], self._pages(merger.join()))

    def test_addFromFile_with_file_object(self) -> None:
        merger = pisaPDF()
        merger.addFromFile(io.BytesIO(self.one))
        self.assertEqual(["one"], self._pages(merger.join()))

    def test_addFromFile_with_path(self) -> None:
        merger = pisaPDF()
        merger.addFromFile(str(SAMPLES / "images.pdf"))
        self.assertEqual(1, len(self._pages(merger.join())))

    def test_addDocument(self) -> None:
        dest = io.BytesIO()
        doc = pisaDocument(io.StringIO("<html><body><p>doc</p></body></html>"), dest)
        merger = pisaPDF()
        merger.addDocument(doc)
        self.assertEqual(["doc"], self._pages(merger.join()))

    def test_join_into_a_given_file(self) -> None:
        merger = pisaPDF()
        merger.addFromString(self.one)
        target = io.BytesIO()
        self.assertIs(target, merger.join(target))
        self.assertEqual(["one"], self._pages(target.getvalue()))

    def test_getvalue_is_an_alias_of_join(self) -> None:
        merger = pisaPDF()
        merger.addFromString(self.one)
        self.assertEqual(["one"], self._pages(merger.getvalue()))

    def test_empty_merger_produces_a_valid_pdf(self) -> None:
        self.assertEqual([], self._pages(pisaPDF().join()))


class PisaPDFNetworkTest(LocalServerMixin, TestCase):
    def test_addFromURI(self) -> None:
        merger = pisaPDF()
        merger.addFromURI(f"{self.base_url}/images.pdf")
        self.assertEqual(1, len(PdfReader(io.BytesIO(merger.join())).pages))

    def test_addFromURI_missing_resource_is_ignored(self) -> None:
        merger = pisaPDF()
        with self.assertLogs("xhtml2pdf.files", level="WARNING"):
            merger.addFromURI(f"{self.base_url}/status/404")
        self.assertEqual([], merger.files)
