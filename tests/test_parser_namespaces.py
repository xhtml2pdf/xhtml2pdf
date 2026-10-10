import io
from typing import Final
from xml.dom.minidom import parseString

import pytest

from xhtml2pdf.document import pisaStory


@pytest.mark.parametrize(
    ("attribute", "namespace"),
    [
        pytest.param("xml:lang", "http://www.w3.org/XML/1998/namespace", id="xml"),
        pytest.param("xmlns:lang", "http://www.w3.org/2000/xmlns/", id="xmlns"),
        pytest.param("xlink:lang", "http://www.w3.org/1999/xlink", id="xlink"),
    ],
)
def test_parser_keeps_namespaced_attributes(attribute: str, namespace: str) -> None:
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
        ) == ("en", "ar")
