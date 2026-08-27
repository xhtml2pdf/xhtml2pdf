import io
from unittest import TestCase
from xml.dom import minidom

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
