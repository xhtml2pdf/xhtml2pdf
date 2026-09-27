"""
The limits a server rendering untrusted HTML needs, one test per limit.

``ResourceAccessPolicy`` has bounded network fetches since 0.2.19, but every
other way a document can make a worker spend memory or time was open: a local
file or a ``data:`` URI was read whole, whatever its size. Each limit here is
off by default, for compatibility, and on in ``ResourceAccessPolicy.server()``.
Hitting one must be a logged refusal, never a crash or a hang.
"""

from __future__ import annotations

import base64
import io
import re
import struct
import tempfile
import time
import zlib
from pathlib import Path
from unittest import TestCase, mock

from pypdf import PdfReader
from reportlab.platypus import Spacer

from xhtml2pdf import pisa
from xhtml2pdf.config.resources import (
    RenderLimitError,
    ResourceAccessError,
    ResourceAccessPolicy,
    render_budget,
    use_policy,
)
from xhtml2pdf.files import getFile
from xhtml2pdf.xhtml2pdf_reportlab import PmlBaseDoc, PmlImage, looks_like_svg

from .httpserver import LocalServerMixin


class LocalSizeLimitTest(TestCase):
    """``max_local_bytes``: local files and ``data:`` URIs."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.policy = ResourceAccessPolicy(base_dir=self.base, max_local_bytes=1000)

    def write(self, name: str, size: int) -> Path:
        path = self.base / name
        path.write_bytes(b"x" * size)
        return path

    def test_a_local_file_over_the_limit_is_refused(self) -> None:
        self.write("big.png", 1001)
        with (
            use_policy(self.policy),
            self.assertLogs("xhtml2pdf.files", level="WARNING") as logs,
        ):
            self.assertIsNone(getFile("big.png", str(self.base)).getData())

        self.assertIn("Blocked by the resource policy", logs.output[0])
        self.assertIn("1000 bytes", logs.output[0])

    def test_a_local_file_at_the_limit_is_read(self) -> None:
        self.write("fits.png", 1000)
        with use_policy(self.policy):
            data = getFile("fits.png", str(self.base)).getData()

        self.assertEqual(1000, len(data or b""))

    def test_the_size_is_checked_before_the_file_is_read(self) -> None:
        """A 200 MiB file must be refused from its size, not after reading it."""
        path = self.base / "sparse.png"
        with path.open("wb") as handle:
            handle.truncate(200 * 1024 * 1024)
        with (
            use_policy(self.policy),
            mock.patch("builtins.open", side_effect=AssertionError("read")),
            self.assertLogs("xhtml2pdf.files", level="WARNING") as logs,
        ):
            self.assertIsNone(getFile("sparse.png", str(self.base)).getData())

        self.assertIn("Blocked by the resource policy", logs.output[0])

    def test_a_file_uri_over_the_limit_is_refused(self) -> None:
        path = self.write("big.png", 1001)
        with (
            use_policy(self.policy),
            self.assertLogs("xhtml2pdf.files", level="WARNING"),
        ):
            self.assertIsNone(getFile(path.as_uri()).getData())

    def test_a_data_uri_over_the_limit_is_refused(self) -> None:
        payload = base64.b64encode(b"x" * 1001).decode()
        with (
            use_policy(self.policy),
            self.assertLogs("xhtml2pdf.files", level="WARNING"),
        ):
            self.assertIsNone(getFile(f"data:image/png;base64,{payload}").getData())

    def test_a_percent_encoded_data_uri_over_the_limit_is_refused(self) -> None:
        with (
            use_policy(self.policy),
            self.assertLogs("xhtml2pdf.files", level="WARNING"),
        ):
            self.assertIsNone(getFile("data:text/plain," + "x" * 1001).getData())

    def test_the_limit_is_off_by_default(self) -> None:
        """Compatibility: a policy that says nothing reads local files whole."""
        self.write("big.png", 30 * 1024 * 1024)
        policy = ResourceAccessPolicy(base_dir=self.base)
        self.assertIsNone(policy.max_local_bytes)
        with use_policy(policy):
            data = getFile("big.png", str(self.base)).getData()

        self.assertEqual(30 * 1024 * 1024, len(data or b""))

    def test_check_local_size_names_the_resource(self) -> None:
        with self.assertRaises(ResourceAccessError) as refused:
            self.policy.check_local_size(1001, "some/where.png")

        self.assertIn("some/where.png", str(refused.exception))


SAMPLES = Path(__file__).parent / "samples"

#: The smallest SVG svglib turns into a drawing with a size.
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
    b'<rect width="20" height="10" fill="red"/></svg>'
)


class SvgSniffingTest(TestCase):
    """svglib is handed SVG only, and parses it without reaching out."""

    def test_a_raster_image_never_reaches_svglib(self) -> None:
        png = (SAMPLES / "img" / "denker.png").read_bytes()
        # A side effect would not do: getDrawing swallows whatever svglib
        # raises, which is how a PNG used to fall through to the raster path.
        with mock.patch(
            "xhtml2pdf.xhtml2pdf_reportlab.svg2rlg", return_value=None
        ) as svg2rlg:
            image = PmlImage(png)

        svg2rlg.assert_not_called()
        self.assertGreater(image.imageWidth, 0)

    def test_an_svg_is_still_drawn(self) -> None:
        image = PmlImage(SVG)

        # svglib reads SVG pixels as CSS pixels, three quarters of a point
        self.assertEqual((15, 7.5), (image.imageWidth, image.imageHeight))

    def test_an_svg_with_a_bom_and_a_prolog_is_recognised(self) -> None:
        self.assertTrue(looks_like_svg(b"\xef\xbb\xbf  <?xml version='1.0'?>" + SVG))
        self.assertTrue(looks_like_svg("<svg/>".encode("utf-16")))
        self.assertTrue(looks_like_svg(b"anything", "image/svg+xml"))
        self.assertFalse(looks_like_svg(b"\x89PNG\r\n\x1a\n"))
        self.assertFalse(looks_like_svg(b"\xff\xd8\xff\xe0"))
        self.assertFalse(looks_like_svg(b""))

    def test_an_external_entity_is_not_resolved(self) -> None:
        secret = SAMPLES / "img" / "denker.png"
        svg = (
            b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "'
            + secret.as_uri().encode()
            + b'">]><svg xmlns="http://www.w3.org/2000/svg" width="20" '
            b'height="10"><rect width="20" height="10"/><text>&x;</text></svg>'
        )
        with mock.patch("builtins.open", side_effect=AssertionError("opened")):
            image = PmlImage(svg)

        # the drawing survives, with the entity left out
        self.assertEqual(15, image.imageWidth)

    def test_a_billion_laughs_does_not_expand(self) -> None:
        entities = b'<!ENTITY a0 "lol">' + b"".join(
            b'<!ENTITY a%d "' % n + b"&a%d;" % (n - 1) * 10 + b'">'
            for n in range(1, 10)
        )
        svg = (
            b"<!DOCTYPE svg [" + entities + b"]>"
            b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
            b'<rect width="20" height="10"/><text>&a9;</text></svg>'
        )
        # A thousand million "lol"s would take minutes and gigabytes; the
        # test finishing is most of the assertion.
        image = PmlImage(svg)

        self.assertEqual(15, image.imageWidth)

    def test_an_image_reference_inside_an_svg_is_not_followed(self) -> None:
        for href in (
            (SAMPLES / "img" / "denker.png").as_uri(),
            str(SAMPLES / "img" / "denker.png"),
            "http://169.254.169.254/latest/meta-data/",
        ):
            svg = (
                b'<svg xmlns="http://www.w3.org/2000/svg" '
                b'xmlns:xlink="http://www.w3.org/1999/xlink" width="20" '
                b'height="10"><image width="20" height="10" xlink:href="'
                + href.encode()
                + b'"/></svg>'
            )
            with (
                self.subTest(href=href),
                mock.patch("socket.create_connection", side_effect=AssertionError),
                mock.patch("builtins.open", side_effect=AssertionError("opened")),
            ):
                PmlImage(svg)


def blank_png(width: int, height: int) -> bytes:
    """
    A valid 1-bit PNG, a few hundred bytes on disk however many pixels.

    Built by hand: Pillow holds a 1-bit image at a byte per pixel, so making
    a large one with it would take the memory the test is about.
    """

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body))
        )

    row = b"\x00" * (1 + (width + 7) // 8)
    idat = zlib.compressobj(9)
    body = b"".join(idat.compress(row) for _ in range(height)) + idat.flush()
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0))
        + chunk(b"IDAT", body)
        + chunk(b"IEND", b"")
    )


def image_count(pdf: bytes) -> int:
    """
    How many times an XObject is drawn: the same image twice is one XObject.

    A page background is merged in with its own content stream, so it is
    counted where it is drawn as well.
    """
    return sum(
        len(re.findall(rb"/[^\s/]+ Do\b", page.get_contents().get_data()))
        for page in PdfReader(io.BytesIO(pdf)).pages
        if page.get_contents() is not None
    )


class ImagePixelLimitTest(TestCase):
    """``max_image_pixels``: refused from the header, before decoding."""

    def setUp(self) -> None:
        self.png = base64.b64encode(blank_png(2000, 2000)).decode()
        self.policy = ResourceAccessPolicy(max_image_pixels=1_000_000)

    @staticmethod
    def render(html: str, policy: ResourceAccessPolicy) -> bytes:
        dest = io.BytesIO()
        pisa.CreatePDF(html, dest=dest, resource_policy=policy)
        return dest.getvalue()

    def assert_refused(self, html: str, pixels: int = 2000 * 2000) -> None:
        with self.assertLogs("xhtml2pdf", level="WARNING") as logs:
            pdf = self.render(html, self.policy)

        self.assertEqual(0, image_count(pdf))
        self.assertTrue(
            any("Blocked by the resource policy" in line for line in logs.output),
            logs.output,
        )
        self.assertTrue(any(f"{pixels} pixels" in line for line in logs.output))

    def test_an_img_over_the_limit_is_refused(self) -> None:
        self.assert_refused(f'<img src="data:image/png;base64,{self.png}">')

    def test_a_list_marker_over_the_limit_is_refused(self) -> None:
        self.assert_refused(
            f"<ul style=\"list-style-image: url('data:image/png;base64,{self.png}')\">"
            "<li>item</li></ul>"
        )

    def test_a_background_over_the_limit_is_refused(self) -> None:
        self.assert_refused(
            "<p style=\"background-image: url('data:image/png;base64,"
            f"{self.png}')\">text</p>"
        )

    def test_a_page_background_over_the_limit_is_refused(self) -> None:
        for opacity in ("", "opacity: 0.5;"):
            with self.subTest(opacity=opacity or None):
                self.assert_refused(
                    "<style>@page { background-image: url('data:image/png;base64,"
                    f"{self.png}'); {opacity} }}</style><p>text</p>"
                )

    def test_an_svg_raster_over_the_limit_is_refused(self) -> None:
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="3000" height="3000">'
            b'<rect width="3000" height="3000"/></svg>'
        )
        with mock.patch(
            "xhtml2pdf.xhtml2pdf_reportlab.renderPM.drawToFile",
            side_effect=AssertionError("rasterised"),
        ):
            # rasterised at a point per pixel, and 3000 CSS pixels are 2250pt
            self.assert_refused(
                f'<img src="data:image/svg+xml;base64,{base64.b64encode(svg).decode()}">',
                pixels=2250 * 2250,
            )

    def test_the_decode_is_never_reached(self) -> None:
        with mock.patch(
            "PIL.ImageFile.ImageFile.load", side_effect=AssertionError("decoded")
        ):
            self.assert_refused(f'<img src="data:image/png;base64,{self.png}">')

    def test_the_limit_is_off_by_default(self) -> None:
        pdf = self.render(
            f'<img src="data:image/png;base64,{self.png}">', ResourceAccessPolicy()
        )

        self.assertEqual(1, image_count(pdf))


class RenderBudgetTest(LocalServerMixin, TestCase):
    """The limits on a whole render rather than on one resource."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        for name in ("a", "b", "c"):
            (self.base / f"{name}.png").write_bytes(
                (SAMPLES / "img" / "denker.png").read_bytes()
            )
        self.size = (SAMPLES / "img" / "denker.png").stat().st_size

    def render(self, html: str | bytes | io.BytesIO, **limits) -> bytes:
        dest = io.BytesIO()
        policy = ResourceAccessPolicy(
            base_dir=self.base, allow_private_networks=True, **limits
        )
        pisa.CreatePDF(
            html, dest=dest, resource_policy=policy, path=str(self.base / "doc.html")
        )
        return dest.getvalue()

    def test_max_resources_refuses_the_ones_past_it(self) -> None:
        html = '<img src="a.png"><img src="b.png"><img src="c.png">'
        with self.assertLogs("xhtml2pdf", level="WARNING") as logs:
            pdf = self.render(html, max_resources=2)

        self.assertEqual(2, image_count(pdf))
        self.assertTrue(any("more than 2 resources" in line for line in logs.output))

    def test_a_resource_used_twice_counts_once(self) -> None:
        pdf = self.render('<img src="a.png"><img src="a.png">', max_resources=1)

        # both drawn: the second use was not a second resource
        self.assertEqual(2, image_count(pdf))

    def test_max_total_bytes_refuses_what_does_not_fit(self) -> None:
        html = '<img src="a.png"><img src="b.png">'
        with self.assertLogs("xhtml2pdf", level="WARNING") as logs:
            pdf = self.render(html, max_total_bytes=self.size + self.size // 2)

        self.assertEqual(1, image_count(pdf))
        self.assertTrue(any("resources in all" in line for line in logs.output))

    def test_data_uris_are_not_resources(self) -> None:
        png = base64.b64encode(blank_png(10, 10)).decode()
        pdf = self.render(
            f'<img src="data:image/png;base64,{png}">'
            f'<img src="data:image/png;base64,{png}">',
            max_resources=0,
        )

        self.assertEqual(2, image_count(pdf))

    def test_max_render_seconds_abandons_the_render(self) -> None:
        with self.assertRaises(RenderLimitError) as refused:
            self.render("<p>text</p>", max_render_seconds=0)

        self.assertIn("0 seconds", str(refused.exception))

    def test_the_deadline_is_checked_while_pages_are_built(self) -> None:
        with render_budget(ResourceAccessPolicy(max_render_seconds=0)):
            doc = PmlBaseDoc(io.BytesIO())
            with self.assertRaises(RenderLimitError):
                doc.afterFlowable(Spacer(1, 1))

    def test_max_fetch_seconds_cuts_off_a_dripping_server(self) -> None:
        started = time.monotonic()
        with self.assertLogs("xhtml2pdf.files", level="WARNING") as logs:
            pdf = self.render(
                f'<img src="{self.base_url}/drip/100/0.2">', max_fetch_seconds=1
            )

        # Each byte comes well inside the 5 second socket timeout, so only a
        # deadline on the whole fetch stops this; and a refusal is not retried.
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(0, image_count(pdf))
        self.assertTrue(any("1 seconds" in line for line in logs.output), logs.output)

    def test_max_document_bytes_refuses_the_source(self) -> None:
        for src in ("<p>" + "x" * 2000 + "</p>", b"<p>" + b"x" * 2000 + b"</p>"):
            with (
                self.subTest(type=type(src).__name__),
                self.assertRaises(RenderLimitError) as refused,
            ):
                self.render(src, max_document_bytes=1000)

            self.assertIn("1000 bytes", str(refused.exception))
        with self.assertRaises(RenderLimitError):
            self.render(io.BytesIO(b"x" * 2000), max_document_bytes=1000)

    def test_max_depth_refuses_deep_nesting(self) -> None:
        html = "<div>" * 50 + "deep" + "</div>" * 50
        with self.assertRaises(RenderLimitError) as refused:
            self.render(html, max_depth=20)

        self.assertIn("20 levels", str(refused.exception))
        # and a document inside the limit still renders
        self.render(html, max_depth=100)

    def test_every_budget_limit_is_off_by_default(self) -> None:
        policy = ResourceAccessPolicy()
        for name in (
            "max_resources",
            "max_total_bytes",
            "max_render_seconds",
            "max_fetch_seconds",
            "max_document_bytes",
            "max_depth",
        ):
            self.assertIsNone(getattr(policy, name), name)


class ServerProfileTest(TestCase):
    """``ResourceAccessPolicy.server()``: every limit on at once."""

    def test_every_limit_is_on(self) -> None:
        policy = ResourceAccessPolicy.server(base_dir=SAMPLES)
        for name in (
            "max_resource_bytes",
            "max_local_bytes",
            "max_image_pixels",
            "max_resources",
            "max_total_bytes",
            "max_fetch_seconds",
            "max_render_seconds",
            "max_document_bytes",
            "max_depth",
        ):
            self.assertIsNotNone(getattr(policy, name), name)
        self.assertFalse(policy.allow_private_networks)
        self.assertFalse(policy.allow_local_outside_base)

    def test_without_a_base_dir_local_reads_are_denied(self) -> None:
        """Not the working directory, which on a server holds its source."""
        with self.assertRaises(ResourceAccessError):
            ResourceAccessPolicy.server().check_path(SAMPLES / "img" / "denker.png")

    def test_a_limit_can_be_changed_and_the_rest_kept(self) -> None:
        policy = ResourceAccessPolicy.server(base_dir=SAMPLES, max_depth=50)

        self.assertEqual(50, policy.max_depth)
        self.assertIsNotNone(policy.max_render_seconds)

    def test_an_ordinary_document_renders_under_it(self) -> None:
        dest = io.BytesIO()
        result = pisa.CreatePDF(
            '<h1>Title</h1><p>text</p><img src="img/denker.png">',
            dest=dest,
            path=str(SAMPLES / "doc.html"),
            resource_policy=ResourceAccessPolicy.server(base_dir=SAMPLES),
        )

        self.assertEqual(0, result.err)
        self.assertEqual(1, image_count(dest.getvalue()))
