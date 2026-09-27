"""CSS positioning: position, top/right/bottom/left and z-index."""

from __future__ import annotations

import io
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.builders.position import read_position, read_z_index


def render(html: str) -> PdfReader:
    dest = io.BytesIO()
    result = pisa.CreatePDF(html, dest=dest)
    assert not result.err
    return PdfReader(io.BytesIO(dest.getvalue()))


def positions(html: str, page: int = 0) -> dict[str, tuple[float, float]]:
    """Where each word is drawn on `page`, in page coordinates."""
    out: dict[str, tuple[float, float]] = {}

    def visit(text, cm, tm, font_dict, font_size) -> None:  # noqa: ARG001
        word = text.strip()
        if word:
            x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
            y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
            out.setdefault(word, (round(x, 1), round(y, 1)))

    render(html).pages[page].extract_text(visitor_text=visit)
    return out


class ReadPositionTest(TestCase):
    def test_values(self) -> None:
        self.assertEqual("relative", read_position({"position": "Relative"}))
        self.assertEqual("relative", read_position({"position": "sticky"}))
        self.assertEqual("static", read_position({"position": "nonsense"}))
        self.assertEqual("static", read_position({}))

    def test_z_index(self) -> None:
        self.assertEqual(3, read_z_index({"z-index": "3"}))
        self.assertEqual(-1, read_z_index({"z-index": "-1"}))
        self.assertEqual(0, read_z_index({"z-index": "auto"}))


class RelativeTest(TestCase):
    PLAIN = "<p>Alpha</p><p>Bravo</p><p>Charlie</p>"

    def moved(self, style: str) -> tuple[tuple[float, float], tuple[float, float]]:
        """(how far Bravo moved, how far Charlie moved)."""
        plain = positions(self.PLAIN)
        shifted = positions(self.PLAIN.replace("<p>Bravo", f'<p style="{style}">Bravo'))

        def delta(word: str) -> tuple[float, float]:
            return (
                round(shifted[word][0] - plain[word][0], 1),
                round(shifted[word][1] - plain[word][1], 1),
            )

        return delta("Bravo"), delta("Charlie")

    def test_top_left_move_the_block_and_nothing_else(self) -> None:
        bravo, charlie = self.moved("position: relative; top: 20pt; left: 30pt")
        self.assertEqual((30.0, -20.0), bravo)
        self.assertEqual((0.0, 0.0), charlie)

    def test_bottom_right_move_the_other_way(self) -> None:
        bravo, _charlie = self.moved("position: relative; bottom: 10pt; right: 5pt")
        self.assertEqual((-5.0, 10.0), bravo)

    def test_left_wins_over_right_and_top_over_bottom(self) -> None:
        bravo, _charlie = self.moved(
            "position: relative; top: 4pt; bottom: 50pt; left: 6pt; right: 50pt"
        )
        self.assertEqual((6.0, -4.0), bravo)

    def test_a_percentage_left_is_of_the_frame_width(self) -> None:
        bravo, _charlie = self.moved("position: relative; left: 10%")
        # A4 less the default 1cm margins on either side.
        self.assertAlmostEqual((595.28 - 2 * 28.35) / 10, bravo[0], places=0)

    def test_static_ignores_the_offsets(self) -> None:
        bravo, _charlie = self.moved("position: static; top: 20pt; left: 30pt")
        self.assertEqual((0.0, 0.0), bravo)

    def test_nested_relative_blocks_add_up(self) -> None:
        plain = positions("<div><div><p>Bravo</p></div></div>")
        nested = positions(
            '<div style="position: relative; left: 10pt">'
            '<div style="position: relative; left: 15pt"><p>Bravo</p></div></div>'
        )
        self.assertEqual(25.0, round(nested["Bravo"][0] - plain["Bravo"][0], 1))

    def test_a_relative_heading_keeps_its_outline(self) -> None:
        reader = render('<h1 style="position: relative; left: 10pt">Title</h1><p>x</p>')
        self.assertEqual(["Title"], [item.title for item in reader.outline])

    def test_a_relative_block_across_pages_moves_on_both(self) -> None:
        text = " ".join(f"word{i}" for i in range(4000))
        html = f'<p style="position: relative; left: 40pt">{text}</p>'
        reader = render(html)
        self.assertGreater(len(reader.pages), 1)
        first = positions(html, 0)
        second = positions(html, 1)
        self.assertAlmostEqual(28.3 + 40, min(x for x, _y in first.values()), places=0)
        self.assertAlmostEqual(28.3 + 40, min(x for x, _y in second.values()), places=0)
