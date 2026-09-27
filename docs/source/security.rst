Security
========

A document decides what the converter does: which files it opens and which
hosts it talks to. If the HTML you convert is your own, there is little here
to think about. If any of it comes from somewhere else -- a rich-text field,
an uploaded template -- then its author is choosing what your server fetches.

Two things a document could ask for, and no longer can by default:

.. code:: html

    <!-- cloud instance credentials, from inside your VPC -->
    <img src="http://169.254.169.254/latest/meta-data/">

    <!-- a file the document has no business seeing -->
    <img src="/etc/passwd">

What is refused by default
--------------------------

* Destinations that resolve to an internal address: loopback, private,
  link-local (where cloud metadata services live), multicast, reserved. A host
  is judged by the address it resolves to, on every hop of a redirect chain.
* Local reads outside the document's own directory -- the directory of the
  ``path`` argument, or the working directory for a document rendered from a
  string. Symlinks and ``..`` are resolved first.
* Schemes the fetcher does not understand, such as ``ftp:``.

Public HTTP(S) is unaffected. A refused resource is logged by
``xhtml2pdf.files`` at warning level and left out of the document; the render
continues, as it does for a resource that is merely unreachable.

Rendering untrusted HTML on a server
------------------------------------

The default keeps a document away from your network and your files, but not
from your worker's memory and time. ``ResourceAccessPolicy.server()`` turns
every limit below on at once:

.. code:: python

    from xhtml2pdf import pisa
    from xhtml2pdf.config.resources import RenderLimitError, ResourceAccessPolicy

    policy = ResourceAccessPolicy.server(base_dir="/srv/app/media")

    try:
        pisa.CreatePDF(user_html, dest=out, resource_policy=policy)
    except RenderLimitError:
        ...  # too large, too deep or too slow: tell the user

=========================  ==================================
``max_resource_bytes``     20 MiB per fetched resource
``max_local_bytes``        20 MiB per local file or ``data:`` URI
``max_image_pixels``       25 million (a 6000 x 4000 photograph)
``max_resources``          100 files and URLs
``max_total_bytes``        50 MiB for all of them
``max_fetch_seconds``      10 seconds per fetch
``max_render_seconds``     60 seconds
``max_document_bytes``     10 MiB of source
``max_depth``              200 levels of nesting
=========================  ==================================

It also refuses a PDF page background that was fetched or written inline
(``allow_remote_pdf_backgrounds=False``).

Without ``base_dir`` local reads are denied outright, rather than confined to
the working directory, which on a server holds its source and its settings.
Any field can be passed to change one limit and keep the rest:
``ResourceAccessPolicy.server(media, max_render_seconds=20)``.

Server deployment checklist
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Use ``ResourceAccessPolicy.server()`` and handle ``RenderLimitError``.
* Name the hosts a document may fetch from with ``allowed_hosts``, or turn
  remote fetches off with ``allow_remote=False``. The address check alone
  cannot close DNS rebinding: the connection resolves the name a second time,
  and a name can answer differently.
* Do not turn off certificate checks (``nosslcheck``, ``--http_nosslcheck``)
  for untrusted documents: that lets anyone on the path answer for the host.
* Still run conversions in a process you can bound from outside -- memory,
  CPU, a wall-clock kill. The limits here are checked between steps, and a
  single step, such as laying out one very large table, is not interrupted.
* Fonts from ``@font-face`` are registered process-wide by family name, so
  in a process shared between tenants one document's font can stand in for
  another's. Render tenants' documents in separate processes until that
  changes.

Choosing your own policy
------------------------

The default is a floor. An application rendering untrusted HTML should say
what it actually allows:

.. code:: python

    from pathlib import Path

    from xhtml2pdf import pisa
    from xhtml2pdf.config.resources import ResourceAccessPolicy

    policy = ResourceAccessPolicy(
        allowed_hosts=frozenset({"cdn.example.com"}),
        base_dir=Path("/srv/app/media"),
        extra_roots=(Path("/srv/app/fonts"),),
    )

    pisa.CreatePDF(user_html, dest=out, resource_policy=policy)

``allow_remote`` (default ``True``)
    Fetch over http(s) at all. ``False`` for a renderer that should only ever
    use local assets and inline ``data:`` URIs.

``allow_private_networks`` (default ``False``)
    Permit internal addresses, for assets that really do live on the LAN.

``allowed_hosts`` (default ``None``)
    Fetch only from these hosts. This is also the answer to DNS rebinding,
    which the address check alone cannot close: the connection resolves the
    name again and it can answer differently.

``base_dir``, ``extra_roots``, ``allow_local_outside_base``
    Where local reads may go. ``base_dir`` defaults to the working directory,
    so a policy you build by hand confines local reads whether or not you
    thought about it; naming a directory of your own is better, because the
    working directory of a server holds its source, its settings and often its
    database. ``base_dir=None`` names no directory and denies local reads
    outright. ``allow_local_outside_base=True`` lifts the confinement and
    keeps the network rules.

``max_resource_bytes`` (default 20 MiB)
    How large one fetched resource may be, checked against the declared
    ``Content-Length``, against the body as it is read, and again against what
    a gzipped body expands to. The document chooses the server it downloads
    from, so without this a 200 KB response can arrive as 200 MB of memory.
    ``None`` removes the limit.

``max_local_bytes`` (default ``None``)
    How large a local file or a decoded ``data:`` URI may be. A local file is
    refused from its size on disk, before it is opened. Off by default, since
    a local read has always been unbounded and the document you render may
    sit beside large assets of its own.

``max_image_pixels`` (default ``None``)
    How many pixels an image may decode to: ``<img>``, a list marker, a
    ``background-image``, a page background, and the raster an SVG is drawn
    as. It is read from the image header, before anything is decoded. The
    byte limits cannot do this: a PNG of a few hundred bytes can declare
    50,000 x 50,000 pixels. With ``None`` only Pillow's own guard remains,
    which refuses about 179 million pixels. A refused image is left out of
    the document.

``max_resources``, ``max_total_bytes`` (default ``None``)
    How many distinct files and URLs one render may read, and how many bytes
    they may add up to. A resource used twice counts once, and ``data:``
    URIs are part of the document rather than resources. What does not fit
    is left out, like any refused resource.

``max_fetch_seconds`` (default ``None``)
    How long one network fetch may take in all, retries and redirects
    included. The socket timeout of five seconds bounds each read only, so a
    server sending a byte every four seconds is never cut off without this.

``max_render_seconds``, ``max_document_bytes``, ``max_depth`` (default ``None``)
    Limits on the render as a whole: its time, the size of the source
    document, and how deeply its elements nest. There is no useful remainder
    to a document that breaks one of these, so the render is abandoned with
    ``RenderLimitError`` rather than continued without something. Time is
    checked between elements, fetches and flowables, so it is a bound rather
    than a precise stop.

``allow_remote_pdf_backgrounds`` (default ``True``)
    Whether ``@page { background-image }`` may name a PDF fetched over the
    network or written as a ``data:`` URI. A PDF is parsed by pypdf, and one
    from anywhere but a file beside the document is the document author's
    input. A local PDF is still used. Whatever its source, a PDF that cannot
    be read is logged and left out rather than aborting the render.

A renderer with several entry points can set the policy once around a build
instead of passing it to every call. The ``resource_policy`` argument still
wins over it:

.. code:: python

    from xhtml2pdf.config.resources import use_policy

    with use_policy(policy):
        pisa.CreatePDF(html, dest=out)

Two policies come ready-made. ``default_policy(base_dir=None)`` builds the one
described at the top of this page, which is what a build that chooses nothing
gets. ``PERMISSIVE_POLICY`` turns all of it off and fetches anything: it is
what ``--unsafe-resources`` selects, and what xhtml2pdf already uses for a
resource *you* named -- the source document itself -- rather than one the
markup asked for.

.. code:: python

    from xhtml2pdf.config.resources import PERMISSIVE_POLICY, default_policy

A refused resource raises ``ResourceAccessError`` inside the fetcher, which a
render logs and steps over: the document comes out with that resource missing
rather than failing. Only a caller using the fetcher directly sees the
exception.

.. warning::

   ``link_callback`` is not a security boundary, and this is where an existing
   integration usually meets the policy. It rewrites a URI; it does not
   authorise one. A callback that maps ``/static/x.css`` onto a shared asset
   directory needs that directory named in ``base_dir`` or ``extra_roots``. It
   is also optional, defaults to ``None``, and around ten fetches inside the
   library never reach it -- fonts, watermarks, signatures, the image reader.
   The policy sits below all of them.

Calling the fetcher yourself
----------------------------

``xhtml2pdf.files.getFile("/etc/passwd")`` from your own code is your code
asking for your own file, not an attacker-controlled fetch, and is
unrestricted unless you pass ``policy=``.

On the command line
-------------------

The document you name is your own, so local reads are not confined there; the
network rules still apply. ``--resource-root`` asks for confinement, for
converting HTML that came from somewhere else. The flags are listed in
:doc:`reference/cli`.

Before 0.2.19, ``--start-viewer`` built a shell command by string
interpolation, so a destination whose name contained shell metacharacters was
executed rather than opened (CWE-78). If you compose that name from user
input, upgrade.

What this does not protect you from
-----------------------------------

* **Resource exhaustion, by default.** Unless you choose the limits above,
  a document can ask for a very large image or thousands of pages, and
  nothing bounds conversion time or memory. Even with them, a single step of
  the layout is not interrupted; run untrusted conversions where you can
  bound both from outside.
* **What you do with the PDF afterwards.** xhtml2pdf writes a file; it does
  not sanitise what reads it.

Reporting a vulnerability
-------------------------

Privately, by email, rather than in a public issue: **luisza {at} gmail.com**.
Include the component affected, how to reproduce it, and the impact. The
project patches the default branch and issues a fix release; older versions
are not backported. Full statement in ``SECURITY.md``.
