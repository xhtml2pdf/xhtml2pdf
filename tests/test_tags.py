import unittest
from xml.dom import minidom

from xhtml2pdf import tags


class PisaTagTestCase(unittest.TestCase):

    def test_pisa_tag_will_set_attrs_on_init(self):
        dom = minidom.parseString("<unit>test</unit>")
        element = dom.getElementsByTagName("unit")[0]
        instance = tags.pisaTag(element, "attr")
        self.assertEqual(instance.node, element)
        self.assertEqual(instance.tag, "unit")
        self.assertEqual(instance.attr, "attr")
