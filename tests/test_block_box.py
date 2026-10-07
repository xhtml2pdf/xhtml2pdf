"""A block's padding, border and background drawn once around all it holds (#627)."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, NamedTuple
from unittest import TestCase, mock

from pypdf import PdfReader
from reportlab.lib.colors import toColor
from reportlab.platypus.tables import Table

from xhtml2pdf import pisa
from xhtml2pdf.builders import block
from xhtml2pdf.builders.block import BlockBox
from xhtml2pdf.document import pisaStory
from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph, PmlTable

if TYPE_CHECKING:
    from xhtml2pdf.builders.flex import BoxStyle

RED = toColor("red")
BLUE = toColor("blue")


class Box(NamedTuple):
    """A box's border, as drawn: page, left, bottom, width, height, style."""

    page: int
    x: float
    y: float
    w: float
    h: float
    style: BoxStyle


class Drawn(NamedTuple):
    """A table as drawn: page, left, bottom, width, height."""

    page: int
    x: float
    y: float
    w: float
    h: float


def render(html: str) -> tuple[list[Box], list[Drawn], bytes]:
    """The boxes BlockBox drew, the tables, and the PDF."""
    boxes: list[Box] = []
    tables: list[Drawn] = []
    borders = block.drawBoxBorders
    draw = Table.drawOn

    def spy_borders(canvas, x, y, w, h, style, *args, **kw):
        ax, ay = canvas.absolutePosition(x, y)
        boxes.append(Box(canvas.getPageNumber(), ax, ay, w, h, style))
        return borders(canvas, x, y, w, h, style, *args, **kw)

    def spy_table(self, canvas, x, y, _sW=0):
        ax, ay = canvas.absolutePosition(self._hAlignAdjust(x, _sW), y)
        tables.append(Drawn(canvas.getPageNumber(), ax, ay, self._width, self._height))
        return draw(self, canvas, x, y, _sW)

    dest = io.BytesIO()
    with (
        mock.patch.object(block, "drawBoxBorders", spy_borders),
        mock.patch.object(Table, "drawOn", spy_table),
    ):
        result = pisa.CreatePDF(html, dest=dest)
    assert not result.err
    return boxes, tables, dest.getvalue()


def table_commands(html: str) -> list[tuple]:
    """The style commands of every PmlTable built."""
    commands: list[tuple] = []
    init = PmlTable.__init__

    def spy(self, data, *args, **kw):
        init(self, data, *args, **kw)
        commands.extend(kw["style"].getCommands())

    with mock.patch.object(PmlTable, "__init__", spy):
        pisa.CreatePDF(html, dest=io.BytesIO())
    return commands


def frame() -> tuple[float, float]:
    """The left edge and the width of the default frame."""
    _, (table,), _ = render("<table><tr><td>x</td></tr></table>")
    return table.x, table.w


ROW = "<tr><td>one</td><td>two</td></tr>"
DIV = '<div style="margin-left: 50pt; padding: 10pt; border: 2pt solid red">{}</div>'
TABLE = f'<table style="border: 1pt solid blue">{ROW}</table>'


class OneBoxTestCase(TestCase):
    def test_text_table_and_text_are_in_one_box(self) -> None:
        boxes, (table,), _ = render(DIV.format(f"<p>before</p>{TABLE}<p>after</p>"))

        (box,) = boxes
        self.assertGreater(box.y + box.h, table.y + table.h)
        self.assertLess(box.y, table.y)
        # Room above the table for "before", below it for "after".
        self.assertGreater(box.y + box.h - (table.y + table.h), 20)
        self.assertGreater(table.y - box.y, 20)

    def test_the_table_sits_inside_the_margin_and_padding(self) -> None:
        left, width = frame()
        boxes, (table,), _ = render(DIV.format(TABLE))

        (box,) = boxes
        self.assertAlmostEqual(left + 50, box.x)
        self.assertAlmostEqual(width - 50, box.w)
        self.assertAlmostEqual(left + 50 + 12, table.x)
        self.assertAlmostEqual(width - 50 - 24, table.w)
        self.assertAlmostEqual(box.y + 12, table.y)

    def test_each_border_keeps_its_own_colour(self) -> None:
        html = DIV.format(TABLE)
        lines = [c for c in table_commands(html) if c[0].startswith("LINE")]
        boxes, _, _ = render(html)

        self.assertTrue(lines)
        self.assertTrue(all(c[4] == BLUE for c in lines), lines)
        (box,) = boxes
        for side in ("Left", "Right", "Top", "Bottom"):
            self.assertEqual(RED, getattr(box.style, f"border{side}Color"))

    def test_the_table_does_not_take_the_padding(self) -> None:
        commands = table_commands(DIV.format(TABLE))

        paddings = {c[3] for c in commands if c[0].endswith("PADDING")}
        self.assertNotIn(10.0, paddings, commands)

    def test_what_is_inside_does_not_repeat_the_box(self) -> None:
        story = pisaStory(DIV.format(f"<p>before</p>{TABLE}<p>after</p>")).story
        (box,) = [f for f in story if isinstance(f, BlockBox)]

        paragraphs = [f for f in box.content if isinstance(f, PmlParagraph)]
        self.assertEqual(2, len(paragraphs))
        for paragraph in paragraphs:
            style = paragraph.style
            self.assertEqual(0, style.paddingLeft)
            self.assertEqual(0, style.borderLeftWidth or 0)
            self.assertIsNone(style.backColor)
            self.assertEqual(0, style.leftIndent)

    def test_a_block_of_text_alone_keeps_its_paragraph_box(self) -> None:
        story = pisaStory(DIV.format("only text")).story

        self.assertFalse([f for f in story if isinstance(f, BlockBox)])
        (paragraph,) = [f for f in story if isinstance(f, PmlParagraph)]
        self.assertEqual(10, paragraph.style.paddingLeft)

    def test_an_inherited_padding_is_no_box(self) -> None:
        """A margin alone makes no box: the indent is the paragraphs' still."""
        story = pisaStory('<div style="margin-left: 50pt"><p>a</p><p>b</p></div>').story

        self.assertFalse([f for f in story if isinstance(f, BlockBox)])

    def test_a_background_covers_the_gap_between_paragraphs(self) -> None:
        story = pisaStory(
            '<div style="background-color: #eee"><p>a</p><p>b</p></div>'
        ).story

        (box,) = [f for f in story if isinstance(f, BlockBox)]
        self.assertIsNotNone(box.style.backColor)
        for paragraph in box.content:
            self.assertIsNone(paragraph.style.backColor)

    def test_nested_boxes(self) -> None:
        inner = (
            '<div style="border: 1pt solid blue; padding: 5pt"><p>a</p><p>b</p></div>'
        )
        boxes, _, _ = render(DIV.format(f"<p>x</p>{inner}"))

        outer, nested = sorted(boxes, key=lambda b: b.w, reverse=True)
        self.assertAlmostEqual(outer.x + 12, nested.x)
        self.assertAlmostEqual(outer.w - 24, nested.w)

    def test_a_shrunk_table_is_centred_in_the_content_area(self) -> None:
        boxes, (table,), _ = render(
            DIV.format(f'<table style="margin: 0 auto">{ROW}</table>')
        )

        (box,) = boxes
        middle = box.x + box.w / 2
        self.assertAlmostEqual(middle, table.x + table.w / 2, places=3)
        self.assertLess(table.w, box.w / 2)

    def test_a_rounded_border_is_drawn_once(self) -> None:
        boxes, _, _ = render(
            '<div style="border: 1pt solid red; border-radius: 6pt">'
            f"<p>a</p>{TABLE}</div>"
        )

        self.assertEqual(1, len(boxes))


class PageTestCase(TestCase):
    PARAS = "".join(f"<p>paragraph {i}</p>" for i in range(120))

    def test_a_box_across_pages_is_sliced(self) -> None:
        boxes, _, _ = render(DIV.format(self.PARAS))

        self.assertGreater(len(boxes), 1)
        self.assertEqual(list(range(1, len(boxes) + 1)), [b.page for b in boxes])
        first, last = boxes[0].style, boxes[-1].style
        self.assertIsNone(first.borderBottomStyle)
        self.assertEqual("solid", first.borderTopStyle)
        self.assertIsNone(last.borderTopStyle)
        self.assertEqual("solid", last.borderBottomStyle)

    def test_a_page_break_inside_cuts_the_box(self) -> None:
        for brk in ("<pdf:nextpage/>", '<p style="page-break-before: always">b</p>'):
            with self.subTest(brk=brk):
                boxes, _, _ = render(DIV.format(f"<p>a</p>{brk}<p>c</p>"))

                self.assertEqual([1, 2], [b.page for b in boxes])
                self.assertIsNone(boxes[0].style.borderBottomStyle)
                self.assertIsNone(boxes[1].style.borderTopStyle)

    def test_page_break_inside_avoid_moves_the_box_whole(self) -> None:
        filler = '<div style="height: 1pt"></div>' + "<p>filler</p>" * 50
        boxes, _, _ = render(
            filler
            + '<div style="border: 1pt solid red; page-break-inside: avoid">'
            + "".join(f"<p>{i}</p>" for i in range(20))
            + "</div>"
        )

        self.assertEqual([2], [b.page for b in boxes])

    def test_a_heading_inside_reaches_the_index(self) -> None:
        _, _, pdf = render(
            '<div style="page-break-after: always"><pdf:toc/></div>'
            + DIV.format("<h1>Chapter</h1><p>text</p>")
        )

        reader = PdfReader(io.BytesIO(pdf))
        self.assertIn("Chapter", reader.pages[0].extract_text())
        self.assertEqual(["Chapter"], [o.title for o in reader.outline])

    def test_an_index_inside_a_box_still_fills(self) -> None:
        _, _, pdf = render(
            DIV.format("<pdf:toc/><p>x</p>")
            + '<h1 style="page-break-before: always">Chapter</h1>'
        )

        reader = PdfReader(io.BytesIO(pdf))
        self.assertIn("Chapter", reader.pages[0].extract_text())


class ListTestCase(TestCase):
    @staticmethod
    def marker_and_text(html: str) -> tuple[float, float]:
        """The x of the list marker and of the item's text."""
        dest = io.BytesIO()
        pisa.CreatePDF(html, dest=dest)
        runs: list[tuple[float, str]] = []

        def visit(text, cm, tm, font_dict, font_size) -> None:  # noqa: ARG001
            if text.strip():
                runs.append((tm[4] * cm[0] + cm[4], text.strip()))

        PdfReader(io.BytesIO(dest.getvalue())).pages[0].extract_text(visitor_text=visit)
        marker = min(x for x, t in runs if "item" not in t)
        text = min(x for x, t in runs if "item" in t)
        return marker, text

    def test_a_marker_hangs_outside_a_bordered_item(self) -> None:
        plain = self.marker_and_text("<ul><li><p>item</p><p>more</p></li></ul>")
        boxed = self.marker_and_text(
            '<ul><li style="border: 1pt solid red"><p>item</p><p>more</p></li></ul>'
        )

        self.assertLess(boxed[0], boxed[1])
        self.assertAlmostEqual(plain[0], boxed[0], places=1)

    def test_a_box_inside_an_item_keeps_the_marker(self) -> None:
        marker, text = self.marker_and_text(
            '<ul><li><div style="border: 1pt solid red"><p>item</p><p>x</p></div>'
            "</li></ul>"
        )

        self.assertLess(marker, text)


class PlacesTestCase(TestCase):
    def test_in_a_table_cell(self) -> None:
        boxes, _, _ = render(
            f"<table><tr><td>{DIV.format('<p>a</p><p>b</p>')}</td></tr></table>"
        )

        self.assertEqual(1, len(boxes))

    def test_in_a_flex_item(self) -> None:
        boxes, _, _ = render(
            '<div style="display: flex"><div>'
            + DIV.format("<p>a</p><p>b</p>")
            + "</div><div>c</div></div>"
        )

        self.assertEqual(1, len(boxes))

    def test_right_to_left(self) -> None:
        left, width = frame()
        boxes, (table,), _ = render(
            '<div dir="rtl" style="margin-right: 50pt; padding: 10pt;'
            f' border: 2pt solid red">{TABLE}</div>'
        )

        (box,) = boxes
        self.assertAlmostEqual(left, box.x)
        self.assertAlmostEqual(width - 50, box.w)
        self.assertAlmostEqual(box.x + box.w - 12, table.x + table.w)

    def test_a_relative_box(self) -> None:
        boxes, _, _ = render(
            '<div style="position: relative; border: 1pt solid red; padding: 5pt">'
            '<p>a</p><p>b</p><div style="position: absolute; top: 0; right: 0">'
            "corner</div></div>"
        )

        self.assertEqual(1, len(boxes))
