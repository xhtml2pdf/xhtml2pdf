"""
display: flex through the parser: what pisaLoop makes of a container.

The flowable's own behaviour is tests/test_flex_flowable.py; here the
question is whether the walk collects the right items with the right
properties, restores every story it swapped, and keeps the container's box
off its items.
"""

import io
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.builders.flex import FlexContainer
from xhtml2pdf.document import pisaStory
from xhtml2pdf.xhtml2pdf_reportlab import PmlParagraph, PmlTable


def _containers(html: str) -> list[FlexContainer]:
    context = pisaStory(html)
    assert context.err == 0
    return [f for f in context.story if isinstance(f, FlexContainer)]


def _container(html: str) -> FlexContainer:
    containers = _containers(html)
    assert len(containers) == 1, containers
    return containers[0]


class FlexItemsTest(TestCase):
    def test_a_flex_container_becomes_one_flowable(self) -> None:
        context = pisaStory(
            "<p>before</p>"
            "<div style='display:flex'><div>a</div><div>b</div></div>"
            "<p>after</p>"
        )
        kinds = [type(f).__name__ for f in context.story]
        self.assertEqual(1, kinds.count("FlexContainer"))
        self.assertLess(kinds.index("PmlParagraph"), kinds.index("FlexContainer"))
        self.assertGreater(len(kinds) - 1, kinds.index("FlexContainer"))

    def test_each_element_child_is_one_item(self) -> None:
        container = _container(
            "<div style='display:flex'><div>a</div><p>b</p><span>c</span></div>"
        )
        self.assertEqual(3, len(container.items))
        for item in container.items:
            self.assertIsInstance(item.content[0], PmlParagraph)

    def test_whitespace_between_items_is_not_an_item(self) -> None:
        container = _container(
            "<div style='display:flex'>\n  <div>a</div>\n  <!-- x -->\n  <div>b</div>\n</div>"
        )
        self.assertEqual(2, len(container.items))

    def test_display_none_child_is_not_an_item(self) -> None:
        container = _container(
            "<div style='display:flex'><div>a</div>"
            "<div style='display:none'>hidden</div><div>b</div></div>"
        )
        self.assertEqual(2, len(container.items))

    def test_text_straight_inside_the_container_is_an_anonymous_item(self) -> None:
        container = _container("<div style='display:flex'>loose<div>a</div></div>")
        self.assertEqual(2, len(container.items))
        self.assertEqual(0.0, container.items[0].flex_grow)

    def test_an_empty_container_emits_nothing(self) -> None:
        self.assertEqual([], _containers("<div style='display:flex'>  </div>"))

    def test_inline_flex_is_a_container_too(self) -> None:
        container = _container(
            "<span style='display:inline-flex'><b>a</b><i>b</i></span>"
        )
        self.assertEqual(2, len(container.items))


class FlexPropertiesTest(TestCase):
    def test_align_items_baseline_reaches_the_flowable(self) -> None:
        container = _container(
            "<div style='display:flex; align-items: baseline'>"
            "<div>a</div><div style='font-size: 20pt'>b</div></div>"
        )
        self.assertEqual("baseline", container.align_items)

    def test_item_properties_are_read_from_the_child_not_the_container(self) -> None:
        container = _container(
            "<div style='display:flex; flex-grow: 9'>"
            "<div style='flex: 2 0 10pt; order: -1; align-self: center'>a</div>"
            "<div>b</div></div>"
        )
        first, second = container.items
        self.assertEqual(
            (2.0, 0.0, 10.0),
            (first.flex_grow, first.flex_shrink, first.flex_basis.value),
        )
        self.assertEqual(-1, first.order)
        self.assertEqual("center", first.align_self)
        self.assertEqual(
            (0.0, 1.0, "auto"),
            (second.flex_grow, second.flex_shrink, second.flex_basis.kind),
        )

    def test_container_properties_reach_the_flowable(self) -> None:
        container = _container(
            "<div style='display:flex; flex-flow: column wrap; justify-content: space-between;"
            " align-items: flex-end; gap: 12pt 6pt'><div>a</div></div>"
        )
        self.assertEqual("column", container.direction)
        self.assertEqual("wrap", container.flex_wrap)
        self.assertEqual("space-between", container.justify_content)
        self.assertEqual("flex-end", container.align_items)
        self.assertEqual(
            (12.0, 6.0), (container.row_gap.value, container.column_gap.value)
        )

    def test_flex_properties_do_not_inherit_into_a_nested_container(self) -> None:
        outer = _container(
            "<div style='display:flex'><div style='flex-grow: 2; order: 5'>"
            "<div style='display:flex'><div>x</div></div></div></div>"
        )
        inner = outer.items[0].content[0]
        self.assertIsInstance(inner, FlexContainer)
        self.assertEqual(0.0, inner.items[0].flex_grow)
        self.assertEqual(0, inner.items[0].order)

    def test_item_margins_come_from_the_declarations(self) -> None:
        container = _container(
            "<div style='display:flex'>"
            "<div style='margin-left: auto; margin-top: 8pt'>a</div></div>"
        )
        item = container.items[0]
        self.assertEqual("auto", item.margin_left.kind)
        self.assertEqual(8.0, item.margin_top.value)
        self.assertEqual(0.0, item.margin_right.value)

    def test_the_containers_own_size_does_not_become_the_items(self) -> None:
        # CSS does not inherit width or height. Before properties.py reset
        # them per element the frag carried them down the clone, so every
        # item of a sized container took that size as its own: a row with
        # height: 26pt gave each item a 26pt height, which made the item's
        # cross size definite and stopped align-items: stretch from ever
        # sizing it to the line.
        container = _container(
            "<div style='display:flex; width: 200pt; height: 26pt'>"
            "<div>a</div><div style='height: 12pt'>b</div></div>"
        )
        first, second = container.items
        self.assertEqual("auto", first.width.kind)
        self.assertEqual("auto", first.height.kind)
        # The item's own declaration still lands.
        self.assertEqual(("length", 12.0), second.height)

    def test_a_block_does_not_hand_its_width_to_what_is_inside_it(self) -> None:
        container = _container(
            "<div style='width: 300pt'><div style='display:flex'>"
            "<div>a</div></div></div>"
        )
        self.assertEqual("auto", container.css_width.kind)
        self.assertEqual("auto", container.items[0].width.kind)

    def test_width_and_height_become_the_items_size(self) -> None:
        container = _container(
            "<div style='display:flex'><div style='width: 50%; height: 30pt'>a</div></div>"
        )
        item = container.items[0]
        self.assertEqual(("percent", 50.0), item.width)
        self.assertEqual(("length", 30.0), item.height)


class FlexBoxesTest(TestCase):
    def test_the_container_paints_its_own_box_and_the_items_do_not(self) -> None:
        container = _container(
            "<div style='display:flex; background-color: #ff0000; padding: 8pt;"
            " border: 2pt solid #0000ff; margin-left: 10pt'><div>a</div></div>"
        )
        style = container.style
        self.assertEqual(8.0, style.paddingLeft)
        self.assertEqual("solid", style.borderTopStyle)
        self.assertEqual(10.0, style.leftIndent)
        self.assertIsNotNone(style.backColor)
        paragraph = container.items[0].content[0]
        self.assertEqual(0, paragraph.style.paddingLeft)
        self.assertEqual(0, paragraph.style.leftIndent)
        self.assertIsNone(paragraph.style.backColor)
        self.assertEqual(0, container.items[0].style.paddingLeft)

    def test_the_items_box_is_painted_once(self) -> None:
        container = _container(
            "<div style='display:flex'>"
            "<div style='padding: 6pt; background-color: #00ff00'><p>a</p></div></div>"
        )
        item = container.items[0]
        self.assertEqual(6.0, item.style.paddingTop)
        self.assertIsNotNone(item.style.backColor)
        paragraph = item.content[0]
        self.assertEqual(0, paragraph.style.paddingTop)
        self.assertIsNone(paragraph.style.backColor)

    def test_margins_are_not_applied_twice_inside_an_item(self) -> None:
        container = _container(
            "<div style='display:flex; margin-left: 20pt'>"
            "<div style='margin-left: 10pt'><p style='margin-left: 5pt'>x</p></div></div>"
        )
        self.assertEqual(20.0, container.style.leftIndent)
        item = container.items[0]
        self.assertEqual(10.0, item.margin_left.value)
        # The paragraph's own margin, and nothing above it.
        self.assertEqual(5.0, item.content[0].style.leftIndent)

    def test_an_inline_child_is_blockified(self) -> None:
        container = _container(
            "<div style='display:flex'><span style='padding: 4pt'>a</span></div>"
        )
        self.assertEqual(4.0, container.items[0].style.paddingLeft)


class FlexNestingTest(TestCase):
    def test_a_container_inside_a_table_cell_restores_the_story(self) -> None:
        context = pisaStory(
            "<table><tr><td><div style='display:flex'><div>a</div></div></td></tr></table>"
            "<p>after</p>"
        )
        kinds = [type(f).__name__ for f in context.story]
        self.assertIn("PmlTable", kinds)
        self.assertNotIn("FlexContainer", kinds)
        self.assertEqual("PmlParagraph", kinds[-1])
        table = next(f for f in context.story if isinstance(f, PmlTable))
        cell = table._cellvalues[0][0]
        self.assertTrue(any(isinstance(f, FlexContainer) for f in cell._content))

    def test_a_table_inside_an_item_still_renders(self) -> None:
        container = _container(
            "<div style='display:flex'><div><table><tr><td>a</td></tr></table></div>"
            "<div>b</div></div>"
        )
        self.assertTrue(
            any(isinstance(f, PmlTable) for f in container.items[0].content)
        )

    def test_nested_containers_nest(self) -> None:
        outer = _container(
            "<div style='display:flex'><div style='display:flex'><div>a</div>"
            "<div>b</div></div><div>c</div></div>"
        )
        self.assertEqual(2, len(outer.items))
        inner = outer.items[0].content[0]
        self.assertIsInstance(inner, FlexContainer)
        self.assertEqual(2, len(inner.items))

    def test_keep_in_frame_wraps_the_container(self) -> None:
        context = pisaStory(
            "<div style='display:flex; -pdf-keep-in-frame-mode: shrink'>"
            "<div>a</div></div>"
        )
        kinds = [type(f).__name__ for f in context.story]
        self.assertIn("KeepInFrame", kinds)
        self.assertNotIn("FlexContainer", kinds)

    def test_right_to_left_starts_at_the_right(self) -> None:
        container = _container(
            "<body dir='rtl'><div style='display:flex'><div>a</div></div>"
            "</body></html>"
        )
        self.assertEqual("row-reverse", container.direction)

    def test_the_direction_is_read_from_the_html_element_too(self) -> None:
        # <body dir> and <div dir> were honoured but <html dir> was not, and
        # the root element is where a document usually declares it.
        container = _container(
            "<html dir='rtl'><body><div style='display:flex'><div>a</div></div>"
            "</body></html>"
        )
        self.assertEqual("row-reverse", container.direction)


class FlexRenderTest(TestCase):
    """End to end: the PDF comes out, and the items share a line."""

    @staticmethod
    def _render(html: str) -> PdfReader:
        out = io.BytesIO()
        result = pisa.CreatePDF(html, dest=out)
        assert not result.err
        return PdfReader(io.BytesIO(out.getvalue()))

    def test_two_items_share_one_line(self) -> None:
        reader = self._render(
            "<div style='display:flex'><div style='flex:1'>LEFT</div>"
            "<div style='flex:1'>RIGHT</div></div>"
        )
        placed: dict[str, tuple[float, float]] = {}

        def visitor(text, cm, tm, _font, _size) -> None:
            # The paragraph is drawn translated (cm); the text sits at tm
            # inside it. Both are translations here.
            if text.strip():
                placed[text.strip()] = (cm[4] + tm[4], cm[5] + tm[5])

        reader.pages[0].extract_text(visitor_text=visitor)
        self.assertIn("LEFT", placed)
        self.assertIn("RIGHT", placed)
        # Same baseline, and RIGHT to the right of LEFT.
        self.assertAlmostEqual(placed["LEFT"][1], placed["RIGHT"][1], places=1)
        self.assertLess(placed["LEFT"][0], placed["RIGHT"][0])

    def test_a_container_with_a_box_and_a_nested_table_renders(self) -> None:
        reader = self._render(
            "<div style='display:flex; border: 1pt solid #000; padding: 4pt;"
            " background-color: #eee; gap: 8pt'>"
            "<div style='flex: 0 0 100pt; background-color: #ccc'>SIDE</div>"
            "<div style='flex: 1'><table><tr><td>CELL</td></tr></table></div></div>"
        )
        text = reader.pages[0].extract_text()
        self.assertIn("SIDE", text)
        self.assertIn("CELL", text)


class FlexWrapTest(TestCase):
    def test_wrap_makes_lines(self) -> None:
        from io import BytesIO

        from reportlab.pdfgen.canvas import Canvas

        container = _container(
            "<div style='display:flex; flex-wrap: wrap; gap: 10pt'>"
            + "".join(f"<div style='flex: 0 0 200pt'>{n}</div>" for n in range(4))
            + "</div>"
        )
        container.wrapOn(Canvas(BytesIO()), 500, 800)
        self.assertEqual(2, len(container.layout.lines))
        self.assertEqual([2, 2], [len(line.items) for line in container.layout.lines])

    def test_a_long_wrapped_container_splits_across_pages(self) -> None:
        html = (
            "<div style='display:flex; flex-wrap: wrap'>"
            + "".join(
                f"<div style='flex: 0 0 45%; height: 60pt'>item {n}</div>"
                for n in range(40)
            )
            + "</div>"
        )
        out = io.BytesIO()
        result = pisa.CreatePDF(html, dest=out)
        self.assertFalse(result.err)
        reader = PdfReader(io.BytesIO(out.getvalue()))
        self.assertGreater(len(reader.pages), 1)
        text = "".join(page.extract_text() for page in reader.pages)
        self.assertIn("item 0", text)
        self.assertIn("item 39", text)
