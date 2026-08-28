import io
from unittest import TestCase
from xml.dom import minidom

from pypdf import PdfReader

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
