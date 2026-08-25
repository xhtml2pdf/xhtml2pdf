"""
A throwaway HTTP server for tests.

The suite used to fetch fixtures from raw.githubusercontent.com and
cars.usnews.com, which made it slow, flaky and unusable offline. Everything is
served from ``tests/samples`` on localhost instead.

Beyond plain files the handler understands a few control paths, which double as
fixtures for the redirect/error handling in ``xhtml2pdf.files.NetworkFileUri``:

``/redirect/<n>/<path>``   n 301 hops, then a redirect to ``/<path>``
``/redirect-loop``         a 302 pointing at itself
``/redirect-no-location``  a 302 with no ``Location`` header
``/status/<code>``         responds with that status and an empty body
``/slow/<seconds>``        sleeps before responding
"""

from __future__ import annotations

import contextlib
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextlib import AbstractContextManager
    from unittest import TestCase

    # A mixin has no base of its own, so a type checker cannot see that
    # super().setUpClass() resolves or that the class it is mixed into is a
    # TestCase. Standing it on TestCase for type checking only says so without
    # changing the runtime MRO.
    MixinBase = TestCase
else:
    MixinBase = object

SAMPLES_DIR: Path = Path(__file__).parent / "samples"


class SampleRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Keep the test output quiet."""

    def handle_one_request(self) -> None:
        # a client that times out mid-response is expected here, not a failure
        with contextlib.suppress(OSError):
            super().handle_one_request()

    def _redirect(self, location: str, status: int = 301) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path

        if path == "/redirect-loop":
            self._redirect("/redirect-loop", status=302)
            return

        if path == "/redirect-no-location":
            self.send_response(302)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path.startswith("/redirect/"):
            _, _, rest = path[len("/redirect/") :].partition("/")
            hops = int(path[len("/redirect/") :].split("/", 1)[0])
            target = f"/{rest}" if hops <= 1 else f"/redirect/{hops - 1}/{rest}"
            self._redirect(target)
            return

        if path.startswith("/status/"):
            self.send_response(int(path[len("/status/") :]))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path.startswith("/slow/"):
            time.sleep(float(path[len("/slow/") :]))
            # the client has usually timed out and hung up by now
            with contextlib.suppress(OSError):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
            return

        super().do_GET()


@contextlib.contextmanager
def sample_server(directory: Path | str = SAMPLES_DIR) -> Iterator[str]:
    """Serve ``directory`` on a free localhost port; yields the base URL."""
    handler = partial(SampleRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class LocalServerMixin(MixinBase):
    """Starts a sample server for the whole TestCase; base URL in ``cls.base_url``."""

    #: Filled in by setUpClass. Declared here so that every TestCase mixing
    #: this in can see them.
    base_url: ClassVar[str]
    _server_ctx: ClassVar[AbstractContextManager[str]]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._server_ctx = sample_server()
        # unittest grew enterClassContext in 3.11; this package still
        # supports 3.10, so the context is entered and exited by hand.
        cls.base_url = cls._server_ctx.__enter__()  # noqa: PLC2801

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server_ctx.__exit__(None, None, None)
        super().tearDownClass()
