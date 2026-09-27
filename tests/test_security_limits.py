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
