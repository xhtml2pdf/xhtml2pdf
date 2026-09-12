from __future__ import annotations

import time
from io import BytesIO
from unittest import TestCase

from pypdf import PdfReader

from xhtml2pdf.config.httpconfig import httpConfig
from xhtml2pdf.config.resources import ResourceAccessPolicy
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
            BytesIO(HTML.format(src=f"{self.base_url}/img/denker.png").encode()),
            dest,
            resource_policy=self.policy,
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


class ResourceSizeLimitTest(LocalServerMixin, TestCase):
    """
    A document names the server it downloads from, so the size of what comes
    back is the attacker's to choose. Nothing looked at it: the body was read
    whole, and a gzip stream was expanded whole -- 203KB on the wire reached
    209MB of resident memory, and twenty images like it took the worker.
    """

    LIMIT: int = 64 * 1024

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.policy = ResourceAccessPolicy(
            allow_private_networks=True,
            allow_local_outside_base=True,
            max_resource_bytes=cls.LIMIT,
        )

    def fetch(self, path: str) -> bytes | None:
        return getFile(f"{self.base_url}{path}", policy=self.policy).getFileContent()

    def test_a_body_within_the_limit_still_arrives(self) -> None:
        self.assertEqual(self.LIMIT, len(self.fetch(f"/large/{self.LIMIT}") or b""))

    def test_a_body_over_the_limit_is_refused(self) -> None:
        with self.assertLogs("xhtml2pdf.files", level="WARNING") as logged:
            self.assertIsNone(self.fetch(f"/large/{self.LIMIT + 1}"))
        self.assertIn("larger than", "".join(logged.output))

    def test_a_gzip_bomb_is_refused(self) -> None:
        """
        The compressed body is well within the limit; what it expands to is
        not, and only decompression can tell.
        """
        with self.assertLogs("xhtml2pdf.files", level="WARNING") as logged:
            self.assertIsNone(self.fetch(f"/gzip-bomb/{self.LIMIT * 64}"))
        self.assertIn("larger than", "".join(logged.output))

    def test_a_gzipped_body_within_the_limit_still_arrives(self) -> None:
        self.assertEqual(self.LIMIT, len(self.fetch(f"/gzip-bomb/{self.LIMIT}") or b""))

    def test_no_limit_means_no_limit(self) -> None:
        """A caller fetching its own resources can still turn the cap off."""
        policy = ResourceAccessPolicy(
            allow_private_networks=True,
            allow_local_outside_base=True,
            max_resource_bytes=None,
        )
        data = getFile(
            f"{self.base_url}/large/{self.LIMIT * 2}", policy=policy
        ).getFileContent()
        self.assertEqual(self.LIMIT * 2, len(data or b""))
