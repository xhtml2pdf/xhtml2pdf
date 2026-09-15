"""
The FlexContainer flowable, built by hand and measured on a real canvas.

Nothing here goes through the parser: the items are lists of flowables and
the properties are given directly. What is checked is the contract with
Platypus -- wrap, split, drawOn -- and the two hazards the module docstring
names: measuring with side effects, and drawing what was not measured.
"""

from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus.flowables import Flowable

from xhtml2pdf.builders import flex
from xhtml2pdf.builders.flex import (
    BoxStyle,
    FlexContainer,
    FlexItem,
    content_widths,
    stack_flowables,
)
from xhtml2pdf.reportlab_paragraph import Paragraph
from xhtml2pdf.util import AUTO, CSSLength
from xhtml2pdf.xhtml2pdf_reportlab import PmlKeepInFrame, PmlTable


class _Probe(Flowable):
    """A box of a fixed size that remembers where it was drawn."""

    def __init__(self, width: float, height: float) -> None:
        super().__init__()
        self.fixed = (width, height)
        self.drawn: list[tuple[float, float]] = []

    def wrap(self, availWidth, availHeight):
        self.width, self.height = self.fixed
        return self.fixed

    def minWidth(self):
        return self.fixed[0]

    def drawOn(self, canvas, x, y, _sW=0):
        self.drawn.append((round(x, 3), round(y, 3)))


def _paragraph(text: str = "x") -> Paragraph:
    return Paragraph(text, getSampleStyleSheet()["Normal"])


def _length(points: float) -> CSSLength:
    return CSSLength("length", points)


class StackFlowablesTest(TestCase):
    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    def test_heights_add_up_and_the_last_space_after_is_dropped(self) -> None:
        a, b = _Probe(10, 30), _Probe(10, 20)
        a.spaceAfter = 5
        b.spaceBefore = 8
        b.spaceAfter = 100
        entries, height = stack_flowables([a, b], 100, self.canv)
        # 30, its 5 after, the 8 before merged down to the 3 in excess of
        # that 5, then 20; b's own space after is not part of the height.
        self.assertEqual(30 + 5 + 3 + 20, height)
        self.assertEqual([0, 3], [e.before for e in entries])
        self.assertEqual([5, 100], [e.after for e in entries])

    def test_a_flowable_with_no_height_is_skipped(self) -> None:
        entries, height = stack_flowables(
            [_Probe(10, 0), _Probe(10, 7)], 100, self.canv
        )
        self.assertEqual(1, len(entries))
        self.assertEqual(7, height)


class ContentWidthsTest(TestCase):
    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    def test_a_paragraph_is_read_not_wrapped(self) -> None:
        para = _paragraph("one two three")
        low, high = content_widths([para], self.canv)
        self.assertGreater(high, low)
        self.assertFalse(hasattr(para, "blPara"), "the paragraph was wrapped")

    def test_probing_does_not_wrap_a_nested_table(self) -> None:
        # PmlTable.wrap turns "50%" into points in place; a table probed at
        # a trial width would carry that width around forever.
        table = PmlTable([["a", "b"]], colWidths=["50%", None])
        content_widths([table], self.canv)
        self.assertEqual(["50%", None], table._colWidths)

    def test_a_table_is_measured_by_its_cells(self) -> None:
        # Table.minWidth() answers 1000pt and more for three one-letter
        # cells, because the cells are KeepInFrames it cannot measure.
        cells = [
            PmlKeepInFrame(maxWidth=0, maxHeight=0, content=[_paragraph("a")]),
            "bb",
            _Probe(30, 5),
        ]
        table = PmlTable([cells], colWidths=[None, None, 40])
        low, high = content_widths([table], self.canv)
        self.assertLess(high, 200)
        self.assertGreater(low, 40)
        self.assertLessEqual(low, high)
        self.assertEqual([None, None, 40], table._colWidths)

    def test_a_keep_in_frame_is_measured_by_its_content(self) -> None:
        frame = PmlKeepInFrame(maxWidth=0, maxHeight=0, content=[_Probe(70, 5)])
        self.assertEqual((70, 70), content_widths([frame], self.canv))

    def test_the_widest_member_sets_the_width(self) -> None:
        low, high = content_widths([_Probe(30, 5), _Probe(80, 5)], self.canv)
        self.assertEqual((80, 80), (low, high))


class FlexContainerWrapTest(TestCase):
    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    @staticmethod
    def _container(items, **kwargs) -> FlexContainer:
        return FlexContainer(
            [FlexItem(content=list(i), **kw) for i, kw in items], **kwargs
        )

    def test_wrap_returns_the_available_width_and_the_tallest_item(self) -> None:
        container = self._container([([_Probe(50, 30)], {}), ([_Probe(50, 10)], {})])
        self.assertEqual((300, 30), container.wrapOn(self.canv, 300, 800))

    def test_items_share_the_width_by_flex_grow(self) -> None:
        container = self._container(
            [
                ([_Probe(10, 10)], {"flex_basis": _length(0), "flex_grow": 1}),
                ([_Probe(10, 10)], {"flex_basis": _length(0), "flex_grow": 3}),
            ]
        )
        container.wrapOn(self.canv, 400, 800)
        self.assertEqual([100, 300], [p.main_size for p in container.layout.placed])

    def test_padding_and_borders_are_outside_the_content_size(self) -> None:
        style = BoxStyle(
            paddingLeft=5,
            paddingRight=5,
            paddingTop=2,
            paddingBottom=2,
            borderLeftStyle="solid",
            borderLeftWidth=1,
        )
        container = self._container(
            [([_Probe(50, 30)], {"style": style, "flex_basis": _length(50)})]
        )
        container.wrapOn(self.canv, 300, 800)
        placed = container.layout.placed[0]
        self.assertEqual(50 + 5 + 5 + 1, placed.main_size)
        self.assertEqual(30 + 2 + 2, placed.cross_size)

    def test_the_containers_own_box_adds_to_its_height(self) -> None:
        style = BoxStyle(paddingTop=10, paddingBottom=10, spaceBefore=7)
        container = self._container([([_Probe(50, 30)], {})], style=style)
        self.assertEqual((300, 50), container.wrapOn(self.canv, 300, 800))
        self.assertEqual(7, container.getSpaceBefore())

    def test_gap_and_justify_content_reach_the_layout(self) -> None:
        container = self._container(
            [([_Probe(50, 10)], {}), ([_Probe(50, 10)], {})],
            column_gap=_length(20),
            justify_content="flex-end",
        )
        container.wrapOn(self.canv, 300, 800)
        self.assertEqual([180, 250], [p.main_pos for p in container.layout.placed])

    def test_wrap_is_memoised_for_the_same_available_size(self) -> None:
        grow = {"flex_basis": _length(0), "flex_grow": 1}
        container = self._container([([_paragraph()], grow), ([_paragraph()], grow)])
        with patch.object(flex, "stack_flowables", wraps=stack_flowables) as spy:
            container.wrapOn(self.canv, 300, 800)
            first = spy.call_count
            container.wrapOn(self.canv, 300, 800)
            self.assertEqual(first, spy.call_count)
            container.wrapOn(self.canv, 200, 800)
            self.assertGreater(spy.call_count, first)

    def test_measuring_twice_does_not_change_a_nested_table(self) -> None:
        table = PmlTable([["a", "b"]], colWidths=["50%", None])
        container = self._container([([table], {"flex_basis": _length(200)})])
        container.wrapOn(self.canv, 400, 800)
        first = list(table._colWidths)
        container.wrapOn(self.canv, 400, 800)
        self.assertEqual(first, table._colWidths)
        self.assertLessEqual(sum(first), 200)

    def test_a_column_stacks_its_items(self) -> None:
        container = self._container(
            [([_Probe(50, 30)], {}), ([_Probe(50, 10)], {})], direction="column"
        )
        self.assertEqual((300, 40), container.wrapOn(self.canv, 300, 800))
        self.assertEqual([0, 30], [p.main_pos for p in container.layout.placed])

    def test_min_width_is_the_min_content_of_the_row(self) -> None:
        container = self._container([([_Probe(30, 5)], {}), ([_Probe(80, 5)], {})])
        self.assertEqual(110, container.minWidth())


class FlexContainerSplitTest(TestCase):
    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())
        self.container = FlexContainer([FlexItem(content=[_Probe(50, 100)])])

    def test_it_returns_itself_when_it_fits(self) -> None:
        self.container.wrapOn(self.canv, 300, 800)
        self.assertEqual([self.container], self.container.splitOn(self.canv, 300, 800))

    def test_it_waits_for_the_next_frame_when_one_would_hold_it(self) -> None:
        # A page has 800 of room; this frame has 50 left.
        self.container.wrapOn(self.canv, 300, 800)
        self.assertEqual([], self.container.splitOn(self.canv, 300, 50))

    def test_taller_than_any_page_it_is_shrunk_rather_than_lost(self) -> None:
        self.container.wrapOn(self.canv, 300, 60)
        result = self.container.splitOn(self.canv, 300, 60)
        self.assertEqual(1, len(result))
        self.assertIsInstance(result[0], PmlKeepInFrame)
        self.assertEqual("shrink", result[0].mode)
        inner = result[0]._content[0]
        self.assertEqual([inner], inner.split(300, 1))


class FlexContainerDrawTest(TestCase):
    """The positions handed to drawOn are the ones wrap measured."""

    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    def _draw(self, container: FlexContainer, width=300) -> None:
        container.wrapOn(self.canv, width, 800)
        container.drawOn(self.canv, 0, 0)

    def test_a_row_is_drawn_left_to_right_from_the_top(self) -> None:
        tall, short = _Probe(50, 30), _Probe(50, 10)
        container = FlexContainer(
            [FlexItem(content=[tall]), FlexItem(content=[short])],
            align_items="flex-start",
        )
        self._draw(container)
        self.assertEqual([(0, 0)], tall.drawn)
        # 30 high container, 10 high item at the top: its bottom is at 20.
        self.assertEqual([(50, 20)], short.drawn)

    def test_flex_end_moves_the_item_down(self) -> None:
        tall, short = _Probe(50, 30), _Probe(50, 10)
        container = FlexContainer(
            [FlexItem(content=[tall]), FlexItem(content=[short])],
            align_items="flex-end",
        )
        self._draw(container)
        self.assertEqual([(50, 0)], short.drawn)

    def test_the_content_sits_inside_the_padding(self) -> None:
        probe = _Probe(50, 30)
        style = BoxStyle(paddingLeft=5, paddingTop=4, paddingBottom=1)
        container = FlexContainer([FlexItem(content=[probe], style=style)])
        self._draw(container)
        # Box is 35 high; content top is 4 below its top, 30 high.
        self.assertEqual([(5, 1)], probe.drawn)

    def test_stacked_content_keeps_the_measured_spacing(self) -> None:
        a, b = _Probe(50, 30), _Probe(50, 10)
        a.spaceAfter = 6
        container = FlexContainer([FlexItem(content=[a, b])])
        self._draw(container)
        self.assertEqual(46, container.height)
        self.assertEqual([(0, 16)], a.drawn)
        self.assertEqual([(0, 0)], b.drawn)

    def test_a_column_is_drawn_from_the_top(self) -> None:
        a, b = _Probe(50, 30), _Probe(50, 10)
        container = FlexContainer(
            [FlexItem(content=[a]), FlexItem(content=[b])], direction="column"
        )
        self._draw(container)
        self.assertEqual([(0, 10)], a.drawn)
        self.assertEqual([(0, 0)], b.drawn)

    def test_the_container_and_the_items_paint_their_boxes(self) -> None:
        item_style = BoxStyle(backColor="red")
        style = BoxStyle(backColor="blue", paddingLeft=10)
        container = FlexContainer(
            [FlexItem(content=[_Probe(50, 30)], style=item_style)], style=style
        )
        with (
            patch.object(flex, "drawBoxBackground") as background,
            patch.object(flex, "drawBoxBorders") as borders,
        ):
            self._draw(container)
        (outer, inner) = background.call_args_list
        self.assertEqual((0, 0, 300, 30), outer.args[1:5])
        self.assertIs(style, outer.args[5])
        self.assertEqual((10, 0, 50, 30), inner.args[1:5])
        self.assertIs(item_style, inner.args[5])
        # Borders go over the content: the item's first, the container's last.
        self.assertIs(item_style, borders.call_args_list[0].args[5])
        self.assertIs(style, borders.call_args_list[1].args[5])

    def test_auto_margin_pushes_the_item_to_the_end(self) -> None:
        probe = _Probe(50, 10)
        container = FlexContainer([FlexItem(content=[probe], margin_left=AUTO)])
        self._draw(container)
        self.assertEqual([(250, 0)], probe.drawn)


class FlexContainerLineSplitTest(TestCase):
    """A container that does not fit is cut between its lines."""

    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    @staticmethod
    def _three_rows(**kwargs) -> FlexContainer:
        # 200 wide items in a 300 wide container: one per line.
        items = [FlexItem(content=[_Probe(200, 30)], flex_shrink=0) for _ in range(3)]
        return FlexContainer(items, wrap="wrap", **kwargs)

    def test_split_cuts_between_flex_lines(self) -> None:
        container = self._three_rows(style=BoxStyle(paddingTop=5, paddingBottom=5))
        container.wrapOn(self.canv, 300, 800)
        self.assertEqual(100, container.height)
        head, tail = container.splitOn(self.canv, 300, 70)
        self.assertEqual((2, 1), (len(head.items), len(tail.items)))
        # The cut edges carry no padding; the outer ones keep theirs.
        self.assertEqual((5, 0), (head.style.paddingTop, head.style.paddingBottom))
        self.assertEqual((0, 5), (tail.style.paddingTop, tail.style.paddingBottom))
        self.assertEqual((300, 65), head.wrapOn(self.canv, 300, 800))
        self.assertEqual((300, 35), tail.wrapOn(self.canv, 300, 800))

    def test_the_tail_keeps_the_containers_properties(self) -> None:
        container = self._three_rows(justify_content="center", column_gap=_length(4))
        container.wrapOn(self.canv, 300, 800)
        _head, tail = container.splitOn(self.canv, 300, 40)
        self.assertEqual("center", tail.justify_content)
        self.assertEqual("wrap", tail.flex_wrap)
        self.assertEqual(4, tail.column_gap.value)

    def test_it_never_cuts_inside_a_line(self) -> None:
        container = self._three_rows()
        container.wrapOn(self.canv, 300, 800)
        # 20 of room: not even the first line fits, so nothing is cut.
        self.assertEqual([], container.splitOn(self.canv, 300, 20))

    def test_a_tail_that_fits_a_frame_waits_for_one_rather_than_shrinking(self) -> None:
        # The bug this guards: the tail of a cut container was shrunk into
        # the sliver left on the page because, as a whole, it was taller
        # than a page, though every one of its lines fits one.
        container = self._three_rows()
        container.wrapOn(self.canv, 300, 80)
        self.assertEqual([], container.splitOn(self.canv, 300, 20))

    def test_a_line_taller_than_any_frame_is_shrunk(self) -> None:
        items = [
            FlexItem(content=[_Probe(200, 30)], flex_shrink=0),
            FlexItem(content=[_Probe(200, 500)], flex_shrink=0),
        ]
        container = FlexContainer(items, wrap="wrap")
        container.wrapOn(self.canv, 300, 100)
        head, tail = container.splitOn(self.canv, 300, 50)
        self.assertEqual(1, len(head.items))
        tail.wrapOn(self.canv, 300, 100)
        (shrunk,) = tail.splitOn(self.canv, 300, 100)
        self.assertIsInstance(shrunk, PmlKeepInFrame)

    def test_a_column_is_cut_between_its_items(self) -> None:
        items = [FlexItem(content=[_Probe(50, 30)]) for _ in range(3)]
        container = FlexContainer(items, direction="column")
        container.wrapOn(self.canv, 300, 800)
        head, tail = container.splitOn(self.canv, 300, 65)
        self.assertEqual((2, 1), (len(head.items), len(tail.items)))

    def test_items_keep_their_source_order_across_the_cut(self) -> None:
        a, b, c = (_Probe(200, 30) for _ in range(3))
        items = [
            FlexItem(content=[a], flex_shrink=0, order=2),
            FlexItem(content=[b], flex_shrink=0, order=1),
            FlexItem(content=[c], flex_shrink=0, order=3),
        ]
        container = FlexContainer(items, wrap="wrap")
        container.wrapOn(self.canv, 300, 800)
        head, tail = container.splitOn(self.canv, 300, 65)
        # b (order 1) and a (order 2) are the first two lines.
        self.assertEqual([a, b], [item.content[0] for item in head.items])
        self.assertEqual([c], [item.content[0] for item in tail.items])
