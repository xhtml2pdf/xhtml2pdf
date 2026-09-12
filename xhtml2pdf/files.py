from __future__ import annotations

import base64
import gzip
import http.client as httplib
import logging
import mimetypes
import sys
import tempfile
import threading
import urllib.parse as urlparse
from abc import abstractmethod
from io import BytesIO
from pathlib import Path
from tempfile import _TemporaryFileWrapper
from typing import TYPE_CHECKING, Any
from urllib import request
from urllib.parse import unquote as urllib_unquote
from urllib.parse import unquote_to_bytes

from xhtml2pdf.config.httpconfig import httpConfig
from xhtml2pdf.config.resources import (
    ResourceAccessError,
    ResourceAccessPolicy,
    current_policy,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from http.client import HTTPResponse
    from urllib.parse import SplitResult

log = logging.getLogger(__name__)

GAE: bool = "google.appengine" in sys.modules
STRATEGIES: tuple[type, Any] = (
    (BytesIO, BytesIO) if GAE else (BytesIO, tempfile.NamedTemporaryFile)
)


class TmpFiles(threading.local):
    """
    Per-thread registry of temporary files kept alive for the duration of a
    render.

    ``files`` must be set in ``__init__`` rather than declared as a class
    attribute: ``threading.local`` re-runs ``__init__`` for each thread that
    touches the instance, whereas a class attribute would be shared by every
    thread and let one request's ``cleanFiles()`` close files another request
    is still reading.
    """

    def __init__(self) -> None:
        super().__init__()
        self.files: list[_TemporaryFileWrapper[bytes]] = []

    def append(self, file) -> None:
        self.files.append(file)

    def cleanFiles(self) -> None:
        for file in self.files:
            file.close()
        self.files.clear()


files_tmp: TmpFiles = TmpFiles()  # permanent safe file, to prevent file close


class pisaTempFile:
    """
    A temporary file implementation that uses memory unless
    either capacity is breached or fileno is requested, at which
    point a real temporary file will be created and the relevant
    details returned
    If capacity is -1 the second strategy will never be used.
    Inspired by:
    http://code.activestate.com/recipes/496744/.
    """

    STRATEGIES = STRATEGIES

    CAPACITY: int = 10 * 1024

    def __init__(self, buffer: str = "", capacity: int = CAPACITY) -> None:
        """
        Creates a TempFile object containing the specified buffer.
        If capacity is specified, we use a real temporary file once the
        file gets larger than that size.  Otherwise, the data is stored
        in memory.
        """
        self.name: str | None = None
        self.capacity: int = capacity
        # A negative capacity means "never spill to disk". `len(buffer) >
        # capacity` is true for any buffer when capacity is -1, so this used to
        # select the on-disk strategy immediately -- the exact opposite of the
        # documented behaviour, and of what every caller that passes -1 wants.
        self.strategy: int = int(self.capacity >= 0 and len(buffer) > self.capacity)
        try:
            self._delegate = self.STRATEGIES[self.strategy]()
        except IndexError:
            # Fallback for Google AppEngine etc.
            self._delegate = self.STRATEGIES[0]()
        self.write(buffer)
        # we must set the file's position for preparing to read
        self.seek(0)

    def makeTempFile(self) -> None:
        """
        Switch to next strategy. If an error occurred,
        stay with the first strategy.
        """
        if self.strategy == 0:
            try:
                new_delegate = self.STRATEGIES[1]()
                new_delegate.write(self.getvalue())
                self._delegate = new_delegate
                self.strategy = 1
                # was never assigned, so getFileName() always returned None
                self.name = getattr(new_delegate, "name", None)
                log.warning("Created temporary file %s", self.name)
            except Exception:
                self.capacity = -1

    def getFileName(self) -> str | None:
        """Get a named temporary file."""
        self.makeTempFile()
        return self.name

    def fileno(self) -> int:
        """
        Forces this buffer to use a temporary file as the underlying.
        object and returns the fileno associated with it.
        """
        self.makeTempFile()
        return self._delegate.fileno()

    def getvalue(self) -> bytes:
        """
        Get value of file. Work around for second strategy.
        Always returns bytes.
        """
        if self.strategy == 0:
            return self._delegate.getvalue()
        self._delegate.flush()
        self._delegate.seek(0)
        value = self._delegate.read()
        if not isinstance(value, bytes):
            value = value.encode("utf-8")
        return value

    def write(self, value: bytes | str):
        """If capacity != -1 and length of file > capacity it is time to switch."""
        if self.capacity > 0 and self.strategy == 0:
            len_value = len(value)
            if len_value >= self.capacity:
                needs_new_strategy = True
            else:
                self.seek(0, 2)  # find end of file
                needs_new_strategy = (self.tell() + len_value) >= self.capacity
            if needs_new_strategy:
                self.makeTempFile()

        if not isinstance(value, bytes):
            value = value.encode("utf-8")

        self._delegate.write(value)

    def __getattr__(self, name: str) -> Any:
        try:
            return getattr(self._delegate, name)
        except AttributeError as e:
            msg = f"object '{type(self).__name__}' has no attribute '{name}'"
            raise AttributeError(msg) from e


class BaseFile:
    def __init__(
        self,
        path: str,
        basepath: str | None,
        policy: ResourceAccessPolicy | None = None,
    ) -> None:
        self.path: str = path
        self.basepath: str | None = basepath
        self.mimetype: str | None = None
        self.suffix: str | None = None
        self.uri: str | Path | None = None
        #: What this document is allowed to fetch. Resolved once, here, so
        #: every subclass consults the same policy for the whole fetch.
        self.policy: ResourceAccessPolicy = policy or current_policy()

    @abstractmethod
    def extract_data(self) -> bytes | None:
        raise NotImplementedError

    def get_data(self) -> bytes | None:
        try:
            return self.extract_data()
        except ResourceAccessError as e:
            # A refusal is a decision, not a failure: log it as its own thing
            # and carry on with the resource missing, the same way an
            # unreachable one is handled. A blocked image must not abort a
            # render.
            log.warning("Blocked by the resource policy: %s", e)
        except Exception as e:
            log.error(  # noqa: TRY400
                "%s: %s while extracting data from %s: %r",
                type(e).__name__,
                e,
                type(self).__name__,
                self.uri,
            )
        return None

    def get_uri(self) -> str | Path | None:
        return self.uri

    def get_mimetype(self) -> str | None:
        return self.mimetype

    def get_named_tmp_file(self) -> _TemporaryFileWrapper[bytes]:
        data: bytes | None = self.get_data()
        # Not a context manager: the handle outlives this call on purpose,
        # registered below for cleanFiles() to close.
        tmp_file = tempfile.NamedTemporaryFile(suffix=self.suffix)  # noqa: SIM115
        # Register unconditionally. Registration used to sit inside the `if
        # data` below, so a temp file created for an empty resource was never
        # closed by cleanFiles() and survived until the garbage collector ran
        # (Python 3.14 reports this as a ResourceWarning).
        files_tmp.append(tmp_file)
        if data:
            tmp_file.write(data)
            tmp_file.flush()
        if self.path is None:
            self.path = tmp_file.name
        return tmp_file

    def get_BytesIO(self) -> BytesIO | None:
        data: bytes | None = self.get_data()
        if data:
            return BytesIO(data)
        return None


class InlineDataURI(BaseFile):
    """
    RFC 2397 ``data:`` URI.

    Handles both the base64 form (``data:image/png;base64,iVBOR...``) and the
    percent-encoded form (``data:image/svg+xml,%3Csvg...``); the latter is the
    usual way inline SVG is written and used to be rejected outright.
    """

    mime_params: list

    def extract_data(self) -> bytes | None:
        if not self.path.startswith("data:") or "," not in self.path:
            msg = "Data URI is malformed"
            raise RuntimeError(msg)

        # data:[<mediatype>][;base64],<data> -- split on the FIRST comma, the
        # payload may legitimately contain further commas.
        header, _, data = self.path[len("data:") :].partition(",")

        params = [part for part in header.split(";") if part]
        is_base64 = bool(params) and params[-1].lower() == "base64"
        if is_base64:
            params.pop()

        # RFC 2397: an omitted mediatype means text/plain;charset=US-ASCII
        self.mimetype = params[0] if params and "/" in params[0] else "text/plain"
        # mime_params are preserved for future use
        self.mime_params = params[1:] if params and "/" in params[0] else params

        if is_base64:
            return base64.b64decode(urllib_unquote(data).encode("utf-8"))
        return unquote_to_bytes(data)


# Backwards-compatible alias: this class was named after the base64 form only.
B64InlineURI = InlineDataURI


class LocalProtocolURI(BaseFile):
    """
    A ``file:`` URI.

    The body used to go through ``urllib.request.urlopen``, which resolves
    whatever scheme the ``urljoin`` happened to produce -- so a ``file:``
    basepath joined with an absolute URL fetched over the network under the
    guise of a local read. The path is now taken apart and read directly, and
    the policy sees it as the local read it is.
    """

    def extract_data(self) -> bytes | None:
        if self.basepath and self.path.startswith("/"):
            self.uri = urlparse.urljoin(self.basepath, self.path[1:])
        elif self.path.startswith("file:"):
            self.uri = self.path
        else:
            return None
        parts = urlparse.urlsplit(str(self.uri))
        if parts.scheme and parts.scheme != "file":
            msg = f"{self.uri!r} is not a local file"
            raise ResourceAccessError(msg)
        path = Path(request.url2pathname(parts.path))
        self.policy.check_path(path)
        if not path.is_file():
            return None
        self.suffix = path.suffix
        self.mimetype = LocalFileURI.guess_mimetype(path)
        return path.read_bytes()


class NetworkFileUri(BaseFile):
    MAX_REDIRECTS: int = 5

    def __init__(
        self,
        path: str,
        basepath: str | None,
        policy: ResourceAccessPolicy | None = None,
    ) -> None:
        super().__init__(path, basepath, policy)
        self.attempts: int = 3
        self.actual_attempts: int = 0

    def get_data(self) -> bytes | None:
        data = None
        # try several attempts if network problems happens
        while self.attempts > self.actual_attempts and data is None:
            self.actual_attempts += 1
            try:
                data = self.extract_data()
            except ResourceAccessError as e:
                # Retrying a refusal would only repeat it three times over.
                log.warning("Blocked by the resource policy: %s", e)
                break
            except Exception as e:
                log.error(  # noqa: TRY400
                    "%s: %s while extracting data from %s: %r on attempt %d",
                    type(e).__name__,
                    e,
                    type(self).__name__,
                    self.uri,
                    self.actual_attempts,
                )
        return data

    def _request(self, uri: str) -> tuple[bytes | None, bool, str | None]:
        """
        Perform a single GET.

        Returns ``(data, is_gzip, redirect_target)``; exactly one of ``data``
        and ``redirect_target`` is set on success.
        """
        log.debug("Sending request for %r with httplib", uri)
        url_splitted: SplitResult = urlparse.urlsplit(uri)
        server: str = url_splitted[1]
        path: str = url_splitted[2]
        path += f"?{url_splitted[3]}" if url_splitted[3] else ""
        conn: httplib.HTTPConnection | httplib.HTTPSConnection
        if uri.startswith("https://"):
            conn = httplib.HTTPSConnection(server, **httpConfig)
        else:
            # HTTPConnection accepts only a subset of the HTTPS keywords, but it
            # must still get the configured timeout -- plain http requests used
            # to hang indefinitely.
            conn = httplib.HTTPConnection(
                server,
                **{
                    key: value
                    for key, value in httpConfig.items()
                    if key in {"timeout", "source_address", "blocksize"}
                },
            )
        try:
            conn.request("GET", path)
            r1: HTTPResponse = conn.getresponse()
            if 200 <= r1.status < 300:
                self.mimetype = r1.getheader("Content-Type", "").split(";")[0]
                is_gzip = r1.getheader("content-encoding") == "gzip"
                # the body must be read before the connection is closed
                return self._read_capped(r1, uri), is_gzip, None
            if 300 <= r1.status < 400:
                location = r1.getheader("Location")
                r1.read()  # drain, so the connection can be reused/closed cleanly
                if location:
                    return None, False, urlparse.urljoin(uri, location)
                log.warning(
                    "Redirect without Location header for %r: %d %s",
                    uri,
                    r1.status,
                    r1.reason,
                )
                return None, False, None
            r1.read()
            log.warning(
                "Received non-success status for %r: %d %s", uri, r1.status, r1.reason
            )
        finally:
            # the connection was never closed, leaking a socket per image
            conn.close()
        return None, False, None

    def get_httplib(self, uri) -> tuple[bytes | None, bool]:
        seen: set[str] = set()
        for _ in range(self.MAX_REDIRECTS + 1):
            if uri in seen:
                log.warning("Redirect loop while fetching %r", uri)
                return None, False
            seen.add(uri)
            # Checked per hop: a 302 to http://169.254.169.254/ would
            # otherwise walk straight past a check made only on the first URL.
            self.policy.check_url(uri)
            data, is_gzip, redirect = self._request(uri)
            if redirect is None:
                return data, is_gzip
            log.debug("Following redirect %r -> %r", uri, redirect)
            uri = redirect
        log.warning(
            "Too many redirects (>%d) while fetching %r", self.MAX_REDIRECTS, uri
        )
        return None, False

    def _read_capped(self, response: HTTPResponse, uri: str) -> bytes:
        """
        Read the body, refusing one larger than the policy allows.

        ``read()`` with no argument read whatever the server chose to send,
        which is the server the document picked. Reading one byte past the
        limit is what tells a body at the limit from one over it.
        """
        limit = self.policy.max_resource_bytes
        if limit is None:
            return response.read()
        declared = response.getheader("Content-Length")
        if declared is not None and declared.isdigit():
            # Refused before a byte of it is read, when the server says so.
            self.policy.check_size(int(declared), uri)
        body = response.read(limit + 1)
        self.policy.check_size(len(body), uri)
        return body

    def _gunzip_capped(self, data: bytes, uri: str) -> bytes:
        """
        Decompress, refusing an expansion larger than the policy allows.

        A gzip stream says nothing about what it expands to, and the ratio is
        the attacker's to choose: 203KB of response reached 209MB of memory.
        GzipFile decompresses as it is read, so a capped read never builds the
        whole thing.
        """
        limit = self.policy.max_resource_bytes
        with gzip.GzipFile(mode="rb", fileobj=BytesIO(data)) as gz:
            if limit is None:
                return gz.read()
            expanded = gz.read(limit + 1)
        self.policy.check_size(len(expanded), uri)
        return expanded

    def extract_data(self) -> bytes | None:
        # FIXME: When self.path don't start with http
        if self.basepath and not self.path.startswith("http"):
            uri = urlparse.urljoin(self.basepath, self.path)
        else:
            uri = self.path
        self.uri = uri
        data, is_gzip = self.get_httplib(uri)
        if is_gzip and data:
            data = self._gunzip_capped(data, uri)
        log.debug("Uri parsed: %r", uri)
        return data


class LocalFileURI(BaseFile):
    @staticmethod
    def guess_mimetype(name) -> str | None:
        """Guess the mime type."""
        mimetype = mimetypes.guess_type(str(name))[0]
        if mimetype is not None:
            mimetype = mimetype.split(";")[0]
        return mimetype

    def extract_data(self) -> bytes | None:
        data = None
        log.debug("Unrecognized scheme, assuming local file path")
        path = Path(self.path)
        uri = None
        uri = Path(self.basepath) / path if self.basepath is not None else Path() / path
        if path.exists() and not uri.exists():
            uri = path
        # Before the open, not after: this is the check that stops
        # <img src="/etc/passwd"> and its ../ spellings. Note that joining an
        # absolute path onto the basepath above discards the basepath, which is
        # exactly why the resolved result has to be vetted.
        self.policy.check_path(uri)
        if uri.is_file():
            self.uri = uri
            self.suffix = uri.suffix
            self.mimetype = self.guess_mimetype(uri)
            if self.mimetype and self.mimetype.startswith("text"):
                with open(uri, encoding="utf-8") as file_handler:
                    data = file_handler.read().encode("utf-8")
            else:
                with open(uri, "rb") as file_handler:
                    data = file_handler.read()
        return data


class BytesFileUri(BaseFile):
    def extract_data(self) -> bytes | None:
        # ``path`` is normally already bytes here; calling .encode() on it
        # raised AttributeError, which get_data() swallowed into a silent None.
        if isinstance(self.path, bytes):
            self.uri = f"<bytes:{len(self.path)}>"
            return self.path
        self.uri = self.path
        return self.path.encode("utf-8")


class LocalTmpFile(BaseFile):
    def __init__(self, path, basepath, policy=None) -> None:
        self.path: str = path
        self.basepath: str | None = None
        # a LocalTmpFile is handed its mimetype where the others get a basepath
        self.mimetype: str | None = basepath
        self.suffix: str | None = None
        self.uri: str | Path | None = None
        self.policy: ResourceAccessPolicy = policy or current_policy()

    def get_named_tmp_file(self):
        tmp_file = super().get_named_tmp_file()
        if self.path is None:
            self.path = tmp_file.name
        return tmp_file

    def extract_data(self) -> bytes | None:
        if self.path is None:
            return None
        self.uri = self.path
        with open(self.path, "rb") as arch:
            return arch.read()


class FileNetworkManager:
    @staticmethod
    def get_manager(uri, basepath=None, policy=None):
        if uri is None:
            return LocalTmpFile(uri, basepath, policy)
        if isinstance(uri, bytes):
            return BytesFileUri(uri, basepath, policy)
        if isinstance(uri, Path):
            # pisaFileObject accepts str | Path; Path has no .startswith()
            uri = str(uri)
        if uri.startswith("data:"):
            instance = B64InlineURI(uri, basepath, policy)
        else:
            if basepath and not urlparse.urlparse(uri).scheme:
                urlParts = urlparse.urlparse(basepath)
            else:
                urlParts = urlparse.urlparse(uri)

            log.debug("URLParts: %r, %r", urlParts, urlParts.scheme)
            if urlParts.scheme == "file":
                instance = LocalProtocolURI(uri, basepath, policy)
            elif urlParts.scheme in {"http", "https"}:
                instance = NetworkFileUri(uri, basepath, policy)
            else:
                instance = LocalFileURI(uri, basepath, policy)
        return instance


class pisaFileObject:
    def __init__(
        self,
        uri: str | Path | None,
        basepath: str | None = None,
        callback: Callable | None = None,
        policy: ResourceAccessPolicy | None = None,
    ) -> None:
        self.uri: str | Path | None = uri
        self.basepath: str | None = basepath
        if callback and (new := callback(uri, basepath)):
            self.uri = new
            self.basepath = None

        log.debug("FileObject %r, Basepath: %r", self.uri, self.basepath)

        # Resolved here rather than left to each BaseFile so that a link_callback
        # rewrite above is still subject to it: rewriting a URL is not the same
        # as authorising it.
        self.policy: ResourceAccessPolicy = policy or current_policy()
        self.instance: BaseFile = FileNetworkManager.get_manager(
            self.uri, basepath=self.basepath, policy=self.policy
        )

    def getFileContent(self) -> bytes | None:
        return self.instance.get_data()

    def getNamedFile(self) -> str | None:
        f = self.instance.get_named_tmp_file()
        return f.name if f else None

    def getData(self) -> bytes | None:
        return self.instance.get_data()

    def getFile(self) -> BytesIO | _TemporaryFileWrapper | None:
        if GAE:
            return self.instance.get_BytesIO()
        return self.instance.get_named_tmp_file()

    def getMimeType(self) -> str | None:
        return self.instance.get_mimetype()

    def notFound(self) -> bool:
        return self.getData() is None

    def getAbsPath(self):
        return self.instance.get_uri()

    def getBytesIO(self):
        return self.instance.get_BytesIO()


def getFile(*a, **kw) -> pisaFileObject:
    return pisaFileObject(*a, **kw)


def cleanFiles() -> None:
    files_tmp.cleanFiles()
