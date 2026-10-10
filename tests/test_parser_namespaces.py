import io
import sys
from typing import Final
from xml.dom.minidom import parseString

import pytest

from xhtml2pdf.document import pisaDocument, pisaStory
from xhtml2pdf.w3c.cssDOMElementInterface import CSSDOMElementInterface


@pytest.mark.parametrize(
    ("attribute", "namespace"),
    [
        pytest.param("xml:lang", "http://www.w3.org/XML/1998/namespace", id="xml"),
        pytest.param("xmlns:lang", "http://www.w3.org/2000/xmlns/", id="xmlns"),
        pytest.param("xlink:lang", "http://www.w3.org/1999/xlink", id="xlink"),
    ],
)
def test_parser_namespace_attributes_by_backend(attribute: str, namespace: str) -> None:
    output: Final = io.BytesIO()
    declaration: Final = (
        f' xmlns:xlink="{namespace}"' if attribute.startswith("xlink:") else ""
    )
    pisaStory(
        f'<p{declaration} lang="en" {attribute}="ar">Garden</p>', xml_output=output
    )
    with parseString(output.getvalue()) as document:
        paragraph: Final = document.getElementsByTagName("p")[0]
        assert (
            paragraph.getAttribute("lang"),
            paragraph.getAttributeNS(namespace, "lang"),
        ) == ("en" if sys.version_info >= (3, 11) else "", "ar")


def test_parser_retains_pdf_language_tag() -> None:
    output: Final = io.BytesIO()
    pisaStory('<pdf:language name=""/><p>Garden</p>', xml_output=output)
    assert b'<pdf:language name="">' in output.getvalue()


def test_parser_keeps_table_selector_ancestry() -> None:
    output: Final = io.BytesIO()
    result: Final = pisaDocument(
        "<style>div#foo #bar-table th {background-color:#F0F0F0}</style>"
        '<div id="foo"><table id="foofoo"><tr><th>Foo</th><td>Bar</td></tr></table></div>',
        dest=io.BytesIO(),
        xml_output=output,
    )
    with parseString(output.getvalue()) as document:
        assert (
            result.cssCascade.findCSSRulesFor(
                CSSDOMElementInterface(document.getElementsByTagName("th")[0]),
                "background-color",
            )
            == []
        )


@pytest.mark.parametrize(
    "attribute",
    [
        pytest.param("", id="template"),
        pytest.param(' shadowrootmode="open"', id="shadow-template"),
    ],
)
def test_parser_keeps_template_content(attribute: str) -> None:
    output: Final = io.BytesIO()
    pisaStory(f"<template{attribute}><p>Garden</p></template>", xml_output=output)
    with parseString(output.getvalue()) as document:
        assert (
            document.getElementsByTagName("template")[0]
            .getElementsByTagName("p")[0]
            .toxml()
            == "<p>Garden</p>"
        )
