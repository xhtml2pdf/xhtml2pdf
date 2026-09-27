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
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from xhtml2pdf.config.resources import (
    ResourceAccessError,
    ResourceAccessPolicy,
    use_policy,
)
from xhtml2pdf.files import getFile
from xhtml2pdf.xhtml2pdf_reportlab import PmlImage, looks_like_svg


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
