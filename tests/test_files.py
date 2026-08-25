from __future__ import annotations

import tempfile
import threading
import warnings
from pathlib import Path
from unittest import TestCase

from xhtml2pdf.files import (
    B64InlineURI,
    BytesFileUri,
    InlineDataURI,
    LocalFileURI,
    NetworkFileUri,
    cleanFiles,
    files_tmp,
    getFile,
    pisaTempFile,
)

from .httpserver import LocalServerMixin

SAMPLES = Path(__file__).parent / "samples"


class TmpFilesTest(TestCase):
    @staticmethod
    def tearDown() -> None:
        cleanFiles()

    def test_registry_is_per_thread(self) -> None:
        """
        ``TmpFiles`` subclasses threading.local, but ``files`` used to be a
        class attribute, so every thread shared one list and one request's
        cleanFiles() closed files another request was still reading.
        """
        # Kept open on purpose: the point of the test is what cleanFiles()
        # does with a handle another thread still holds.
        tmp_file = tempfile.NamedTemporaryFile()  # noqa: SIM115
        files_tmp.append(tmp_file)

        seen: list[list] = []

        def worker() -> None:
            seen.append(list(files_tmp.files))
            cleanFiles()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        self.assertEqual([[]], seen, "temp file registry leaked across threads")
        self.assertFalse(tmp_file.file.closed, "another thread closed our temp file")
        self.assertEqual(1, len(files_tmp.files))


class BytesFileUriTest(TestCase):
    def test_bytes_payload_is_returned_verbatim(self) -> None:
        """``.encode()`` on bytes raised AttributeError, swallowed into None."""
        with self.assertNoLogs("xhtml2pdf.files", level="ERROR"):
            self.assertEqual(b"hello", getFile(b"hello").getFileContent())

    def test_manager_selects_bytes_handler(self) -> None:
        self.assertIsInstance(getFile(b"x").instance, BytesFileUri)

    def test_uri_does_not_echo_the_payload(self) -> None:
        instance = getFile(b"secret-pdf-bytes").instance
        instance.get_data()
        self.assertNotIn("secret", str(instance.get_uri()))


class PathUriTest(TestCase):
    def test_path_object_is_accepted(self) -> None:
        """PisaFileObject is annotated ``str | Path``; Path has no .startswith."""
        file_object = getFile(SAMPLES / "img" / "denker.png")
        self.assertIsInstance(file_object.instance, LocalFileURI)
        self.assertTrue(file_object.getFileContent())
        self.assertEqual("image/png", file_object.getMimeType())

    def test_str_path_still_works(self) -> None:
        self.assertTrue(getFile(str(SAMPLES / "img" / "denker.png")).getFileContent())


class InlineDataURITest(TestCase):
    def test_b64_alias_is_the_same_class(self) -> None:
        self.assertIs(InlineDataURI, B64InlineURI)

    def test_variants(self) -> None:
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        cases = [
            ("data:text/plain;base64,aGVsbG8=", b"hello", "text/plain"),
            ("data:text/plain,hello", b"hello", "text/plain"),
            ("data:,hello", b"hello", "text/plain"),
            (
                "data:text/plain;charset=utf-8,h%C3%A9llo",
                "héllo".encode(),
                "text/plain",
            ),
            (
                "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%3E%3C/svg%3E",
                svg,
                "image/svg+xml",
            ),
            ("data:image/png;base64,", b"", "image/png"),
        ]
        for uri, expected, mimetype in cases:
            with self.subTest(uri=uri[:40]):
                file_object = getFile(uri)
                self.assertEqual(expected, file_object.getFileContent())
                self.assertEqual(mimetype, file_object.getMimeType())

    def test_payload_containing_commas(self) -> None:
        self.assertEqual(b"a,b,c", getFile("data:text/plain,a,b,c").getFileContent())

    def test_malformed_uri_returns_none(self) -> None:
        # no comma at all -> RuntimeError, logged and turned into None
        with self.assertLogs("xhtml2pdf.files", level="ERROR"):
            self.assertIsNone(getFile("data:text/plain").getFileContent())


class NetworkFileUriTest(LocalServerMixin, TestCase):
    def test_plain_fetch(self) -> None:
        file_object = getFile(f"{self.base_url}/img/denker.png")
        self.assertIsInstance(file_object.instance, NetworkFileUri)
        self.assertTrue(file_object.getFileContent())
        self.assertEqual("image/png", file_object.getMimeType())

    def test_follows_redirects(self) -> None:
        """3xx used to be treated as an outright failure, retried three times."""
        direct = getFile(f"{self.base_url}/img/denker.png").getFileContent()
        redirected = getFile(
            f"{self.base_url}/redirect/3/img/denker.png"
        ).getFileContent()
        self.assertEqual(direct, redirected)

    def test_redirect_budget_is_bounded(self) -> None:
        hops = NetworkFileUri.MAX_REDIRECTS + 3
        with self.assertLogs("xhtml2pdf.files", level="WARNING"):
            data = getFile(
                f"{self.base_url}/redirect/{hops}/img/denker.png"
            ).getFileContent()
        self.assertIsNone(data)

    def test_redirect_loop_terminates(self) -> None:
        with self.assertLogs("xhtml2pdf.files", level="WARNING"):
            self.assertIsNone(
                getFile(f"{self.base_url}/redirect-loop").getFileContent()
            )

    def test_redirect_without_location(self) -> None:
        with self.assertLogs("xhtml2pdf.files", level="WARNING"):
            self.assertIsNone(
                getFile(f"{self.base_url}/redirect-no-location").getFileContent()
            )

    def test_not_found_warns(self) -> None:
        """A 404 used to be logged at DEBUG, i.e. invisible by default."""
        with self.assertLogs("xhtml2pdf.files", level="WARNING") as logs:
            self.assertIsNone(getFile(f"{self.base_url}/status/404").getFileContent())
        self.assertIn("404", "\n".join(logs.output))

    def test_no_socket_is_leaked(self) -> None:
        """The HTTP connection was never closed, leaking a socket per image."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            for _ in range(3):
                getFile(f"{self.base_url}/img/denker.png").getFileContent()
        leaks = [w for w in caught if issubclass(w.category, ResourceWarning)]
        self.assertEqual([], [str(w.message) for w in leaks])


class PmlImageReaderTest(LocalServerMixin, TestCase):
    """
    reportlab 5 changed ``rl_config.trustedHosts=None`` from "all hosts are
    trusted" to "no host is trusted", so ``reportlab.lib.utils.open_for_read``
    refuses every URL and data: URI by default. PmlImageReader must keep working
    on both majors.
    """

    #: 1x1 red PNG
    PNG_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAD0lEQVR4nGP8z"
        "wABTAxQAAAT2wD5+bJyRAAAAABJRU5ErkJggg=="
    )

    def test_data_uri(self) -> None:
        from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader

        reader = PmlImageReader(f"data:image/png;base64,{self.PNG_B64}")
        self.assertEqual((1, 1), reader.getSize())

    def test_http_url(self) -> None:
        from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader

        reader = PmlImageReader(f"{self.base_url}/img/denker.png")
        self.assertEqual((70, 137), reader.getSize())

    def test_local_path(self) -> None:
        from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader

        reader = PmlImageReader(str(SAMPLES / "img" / "denker.png"))
        # PmlImageReader keeps fp open by design (jpeg_fh re-reads it)
        assert reader.fp is not None
        self.addCleanup(reader.fp.close)
        self.assertEqual((70, 137), reader.getSize())

    def test_unreachable_url_raises(self) -> None:
        from xhtml2pdf.xhtml2pdf_reportlab import PmlImageReader

        # NB: on reportlab 4 + Python 3.14 this logs a ResourceWarning about an
        # unclosed HTTPError. It comes from reportlab's own rlUrlRead, which
        # does not close the error response; reportlab 5 rejects the URL before
        # the request is made, so it does not appear there.
        with self.assertRaises(OSError):
            PmlImageReader(f"{self.base_url}/status/404")


class PisaTempFileTest(TestCase):
    def test_negative_capacity_stays_in_memory(self) -> None:
        """
        A negative capacity documents "never spill to disk", but
        ``len(buffer) > capacity`` is true for any buffer when capacity is -1,
        so the on-disk strategy was selected immediately.
        """
        self.assertEqual(0, pisaTempFile(capacity=-1).strategy)
        self.assertEqual(0, pisaTempFile("x" * 50_000, capacity=-1).strategy)

    def test_capacity_still_spills_when_exceeded(self) -> None:
        self.assertEqual(0, pisaTempFile("x" * 100, capacity=10_000).strategy)
        spilled = pisaTempFile("x" * 20_000, capacity=10_000)
        self.addCleanup(spilled.close)
        self.assertEqual(1, spilled.strategy)

    def test_getFileName_promotes_on_demand(self) -> None:
        """``name`` was never assigned, so getFileName() always returned None."""
        tmp = pisaTempFile(capacity=-1)
        # bind at cleanup time: getFileName() swaps the underlying delegate
        self.addCleanup(lambda: tmp.close())  # noqa: PLW0108
        name = tmp.getFileName()
        self.assertIsNotNone(name)
        self.assertEqual(1, tmp.strategy)

    def test_roundtrip_in_memory(self) -> None:
        self.assertEqual(b"hello", pisaTempFile("hello", capacity=-1).getvalue())


class NamedTmpFileRegistrationTest(TestCase):
    @staticmethod
    def tearDown() -> None:
        cleanFiles()

    def test_empty_resource_is_still_registered(self) -> None:
        """
        Registration used to sit inside ``if data:``, so a temp file created for
        an empty resource was never closed by cleanFiles() and survived until
        the garbage collector ran.
        """
        before = len(files_tmp.files)
        tmp_file = getFile(None).getFile()
        self.assertEqual(before + 1, len(files_tmp.files))
        self.assertIn(tmp_file, files_tmp.files)

        cleanFiles()
        assert isinstance(tmp_file, tempfile._TemporaryFileWrapper)
        self.assertTrue(tmp_file.file.closed)

    def test_non_empty_resource_is_registered(self) -> None:
        before = len(files_tmp.files)
        getFile(str(SAMPLES / "img" / "denker.png")).getFile()
        self.assertEqual(before + 1, len(files_tmp.files))
