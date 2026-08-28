import io
import re
from unittest import TestCase
from xml.dom import minidom

from pypdf import PdfReader
from pypdf.generic import ArrayObject

from xhtml2pdf import pisa, tags
from xhtml2pdf.context import pisaContext
from xhtml2pdf.parser import AttrContainer, pisaGetAttributes


class PisaTagTestCase(TestCase):
    def test_pisa_tag_will_set_attrs_on_init(self) -> None:
        dom = minidom.parseString("<unit>test</unit>")
        element = dom.getElementsByTagName("unit")[0]
        attrs = AttrContainer({})
        instance = tags.pisaTag(element, attrs)
        self.assertEqual(instance.node, element)
        self.assertEqual(instance.tag, "unit")
        self.assertEqual(instance.attr, {})


class PisaTagOLTestCase(TestCase):
    def test_pisa_ol_tag_start_attr(self) -> None:
        dom = minidom.parseString('<ol start="10"><li>item</li></ol>')
        element = dom.getElementsByTagName("ol")[0]
        context = pisaContext()
        attrs = pisaGetAttributes(context, element.tagName.lower(), element.attributes)
        instance = tags.pisaTagOL(element, attrs)
        instance.start(context)
        self.assertEqual(instance.node, element)
        self.assertEqual(context.listCounter, 9)


class BadInputKeepsTheDocumentTestCase(TestCase):
    """
    Three tags used to let an exception from the value they were given escape
    and abort the conversion.

    A mistyped barcode, a chart whose JSON names no type and a <pdf:spacer/>
    without a height are all author mistakes worth a warning, not worth the
    document. Everything else in a stylesheet or in the markup degrades; these
    three did not.
    """

    @staticmethod
    def convert(body: str):
        story = io.BytesIO()
        html = f"<html><body>{body}</body></html>"
        return pisa.pisaDocument(io.StringIO(html), story)

    def assert_warns_and_converts(self, body: str, expected: str) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING") as logged:
            result = self.convert(body)

        self.assertEqual(0, result.err)
        self.assertTrue(any(expected in line for line in logged.output), logged.output)

    def test_a_value_the_symbology_cannot_encode(self) -> None:
        """reportlab raised AttributeError from inside the EAN13 widget."""
        self.assert_warns_and_converts(
            '<pdf:barcode value="abc" type="ean13"/>', "Cannot draw the EAN13 barcode"
        )

    def test_a_postal_code_that_does_not_fit(self) -> None:
        """And ValueError from the four-state one, hence the broad except."""
        self.assert_warns_and_converts(
            '<pdf:barcode value="abc" type="usps4s"/>',
            "Cannot draw the USPS_4State barcode",
        )

    def test_a_barcode_that_does_fit_is_untouched(self) -> None:
        with self.assertNoLogs("xhtml2pdf", level="WARNING"):
            self.assertEqual(
                0, self.convert('<pdf:barcode value="4006381333931" type="ean13"/>').err
            )

    def test_a_chart_with_no_type(self) -> None:
        """self.shapes[data["type"]] raised KeyError."""
        self.assert_warns_and_converts(
            '<canvas type="graph" width="200" height="100">'
            '{"data": [[1, 2]], "labels": ["a", "b"]}</canvas>',
            "with chart type None",
        )

    def test_a_chart_of_an_unknown_type(self) -> None:
        self.assert_warns_and_converts(
            '<canvas type="graph" width="200" height="100">'
            '{"type": "nosuch", "data": [[1, 2]], "labels": ["a", "b"]}</canvas>',
            "with chart type 'nosuch'",
        )

    def test_a_chart_whose_json_is_not_an_object(self) -> None:
        """data.get() on a list raised AttributeError."""
        self.assert_warns_and_converts(
            '<canvas type="graph" width="200" height="100">[1, 2]</canvas>',
            "with chart type None",
        )

    def test_a_chart_that_is_well_formed_still_draws(self) -> None:
        with self.assertNoLogs("xhtml2pdf", level="WARNING"):
            result = self.convert(
                '<canvas type="graph" width="200" height="100">'
                '{"type": "pie", "data": [[1, 2]], "labels": ["a", "b"]}</canvas>'
            )
        self.assertEqual(0, result.err)

    def test_a_spacer_with_no_height(self) -> None:
        """Spacer(1, None) raised TypeError on None + int."""
        self.assert_warns_and_converts(
            "<p>a</p><pdf:spacer/><p>b</p>", "Ignoring <pdf:spacer> with no height"
        )


class SelfClosingTocTestCase(TestCase):
    """
    <pdf:toc /> puts the table of contents where it is written.

    The HTML parser ignores the self-closing slash on an element it does not
    know, so the tag stayed open and swallowed the rest of the document; with
    the contents emitted on the closing tag, they came out at the very end of
    the PDF. Both examples shipped with this repository are written that way.
    """

    HTML = "<html><body>{toc}<h1>One</h1><p>body text</p><h1>Two</h1></body></html>"

    def text(self, toc: str) -> str:
        dest = io.BytesIO()
        result = pisa.pisaDocument(io.StringIO(self.HTML.format(toc=toc)), dest)
        self.assertEqual(0, result.err)
        dest.seek(0)
        return PdfReader(dest).pages[0].extract_text() or ""

    def assert_contents_come_first(self, toc: str) -> None:
        text = self.text(toc)
        # The heading appears twice: once in the contents, once as itself. The
        # body text sits between them only if the contents came first.
        self.assertEqual(2, text.count("One"), text)
        self.assertLess(text.index("One"), text.index("body text"), text)
        self.assertLess(text.index("Two"), text.index("body text"), text)

    def test_the_self_closing_form(self) -> None:
        self.assert_contents_come_first("<pdf:toc />")

    def test_the_paired_form(self) -> None:
        self.assert_contents_come_first("<pdf:toc></pdf:toc>")


class CanvasGraphTestCase(TestCase):
    """
    A chart fills the box its <canvas> reserved, and stays inside it.

    The two were unrelated: the canvas reserved width x height while the chart
    kept reportlab's default geometry of 180x85 at (20, 10), so it sat small in
    a corner; and a chart that asked for more in its JSON simply drew past the
    box, over whatever was beside it. On top of that the drawing carried a pale
    rectangle pinned at (115, 25) and the size of the whole canvas, so it always
    stuck out to the right and above.
    """

    CSS = (
        "@page { size: a4;"
        " @frame f { left: 10mm; right: 10mm; top: 10mm; bottom: 10mm; } }"
    )
    CHART = (
        '{{"type": "verticalbar", "data": [[1, 2, 3]],'
        ' "labels": ["a", "b", "c"]{extra}}}'
    )

    def stream(self, canvas: str) -> str:
        dest = io.BytesIO()
        html = (
            f"<html><head><style>{self.CSS}</style></head>"
            f"<body><p>before</p>{canvas}<p>after</p></body></html>"
        )
        result = pisa.pisaDocument(io.StringIO(html), dest)
        self.assertEqual(0, result.err)
        dest.seek(0)
        page = PdfReader(dest).pages[0]
        contents = page.get("/Contents").get_object()
        if isinstance(contents, ArrayObject):
            data = b"".join(item.get_object().get_data() for item in contents)
        else:
            data = contents.get_data()
        return data.decode("latin-1")

    def drawn_size(self, canvas: str) -> tuple[float, float]:
        """How wide and tall what was actually drawn is, in its own space."""
        points = [
            (float(x), float(y))
            for x, y in re.findall(
                r"([\d.-]+) ([\d.-]+) (?:l|m)\b", self.stream(canvas)
            )
        ]
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        return max(xs) - min(xs), max(ys) - min(ys)

    @staticmethod
    def canvas(width: int, height: int, extra: str = "", style: str = "") -> str:
        chart = CanvasGraphTestCase.CHART.format(extra=extra)
        return (
            f'<canvas type="graph" width="{width}" height="{height}"{style}>'
            f"{chart}</canvas>"
        )

    def test_the_chart_fills_the_canvas(self) -> None:
        """It used to keep reportlab's 180x85 whatever the canvas asked for."""
        small = self.drawn_size(self.canvas(200, 100))
        large = self.drawn_size(self.canvas(350, 180))

        self.assertGreater(large[0], small[0] + 100)
        self.assertGreater(large[1], small[1] + 50)

    def test_a_chart_that_asks_for_more_gets_room_and_says_so(self) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING") as logged:
            width, height = self.drawn_size(
                self.canvas(200, 100, extra=', "width": 400, "height": 300')
            )

        self.assertGreater(width, 200)
        self.assertGreater(height, 100)
        self.assertTrue(
            any("do not fit in its" in line for line in logged.output), logged.output
        )

    def test_css_says_how_big_the_canvas_is(self) -> None:
        """Only the width and height attributes were read before."""
        attribute_only = self.drawn_size(self.canvas(200, 100))
        with_css = self.drawn_size(
            self.canvas(200, 100, style=' style="width:300pt;height:150pt"')
        )

        self.assertGreater(with_css[0], attribute_only[0] + 50)

    def test_a_chart_wider_than_the_frame_is_scaled_down(self) -> None:
        """The frame is about 538 points wide; the canvas asks for 900."""
        scales = set(
            re.findall(
                r"([\d.]+) 0 0 ([\d.]+) [\d.-]+ [\d.-]+ cm",
                self.stream(self.canvas(900, 200)),
            )
        )

        self.assertTrue(
            any(scale != ("1", "1") for scale in scales),
            f"nothing was scaled down: {scales}",
        )

    def test_no_background_unless_it_is_asked_for(self) -> None:
        """#f8fce8, the colour of the rectangle that used to be there."""
        self.assertNotIn(".972549 .988235 .909804", self.stream(self.canvas(200, 100)))

    def test_a_background_is_drawn_where_it_belongs(self) -> None:
        canvas = self.canvas(200, 100, extra=', "background": {"fillColor": "#ff0000"}')
        stream = self.stream(canvas)

        self.assertIn("1 0 0 rg", stream)
        self.assertIn("n 0 0 200 100 re", stream)
