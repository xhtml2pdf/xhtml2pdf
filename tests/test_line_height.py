"""line-height, computed and inherited as CSS 2.1 10.8 says."""

from __future__ import annotations

from unittest import TestCase

from xhtml2pdf.document import pisaStory
from xhtml2pdf.util import leadingFrom, lineHeight
from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph


def leadings(html: str) -> list[float]:
    story = pisaStory(html).story
    return [round(f.style.leading, 3) for f in story if isinstance(f, PmlParagraph)]


def nested(line_height: str) -> list[float]:
    """The leading of a 10pt paragraph and of a 20pt one under the same div."""
    return leadings(
        f'<div style="font-size: 10pt; line-height: {line_height}">'
        '<p>small</p><p style="font-size: 20pt">big</p></div>'
    )


class LineHeightTest(TestCase):
    def test_a_number_multiplies_each_elements_own_size(self) -> None:
        self.assertEqual([15.0, 30.0], nested("1.5"))

    def test_a_whole_number_is_a_number(self) -> None:
        # Not one of HTML's <font size> steps, which read 2 as 0.75em.
        self.assertEqual([20.0, 40.0], nested("2"))

    def test_a_percentage_is_resolved_where_it_is_declared(self) -> None:
        self.assertEqual([15.0, 15.0], nested("150%"))

    def test_em_is_resolved_where_it_is_declared(self) -> None:
        self.assertEqual([15.0, 15.0], nested("1.5em"))

    def test_a_length_is_kept(self) -> None:
        self.assertEqual([12.0, 12.0], nested("12pt"))

    def test_normal_is_the_font_size(self) -> None:
        self.assertEqual([10.0, 20.0], nested("normal"))

    def test_the_default_follows_each_size(self) -> None:
        # DEFAULT_CSS gives html line-height: 1.5, a number.
        self.assertEqual(
            [15.0, 30.0],
            leadings(
                '<p style="font-size: 10pt">a</p><p style="font-size: 20pt">b</p>'
            ),
        )

    def test_inherit_takes_the_parents_source(self) -> None:
        self.assertEqual((30.0, "1.5"), lineHeight("inherit", 20.0, "1.5"))
        self.assertEqual(15.0, leadingFrom("15.0pt", 40.0))
