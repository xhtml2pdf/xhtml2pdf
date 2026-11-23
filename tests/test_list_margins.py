"""The vertical margins of a list, as a browser gives them."""

from __future__ import annotations

from unittest import TestCase

from reportlab.platypus import Spacer

from xhtml2pdf.document import pisaStory
from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph

FONT = "font-size: 10pt; "


def paragraphs(html: str) -> dict[str, tuple[float, float]]:
    """Text -> (space before, space after) of each paragraph of the story."""
    story = pisaStory(html).story
    found = {}
    for flowable in story:
        if isinstance(flowable, PmlParagraph):
            flowable.wrap(400, 800)
            found[flowable.getPlainText().strip()] = (
                flowable.getSpaceBefore(),
                flowable.getSpaceAfter(),
            )
    return found


class ListMarginTest(TestCase):
    def test_a_list_has_an_em_above_and_below(self) -> None:
        found = paragraphs(
            f'<p style="margin: 0">before</p><ul style="{FONT}"><li>one</li>'
            '<li>two</li></ul><p style="margin: 0">after</p>'
        )
        self.assertEqual(10.0, found["one"][0])
        self.assertEqual(10.0, found["two"][1])

    def test_a_list_in_a_list_has_none(self) -> None:
        found = paragraphs(
            f'<ul style="{FONT}"><li>outer<ul><li>inner</li></ul></li>'
            "<li>after</li></ul>"
        )
        self.assertEqual((0.0, 0.0), found["inner"])

    def test_the_last_items_margin_collapses_with_the_lists(self) -> None:
        story = pisaStory(
            '<ul style="margin: 0 0 20pt 0"><li><p style="margin: 0 0 5pt 0">'
            'a</p></li></ul><p style="margin: 0">after</p>'
        ).story
        # The larger of the two, on the item, and no spacer for the list.
        self.assertFalse(any(isinstance(f, Spacer) for f in story))
        found = paragraphs(
            '<ul style="margin: 0 0 20pt 0"><li><p style="margin: 0 0 5pt 0">'
            'a</p></li></ul><p style="margin: 0">after</p>'
        )
        self.assertEqual(20.0, found["a"][1])

    def test_margin_zero_keeps_a_list_tight(self) -> None:
        found = paragraphs(
            '<p style="margin: 0">before</p>'
            '<ul style="margin-top: 0; margin-bottom: 0"><li>one</li></ul>'
            '<p style="margin: 0">after</p>'
        )
        self.assertEqual((0.0, 0.0), found["one"])
