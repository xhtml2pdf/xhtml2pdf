"""border-radius on tables and cells, which ReportLab draws for xhtml2pdf."""

from io import BytesIO
from unittest import TestCase

from reportlab.pdfgen.canvas import Canvas

from xhtml2pdf.document import pisaStory
from xhtml2pdf.xhtml2pdf_reportlab import PmlTable, RoundedTableBox


def _table(html: str) -> PmlTable:
    context = pisaStory(html.encode())
    assert context.err == 0
    return next(f for f in context.story if isinstance(f, PmlTable))


def _painters(table: PmlTable) -> list:
    return [cmd for cmd in table._bkgrndcmds if isinstance(cmd[3], RoundedTableBox)]


class _LineCanvas(Canvas):
    """A canvas that remembers every straight line ReportLab strokes."""

    def __init__(self) -> None:
        super().__init__(BytesIO())
        self.lines: list[tuple] = []

    def line(self, x1, y1, x2, y2):
        self.lines.append((x1, y1, x2, y2))
        super().line(x1, y1, x2, y2)


def _draw(table: PmlTable, width: float = 400) -> _LineCanvas:
    canvas = _LineCanvas()
    table.wrapOn(canvas, width, 800)
    table.drawOn(canvas, 0, 0)
    return canvas


class RoundedTableCommandsTest(TestCase):
    def test_a_rounded_table_paints_its_box_through_a_painter(self) -> None:
        table = _table(
            "<table style='background-color: #eee; border-radius: 8pt'>"
            "<tr><td>a</td></tr></table>"
        )
        ((cmd, begin, end, painter),) = _painters(table)
        self.assertEqual(("BACKGROUND", (0, 0), (-1, -1)), (cmd, begin, end))
        self.assertEqual("table", painter.kind)
        # The painter paints the colour; no square copy of it remains.
        plain = [c for c in table._bkgrndcmds if not isinstance(c[3], RoundedTableBox)]
        self.assertEqual([], plain)

    def test_a_rounded_cell_paints_its_box_over_its_span(self) -> None:
        table = _table(
            "<table><tr><td colspan='2' style='background-color: #eee; "
            "border-radius: 8pt'>a</td></tr><tr><td>b</td><td>c</td></tr></table>"
        )
        ((_cmd, begin, end, painter),) = _painters(table)
        self.assertEqual(((0, 0), (1, 0)), (begin, end))
        self.assertEqual("td", painter.kind)

    def test_a_rounded_row_is_ignored(self) -> None:
        table = _table(
            "<table><tr style='background-color: #eee; border-radius: 8pt'>"
            "<td>a</td></tr></table>"
        )
        self.assertEqual([], _painters(table))

    def test_without_a_radius_the_commands_are_as_before(self) -> None:
        table = _table(
            "<table style='background-color: #eee; border: 1pt solid red'>"
            "<tr><td>a</td></tr></table>"
        )
        self.assertEqual([], _painters(table))
        self.assertEqual("BACKGROUND", table._bkgrndcmds[0][0])

    def test_the_cell_content_does_not_paint_the_colour_again(self) -> None:
        # A paragraph in the cell would repaint it square, over the corners.
        context = pisaStory(
            b"<table><tr><td style='background-color: #eee; border-radius: 8pt'>"
            b"text</td></tr></table>"
        )
        table = next(f for f in context.story if isinstance(f, PmlTable))
        (cell,) = table._cellvalues[0]
        paragraph = cell._content[0]
        self.assertIsNone(paragraph.style.backColor)


class RoundedTableDrawingTest(TestCase):
    CELL = "border: 2pt solid red; border-radius: 6pt"

    def test_the_rounded_edges_are_not_drawn_as_grid_lines(self) -> None:
        table = _table(
            f"<table><tr><td style='{self.CELL}'>a</td>"
            "<td style='border: 1pt solid blue'>b</td></tr></table>"
        )
        canvas = _draw(table)
        edge = table._colpositions[1]
        # The first cell's right edge is shared with the second cell's left
        # one; the rounded cell draws it, so no straight line runs there.
        self.assertEqual(
            [], [line for line in canvas.lines if line[0] == line[2] == edge]
        )
        # The second cell's other edges are still ReportLab's lines.
        right = table._colpositions[2]
        self.assertTrue(any(line[0] == line[2] == right for line in canvas.lines))

    def test_a_split_table_is_open_at_the_cut(self) -> None:
        rows = "".join(f"<tr><td>row {i}</td></tr>" for i in range(40))
        table = _table(
            "<table style='background-color: #eee; border-radius: 8pt'>"
            f"{rows}</table>"
        )
        canvas = Canvas(BytesIO())
        table.wrapOn(canvas, 400, 800)
        head, tail = table.splitOn(canvas, 400, 200)
        self.assertEqual((False, True), (head._cutTop, head._cutBottom))
        self.assertEqual((True, False), (tail._cutTop, tail._cutBottom))
        for part, sides in (
            (head, ("Left", "Right", "Top")),
            (tail, ("Left", "Right", "Bottom")),
        ):
            part.wrapOn(canvas, 400, 800)
            part.drawOn(canvas, 0, 0)
            (box,) = part._roundedBoxes.values()
            self.assertEqual(sides, box.sides)

    def test_repeated_header_rows_make_one_box(self) -> None:
        rows = "".join(f"<tr><td>row {i}</td></tr>" for i in range(40))
        table = _table(
            "<table repeat='1' style='background-color: #eee; border-radius: 8pt'>"
            f"<tr><th>head</th></tr>{rows}</table>"
        )
        canvas = Canvas(BytesIO())
        table.wrapOn(canvas, 400, 800)
        _head, tail = table.splitOn(canvas, 400, 200)
        tail.wrapOn(canvas, 400, 800)
        tail.drawOn(canvas, 0, 0)
        (box,) = tail._roundedBoxes.values()
        # From the top of the repeated header to the bottom of the table.
        self.assertEqual(tail._rowpositions[0], box.top)
        self.assertEqual(tail._rowpositions[-1], box.bottom)
