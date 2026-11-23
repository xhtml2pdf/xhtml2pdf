"""CSS opacity: a box and its content painted as one translucent group."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.util import getOpacity

if TYPE_CHECKING:
    from pypdf.generic import DictionaryObject


def render(html: str):
    out = io.BytesIO()
    result = pisa.CreatePDF(html, dest=out)
    assert not result.err
    return PdfReader(io.BytesIO(out.getvalue())).pages[0]


def groups(resources: DictionaryObject) -> list[DictionaryObject]:
    """Every transparency group form under `resources`, nested ones too."""
    found = []
    for form in (resources.get("/XObject") or {}).values():
        form = form.get_object()
        if form.get("/Group", {}).get("/S") == "/Transparency":
            found.append(form)
            found += groups(form["/Resources"])
    return found


def alphas(resources: DictionaryObject) -> set[float]:
    return {
        round(float(state.get_object().get("/ca", 1)), 3)
        for state in (resources.get("/ExtGState") or {}).values()
    }


class OpacityTest(TestCase):
    def test_a_block_is_one_group_painted_at_its_opacity(self) -> None:
        page = render(
            '<div style="opacity: 0.4; background: #f00">'
            '<p style="background: #00f">overlapping</p></div>'
        )
        (group,) = groups(page["/Resources"])
        self.assertIn(0.4, alphas(page["/Resources"]))
        # The child's background is inside the group, drawn opaque.
        self.assertNotIn(0.4, alphas(group["/Resources"]))
        self.assertIn("overlapping", page.extract_text())

    def test_a_paragraph_of_text_alone_is_a_group(self) -> None:
        page = render('<p style="opacity: 50%">text</p>')
        self.assertEqual(1, len(groups(page["/Resources"])))

    def test_nested_opacities_nest(self) -> None:
        page = render(
            '<div style="opacity: 0.5"><div style="opacity: 0.5">x</div></div>'
        )
        self.assertEqual(2, len(groups(page["/Resources"])))

    def test_a_link_in_a_group_still_works(self) -> None:
        page = render(
            '<p style="opacity: 0.5"><a href="https://example.com">link</a></p>'
        )
        (annotation,) = page["/Annots"]
        annotation = annotation.get_object()
        self.assertEqual("https://example.com", annotation["/A"]["/URI"])
        # On the page, where the word is.
        x0, _y0, x1, _y1 = (float(v) for v in annotation["/Rect"])
        self.assertLess(x0, 40)
        self.assertGreater(x1, x0)

    def test_each_kind_of_box_reads_it(self) -> None:
        for html in (
            '<table style="opacity: 0.5"><tr><td>cell</td></tr></table>',
            '<div style="display: flex; opacity: 0.5"><div>a</div></div>',
            '<div style="display: flex"><div style="opacity: 0.5">a</div></div>',
            '<p>x <span style="display: inline-block; opacity: 0.5">b</span></p>',
            '<div style="position: absolute; top: 0; opacity: 0.5">abs</div>',
            '<img src="tests/samples/img/denker.png" style="opacity: 0.5">',
        ):
            with self.subTest(html=html):
                page = render(html)
                self.assertEqual(1, len(groups(page["/Resources"])))
                self.assertIn(0.5, alphas(page["/Resources"]))

    def test_an_inline_element_fades_its_colours(self) -> None:
        page = render('<p>a <span style="opacity: 0.5; color: #f00">faded</span> b</p>')
        self.assertEqual([], groups(page["/Resources"]))
        self.assertIn(0.5, alphas(page["/Resources"]))

    def test_opaque_draws_no_group(self) -> None:
        page = render('<div style="opacity: 1; background: #f00">x</div>')
        self.assertEqual([], groups(page["/Resources"]))


class GetOpacityTest(TestCase):
    def test_numbers_and_percentages_are_clamped(self) -> None:
        self.assertEqual(
            [0.5, 0.25, 1.0, 0.0], [getOpacity(v) for v in ("0.5", "25%", "3", "-1")]
        )

    def test_nonsense_is_opaque(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING"):
            self.assertEqual(1.0, getOpacity("half"))
