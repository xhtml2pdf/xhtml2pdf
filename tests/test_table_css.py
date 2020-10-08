from io import BytesIO
from unittest import TestCase

import html5lib

from xhtml2pdf.document import pisaDocument
from xhtml2pdf.w3c.cssDOMElementInterface import CSSDOMElementInterface

HTML_CONTENT = """
<html>
<head>
    <title>None</title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <style type="text/css">
        div#foo #bar-table th,
        div#bar #bar-table th {
            background-color: #F0F0F0;
        }
    </style>
</head>
<body>
<div id="foo">
    <div id="foo-header">
        <table id="foofoo">
            <tr>
                <th>Foo</th>
                <td>Bar</td>
            </tr>
        </table>
    </div>
</div>
</body>
</html>
"""


class TableTest(TestCase):
    def test_th_has_no_css_rules(self):
        html = HTML_CONTENT

        result = BytesIO()
        pdf = pisaDocument(BytesIO(html.encode('utf-8')), result)

        parser = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom"))
        document = parser.parse(html)
        th_element = document.getElementsByTagName("th")[0]
        th_element = CSSDOMElementInterface(th_element)
        attr_name = "background-color"
        rules = pdf.cssCascade.findCSSRulesFor(th_element, attr_name)

        self.assertEqual(rules, [])
