from __future__ import annotations

import time
from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf.config.httpconfig import httpConfig
from xhtml2pdf.context import pisaContext
from xhtml2pdf.document import pisaDocument
from xhtml2pdf.files import getFile
from xhtml2pdf.parser import pisaParser

from .httpserver import LocalServerMixin

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/><title></title></head>
<body><h1>works</h1><img src="{src}" alt=""/></body></html>
"""


class HttpTest(LocalServerMixin, TestCase):
    def test_remote_image_is_embedded(self) -> None:
        dest = BytesIO()
        result = pisaDocument(
            BytesIO(HTML.format(src=f"{self.base_url}/img/denker.png").encode()), dest
        )
        self.assertEqual(0, result.err)

        dest.seek(0)
        page = PdfReader(dest).pages[0]
        xobjects = page["/Resources"]["/XObject"]
        self.assertEqual(
            1, sum(1 for name in xobjects if xobjects[name]["/Subtype"] == "/Image")
        )

    def test_slow_request_honours_the_configured_timeout(self) -> None:
        """
        Regression: httpConfig was only splatted into HTTPSConnection, so plain
        http requests were made with no timeout at all and could hang forever.
        """
        self.assertGreater(httpConfig["timeout"], 0)

        timeout = 0.5
        original = httpConfig["timeout"]
        httpConfig["timeout"] = timeout
        try:
            started = time.monotonic()
            with self.assertLogs("xhtml2pdf.files", level="ERROR"):
                data = getFile(f"{self.base_url}/slow/30").getFileContent()
            elapsed = time.monotonic() - started
        finally:
            httpConfig["timeout"] = original

        self.assertIsNone(data)
        # three attempts, each capped by the timeout, plus generous slack
        self.assertLess(elapsed, timeout * 3 + 5)

    def test_parser_survives_an_unreachable_image(self) -> None:
        """A failing image must not abort the parse."""
        context = pisaParser(
            BytesIO(HTML.format(src=f"{self.base_url}/status/404").encode()),
            pisaContext(),
        )
        self.assertEqual(0, context.err)
