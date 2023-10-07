from unittest import TestCase
from xml.dom import minidom

from xhtml2pdf import tags
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
