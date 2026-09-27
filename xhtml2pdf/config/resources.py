# Copyright 2025 xhtml2pdf contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Which resources a rendering document is allowed to fetch.

The untrusted input in xhtml2pdf is the *HTML being rendered*, and it decides
what the renderer downloads: ``<img src=...>``, ``@import``, ``@font-face``,
``background-image`` and the ``<pdf:*>`` tags all reach the network and the
filesystem through :mod:`xhtml2pdf.files`. An application that turns
user-supplied markup into a PDF therefore lends that user its network position
and its filesystem, which is how the two classic findings against this library
arise:

* **SSRF** -- ``<img src="http://169.254.169.254/latest/meta-data/">`` fetches
  cloud instance metadata from inside the VPC.
* **Local file disclosure** -- ``<img src="/etc/passwd">`` reads a file the
  document has no business seeing, because ``LocalFileURI`` is the fallback for
  every unrecognised scheme.

``link_callback`` cannot serve as the gate for this. It is optional, defaults to
``None``, only rewrites the URL, and roughly ten call sites bypass it entirely
(fonts, watermarks, signatures, ``PmlImageReader._open``). The policy lives in
the fetcher instead, so every path is covered.

The default is not "deny everything". Public HTTP(S) keeps working, because
fetching remote images is the ordinary use of this library. What the default
denies is the part with no legitimate use in a rendered document: destinations
on internal networks, and local reads that escape the document's own directory.

Scope, deliberately: the hardened policy is active for the duration of a
``pisaDocument``/``pisaStory`` build. A direct call such as
``files.getFile("/etc/passwd")`` from the integrator's own code is that code
asking for its own file, not an attacker-controlled fetch, and stays
unrestricted unless a policy is passed explicitly.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
import urllib.parse as urlparse
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "PERMISSIVE_POLICY",
    "RenderBudget",
    "RenderLimitError",
    "ResourceAccessError",
    "ResourceAccessPolicy",
    "active_budget",
    "active_policy",
    "check_deadline",
    "current_policy",
    "default_policy",
    "render_budget",
    "use_policy",
]

log = logging.getLogger(__name__)

#: Schemes the fetcher understands. Anything else (``ftp:``, ``gopher:``,
#: ``jar:``) would otherwise reach urllib and is refused.
KNOWN_SCHEMES: frozenset[str] = frozenset({"", "data", "file", "http", "https"})

REMOTE_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class ResourceAccessError(Exception):
    """A resource was refused by the active :class:`ResourceAccessPolicy`."""


class RenderLimitError(Exception):
    """
    A render went past a limit on the whole document, and was abandoned.

    Not a :class:`ResourceAccessError`: a refused resource leaves the document
    without it and the render goes on, whereas a document that is too large,
    too deep or out of time has no useful remainder to render.
    """


def _is_internal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """
    Is this address one a document must not be able to reach?

    Covers loopback, RFC1918/ULA private ranges, link-local (which is where the
    AWS/GCP/Azure metadata service at 169.254.169.254 lives), CGNAT, multicast,
    and the reserved and unspecified blocks. IPv4-mapped IPv6 addresses are
    unwrapped first, so ``::ffff:127.0.0.1`` cannot be used to slip past the
    IPv4 checks.
    """
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return bool(
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


@dataclass(frozen=True)
class ResourceAccessPolicy:
    """
    What a rendering document may fetch.

    :param allow_remote: fetch over http(s) at all.
    :param allow_private_networks: allow destinations that resolve to loopback,
        private, link-local or reserved addresses. Off by default: this is the
        SSRF gate.
    :param allowed_hosts: when set, only these host names may be fetched, and
        every other remote destination is refused regardless of its address.
        Matching is case-insensitive and on the host name alone, not the port.
    :param base_dir: the directory local reads are confined to -- normally the
        directory of the document being rendered, and the working directory
        when nothing is said. ``None`` names no directory at all, which denies
        local reads rather than allowing every one of them.
    :param extra_roots: further directories local reads may reach, for assets
        that legitimately live outside the document's directory (a shared font
        or image directory, say).
    :param allow_local_outside_base: turn the confinement off while keeping the
        network rules.
    :param max_resource_bytes: how large a single fetched resource may be,
        before and after decompression. ``None`` removes the limit.
    :param max_local_bytes: how large a local file or a decoded ``data:`` URI
        may be. ``None``, the default, removes the limit: the caller's own
        document is read under a policy too, and it may be large.
    :param max_image_pixels: how many pixels an image may decode to, read
        from its header before it is decoded. ``None``, the default, leaves
        only Pillow's own decompression-bomb guard.
    :param max_resources: how many distinct files and URLs one render may
        read. ``data:`` URIs are part of the document and do not count.
    :param max_total_bytes: how many bytes those may add up to.
    :param max_fetch_seconds: how long one network fetch may take in all,
        across its retries and redirects. The socket timeout bounds each read
        only, so a server sending a byte every few seconds is never cut off
        without this.
    :param max_render_seconds: how long a render may take. Checked between
        elements, fetches and flowables, so it is a bound, not a precise stop.
    :param max_document_bytes: how large the source document may be.
    :param max_depth: how deeply its elements may nest.
    :param allow_remote_pdf_backgrounds: use a PDF page background that was
        fetched over the network or written inline as a ``data:`` URI. A PDF
        is a complex format parsed by pypdf; one from a file beside the
        document is the integrator's, one from anywhere else is the
        document author's.

    Every limit after ``max_resource_bytes`` is off (``None``) by default;
    :meth:`server` turns them all on.
    """

    allow_remote: bool = True
    allow_private_networks: bool = False
    allowed_hosts: frozenset[str] | None = None
    #: The working directory rather than ``None``, so that a policy built by
    #: hand -- ``ResourceAccessPolicy(allowed_hosts={"cdn.example.com"})``,
    #: say -- confines local reads as well as network ones; tightening one of
    #: the two must not leave the other open. Confinement is off only when it
    #: is turned off, by ``allow_local_outside_base`` or by passing
    #: ``base_dir=None``, which denies local reads outright rather than
    #: allowing all of them.
    base_dir: Path | None = field(default_factory=Path.cwd)
    extra_roots: tuple[Path, ...] = field(default=())
    allow_local_outside_base: bool = False
    #: Generous for an image or a font, and far below what it takes to hurt a
    #: worker: without a limit, a 203KB response declaring Content-Encoding:
    #: gzip expands to 209MB of resident memory.
    max_resource_bytes: int | None = 20 * 1024 * 1024
    #: Off by default, unlike the network limit, because a local read has
    #: always been unbounded and documents rely on it: a large image beside
    #: the document is not an attack when the caller wrote the document.
    max_local_bytes: int | None = None
    #: The byte limits do not bound an image: a 400-byte PNG can declare
    #: 50,000 x 50,000 pixels, gigabytes once decoded.
    max_image_pixels: int | None = None
    max_resources: int | None = None
    max_total_bytes: int | None = None
    max_fetch_seconds: float | None = None
    max_render_seconds: float | None = None
    max_document_bytes: int | None = None
    max_depth: int | None = None
    allow_remote_pdf_backgrounds: bool = True

    @classmethod
    def server(
        cls, base_dir: str | Path | None = None, **overrides: object
    ) -> ResourceAccessPolicy:
        """
        The policy for rendering HTML you did not write: every limit on.

        Local reads are confined to ``base_dir`` and denied outright without
        one -- not the working directory, which on a server holds its source
        and its settings. Any field can be given to change one limit and keep
        the others, ``ResourceAccessPolicy.server(media, max_depth=50)``.

        The values are generous for a document and far below what it takes
        to hurt a worker; the security guide lists them.
        """
        policy = cls(
            base_dir=Path(base_dir) if base_dir is not None else None,
            max_resource_bytes=20 * 1024 * 1024,
            max_local_bytes=20 * 1024 * 1024,
            # A 24 megapixel photograph, 6000 x 4000, fits; decoded as RGBA
            # this is 100 MB.
            max_image_pixels=25_000_000,
            max_resources=100,
            max_total_bytes=50 * 1024 * 1024,
            max_fetch_seconds=10,
            max_render_seconds=60,
            max_document_bytes=10 * 1024 * 1024,
            # Far from the ~1,200 levels where the walks run out of stack.
            max_depth=200,
            allow_remote_pdf_backgrounds=False,
        )
        return replace(policy, **overrides)  # type: ignore[arg-type]

    @property
    def roots(self) -> tuple[Path, ...]:
        """
        The directories local reads are confined to.

        Empty when confinement is off, and empty when it is on but nothing was
        configured to bound it -- :meth:`check_path` tells those two apart.
        """
        if self.allow_local_outside_base:
            return ()
        roots = [*self.extra_roots]
        if self.base_dir is not None:
            roots.insert(0, self.base_dir)
        resolved = []
        for root in roots:
            try:
                resolved.append(Path(root).resolve())
            except OSError:  # noqa: PERF203
                log.debug("Ignoring unresolvable resource root %r", root)
        return tuple(resolved)

    def check_url(self, url: str) -> None:
        """Raise :class:`ResourceAccessError` unless ``url`` may be fetched."""
        parts = urlparse.urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme not in KNOWN_SCHEMES:
            msg = f"scheme {scheme!r} is not allowed: {url[:120]!r}"
            raise ResourceAccessError(msg)
        if scheme not in REMOTE_SCHEMES:
            return
        if not self.allow_remote:
            msg = f"remote resources are not allowed: {url[:120]!r}"
            raise ResourceAccessError(msg)

        host = parts.hostname
        if not host:
            msg = f"no host to check in {url[:120]!r}"
            raise ResourceAccessError(msg)

        if self.allowed_hosts is not None and host.lower() not in self.allowed_hosts:
            msg = f"host {host!r} is not in the allowed hosts"
            raise ResourceAccessError(msg)

        if self.allow_private_networks:
            return

        for address in self._resolve(host, parts.port, url):
            if _is_internal(address):
                msg = (
                    f"host {host!r} resolves to the internal address "
                    f"{address}, which a rendered document may not reach"
                )
                raise ResourceAccessError(msg)

    @staticmethod
    def _resolve(
        host: str, port: int | None, url: str
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """
        Every address ``host`` resolves to.

        A name is checked by what it resolves to, not by how it is spelled, so
        a name pointing at 127.0.0.1 or at the metadata service is caught. A
        name that does not resolve is refused rather than passed through: the
        fetch could not have succeeded anyway, and a resolution this code
        cannot see is one it cannot vet.

        This does not close the DNS-rebinding window -- http.client resolves the
        name again when it connects, and a name can answer differently the
        second time. Pinning the checked address would mean taking over
        connection setup; ``allowed_hosts`` is the answer where that matters.
        """
        try:
            info = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            msg = f"cannot resolve host {host!r} for {url[:120]!r}: {exc}"
            raise ResourceAccessError(msg) from exc
        return [ipaddress.ip_address(entry[4][0]) for entry in info]

    def check_path(self, path: str | Path) -> None:
        """Raise :class:`ResourceAccessError` unless ``path`` may be read."""
        if self.allow_local_outside_base:
            return
        roots = self.roots
        if not roots:
            # Nothing to be relative to. Refusing is the safe reading of that,
            # and the only one that cannot be reached by accident: allowing
            # every path is what ``allow_local_outside_base`` is for.
            msg = (
                f"{str(path)[:120]!r} cannot be read: this policy names no "
                f"directory a document may read. Set base_dir or extra_roots, "
                f"or allow_local_outside_base=True to lift the confinement."
            )
            raise ResourceAccessError(msg)
        try:
            resolved = Path(path).resolve()
        except OSError as exc:
            msg = f"cannot resolve path {str(path)[:120]!r}: {exc}"
            raise ResourceAccessError(msg) from exc
        # resolve() follows symlinks, so a link planted inside a root that
        # points outside it is caught here rather than granting access.
        if any(resolved == root or resolved.is_relative_to(root) for root in roots):
            return
        msg = (
            f"{str(resolved)[:120]!r} is outside the directories this document "
            f"may read ({', '.join(str(root) for root in roots)})"
        )
        raise ResourceAccessError(msg)

    def check_size(self, size: int, url: str | Path) -> None:
        """Raise :class:`ResourceAccessError` if a resource is too large."""
        limit = self.max_resource_bytes
        if limit is not None and size > limit:
            msg = (
                f"{str(url)[:120]!r} is larger than the {limit} bytes a single "
                f"resource may take"
            )
            raise ResourceAccessError(msg)

    def check_local_size(self, size: int, where: str | Path) -> None:
        """Raise :class:`ResourceAccessError` if a local resource is too large."""
        limit = self.max_local_bytes
        if limit is not None and size > limit:
            msg = (
                f"{str(where)[:120]!r} is larger than the {limit} bytes a local "
                f"resource may take"
            )
            raise ResourceAccessError(msg)

    def check_image_pixels(self, width: float, height: float, where: object) -> None:
        """Raise :class:`ResourceAccessError` if an image is too large to decode."""
        limit = self.max_image_pixels
        pixels = int(width) * int(height)
        if limit is not None and pixels > limit:
            msg = (
                f"{str(where)[:120]!r} is {int(width)} x {int(height)} = "
                f"{pixels} pixels, more than the {limit} an image may decode to"
            )
            raise ResourceAccessError(msg)


#: No confinement at all: any host, any path. Used for resources the *caller*
#: named explicitly (the source document on the command line) and by
#: ``--unsafe-resources``.
PERMISSIVE_POLICY: ResourceAccessPolicy = ResourceAccessPolicy(
    allow_private_networks=True, allow_local_outside_base=True
)


def default_policy(base_dir: str | Path | None = None) -> ResourceAccessPolicy:
    """
    The policy a document gets when its caller did not choose one.

    Public HTTP(S) still works; internal addresses do not, and local reads are
    confined to ``base_dir`` -- the directory of the document being rendered.
    A document rendered from a string has no directory of its own, so the
    working directory stands in, which is where its relative paths resolve
    anyway.
    """
    if base_dir and urlparse.urlsplit(str(base_dir)).scheme:
        # A document loaded over http has a URL for a base, not a directory.
        # Local reads have nothing to be relative to, so the working directory
        # is the honest bound.
        base_dir = None
    return ResourceAccessPolicy(base_dir=Path(base_dir) if base_dir else Path.cwd())


class _ActivePolicy(threading.local):
    """
    The policy in force on this thread.

    Per-thread for the same reason ``TmpFiles`` is: a WSGI worker rendering one
    document must not have its policy replaced by another request's build.
    """

    def __init__(self) -> None:
        super().__init__()
        self.policy: ResourceAccessPolicy | None = None
        self.budget: RenderBudget | None = None


_active: _ActivePolicy = _ActivePolicy()


def current_policy() -> ResourceAccessPolicy:
    """
    The policy to apply to a fetch nobody passed one for.

    Inside a document build this is the build's policy; outside one it is
    :data:`PERMISSIVE_POLICY`, because a direct call into
    :mod:`xhtml2pdf.files` comes from the integrator's own code rather than
    from untrusted markup.
    """
    return _active.policy or PERMISSIVE_POLICY


def active_policy() -> ResourceAccessPolicy | None:
    """
    The policy a surrounding ``use_policy`` block put in force, if any.

    Distinct from :func:`current_policy`, which substitutes the permissive one
    when nothing is active: a caller deciding whether to build a default of
    its own has to be able to tell "nobody chose" from "somebody chose to
    allow everything".
    """
    return _active.policy


class RenderBudget:
    """
    What one render has spent against its policy's limits on the whole.

    A policy is shared, frozen, often a module constant; what a render has
    used so far is not, so it lives here, one per render.
    """

    def __init__(self, policy: ResourceAccessPolicy) -> None:
        self.policy: ResourceAccessPolicy = policy
        self.started: float = time.monotonic()
        #: The resources charged so far, so that one read twice -- an image
        #: used on every page, or the same file asked for by getData() and
        #: notFound() -- is charged once.
        self.charged: set[object] = set()
        self.total_bytes: int = 0

    def remaining(self) -> float | None:
        """Seconds left before the render's deadline, or None for no deadline."""
        limit = self.policy.max_render_seconds
        if limit is None:
            return None
        return limit - (time.monotonic() - self.started)

    def check_deadline(self) -> None:
        """Raise :class:`RenderLimitError` once the render is out of time."""
        remaining = self.remaining()
        if remaining is not None and remaining <= 0:
            msg = (
                f"the render took longer than the "
                f"{self.policy.max_render_seconds:g} seconds it may take"
            )
            raise RenderLimitError(msg)

    def admit(self, key: object, where: object) -> None:
        """Raise :class:`ResourceAccessError` if one more resource is too many."""
        limit = self.policy.max_resources
        if limit is not None and key not in self.charged and len(self.charged) >= limit:
            msg = (
                f"{str(where)[:120]!r} would be more than {limit} resources "
                f"in one document"
            )
            raise ResourceAccessError(msg)

    def charge(self, key: object, size: int, where: object) -> None:
        """Count a resource that was read, or refuse it if it does not fit."""
        if key in self.charged:
            return
        self.admit(key, where)
        limit = self.policy.max_total_bytes
        if limit is not None and self.total_bytes + size > limit:
            msg = (
                f"{str(where)[:120]!r} does not fit in the {limit} bytes one "
                f"document's resources in all may take"
            )
            raise ResourceAccessError(msg)
        self.charged.add(key)
        self.total_bytes += size


@contextmanager
def render_budget(policy: ResourceAccessPolicy) -> Iterator[RenderBudget]:
    """
    Keep a budget for the render in this block.

    A render nested in another -- pisaStory inside pisaDocument -- shares the
    outer one's budget rather than starting its clock again.
    """
    if _active.budget is not None:
        yield _active.budget
        return
    _active.budget = RenderBudget(policy)
    try:
        yield _active.budget
    finally:
        _active.budget = None


def active_budget() -> RenderBudget | None:
    """The budget of the render in progress on this thread, if any."""
    return _active.budget


def check_deadline() -> None:
    """Raise :class:`RenderLimitError` if the render in progress is out of time."""
    if _active.budget is not None:
        _active.budget.check_deadline()


@contextmanager
def use_policy(policy: ResourceAccessPolicy | None) -> Iterator[None]:
    """Make ``policy`` the active one for the duration of the block."""
    previous = _active.policy
    _active.policy = policy
    try:
        yield
    finally:
        _active.policy = previous
