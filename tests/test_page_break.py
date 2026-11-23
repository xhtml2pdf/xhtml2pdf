"""A forced page break never leaves an empty page (CSS Fragmentation 3, 4.1)."""

from __future__ import annotations

import io
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa


def pages(html: str) -> list[list[str]]:
    out = io.BytesIO()
    result = pisa.CreatePDF(html, dest=out)
    assert not result.err
    return [page.extract_text().split() for page in PdfReader(out).pages]


class ForcedBreakTest(TestCase):
    def test_a_break_before_the_first_element_does_nothing(self) -> None:
        self.assertEqual(
            [["One", "a"], ["Two"]],
            pages(
                "<style>h1 { page-break-before: always }</style>"
                "<h1>One</h1><p>a</p><h1>Two</h1>"
            ),
        )

    def test_a_break_after_and_a_break_before_make_one_break(self) -> None:
        self.assertEqual(
            [["A"], ["B"]],
            pages(
                '<p style="page-break-after: always">A</p>'
                '<p style="page-break-before: always">B</p>'
            ),
        )

    def test_a_break_in_the_middle_still_breaks(self) -> None:
        self.assertEqual(
            [["A"], ["B"]], pages('<p>A</p><p style="break-before: page">B</p>')
        )

    def test_a_break_after_the_last_element_adds_no_page(self) -> None:
        self.assertEqual(
            [["A", "B"]], pages('<p>A</p><p style="page-break-after: always">B</p>')
        )

    def test_right_at_the_start_stays_on_page_one(self) -> None:
        # Page one is a right page; the second break needs a blank left one.
        self.assertEqual(
            [["A"], [], ["B"]],
            pages(
                '<p style="page-break-before: right">A</p>'
                '<p style="page-break-before: right">B</p>'
            ),
        )

    def test_with_a_first_page_template(self) -> None:
        self.assertEqual(
            [["One", "Cover"], ["Two", "Head"]],
            pages(
                "<style>@page { margin: 2cm; @top-center { content: 'Head' } }"
                " @page :first { @top-center { content: 'Cover' } }"
                " h1 { page-break-before: always }</style><h1>One</h1><h1>Two</h1>"
            ),
        )

    def test_pdf_nextpage_still_asks_for_a_page(self) -> None:
        self.assertEqual([[], ["A"]], pages("<pdf:nextpage/><p>A</p>"))
