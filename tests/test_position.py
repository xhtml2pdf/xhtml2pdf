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


#: A4 less the default 1cm margins: the page area, where the initial
#: containing block is.
AREA_LEFT = 28.35
AREA_TOP = 841.89 - 28.35
AREA_RIGHT = 595.28 - 28.35
AREA_BOTTOM = 28.35


class AbsoluteTest(TestCase):
    def test_top_left_from_the_page_area(self) -> None:
        where = positions(
            '<p>Alpha</p><div style="position: absolute; top: 100pt; left: 50pt">Boxed</div>'
        )
        self.assertAlmostEqual(AREA_LEFT + 50, where["Boxed"][0], places=0)
        self.assertLess(where["Boxed"][1], AREA_TOP - 100)
        self.assertGreater(where["Boxed"][1], AREA_TOP - 115)

    def test_the_flow_does_not_move(self) -> None:
        plain = positions("<p>Alpha</p><p>Charlie</p>")
        with_box = positions(
            '<p>Alpha</p><div style="position: absolute; top: 300pt">Boxed</div><p>Charlie</p>'
        )
        self.assertEqual(plain["Charlie"], with_box["Charlie"])

    def test_bottom_right_from_the_page_area(self) -> None:
        where = positions(
            '<p>Alpha <span style="position: absolute; bottom: 0; right: 0">Corner</span></p>'
        )
        x, y = where["Corner"]
        self.assertGreater(x, AREA_RIGHT - 40)
        self.assertLess(y, AREA_BOTTOM + 10)

    def test_left_and_right_stretch_the_box(self) -> None:
        reader = render(
            '<div style="position: absolute; top: 0; left: 100pt; right: 100pt;'
            ' background-color: #ff0000">x</div>'
        )
        data = reader.pages[0].get_contents().get_data().decode("latin-1")
        rect = next(line for line in data.splitlines() if " re " in line).split()
        width = float(rect[rect.index("re") - 2])
        self.assertAlmostEqual(AREA_RIGHT - AREA_LEFT - 200, width, places=0)

    def test_the_static_position_is_where_the_element_was(self) -> None:
        plain = positions("<p>Alpha</p><p>Static</p>")
        where = positions('<p>Alpha</p><div style="position: absolute">Static</div>')
        self.assertEqual(plain["Static"], where["Static"])

    def test_z_index_orders_the_painting(self) -> None:
        reader = render(
            '<div style="position: absolute; top: 0; z-index: 2">Upper</div>'
            '<div style="position: absolute; top: 0; z-index: 1">Lower</div>'
        )
        data = reader.pages[0].get_contents().get_data().decode("latin-1")
        self.assertLess(data.index("(Lower)"), data.index("(Upper)"))

    def test_a_top_past_the_first_page_goes_on_a_later_page(self) -> None:
        paragraphs = "".join(f"<p>paragraph {i}</p>" for i in range(120))
        reader = render(
            f'<div style="position: absolute; top: 1000pt">Later</div>{paragraphs}'
        )
        pages = [
            i for i, page in enumerate(reader.pages) if "Later" in page.extract_text()
        ]
        self.assertEqual([1], pages)


class FixedTest(TestCase):
    def test_on_every_page(self) -> None:
        paragraphs = "".join(f"<p>paragraph {i}</p>" for i in range(150))
        reader = render(
            f'<div style="position: fixed; top: 0; right: 0">Stamp</div>{paragraphs}'
        )
        self.assertGreater(len(reader.pages), 2)
        self.assertTrue(all("Stamp" in page.extract_text() for page in reader.pages))

    def test_leaves_nothing_in_the_flow(self) -> None:
        plain = positions("<p>Alpha</p><p>Charlie</p>")
        where = positions(
            '<p>Alpha</p><div style="position: fixed; bottom: 0">Stamp</div><p>Charlie</p>'
        )
        self.assertEqual(plain["Charlie"], where["Charlie"])


class ContainingBlockTest(TestCase):
    """An absolute box inside a positioned ancestor is placed from it (#566)."""

    def test_from_a_relative_block(self) -> None:
        where = positions(
            '<p>Intro</p><div style="position: relative; margin-left: 50pt">'
            "<p>Inside</p>"
            '<div style="position: absolute; top: 0; left: 20pt">Over</div></div>'
        )
        # Over sits on Inside's line, 20pt into the block, which starts 50pt in.
        self.assertAlmostEqual(where["Inside"][1], where["Over"][1], places=0)
        self.assertAlmostEqual(AREA_LEFT + 50 + 20, where["Over"][0], places=0)

    def test_right_is_from_the_relative_blocks_right_edge(self) -> None:
        where = positions(
            '<div style="position: relative; margin-right: 100pt"><p>Inside</p>'
            '<span style="position: absolute; top: 0; right: 0">R</span></div>'
        )
        self.assertLess(where["R"][0], AREA_RIGHT - 100)
        self.assertGreater(where["R"][0], AREA_RIGHT - 115)

    def test_a_moved_relative_block_moves_what_it_contains(self) -> None:
        plain = positions(
            '<div style="position: relative"><p>Inside</p>'
            '<span style="position: absolute; top: 0; right: 0">R</span></div>'
        )
        moved = positions(
            '<div style="position: relative; left: 30pt"><p>Inside</p>'
            '<span style="position: absolute; top: 0; right: 0">R</span></div>'
        )
        self.assertAlmostEqual(30, moved["R"][0] - plain["R"][0], places=0)

    def test_from_an_absolute_box(self) -> None:
        where = positions(
            '<div style="position: absolute; top: 100pt; left: 100pt; width: 200pt;'
            ' height: 100pt">Parent<div style="position: absolute; bottom: 0; left: 0">Child</div>'
            "</div>"
        )
        self.assertAlmostEqual(AREA_LEFT + 100, where["Child"][0], places=0)
        self.assertLess(where["Child"][1], AREA_TOP - 185)
        self.assertGreater(where["Child"][1], AREA_TOP - 200)

    def test_a_child_paints_over_its_parent_whatever_its_z_index(self) -> None:
        reader = render(
            '<div style="position: absolute; top: 0; z-index: 5">Parent'
            '<div style="position: absolute; top: 0; z-index: -3">Child</div></div>'
        )
        data = reader.pages[0].get_contents().get_data().decode("latin-1")
        self.assertLess(data.index("(Parent)"), data.index("(Child)"))

    def test_the_relative_block_does_not_move_the_flow(self) -> None:
        plain = positions("<div><p>Inside</p></div><p>After</p>")
        with_boxes = positions(
            '<div style="position: relative"><p>Inside</p>'
            '<div style="position: absolute; top: 0">Box</div></div><p>After</p>'
        )
        self.assertEqual(plain["After"], with_boxes["After"])
