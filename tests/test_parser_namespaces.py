import io
import sys
from unittest import TestCase
from xml.dom.minidom import parseString

from xhtml2pdf.document import pisaDocument, pisaStory
from xhtml2pdf.w3c.cssDOMElementInterface import CSSDOMElementInterface


class ParserNamespaceTests(TestCase):
    @staticmethod
    def xml_output(html: str) -> bytes:
        output = io.BytesIO()
        pisaStory(html, xml_output=output)
        return output.getvalue()

    def test_namespaced_attribute_keeps_its_unprefixed_twin(self) -> None:
        # html5lib on Python 3.10 drops the plain attribute on the collision.
        plain = "en" if sys.version_info >= (3, 11) else ""
        for attribute, namespace in (
            ("xml:lang", "http://www.w3.org/XML/1998/namespace"),
            ("xmlns:lang", "http://www.w3.org/2000/xmlns/"),
            ("xlink:lang", "http://www.w3.org/1999/xlink"),
        ):
            with self.subTest(attribute):
                declaration = (
                    f' xmlns:xlink="{namespace}"'
                    if attribute.startswith("xlink:")
                    else ""
                )
                with parseString(
                    self.xml_output(
                        f'<p{declaration} lang="en" {attribute}="ar">Garden</p>'
                    )
                ) as document:
                    paragraph = document.getElementsByTagName("p")[0]
                    self.assertEqual(
                        (plain, "ar"),
                        (
                            paragraph.getAttribute("lang"),
                            paragraph.getAttributeNS(namespace, "lang"),
                        ),
                    )

    def test_pdf_language_tag_is_kept(self) -> None:
        self.assertIn(
            b'<pdf:language name="">',
            self.xml_output('<pdf:language name=""/><p>Garden</p>'),
        )

    def test_table_selector_ancestry_is_kept(self) -> None:
        output = io.BytesIO()
        result = pisaDocument(
            "<style>div#foo #bar-table th {background-color:#F0F0F0}</style>"
            '<div id="foo"><table id="foofoo"><tr><th>Foo</th><td>Bar</td></tr></table></div>',
            dest=io.BytesIO(),
            xml_output=output,
        )
        with parseString(output.getvalue()) as document:
            self.assertEqual(
                [],
                result.cssCascade.findCSSRulesFor(
                    CSSDOMElementInterface(document.getElementsByTagName("th")[0]),
                    "background-color",
                ),
            )

    def test_template_content_is_kept(self) -> None:
        for attribute in ("", ' shadowrootmode="open"'):
            with (
                self.subTest(attribute or "template"),
                parseString(
                    self.xml_output(f"<template{attribute}><p>Garden</p></template>")
                ) as document,
            ):
                self.assertEqual(
                    "<p>Garden</p>",
                    document.getElementsByTagName("template")[0]
                    .getElementsByTagName("p")[0]
                    .toxml(),
                )
