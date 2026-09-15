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
    _FlexFragment,
    content_widths,
    flowable_baseline,
    flowable_last_baseline,
    split_stack,
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


class _SplitProbe(_Probe):
    """A probe that splits at multiples of `step`, and remembers the room asked."""

    def __init__(self, width: float, height: float, step: float) -> None:
        super().__init__(width, height)
        self.step = step
        self.asked: list[float] = []

    def split(self, availWidth, availHeight):
        self.asked.append(availHeight)
        fits = int(availHeight / self.step + 1e-6) * self.step
        if fits <= 0:
            return []
        return [
            _Probe(self.fixed[0], fits),
            _SplitProbe(self.fixed[0], self.fixed[1] - fits, self.step),
        ]


def _paragraph(text: str = "x") -> Paragraph:
    return Paragraph(text, getSampleStyleSheet()["Normal"])


def _length(points: float) -> CSSLength:
    return CSSLength("length", points)


def _baseline(flowable) -> float:
    value = flowable_baseline(flowable)
    assert value is not None
    return value


def _last_baseline(flowable) -> float:
    value = flowable_last_baseline(flowable)
    assert value is not None
    return value


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


class SplitStackTest(TestCase):
    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    def _entries(self, *flowables):
        entries, _height = stack_flowables(flowables, 100, self.canv)
        return entries

    def test_entries_above_the_cut_go_to_the_head_and_the_rest_to_the_tail(self):
        first, second = _Probe(50, 30), _Probe(50, 30)
        head, tail = split_stack(self._entries(first, second), 30, 100, self.canv)
        self.assertEqual(([first], [second]), (head, tail))

    def test_the_crossing_flowable_is_asked_for_the_room_below_its_top(self) -> None:
        first, second = _Probe(50, 30), _SplitProbe(50, 100, 10)
        head, tail = split_stack(self._entries(first, second), 45, 100, self.canv)
        self.assertEqual([15], second.asked)
        self.assertEqual([first, 10], [head[0], head[1].fixed[1]])
        self.assertEqual([90], [f.fixed[1] for f in tail])

    def test_a_flowable_that_refuses_goes_whole_to_the_tail_with_what_follows(
        self,
    ) -> None:
        first, second = _SplitProbe(50, 100, 10), _Probe(50, 30)
        head, tail = split_stack(self._entries(first, second), 5, 100, self.canv)
        self.assertEqual(([], [first, second]), (head, tail))

    def test_nothing_above_the_first_flowable_gives_an_empty_head(self) -> None:
        first = _SplitProbe(50, 100, 10)
        head, tail = split_stack(self._entries(first), 0, 100, self.canv)
        self.assertEqual(([], [first]), (head, tail))
        self.assertEqual([], first.asked)


class FlexContainerCutTest(TestCase):
    """A page cut inside a flex line, through its items."""

    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    def _cut(self, container, room, width=300):
        container.wrapOn(self.canv, width, 800)
        head, tail = container.splitOn(self.canv, width, room)
        return head, tail

    def test_a_line_is_cut_at_the_page_edge(self) -> None:
        container = FlexContainer([FlexItem(content=[_SplitProbe(200, 100, 10)])])
        head, tail = self._cut(container, 45)
        self.assertEqual(45, head.height)
        self.assertEqual((300, 60), tail.wrapOn(self.canv, 300, 800))

    def test_the_head_is_a_fragment_that_keeps_its_size_and_never_splits(self):
        container = FlexContainer([FlexItem(content=[_SplitProbe(200, 100, 10)])])
        head, _tail = self._cut(container, 45)
        self.assertIsInstance(head, _FlexFragment)
        self.assertEqual((300, 45), head.wrapOn(self.canv, 300, 45))
        self.assertEqual([head], head.splitOn(self.canv, 300, 45))

    def test_the_cut_item_loses_its_bottom_edge_and_the_tail_its_top(self) -> None:
        style = BoxStyle(
            paddingTop=3,
            paddingBottom=4,
            borderTopStyle="solid",
            borderTopWidth=1,
            borderBottomStyle="solid",
            borderBottomWidth=1,
        )
        container = FlexContainer(
            [FlexItem(content=[_SplitProbe(200, 100, 10)], style=style)]
        )
        head, tail = self._cut(container, 45)
        (top,) = head.items
        (bottom,) = tail.items
        self.assertEqual(
            (3, 0, None),
            (
                top.style.paddingTop,
                top.style.paddingBottom,
                top.style.borderBottomStyle,
            ),
        )
        self.assertEqual("solid", top.style.borderTopStyle)
        self.assertEqual(
            (0, 4, None),
            (
                bottom.style.paddingTop,
                bottom.style.paddingBottom,
                bottom.style.borderTopStyle,
            ),
        )
        self.assertEqual("solid", bottom.style.borderBottomStyle)

    def test_the_tail_line_keeps_the_main_sizes_of_the_cut_line(self) -> None:
        container = FlexContainer(
            [
                FlexItem(
                    content=[_SplitProbe(10, 100, 10)],
                    flex_grow=1,
                    flex_basis=_length(0),
                ),
                FlexItem(content=[_Probe(10, 20)], flex_grow=3, flex_basis=_length(0)),
            ]
        )
        _head, tail = self._cut(container, 45, width=400)
        self.assertEqual(2, len(tail.items))
        self.assertEqual([], tail.items[1].content)  # a ghost, holding its place
        tail.wrapOn(self.canv, 400, 800)
        self.assertEqual([100, 300], [p.main_size for p in tail.layout.placed])

    def test_an_item_that_ends_above_the_cut_is_drawn_whole_in_the_head(self):
        short = _Probe(100, 20)
        container = FlexContainer(
            [FlexItem(content=[_SplitProbe(100, 100, 10)]), FlexItem(content=[short])]
        )
        head, _tail = self._cut(container, 45)
        head.drawOn(self.canv, 0, 0)
        self.assertEqual(1, len(short.drawn))

    def test_an_item_that_starts_below_the_cut_goes_to_the_tail_with_its_offset(
        self,
    ) -> None:
        short = _Probe(100, 20)
        container = FlexContainer(
            [FlexItem(content=[_SplitProbe(100, 100, 10)]), FlexItem(content=[short])],
            align_items="flex-end",
        )
        _head, tail = self._cut(container, 45)
        moved = tail.items[1]
        self.assertEqual([short], moved.content)
        self.assertEqual(35, moved.margin_top.value)

    def test_lines_that_fit_join_the_cut_line_in_the_head(self) -> None:
        items = [
            FlexItem(content=[_SplitProbe(200, 30, 10)], flex_shrink=0)
            for _ in range(3)
        ]
        container = FlexContainer(items, wrap="wrap")
        head, tail = self._cut(container, 75)
        self.assertEqual(75, head.height)
        self.assertEqual((3, 1), (len(head.items), len(tail.items)))
        self.assertEqual(200, tail.items[0].pinned_main)
        self.assertEqual([20], [f.fixed[1] for f in tail.items[0].content])

    def test_a_column_item_is_cut(self) -> None:
        container = FlexContainer(
            [
                FlexItem(content=[_Probe(50, 30)]),
                FlexItem(content=[_SplitProbe(50, 100, 10)]),
            ],
            direction="column",
        )
        head, tail = self._cut(container, 65)
        self.assertEqual(65, head.height)
        self.assertEqual((300, 70), tail.wrapOn(self.canv, 300, 800))

    def test_a_paragraph_is_cut_between_its_lines(self) -> None:
        para = _paragraph("word " * 200)
        container = FlexContainer([FlexItem(content=[para])])
        container.wrapOn(self.canv, 100, 800)
        total = len(para.blPara.lines)
        self.assertGreater(total, 20)
        head, tail = container.splitOn(self.canv, 100, 100)
        # leading 12: eight lines fit in 100.
        (first,) = head.items[0].content
        self.assertEqual(8, len(first.blPara.lines))
        tail.wrapOn(self.canv, 100, 800)
        (second,) = tail.items[0].content
        self.assertEqual(total - 8, len(second.blPara.lines))

    def test_a_declared_height_is_shared_by_the_halves(self) -> None:
        container = FlexContainer(
            [FlexItem(content=[_Probe(50, 100)])], height=_length(500)
        )
        head, tail = self._cut(container, 300)
        self.assertEqual(300, head.height)
        self.assertEqual(200, tail.css_height.value)
        self.assertEqual((300, 200), tail.wrapOn(self.canv, 300, 800))

    def test_a_declared_height_container_no_longer_overflows_after_the_cut(self):
        # The bug this guards: both halves took the whole declared height,
        # and the head then did not fit the room it was cut for.
        items = [FlexItem(content=[_Probe(200, 30)], flex_shrink=0) for _ in range(3)]
        container = FlexContainer(
            items, wrap="wrap", align_content="stretch", height=_length(500)
        )
        head, tail = self._cut(container, 300)
        self.assertLessEqual(head.wrapOn(self.canv, 300, 300)[1], 300)
        self.assertEqual(200, tail.css_height.value)

    def test_the_cut_items_background_reaches_the_edge(self) -> None:
        container = FlexContainer(
            [
                FlexItem(
                    content=[_SplitProbe(200, 100, 10)],
                    style=BoxStyle(backColor="#eee"),
                )
            ]
        )
        head, _tail = self._cut(container, 45)
        rects = []
        with patch.object(
            flex, "drawBoxBackground", lambda _c, _x, y, _w, h, _s: rects.append((y, h))
        ):
            head.drawOn(self.canv, 0, 0)
        self.assertIn((0, 45), [(round(y, 3), round(h, 3)) for y, h in rects])

    def test_a_nested_container_is_cut_through(self) -> None:
        inner = FlexContainer([FlexItem(content=[_SplitProbe(200, 100, 10)])])
        outer = FlexContainer([FlexItem(content=[inner])])
        head, tail = self._cut(outer, 45)
        (inner_head,) = head.items[0].content
        (inner_tail,) = tail.items[0].content
        self.assertIsInstance(inner_head, _FlexFragment)
        self.assertEqual(45, inner_head.height)
        self.assertIsInstance(inner_tail, FlexContainer)
        self.assertEqual((300, 60), tail.wrapOn(self.canv, 300, 800))

    def test_a_refused_paragraph_is_wrapped_again_before_drawing(self) -> None:
        # Two lines: an orphan rule refuses to split, and Paragraph.split
        # drops the lines it broke on the way out. The container must not
        # draw from what it measured before that.
        para = _paragraph("word " * 12)
        container = FlexContainer([FlexItem(content=[para])])
        container.wrapOn(self.canv, 100, 800)
        self.assertGreaterEqual(len(para.blPara.lines), 2)
        # 15 of room holds one line, which the orphan rule refuses.
        self.assertEqual([], container.splitOn(self.canv, 100, 15))
        container.wrapOn(self.canv, 100, 800)
        container.drawOn(self.canv, 0, 0)


class FlexContainerBaselineTest(TestCase):
    def setUp(self) -> None:
        self.canv = Canvas(BytesIO())

    @staticmethod
    def _sized(size: float, text: str = "x") -> Paragraph:
        style = getSampleStyleSheet()["Normal"].clone(
            "s", fontSize=size, leading=size * 1.2
        )
        return Paragraph(text, style)

    def test_paragraphs_of_two_sizes_share_a_baseline(self) -> None:
        small, big = self._sized(10), self._sized(20)
        container = FlexContainer(
            [FlexItem(content=[small]), FlexItem(content=[big])], align_items="baseline"
        )
        container.wrapOn(self.canv, 300, 800)
        first, second = container.layout.placed
        self.assertEqual(0, second.cross_pos)
        self.assertAlmostEqual(_baseline(big) - _baseline(small), first.cross_pos)

    def test_a_probe_has_no_baseline_and_sits_on_its_bottom(self) -> None:
        container = FlexContainer(
            [FlexItem(content=[_Probe(50, 30)]), FlexItem(content=[_Probe(50, 10)])],
            align_items="baseline",
        )
        container.wrapOn(self.canv, 300, 800)
        self.assertEqual([0, 20], [p.cross_pos for p in container.layout.placed])

    def test_the_items_top_padding_and_border_sit_above_its_baseline(self) -> None:
        para = self._sized(10)
        padded = BoxStyle(paddingTop=7, borderTopStyle="solid", borderTopWidth=2)
        container = FlexContainer(
            [
                FlexItem(content=[self._sized(10)]),
                FlexItem(content=[para], style=padded),
            ],
            align_items="baseline",
        )
        container.wrapOn(self.canv, 300, 800)
        first, second = container.layout.placed
        self.assertEqual(0, second.cross_pos)
        self.assertAlmostEqual(9, first.cross_pos)

    def test_a_nested_container_lends_its_first_items_baseline(self) -> None:
        inner = FlexContainer([FlexItem(content=[self._sized(20)])])
        outer = FlexContainer(
            [FlexItem(content=[self._sized(10)]), FlexItem(content=[inner])],
            align_items="baseline",
        )
        outer.wrapOn(self.canv, 300, 800)
        first, second = outer.layout.placed
        self.assertEqual(0, second.cross_pos)
        self.assertGreater(first.cross_pos, 0)
        first_baseline = inner.first_baseline()
        assert first_baseline is not None
        self.assertAlmostEqual(first_baseline, _baseline(inner))

    def test_first_baseline_is_none_before_wrap(self) -> None:
        container = FlexContainer([FlexItem(content=[self._sized(10)])])
        self.assertIsNone(container.first_baseline())
        container.wrapOn(self.canv, 300, 800)
        self.assertIsNotNone(container.first_baseline())

    def test_the_last_baseline_of_a_paragraph_is_its_descent(self) -> None:
        para = self._sized(10, " ".join(["word"] * 40))
        para.wrapOn(self.canv, 100, 800)
        self.assertGreater(len(para.blPara.lines), 3)
        last = _last_baseline(para)
        # Between the descent of a 10pt line and the leading below it.
        self.assertGreater(last, 1)
        self.assertLess(last, 12)
        # The baselines are a leading apart: first from the top, last from
        # the bottom, and the lines in between.
        n = len(para.blPara.lines)
        self.assertAlmostEqual(
            para.height, _baseline(para) + 12 * (n - 1) + last, places=6
        )

    def test_a_probe_has_no_last_baseline(self) -> None:
        self.assertIsNone(flowable_last_baseline(_Probe(10, 10)))


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

    def test_a_line_with_nothing_to_show_above_the_cut_moves_whole(self) -> None:
        container = self._three_rows()
        container.wrapOn(self.canv, 300, 800)
        # 20 of room inside a line of probes that cannot split: nothing to
        # show above the cut, so the line waits for the next frame.
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
