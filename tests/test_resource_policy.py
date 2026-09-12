"""
The resource access policy: what a rendered document is allowed to fetch.

Two findings motivate these tests. A document could reach any host the server
could -- ``<img src="http://169.254.169.254/latest/meta-data/">`` returns cloud
instance credentials from inside the VPC -- and it could read any file the
process could, because an unrecognised scheme falls through to a plain
``open()``. Both are reachable from nothing more than user-supplied HTML.
"""

from __future__ import annotations

import io
import socket
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from pypdf import PdfReader

from xhtml2pdf import pisa
from xhtml2pdf.config.resources import (
    PERMISSIVE_POLICY,
    ResourceAccessError,
    ResourceAccessPolicy,
    current_policy,
    default_policy,
    use_policy,
)
from xhtml2pdf.files import NetworkFileUri, getFile

from .httpserver import LocalServerMixin

SAMPLES = Path(__file__).parent / "samples"
METADATA = "http://169.254.169.254/latest/meta-data/"


def render(html: str, **kwargs) -> None:
    pisa.CreatePDF(html, dest=io.BytesIO(), **kwargs)


class NetworkPolicyTest(TestCase):
    def test_the_metadata_service_is_not_reachable(self) -> None:
        """The SSRF report, end to end: no connection may even be attempted."""
        with (
            mock.patch.object(
                NetworkFileUri, "_request", side_effect=AssertionError("connected")
            ),
            self.assertLogs("xhtml2pdf.files", level="WARNING") as logs,
        ):
            render(f'<img src="{METADATA}">')

        self.assertIn("Blocked by the resource policy", logs.output[0])
        self.assertIn("169.254.169.254", logs.output[0])

    def test_a_name_is_judged_by_what_it_resolves_to(self) -> None:
        """
        Spelling the destination as a host name must not help: the check is on
        the resolved address.
        """
        policy = ResourceAccessPolicy()
        loopback = [(socket.AF_INET, None, None, "", ("127.0.0.1", 80))]

        with (
            mock.patch("socket.getaddrinfo", return_value=loopback),
            self.assertRaises(ResourceAccessError) as caught,
        ):
            policy.check_url("http://images.example.com/logo.png")

        self.assertIn("127.0.0.1", str(caught.exception))

    def test_an_ipv4_mapped_address_does_not_slip_through(self) -> None:
        with self.assertRaises(ResourceAccessError):
            ResourceAccessPolicy().check_url("http://[::ffff:127.0.0.1]/x.png")

    def test_a_redirect_cannot_land_on_an_internal_address(self) -> None:
        """
        Checking only the first URL would leave the whole thing open: the
        document names a public host that answers 302 to the metadata service.
        """
        fetcher = NetworkFileUri(
            "http://public.example/logo.png",
            None,
            ResourceAccessPolicy(allowed_hosts=frozenset({"public.example"})),
        )
        public = [(socket.AF_INET, None, None, "", ("93.184.216.34", 80))]

        with (
            mock.patch.object(
                NetworkFileUri, "_request", return_value=(None, False, METADATA)
            ),
            mock.patch("socket.getaddrinfo", return_value=public),
            self.assertRaises(ResourceAccessError) as caught,
        ):
            fetcher.get_httplib("http://public.example/logo.png")

        self.assertIn("169.254.169.254", str(caught.exception))

    def test_a_refusal_is_not_retried(self) -> None:
        """NetworkFileUri retries three times on failure; a decision is final."""
        fetcher = NetworkFileUri(METADATA, None, ResourceAccessPolicy())

        with (
            mock.patch.object(
                NetworkFileUri, "_request", side_effect=AssertionError("connected")
            ),
            self.assertLogs("xhtml2pdf.files", level="WARNING") as logs,
        ):
            self.assertIsNone(fetcher.get_data())

        self.assertEqual(1, len(logs.output))

    def test_allowed_hosts_refuses_everything_else(self) -> None:
        policy = ResourceAccessPolicy(allowed_hosts=frozenset({"cdn.example.com"}))

        with self.assertRaises(ResourceAccessError):
            policy.check_url("https://evil.example.com/x.png")

    def test_no_remote_refuses_public_hosts_too(self) -> None:
        with self.assertRaises(ResourceAccessError):
            ResourceAccessPolicy(allow_remote=False).check_url(
                "https://example.com/x.png"
            )

    def test_unknown_schemes_are_refused(self) -> None:
        """These used to reach urllib, or fall through to a local open()."""
        for url in ("ftp://example.com/x", "gopher://example.com/x"):
            with self.subTest(url=url), self.assertRaises(ResourceAccessError):
                ResourceAccessPolicy().check_url(url)

    def test_data_uris_are_untouched(self) -> None:
        """Inline data carries no network or filesystem access to police."""
        with use_policy(default_policy(SAMPLES)):
            data = getFile("data:text/plain;base64,aGVsbG8=").getData()  # "hello"

        self.assertEqual(b"hello", data)


class LocalPathPolicyTest(TestCase):
    def setUp(self) -> None:
        self.policy = ResourceAccessPolicy(base_dir=SAMPLES)

    def test_an_absolute_path_is_refused(self) -> None:
        """The local file disclosure report: <img src="/etc/passwd">."""
        with self.assertRaises(ResourceAccessError):
            self.policy.check_path("/etc/passwd")

    def test_traversal_out_of_the_base_is_refused(self) -> None:
        with self.assertRaises(ResourceAccessError):
            self.policy.check_path(SAMPLES / ".." / ".." / "etc" / "passwd")

    def test_a_symlink_pointing_out_is_refused(self) -> None:
        """resolve() follows the link, so planting one inside the base fails."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            link = base / "escape"
            link.symlink_to("/etc/passwd")

            with self.assertRaises(ResourceAccessError):
                ResourceAccessPolicy(base_dir=base).check_path(link)

    def test_a_file_inside_the_base_is_allowed(self) -> None:
        # a refusal raises, so reaching the next line is the assertion
        self.policy.check_path(SAMPLES / "img" / "denker.png")

    def test_extra_roots_are_allowed(self) -> None:
        policy = ResourceAccessPolicy(
            base_dir=SAMPLES / "img", extra_roots=(SAMPLES / "font",)
        )

        policy.check_path(SAMPLES / "font")
        with self.assertRaises(ResourceAccessError):
            policy.check_path(SAMPLES / "test1.html")

    def test_a_policy_built_by_hand_still_confines_local_reads(self) -> None:
        """
        base_dir defaulted to None, and None meant no confinement, so
        ``ResourceAccessPolicy(allowed_hosts=...)`` -- tightening the network
        rules -- silently opened the whole filesystem. The safe default used
        to live only in default_policy().
        """
        policy = ResourceAccessPolicy(allowed_hosts=frozenset({"cdn.example.com"}))

        self.assertEqual((Path.cwd().resolve(),), policy.roots)
        with self.assertRaises(ResourceAccessError):
            policy.check_path("/etc/passwd")

    def test_naming_no_directory_denies_rather_than_allows(self) -> None:
        """The reading of base_dir=None that cannot be reached by accident."""
        with self.assertRaises(ResourceAccessError) as refused:
            ResourceAccessPolicy(base_dir=None).check_path("/etc/passwd")

        self.assertIn("names no directory", str(refused.exception))

    def test_the_confinement_can_still_be_lifted(self) -> None:
        lifted = ResourceAccessPolicy(base_dir=None, allow_local_outside_base=True)

        self.assertEqual((), lifted.roots)
        # a refusal raises, so reaching the next line is the assertion
        lifted.check_path("/etc/passwd")
        PERMISSIVE_POLICY.check_path("/etc/passwd")

    def test_the_fetcher_returns_nothing_for_a_refused_path(self) -> None:
        with (
            use_policy(default_policy(SAMPLES)),
            self.assertLogs("xhtml2pdf.files", level="WARNING"),
        ):
            self.assertIsNone(getFile("/etc/passwd", str(SAMPLES)).getData())

    def test_a_file_uri_is_refused_as_well(self) -> None:
        with (
            use_policy(default_policy(SAMPLES)),
            self.assertLogs("xhtml2pdf.files", level="WARNING"),
        ):
            self.assertIsNone(getFile("file:///etc/passwd").getData())

    def test_a_relative_image_still_renders(self) -> None:
        """The point of the default is that ordinary documents keep working."""
        dest = io.BytesIO()
        result = pisa.CreatePDF(
            '<img src="img/denker.png">', dest=dest, path=str(SAMPLES / "doc.html")
        )

        self.assertEqual(0, result.err)
        page = PdfReader(io.BytesIO(dest.getvalue())).pages[0]
        self.assertIn("/XObject", page["/Resources"])


class PolicyScopeTest(LocalServerMixin, TestCase):
    def test_outside_a_build_nothing_is_restricted(self) -> None:
        """
        A direct getFile() call is the integrator's own code asking for its own
        file, not markup asking on someone else's behalf, so it is left alone.
        """
        self.assertIs(PERMISSIVE_POLICY, current_policy())

        data = getFile(f"{self.base_url}/img/denker.png").getData()

        self.assertTrue(data)

    def test_the_policy_is_restored_after_a_build(self) -> None:
        render("<p>hello</p>")

        self.assertIs(PERMISSIVE_POLICY, current_policy())

    def test_a_surrounding_use_policy_is_honoured(self) -> None:
        """
        A caller can put a policy in force around a build instead of threading
        it through every call -- which is what a renderer with several entry
        points needs. pisaDocument used to build its own default regardless,
        so `with use_policy(...)` around it did nothing at all.
        """
        dest = io.BytesIO()
        with use_policy(self.policy):
            result = pisa.CreatePDF(
                f'<img src="{self.base_url}/img/denker.png">', dest=dest
            )

        self.assertEqual(0, result.err)
        page = PdfReader(io.BytesIO(dest.getvalue())).pages[0]
        self.assertIn("/XObject", page["/Resources"])

    def test_an_argument_beats_a_surrounding_policy(self) -> None:
        with (
            use_policy(self.policy),
            self.assertLogs("xhtml2pdf.files", level="WARNING") as logs,
        ):
            render(
                f'<img src="{self.base_url}/img/denker.png">',
                resource_policy=ResourceAccessPolicy(),
            )

        self.assertIn("Blocked by the resource policy", logs.output[0])

    def test_an_explicit_policy_wins(self) -> None:
        dest = io.BytesIO()
        result = pisa.CreatePDF(
            f'<img src="{self.base_url}/img/denker.png">',
            dest=dest,
            resource_policy=self.policy,
        )

        self.assertEqual(0, result.err)
        page = PdfReader(io.BytesIO(dest.getvalue())).pages[0]
        self.assertIn("/XObject", page["/Resources"])

    def test_the_same_image_is_blocked_by_default(self) -> None:
        with self.assertLogs("xhtml2pdf.files", level="WARNING") as logs:
            render(f'<img src="{self.base_url}/img/denker.png">')

        self.assertIn("Blocked by the resource policy", logs.output[0])
