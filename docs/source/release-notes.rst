#############
Release Notes
#############

***************
Versions >= 0.2
***************


..
    This is a template: Please copy it and then remove indentation!

    X.X.X
    ====================

    Released: YYYY-MM-DD

    **🎉 New**

    * Note: for new, great features
    *

    **💪🏼 Improvements**

    * Note: for smaller improvements
    *

    **🐛 Bug-Fixes**

    * Note: Please reference GitHub issues with :issue:`999` and pull requests with :pr:`999`
    *

    **⚠️ Deprecation**

    * Note: For any dropped Python versions, ReportLab versions, xhtml2pdf arguments etc.
    *

    **📘 Documentation**

    *
    *

    **🧹 Cleanup**

    *
    *

    | Thanks to the following people on GitHub for contributing to this release:
    | *GitHub-Name-1*, *GitHub-Name-2* and *GitHub-Name-3* (Note: mention all the merged pull requests since last release here!)

    --------------------------------------------


0.2.20
====================

Released: 2026-09-15

**🎉 New**

* **CSS flexbox.** ``display: flex`` lays the element's children out in a
  row or a column, following CSS Flexible Box Layout Module Level 1:
  ``flex-direction``, ``flex-wrap``, ``flex-flow``, ``justify-content``,
  ``align-items``, ``align-self``, ``align-content``, ``gap``/``row-gap``/
  ``column-gap``, ``flex-grow``, ``flex-shrink``, ``flex-basis``, ``flex``,
  ``order``, ``min-``/``max-width``/``height`` on the items and ``margin:
  auto``. Before this ``display: flex`` fell through to ``inline`` and the
  children ran into their parent's text. See the Flexbox section of the
  HTML reference for what is and is not supported.
* **``display: inline-block``.** A box inside the line of text, with its
  own width, height, padding, border and background, placed by
  ``vertical-align`` like an inline image. Form controls -- ``<input>``,
  ``<select>``, ``<textarea>`` -- are inline blocks by default and sit in
  the line instead of each closing the paragraph it was in.
* **Inline boxes.** An inline element with ``padding``, a ``border``, a
  ``background-image`` or side margins is drawn as a box around its text,
  in the line: the padding widens the line, the box is painted under the
  words, and one cut by a line break or a page break goes on from the
  next line without an edge at the cut. Before this, padding and borders
  on a ``<span>`` were ignored.
* **Flex containers break across pages.** A container that does not fit
  the room left on a page is cut where the page ends, through its line
  and its items, the way a browser fragments it: each item goes on at
  the top of the next page without an edge at the cut, an item whose
  content cannot break there moves whole, and a line with nothing to
  show above the cut moves whole.
* **A ``font-family`` list is matched per character**, as CSS says it is.
  The first family that existed used to draw everything, so a document
  naming a Latin face first lost every character that face had no glyph
  for: ``ěščřžýáíéí`` came out ``■š■■žýáíéí``, the boxes being exactly the
  letters Helvetica lacks. ``font-family: Helvetica, MySans`` now reaches
  ``MySans`` for those and leaves the rest where it was, and
  ``font-family: "Noto Sans Devanagari", "Noto Sans"`` gives a Devanagari
  subset font the Latin it does not carry. A character no family on the
  list has is reported, by character and by the fonts tried.
* **Right-to-left documents.** A direction declared with ``dir="rtl"`` or
  with ``<pdf:language name="arabic"/>`` now turns the document round
  rather than only reshaping its text: paragraphs are aligned to the right
  unless ``text-align`` says otherwise, and a table's columns run from the
  right, so the first ``<td>`` of a row is its rightmost cell. Hebrew or
  Arabic inside an otherwise left-to-right paragraph is reordered too --
  the bidirectional algorithm used to run only on documents that declared
  a direction, so a Hebrew word in an English sentence read backwards.

**💪🏼 Improvements**

* Every value of ``display`` now means something: ``table``,
  ``list-item``, ``flow-root``, ``grid`` and the ``table-*`` values are
  laid out as ``block`` (before, only ``block`` and ``none`` were looked
  at, so ``display: table`` on a ``<div>`` did not even make it a block),
  and a value this library does not know is reported once rather than
  silently treated as ``inline``.
* The ``flex``, ``flex-flow`` and ``gap`` shorthands are expanded, and a
  flexbox value this library does not support (``align-items: last
  baseline`` is drawn as ``flex-end``) is reported once, by value.
* ``align-items: baseline`` and ``align-self: baseline`` line flex items
  up on the first baseline of their text, the way a browser does; an
  item with no text is aligned by its bottom edge. An inline block with
  ``vertical-align: baseline`` sits on the baseline of its last line of
  text rather than on its bottom edge.
* CSS's generic font families are answered deliberately rather than by
  accident. Only ``sans`` and ``sansserif`` were listed, so ``sans-serif``
  -- the commonest ``font-family`` there is -- matched nothing and arrived at
  Helvetica through the fallback. ``cursive``, ``fantasy``, ``system-ui``,
  ``math`` and the ``ui-*`` families are answered too, each with the nearest
  base-14 face.
* Choosing a font no longer fails in silence. A ``font-family`` that names
  nothing the document knows, a ``@font-face`` whose ``src`` could not be
  read, a CJK name ReportLab does not have, and a second ``@font-face``
  reusing a family name already embedded in the process from another file
  each now say so, naming the family and what was used instead. All four
  used to end in Helvetica with nothing in the log, which made a missing
  font indistinguishable from a missing glyph.
* Arabic letters are no longer replaced by empty boxes when the font has no
  presentation form for them. Joining is done by substituting those forms,
  and a font built for OpenType shaping carries few or none; ligatures are
  dropped first and the letters left unjoined second.
* A font, image or stylesheet that already is a local file is read where it
  lies. It used to be copied through a temporary file first -- read whole,
  written out, and read again -- although the resource policy had already
  vetted the path.

**🐛 Bug-Fixes**

* On Windows, a document with any ``@font-face`` could not be converted:
  ReportLab's open of the font raised ``PermissionError``/``TTFError``.
  xhtml2pdf wrote the font to a ``NamedTemporaryFile``, kept the handle
  open and handed ReportLab the *name*, and on Windows that handle is an
  exclusive share, so the second open could not succeed. A name handed out
  for another library to open now belongs to a closed file, removed at the
  end of the render instead of on close. The same applies to the canvas a
  watermark is drawn on.
* An inline box -- a ``<span>`` with ``padding``, a ``border`` or a
  ``background`` -- a ``display: inline-block``, or any form control,
  which is an inline block by default, stopped the conversion with
  ``OSError: Cannot open resource ...afm, while looking for faceName=...``
  in any document whose font came from ``@font-face``. The frag that
  carries the box holds no text, so it never passed through the step that
  turns a family name into the concrete face registered for it, and an
  embedded TTF is registered as ``<family>_00``. A base-14 family happened
  to survive because it is registered under its own name.
* A family named with the documented ``#`` prefix -- the way to embed
  several TTFs that share one internal face name -- was registered with the
  ``#`` stripped and looked up with it kept, so it was never found and the
  text was drawn in Helvetica.
* A source given as ``bytes`` ignored the ``encoding`` argument. Only a
  ``str`` source carried the caller's encoding through to the HTML parser;
  bytes fell through to the parser's own sniffing, whose last resort is
  windows-1252, so UTF-8 bytes came out as mojibake -- a bullet as
  ``â€¢`` -- however plainly ``encoding="utf-8"`` had been passed. Naming
  no encoding still leaves the document's own ``<meta charset>`` to decide.
* The writing direction had no end. ``dir="rtl"`` on a ``<div>`` or a
  ``<p>``, or a ``<pdf:language>`` naming a right-to-left language, was one
  value for the whole file, set by whichever element declared it last and
  never put back -- so a single right-to-left paragraph left every table
  after it with its columns reversed and every paragraph right-aligned with
  its full stop moved to the front. It is bounded by the element that
  declares it now, and ``<pdf:language name=""/>`` ends it where it says it
  does.
* ``dir="rtl"`` reversed each fragment with ``str[::-1]`` and its words
  twice over, on top of the bidirectional algorithm that had already run, so
  the Latin words of a right-to-left document came out backwards -- "and
  Latin text" as "dna nitaL txet". A right-to-left line is laid out by
  aligning it to the right, not by turning its words around.
* A document that declared both ``dir="rtl"`` and ``<pdf:language>`` had its
  text put through the reshaper twice, once per fragment and once more over
  the whole paragraph, which could leave a NUL in the middle of it.
* ``dir`` on the ``<html>`` element was ignored. It was read on ``<body>``,
  ``<div>`` and ``<p>``, but the root element is where a document usually
  declares its direction.
* ``<pdf:language name="Arabic"/>`` did nothing when it was not spelled in
  lower case: it reshaped no text, and was excluded from ``/Lang`` for being
  a language name, so it did neither job.
* ``width`` and ``height`` were handed down from a block to everything
  inside it, because the frag a child starts from is a clone of its
  parent's and neither was ever put back. CSS inherits neither, and in a
  flex container it was doing real damage: every item took the
  container's own width and height as its own, which made the item's
  cross size definite and stopped ``align-items: stretch`` from ever
  sizing an item to its line.
* A flex container with a declared ``height`` that was cut between pages
  gave both parts the whole height, so the first part no longer fit the
  room it was cut for. The height is now shared: the first part takes
  what it shows, the second the rest.
* A percentage ``row-gap`` was resolved against the container's width.
  css-align 8.3 resolves a gap against the container's own content box
  in that gap's axis, so a percentage ``row-gap`` goes against the
  height, and counts as zero when the height is indefinite -- which, for
  a container that takes its content's height, it usually is.
* ``vertical-align: top`` and ``bottom`` were drawn as ``text-top`` and
  ``text-bottom``. CSS 2.1 10.8.1 aligns the first pair with the edges of
  the whole line box and the second with the parent's content area, so
  the four only coincide when nothing else on the line is taller. The
  line box is known once the line has been assembled, which is where the
  two are now told apart. This reaches inline images too, and an ``<img>``
  with no ``align`` is aligned ``bottom``, so an image sharing a line with
  something taller than itself now sits at the line's bottom edge rather
  than a fifth of the font size below the baseline.
* An inline image measured more than once came out smaller each time: the
  paragraph scaled the size it found instead of the image's natural size,
  so ``-pdf-keep-in-frame-mode: shrink`` -- which measures its content
  repeatedly -- shrank every image twice. Images inside a shrunk frame are
  now the size the frame's scale gives them.

**📘 Documentation**

* :doc:`reference/html` documents flexbox and inline blocks: which
  properties are read, and where the layout differs from a browser's on
  purpose -- ``inline-flex`` as block-level ``flex``, ``align-content``
  needing a length ``height``, a ``column`` without one never wrapping, and
  how a container is fragmented at a page edge.
* :doc:`guide/fonts` is rewritten around what font matching now does: a
  ``font-family`` list resolved per character, what happens when no family
  on it has the character, and the fact that a family the document embeds
  beats a built-in alias of the same name -- the guide said the opposite.
  Its right-to-left section says what declaring a direction actually turns
  round, and how far the Arabic joining goes.

--------------------------------------------


0.2.19
====================

Released: 2026-09-12

This is primarily a security release. Read :doc:`security` before upgrading if
you convert HTML that anyone but you wrote: the defaults changed, and an
application that resolves its assets through ``link_callback`` will have to
say where they live.

**🔐 Security**

* **A rendered document can no longer reach internal network addresses.**
  ``<img src="http://169.254.169.254/latest/meta-data/">`` returned cloud
  instance credentials from inside the VPC. Loopback, private, link-local,
  multicast and reserved addresses are refused by default, on every hop of a
  redirect chain, and a host is judged by the address it resolves to.
* **A rendered document can no longer read arbitrary files.**
  ``<img src="/etc/passwd">`` worked; local reads are now confined to the
  document's own directory, symlinks and ``..`` included.
* **The PDF viewer is no longer started through a shell.** A destination whose
  name contained shell metacharacters was executed rather than opened
  (CWE-78). ``startViewer`` is public API and reachable from the ``-d``
  argument of the command line tool.

  Public HTTP(S) is unaffected by any of this, and a refused resource is
  logged rather than fatal. Callers choose their own policy with the
  ``resource_policy`` argument of ``pisaDocument``, with ``use_policy`` around
  a build, or on the command line with ``--resource-root``, ``--allow-host``,
  ``--allow-private-networks``, ``--no-remote`` and ``--unsafe-resources``.
  See :doc:`security`.

* **A stylesheet can no longer hold a worker with a handful of characters.**
  The CSS string and escape patterns each gave the regular expression engine
  two ways to match the same character, so a string nobody closed backtracked
  catastrophically: ``<style>a{content:"`` followed by 40 backslashes cost
  three minutes of CPU, and every further four characters multiplied that by
  eight.
* **The same for a colour written as an HTML attribute.**
  ``<td bgcolor="rgb(`` and 90 digits cost 23 seconds per attribute; the
  pattern's three unanchored ``.*?`` are gone, and it is matched once rather
  than twice. A channel above 255 is now clamped, as it already was for a
  colour the parser hands over as a function.
* **A conversion that fails no longer leaks a file descriptor.**
  Temporary files were closed at the end of the build, where an exception
  skipped it, so every document that failed to convert left a descriptor and
  a deleted-but-open inode behind for the life of the thread.
* **A fetched resource now has a size limit**, 20 MiB by default and
  ``max_resource_bytes`` on the policy. A rendered document names the server
  it downloads from, and nothing looked at what came back: a 203 KB response
  declaring ``Content-Encoding: gzip`` expanded to 209 MB of resident memory,
  and twenty ``<img>`` like it took the worker. The limit is checked against
  the declared ``Content-Length``, against the body as it is read, and again
  against what a gzipped body expands to.
* **A policy built by hand no longer opens the filesystem.**
  ``ResourceAccessPolicy``'s ``base_dir`` defaulted to ``None`` and ``None``
  meant no confinement, so ``ResourceAccessPolicy(allowed_hosts=...)`` --
  tightening the network rules -- silently allowed a document to read any file
  the process could. ``base_dir`` now defaults to the working directory, as
  ``default_policy()`` always did, and ``base_dir=None`` denies local reads
  rather than allowing all of them. ``allow_local_outside_base=True`` is how
  the confinement is lifted, and ``PERMISSIVE_POLICY`` and the command line
  are unchanged.

**🎉 New**

* The document's language is written to the PDF catalog as ``/Lang``, from
  ``<html lang="es-CR">`` or ``<pdf:language name="fr"/>``. Screen readers and
  PDF/UA read the document language from there, and xhtml2pdf never declared
  it.
* A table of contents can fill the gap between an entry and its page number.
  ``-pdf-toc-leader`` takes ``none`` (the default), ``space``, ``dots``,
  ``dashes``, ``line``, or any other string to repeat; ``<pdf:toc
  leader="dots" />`` sets it for the whole table and a ``.pdftoclevelN`` rule
  for one level. See :doc:`reference/html`.
* A document can have more than one table of contents. ``<pdf:toc
  name="figures" />`` takes only the entries that name it with
  ``-pdf-toc-name: figures``, so a list of figures or of tables can sit beside
  the general contents, each with its own fill and typography. An entry
  belongs to exactly one of them. A second ``<pdf:toc>`` used to fail the
  whole render. See :doc:`reference/html`.

**🐛 Bug-Fixes**

* A table of contents with no entries printed ReportLab's internal
  ``Placeholder for table of contents`` into the finished document.
* ``--start-viewer`` works on Linux. It ran the macOS ``open`` everywhere
  that was not Windows, so it had never done anything there.
* A list item whose content is wrapped in a block keeps its marker.
  ``<li><p>text</p></li>``, which is what rich-text editors emit, lost its
  bullet or number, and so did every other shape a block inside an item can
  take: two blocks in one item, an item followed by a nested list, and an item
  wrapping its text in anything other than ``<p>`` or ``<div>``. A wrapped
  item still hangs under its first line, and ``<li>text<p>block</p></li>`` now
  puts the block on its own line as a browser does.
* ``getSize`` no longer warns ``Not a float '100%'`` for a perfectly valid
  percentage. The value it returned was already correct.
* A table of contents lays its page numbers out flush right, links each one
  to the heading it names, and indents each level. The numbers used to stop an
  inch short of the margin, and a long entry ran into its own page number.

**💪🏼 Improvements**

* **Resolving CSS no longer scans every rule for every property.** Dressing an
  element cost O(elements x properties x rules), which was 30-48% of a render
  and grew with the size of the stylesheet. Rules are now filed under the
  condition an element has to meet, the whole cascade is resolved in one walk
  per element, and the warning that ran on every attribute lookup moved behind
  ``XHTML2PDF_CHECK_CSS_PROPERTIES``. A document of 800 elements against 800
  rules went from 3649 to 392 ms; ``test-loremipsum`` from 408 to 224 ms. What
  comes out is unchanged.
* **An embedded font is parsed once per process rather than once per
  document.** Building a ReportLab ``TTFont`` reads and parses the whole file --
  7 ms for a Latin face, 70 ms for a CJK one, once per declared weight -- and
  ReportLab discarded the result when the name was already registered, so from
  the second document onwards the work was thrown away on arrival. Across a
  gallery of 40 real documents rendered in one process, time inside ``TTFont``
  went from 3.23s to 0s. A process that converts a single file still parses
  each font once, because it has to.
* ``use_policy`` around a build is honoured, so a renderer with several entry
  points can set a resource policy once instead of passing it to every call.
  The order is the ``resource_policy`` argument, then the surrounding block,
  then the default.
* ``<pdf:toc class="...">`` keeps its own classes, so the tag can be styled
  with ``pdftoc.compact.pdftoclevel0``. The level classes no longer leak into
  the rest of the document either.
* The vendored copy of ReportLab's paragraph renderer understands ``<onDraw>``
  again.

**📘 Documentation**

* New :doc:`security` page: what to think about when the markup is not yours,
  the policy options, and how to report a vulnerability.
* The Django example in :doc:`advanced-usage` shows the policy that names
  ``STATIC_ROOT`` and ``MEDIA_ROOT``. Without it that example loses every
  image.
* The Python reference documents ``resource_policy``; the CLI reference
  documents the five resource flags.
* :doc:`reference/html` documents the document language -- what ``<html
  lang>`` and ``<pdf:language>`` each do, and which of the two reaches
  ``/Lang``. :doc:`security` documents the two ready-made policies,
  ``default_policy()`` and ``PERMISSIVE_POLICY``, and what a refused resource
  does to a render.
* ``make devsetup`` builds the development environment in one step: a
  virtualenv, an editable install with the ``test``, ``docs`` and ``release``
  extras, and the pre-commit hooks. The README told contributors to ask for a
  ``build`` extra, which does not exist; the one that brings in ``build`` and
  ``twine`` is ``release``.

**🧹 Cleanup**

* ``pisaContext.cssAttr`` is declared in ``__init__`` rather than appearing
  from the first ``CSSCollect``.

--------------------------------------------


0.2.18
====================

**🎉 New**

* Support for ReportLab 5. The dependency is now ``reportlab>=4.0.4,<6``; both
  major versions are covered by the CI matrix.
* Support for Python 3.14. The CI matrix now covers every supported CPython
  release (3.10 to 3.14) against both ReportLab majors.

**💪🏼 Improvements**

* ``PmlImageReader`` falls back to xhtml2pdf's own fetcher when ReportLab
  refuses a resource. ReportLab 5 changed ``rl_config.trustedHosts=None`` from
  "every host is trusted" to "no host is trusted", so ``open_for_read`` now
  rejects every URL and ``data:`` URI by default. That default is deliberate
  SSRF hardening and is left untouched.
* ``data:`` URIs are parsed per RFC 2397. The percent-encoded form
  (``data:image/svg+xml,%3Csvg...``), which is the usual way inline SVG is
  written, was previously rejected outright; only ``;base64,`` was understood.
* HTTP responses now follow redirects (bounded to 5 hops), accept any 2xx
  status rather than the literal ``200 OK`` reason phrase, close their
  connection, and log a warning instead of a debug message on failure.
* Plain HTTP requests honour the configured ``http_timeout``; it was previously
  only applied to HTTPS connections, so plain HTTP could hang indefinitely.
* The memoization cache in ``xhtml2pdf.util`` is bounded (1000 entries, FIFO)
  and is cleared at the end of each render. Its keys come from CSS in the
  rendered document, so it grew without limit in long-running servers.

**🐛 Bug-Fixes**

* ``@page name:left`` / ``@page name:right`` work. A stray ``sys.exit()`` in
  ``PmlBaseDoc.handle_nextPageTemplate`` terminated the calling process, and the
  vendored ``PTCycle`` predated ReportLab's ``next_value`` protocol, so the
  alternating left/right page feature had never worked. ReportLab's own
  ``PTCycle`` is used now.
* Temporary files are no longer shared between threads. ``TmpFiles`` subclasses
  ``threading.local`` but declared ``files`` as a class attribute, so one
  request's ``cleanFiles()`` closed files another request was still reading.
* ``pisaPDF.addFromString()`` works. It passed an unsupported ``capacity``
  keyword to ``getFile()`` and appended raw bytes where ``PdfReader`` needs a
  file-like object.
* ``pisaFileObject`` accepts ``bytes`` and ``pathlib.Path``, as its type hints
  always claimed. Both raised ``AttributeError``, which was swallowed into a
  silent ``None``.
* The WSGI middleware produces PDFs. ``PisaMiddleware.filter`` wrote PDF bytes
  into a ``StringIO``, and the response buffer rejected the ``bytes`` chunks
  that PEP 3333 requires applications to yield.
* ``Filter.should_filter`` is abstract instead of printing headers to stdout and
  returning ``None``.
* ``Paragraph.getPlainText()`` works; a misplaced bracket made it join a
  sequence of one-element lists and raise ``TypeError`` on every call.
* ``pisaTempFile(capacity=-1)`` keeps its buffer in memory, as documented.
  ``len(buffer) > capacity`` is true for any buffer when capacity is negative,
  so it selected the on-disk strategy immediately -- the opposite of the
  intended behaviour, and the default for ``pisaPDF`` and ``pisaContext``.
* Temporary files are registered with the cleanup registry even when the
  resource is empty. Registration sat inside an ``if data:``, so those files
  were never closed by ``cleanFiles()`` and survived until garbage collection
  (surfaced by the new ``ResourceWarning`` in Python 3.14).
* ``pisaTempFile.getFileName()`` returns the file name instead of ``None``;
  ``name`` was never assigned when the on-disk strategy kicked in.
* The background of ``<body>`` now covers the whole page, as CSS 2.1 14.2
  requires when ``html`` declares no background of its own. It previously
  painted only the area body's boxes occupied, leaving the rest of the page
  white. Found by the new browser comparison; see below.

**⚠️ Deprecation**

* Python 3.8 and 3.9 are no longer supported; the minimum is now Python 3.10.
* The ``renderpm`` extra is deprecated and now an alias for ``pycairo``.
  ReportLab 5 removed the C ``renderPM`` backend together with its ``renderpm``
  extra, so ``reportlab[renderpm]`` silently installed nothing there. The
  pure-Python rlPyCairo backend that ``pycairo`` installs is what
  ``reportlab.graphics.renderPM`` uses now.

**🧹 Cleanup**

* The test suite no longer reaches the public internet; fixtures are served from
  a local HTTP server. A dedicated CI job runs the suite with no outbound
  network at all.
* The rendering comparison in CI is load-bearing. References used to be
  regenerated from the same commit and ReportLab version immediately before
  being compared, and ``--nofail`` suppressed the exit code, so the pixel diff
  could never fail. A cross-version job now builds references with one ReportLab
  major and renders with the other, in both directions. A missing reference
  counts as a difference instead of being silently skipped.
* The tox ``envlist`` matches the CI matrix again; ``TOXENV=py3.13`` previously
  matched no environment, so that leg ran no tests. CI asserts the match.
* ``make test-render`` fails with a clear message when the reference set has not
  been generated yet, instead of reporting every page as a difference. New
  ``make test-render-all`` target creates the reference and compares in one go.
* CI patches whichever ``/etc/ImageMagick-*/policy.xml`` exists rather than
  hardcoding the ImageMagick 6 path.
* New ``testrender/browsercompare.py`` compares xhtml2pdf's output against a
  browser rendering equivalent markup, which is the project's first external
  reference: ``testrender.py`` compares xhtml2pdf against itself and so cannot
  say whether the output is correct. Every fixture has a plain HTML/CSS
  equivalent under ``testrender/data/browser/`` in which the xhtml2pdf-only
  constructs are expressed with ordinary markup -- ``@frame`` as absolute
  positioning, ``<pdf:toc>`` as a hand-written list, ``<pdf:pagenumber>`` as a
  ``counter()`` in an ``@page`` margin box. Run it with ``make test-browser``.
* New tests for previously uncovered modules: ``pdf.py``, ``wsgi.py``, the
  ``pisa`` CLI, ``files.py``, and ``reportlab_paragraph.py``. A contract test
  pins every private ReportLab symbol the package imports.
* Removed the dead ``tests/runtests.py`` harness.

--------------------------------------------


0.2.17
====================

Released: 2025-02-23

**💪🏼 Improvements**

* Reuse background PDF file over multiple pages
* Improve github actions

**🐛 Bug-Fixes**

* fix reDOS CVE in getColor function
* Keep GitHub Actions up to date with GitHub's Dependabot

**📘 Documentation**

* Improve documentation and fixed a lot of typos

| Thanks to the following people on GitHub for contributing to this release:
| *Trupal00p* *cclauss* and *kytta-532-better-docs*


0.2.16
======

Released: 2024-06-08

**🐛 Bug-Fixes**

* Add compatibility for ``reportlab >= 4.1`` (:issue:`751`)

| Thanks to the following people on GitHub for contributing to this release:
| *stefan6419846*


0.2.15
======

Released: 2024-02-08

**🐛 Bug-Fixes**

* Pin ``reportlab>=4.0.4,<4.1`` (:issue:`751`)

| Thanks to the following people on GitHub for contributing to this release:
| *timobrembeck*


0.2.14
======

Released: 2024-01-20

**⚠️ Important notes**

The ``pyCairo`` dependency has been removed to allow the user to define the desired rendering backend individually.
If you need to render bitmaps or vector graphic formats, please specify either ``pycairo`` or ``renderpm`` as extra dependency.

**🐛 Bug-Fixes**

* Remove unintentional packages from wheel (:issue:`736`)
* Make ``pyCairo`` dependency optional (:issue:`741`)
* Fix image rendering with link_callback (:issue:`738`)

| Thanks to the following people on GitHub for contributing to this release:
| *carlsmedstad*, *timobrembeck*


0.2.13
======

Released: 2023-11-09

**🐛 Bug-Fixes**

* Fix ``TypeError`` on column widths specified as percentages (:issue:`731`)
* Fix ``TypeError`` when formatting width in debug logging (:issue:`730`)

| Thanks to the following people on GitHub for contributing to this release:
| *JanEgner*, *timobrembeck*


0.2.12
======

Released: 2023-11-08

**🐛 Bug-Fixes**

* Fix page number & page count (:issue:`106`) (:pr:`695`)
* Fix ``ZeroDivisionError`` on broken image files (:pr:`723`)

**📘 Documentation**

* Update README (:pr:`707`)
* Modernize Sphinx configuration (:pr:`711`)

**🧹 Cleanup**

* Change print statement to log.exception (:pr:`700`)
* Remove Python2 compatibility (:pr:`706`)
* Depend on ``html5lib >= 1.1`` (:issue:`705`) (:pr:`709`)
* Depend on ``reportlab >= 4.0.4`` (:issue:`699`) (:pr:`708`)
* Use black code style (:pr:`714`)
* Enforce consistent file formatting (:pr:`715`)
* Add ruff code linter (:pr:`716`)
* Start using type hints & validate them via mypy (:pr:`717`)
* Drop support for Python 3.7 (reached end of life on 2023-06-27) (:pr:`718`)
* Add support for Python 3.12 (released on 2023-10-02) (:pr:`719`)

| Thanks to the following people on GitHub for contributing to this release:
| *JanEgner*, *lucasgadams*, *a-detiste*, *holtwick*, *stefan6419846*, *timobrembeck*

--------------------------------------------


0.2.11
======

Released: 2023-06-07

This release only aims to fix issues with pycairo and xhtml2pdf dependencies with reportlab.

**🐛 Bug-Fixes**

* Fix setup.py and requirements dependency to set reportlab>=3.5.53,<4 :issue:`688` in :pr:`690`

| Thanks to the following people on GitHub for contributing to this release:
| *gaurab-10*, *jorenham*

--------------------------------------------

0.2.10
======

Released: 2023-04-20

**🐛 Bug-Fixes**

* Fix canvas graph issue :issue:`614` in :pr:`619`

**🧹 Cleanup**

* Remove duplicate pypdf entry from `setup.py` in :pr:`619`

| Thanks to the following people on GitHub for contributing to this release:
| *brandonlake-semaphore*, *sunpoet*

--------------------------------------------


0.2.9
=====

Released: 2023-01-30

**Important notes**

* Text RTL has new implementation but I am not sure if works as required, more works need so use it, for text and let me know if it's works.

**🎉 New**

* OL tag allow start counter
* Div, P, And Body allows dir attribute (rtl and ltr) to provide text direction

**💪🏼 Improvements**

* Page counter and Page number are now available as simple text inside paragraphs
* New regex for strip up to curly bracket
* Change pyPDF3 to pypdf.

| Thanks to the following people on GitHub for contributing to this release:
| *BergLucas*, *matllubos*, *timobrembeck*, *MartinThoma*, *charludo*, *jorenham*

--------------------------------------------


0.2.8
=====

Released: 2022-06-16


**🐛 Bug-Fixes**

* Fix background-image issues with :issue:`614` and pull requests with :pr:`619`
* Fix CSSParseError for minified @font-face definitions  :pr:`609`
* Fixed a few typos and grammar mistakes in usage.rst documentation. :pr:`610`


| Thanks to the following people on GitHub for contributing to this release:
| *MuhammedNihad*, *timobrembeck*, *flash716*

--------------------------------------------

0.2.7
=====

Released: 2022-03-31

**🎉 New**

* Add encryption and password protection
* New WaterMark management system with new options
* Add Graphic builder
* Add signing pdfs (simple and pades)


**🐛 Bug-Fixes**

* Remove import cycle between utils and default
* Fixed link_callback construction of path
* Fixed path when is relative to current path

**⚠️ Deprecation**

*  `xhtml` in pisa.CreatePDF support will removed on next release
*  `XML2PDF` and `XHTML2PDF` will be removed on next release use `HTML2PDF` instead

**📘 Documentation**

* Add render pdf on documentation and add some html example.
* Include graphics examples


| Thanks to the following people on GitHub for contributing to this release:
| *marcelagz* for graphics support :)

--------------------------------------------


0.2.6
=====

Released: 2022-03-11

**🎉 New**

* Set timeout in https options
* Add new file manager approach using factory method, now new classes deal with different types of data B64InlineURI, LocalProtocolURI, NetworkFileUri, LocalFileURI, BytesFileUri
* rtl languages reversed lines added as a ParaFrag (note: not fully supported yet)
* Check if Paragraph has 'rtl' attribute (note: not fully supported yet)
* Add SVG support

**💪🏼 Improvements**

* Update packages dependencies
* Now getColor return None when None is passed ignoring default value, but return default if bool(data) == false
* Change test for github workflow using only Linux
* Add Python 3.9, 3.10
* Switch from PyPDF2 to PyPDF3
* Allow call tests using make.

**🐛 Bug-Fixes**

* Fix UnboundLocalError in reportlab_paragraph (:issue:`585`) (:pr:`586`)

**📘 Documentation**

* Created this release notes section.
* Updated the Sphinx version and the sphinx-rtd-theme version
* Update package information.

**🧹 Cleanup**

* Drop python 2 support.
* Remove most of python 2 code and cleanup
* Remove six dependency and update Readme
* Remove usage of getStringIO (#590) removed form reportlab

| Thanks to the following people on GitHub for contributing to this release:
| *Roman914*, *LeonardoBein*, *myu20*, *myu20*, *captn3m0*, *audoh-tickitto*, *Momoumar*,
| *timobrembeck*, *fbernhart*,*mgodkowicz*, *anze3db * and *luisza*

--------------------------------------------


0.2.5
=====

Released: 2020-10-08

**🎉 New**

* Added Asian fonts support (Simplified Chinese, Traditional Chinese, Japanese & Korean) :issue:`353`
* Added support for right-to-left writings like Arabic, Hebrew, Persian, Pashto, Urdu and Sindhi. Simply include for example ``<pdf:language name="arabic"/>`` :issue:`494`

**💪🏼 Improvements**

* CSS property ``letter-spacing`` now supports float values and relative & absolute units like ``cm``, ``in``, ``em``, ``%`` etc. :issue:`490`
* Added unit tests for Asian and right-to-left fonts. :pr:`520`

**🐛 Bug-Fixes**

* ``@frame`` properties like ``width``, ``right``, ``bottom`` etc. are now correctly calculated depending on the page orientation and size :issue:`499`
* Fixed support for multiple fonts and unicode :issue:`492`
* Fixed an encoding issue with html5lib :issue:`468`
* Fixed a problem with the ``border`` property in ``h1`` to ``h6`` heading tags :issue:`466` :issue:`495`
* Fixed compatibility with ReportLab 3.5.X :issue:`404` :issue:`463`
* Removed default background-image when no background-image is defined :issue:`484`
* Fixed an issue with different font type that have the same name :issue:`381`
* Fixed a bug that prevented support for Python 3.X :issue:`513`
* testrender test: fixed transparences and included new reference files, (now all tests pass in Travis CI without --failed parameter)  :pr:`502`
* ``0.0`` as value for a CSS property now acts the same way as ``0`` and ``None`` :pr:`516`

**⚠️ Deprecation**

* Removed ``i`` and ``inch`` as unofficial synonyms for the ``in`` unit  :pr:`516`

**📘 Documentation**

* Added new section about Asian font support :pr:`505` :pr:`520`
* Added new section about support for right-to-left writings :pr:`520`
* Readme.rst file was updated  :pr:`507` :pr:`512`
* Added missing changelog entries for earlier releases :issue:`478`

**🧹 Cleanup**

* Replaced deprecated ``base64.encodestring`` with ``base64.encodebytes`` :issue:`472`
* Replaced deprecated ``log.warn()`` with ``log.warning()`` :pr:`509`
* Dropped dependency of nose (outdated & unmaintained) in favor of unittest, which is included in the Python standard library :pr:`520`
* Removed the old nose tests and replaced them with unittest :pr:`520`
* Removed unlicensed .tff font files in our tests folder and replaced them with open source fonts :pr:`520`
* Travis CI and AppVeyor are now testing both against the same ReportLab versions (3.3 to 3.5.X) :pr:`520`

| Thanks to the following people on GitHub for contributing to this release:
| *ezawadzki*, *fbernhart*, *KirilNN*, *luisza*, *Mark-Hetherington*, *parthjoshi2007*, *pedroszg*, *silvio-dp*, *sj175*, *tirkarthi* and *z4c*

--------------------------------------------

0.2.4
=====

Released: 2020-01-18

**🎉 New**

* Add ``em`` unit support

**💪🏼 Improvements**

* Added testing for Python 3.7 and 3.8
* Added support for urllib in Python 2 and Python 3

**🐛 Bug-Fixes**

* Fixed cgi escape util on setup version
* Fixed width assignation on fragments
* Repaired base64 unscaped string
* Fixed urlparse when urls has parameters
* Fixed i_rgbcolor support

**📘 Documentation**

* Updated ``link_callback`` documentation
* Stylized code lines in documentation

--------------------------------------------

0.2.3
=====

Released: 2018-09-14

Changes were not documented

--------------------------------------------

0.2.2
=====

Released: 2018-04-16

Changes were not documented

--------------------------------------------

0.2.1
=====

Released: 2018-02-16

**🎉 New**

* Added support for Python 3.8

**💪🏼 Improvements**

* Improved table tests

**🐛 Bug-Fixes**

* Forced html5lib to 1.0.1 (old versions of html5lib are not in pip)
* Allow for URI-escaped strings in base64 data

**🧹 Cleanup**

* Removed the dependency on httplib2

--------------------------------------------

0.2
===

Released: 2018-02-15

**🎉 New**

* Support for a new ``@page`` property: ``background-image``

**💪🏼 Improvements**

* Improved Python 3 support
* Included new ``httplib`` options

**🐛 Bug-Fixes**

* Fix for transparent images in Python 3

**⚠️ Deprecation**

* Removed support for Python 2.3

**📘 Documentation**

* Readthedocs integration
* Updated Django demo site

**🧹 Cleanup**

* PEP8 improvements and code cleanups
* Dropped the ``turbogears`` module

| Thanks to the following people on GitHub for contributing to this release:
| *andreyfedoseev*, *browniebroke*, *flupzor* and *luisza*

--------------------------------------------

0.2beta1
========

Released: 2016-11-30

Changes were not documented

--------------------------------------------


**********************
Versions >= 0.1, < 0.2
**********************

0.1beta3
========

Released: 2016-08-16

Changes were not documented

--------------------------------------------

0.1beta2
========

Released: 2016-08-01

Changes were not documented

--------------------------------------------

0.1beta1
====================

Released: 2016-06-05

Changes were not documented

--------------------------------------------

0.1alpha4
=========

Released: 2016-05-18

* Removed PyPy support
* Avoid exceptions likely to occur systematic to how narrow a text column is #309 - thanks *jkDesignDE*
* Improved tests for tables :pr:`305` - thanks *taddeimania*
* Fix broken empty PDFs in Python2 :pr:`301` - thanks *citizen-stig*
* Unknown page sizes now raise an exception :pr:`71` - thanks *benjaoming*
* Unorderable types caused by duplicate CSS selectors / rules :pr:`69` - thanks *benjaoming*
* Allow empty page definition with no space after @page - :pr:`88` - thanks *benjaoming*
* Error when in addFromFile using file-like object :pr:`245` - thanks *benjaoming*
* Python 3: Bad table formatting with empty columns :pr:`279` - thanks *citizen-stig and benjaoming*
* Removed paragraph2.py, unused ghost file since the beginning of the project :pr:`289` - thanks *citizen-stig*
* Catch-all exceptions removed in a lot of places, not quite done :pr:`290` - thanks *benjaoming*


--------------------------------------------

0.1alpha3
=========

Released: 2016-05-01

* Improved six usage, simplifies codebase :pr:`288` - thanks *citizen-stig*
* Removed mutable types as default args :pr:`287` - thanks *citizen-stig*
* Fix "hangs forever on simple input" :pr:`209`
* Base64 inline <img> works now :pr:`281`

--------------------------------------------

0.1alpha2
=========

Released: 2016-04-14

* Fixed: AttributeError: 'bytes' object has no attribute 'encode' :pr:`265`
* Improved tests, added code coverage

--------------------------------------------

0.1alpha1
=========

Released: 2016-01-20

This major version bump signals that we have added Python 3 support. Other than
that, the project remains largely unchanged.

* Python 3 support
* Cleaning up codebase
* Github and documentation modernizations

--------------------------------------------


**************
Versions < 0.1
**************

0.0.6
=====

Released: 2014-04-27

* get css backgrounds and fonts relative to the css file path
* fix CSS parser breaking on "@media screen and ..." (:issue:`132`)

--------------------------------------------

0.0.5
=====

Released: 2013-03-25

* Switched dependency to Pillow instead of PIL.
* Converted the docs to rst (thanks tomscytale!)
* Huge performance improvements (thanks Andrea Bravetti!)
* Bugfixes.

--------------------------------------------

0.0.4
=====

Released: 2012-05-23

* Added a <pdf:pagecount/> tag to write the total number of pages.
* The <pdf:barcode/> tag now accepts a fontsize argument for the human-readable font.
* Various bugfixes and enhancements

--------------------------------------------

0.0.3
=====

Released: 2011-06-19

Changes were not documented

--------------------------------------------


0.0.2
=====

Released: 2011-05-27

Changes were not documented

--------------------------------------------


0.0.1
=====

Released: 2011-05-20

Changes were not documented

--------------------------------------------


0.0.0
=====

Released: 2011-05-19

Changes were not documented

--------------------------------------------


***************
Legacy Versions
***************

The following changelog entries were relevant before the maintainer change.

"I would like to thank the people mentioned in brackets in this change log
very much for their help and support!" - Dirk


Version 3.0.33, 2010-06-16

- NEW: Changed license to Apache License 2.0, now completely Open Source without any charging. Feel free to continue or for this project.
- FIX: Empty cells now collapse

Version 3.0.32, 2009-05-08

- NEW: New command line option '--base' to specify base path if input comes via STDIN
- FIX: The 'keep in frame' feature for tables did not work inside of static frames (Arun Shanker Prasad)
- FIX: Small typos

Version 3.0.31, 2009-05-04

- NEW: Support for Style "list-style-image", also supports "zoom"
- NEW: Temporary files internally are written to disk if they exceed a certain size
- NEW: Font names can now also read from external URL
- UPD: Modified pdfjoiner.py demo
- FIX: Custom font image problem still appeared
- FIX: Single image in a block issue
- FIX: Randomly used wrong images is fixed using a workaround for the bug in Reportlab _digester routine
- FIX: Empty tables error (Davide Moro)
- FIX: Fallback to urllib2 if httpdlib fails

Version 3.0.30, 2009-03-27

- NEW: Default CSS now hides content of <noscript>
- UPD: Better whitespace handling in RL Paragraph
- FIX: Fixed RL Paragraph.split to work with autoleading and images
- FIX: Small bug fix for show_error_as_pdf
- FIX: Demos used os.startfile which is not supported on non Windows OSes
- FIX: Table available height threw exceptions
- FIX: Switched from urllib2 to httplib for loading external sources
- FIX: Correct homepage and download page in setup.py
- FIX: Paragraphs in lists repeated the bullet
- FIX: Tables now support -pdf-keep-with-next
- FIX: TOC bug fixed
- FIX: Add missing table columns to avoid error in Reportlab table
- FIX: Fix for background images sizing
- FIX: Empty documents now create one blank page
- FIX: Imported fonts caused an error if used together with images

Version 3.0.29, 2008-12-01

- NEW: Warning if Reportlab 2.2 is not installed
- UPD: Better support for named colors
- UPD: Modified frame handling to better support relative values
- FIX: Splitting paragraph threw errors some times; also had problems with line breaks on the second page, fix for RL 2.2 paragraph was needed
- FIX: Added margins to <blockquote> default CSS
- FIX: Inline images in static frames did not work
- FIX: Link anchors and non internal fonts caused a strange error

Version 3.0.28, 2008-11-21

- NEW: Requires Reportlab 2.2 now!
- NEW: Background colors for inline elements like <span>
- NEW: Inline images and left and right aligned images implemented
- NEW: Possibility to handle table cells that are to large via CSS option -pdf-keep-in-frame-mode
- NEW: Option "--system" for command line tool to dump system version infos
- NEW: CSS attribute -pdf-line-spacing for fix space between lines
- NEW: Creation and handling of data URI with base64 encoding (others to come)
- NEW: New general file loader that is also able to load remote data and data URI
- NEW: PDF Joiner to concatenate many PDF and pisa documents
- NEW: Page backgrounds can now be images or PDF
- NEW: Visual Unittests based on ImageMagick and TortoiseIDiff (for Windows)
- NEW: Pisa now raises exceptions if errors occurred; with pisaDocument(..., raise_exception=False) you can turn them off
- UPD: Paragraphs now use the maximum leading to avoid overlapping text
- UPD: Removed "Keep with next" from H1 to H6
- FIX: Sizing of images is now handled better; should better work with PIL
- FIX: Border handling of paragraphs optimized and fixed
- FIX: Images that are higher than the page frame are scaled down to fit
- FIX: Paragraphs only containing &nbsp; are rendered
- FIX: Problem regarding the order of border style definitions
- FIX: Single <br> between two blocks now creates a new line
- FIX: Set table attribute "repeat" to "0"
- FIX: Some <font> attributes did not work as expected
- FIX: Font sizes reworked to behave like browser implementations
- FIX: Like in most HTML browser table cells now have "valign=middle" and table headers have font weight bold
- FIX: Little fix in CSS parsing
- FIX: Default of <link media=""> was "screen", changed to "all"
- FIX: Command line tools did not install with "easy_install"

Version 3.0.27, 2008-10-04

- INF: License changed from Qt to GPLv2
- INF: Not yet completely compatible with Reportlab 2.2 (&nbsp; errors and borders)
- NEW: Command line tool called "xhtml" ("pisa" still available but will be deprecated with pisa 3.1)
- NEW: EGG for Python 2.6
- NEW: Basic support for Data URI
- NEW: New style -pdf-keep-with-next (does not work with pdf:toc for now)
- UPD: Setup now exclusively works with SetupTools

Version 3.0.26, 2008-08-28

- FIX: Python <2.5 didn't work because of a syntax error

Version 3.0.25, 2008-08-15

- UPD: Made imports more explicit to avoid import recursions
- FIX: <pdf:pagenumber/> didn't work in tables (Roman Lisagor)
- FIX: Images without suffixes have been ignored by pisa (Henning von Bargen)
- INF: Preparations for support of HTML FORM using INPUT, TEXTAREA, SELECT

Version 3.0.24, 2008-07-14

- NEW: Support for separate borders on each side of a paragraph has been added (Robin Dunn)
- NEW: Support for font tag (color, face, size)
- UPD: Handling of margin and padding in paragraphs is improved (Robin Dunn)
- UPD: Updated documentation (CreatePDF, Images)
- FIX: A typo in margin-left has been fixed (Robin Dunn)

Version 3.0.23, 2008-06-26

- UPD: getColor() now understands colors like rgb(255,0,0) (Darryl Dixon)
- FIX: c.warning threw errors if no arguments where passed (Searle)
- FIX: pisa now works with html5lib 0.11.1

Version 3.0.22, 2008-06-06

- UPD: Updated documentation
- UPD: Speed optimizations by removing copy.deepcopy (Darryl Dixon)
- FIX: Small fix in CSS parser

Version 3.0.21, 2008-06-05

- FIX: Used a parameter for html5lib that was not supported by html5lib 0.10
- FIX: Now tested against the latest third party packages: ReportLab 2.1, html5lib 0.10, pyPdf 1.11

Version 3.0.20, 2008-06-02

- NEW: New parameter "encoding" to explicitly set an encoding for the source data
- UPD: Added a programming example to documentation
- FIX: If a Unicode string is passed it will automatically be converted to UTF8
- FIX: Fixes for Google AppEngine support
- FIX: If possible cStringIO will be used instead of StringIO
- FIX: An exception in psaDocument was not handled the right way because a context object was expected

Version 3.0.19, 2008-05-31

- NEW: Support for Google AppEngine
- NEW: Support for page break before and after [not yet tested] (Luka Frelih)
- UPD: Reworked parts of the documentation but not yet completed
- UPD: Optimized the command line tool "pisa"
- FIX: TOC bugs regarding entities and additional tags inside the TOC entry definitions (Luka Frelih)
- FIX: Default logging didn't work with Python<2.5 (Anders J. Munch)
- FIX: StringIO is used instead of cStringIO to avoid encoding problems like the ones we had with GoogleAppEngine

Version 3.0.18, 2008-04-19

- WIN: Updated the windows command line version
- NEW: WSGI support and demo
- NEW: Added simple ASPN Cookbook example
- UPD: Unified setup.py and setup_egg.py (Andreas Gabriel)
- UPD: Better handling of XML and HTML parsing
- UPD: Cleanup of Django sample
- UPD: Cleanup of command line tool options
- UPD: Command line tool doesn't stop batch if error occurred any more
- FIX: 'style' attribute was not evaluated!
- FIX: If a string was passed to pisaDocument it had been converted to StringIO, which was not necessary
- FIX: c.addPara(force=True) works again e.g. for forcing empty pages
- FIX: Better handling of CDATA and Comments
- FIX: Better handling of &nbsp;
- FIX: Removed rsplit() for backward compatibility with Python 2.3
- FIX: Handling of inconsistent HTML anchors
- FIX: TurboGears Demo

Version 3.0.17, 2008-03-23

- NEW: Added CSS support for TOC and updated documentation (Jean Baltus)
- UPD: Added "render_to_pdf" to Django demo (Diego Firmenich)
- UPD: Did some refactoring to make CSS parsing more flexible
- UPD: Removed log.exception for warnings
- FIX: Empty entries in TOC (Jean Baltus)
- FIX: Use correct font for <li> now (reported by Gabor Farkas)

Version 3.0.16, 2008-03-16

- Did some researches about support for languages like Farsi, Arabic and Asian
  languages. The dir='rtl' feature seems to be quite time intensive to be
  implemented, maybe I will do it in a later version or on request
- Switched back to HTML parsing by default, but use of XHTML is recommended. Use
  the option "xhtml" in pisaDocument or "-x" in the command line tool
- Added a decorator for use in Turbogears and CherryPy
- Completely switched to Python logging system
- Created a separate download for the fonts in the "test" directory to
  reduce the size of the package
- Just use multiBuild if needed e.g. using pdf:toc
- Bugfix: @font-face threw always a warning about font-weight
- Bugfix: List points have to be always in "Helvetica" (Gabor Farkas)
- Bugfix: Obligatory attributes for tag had not been handle the right way
- Bugfix: Marked some old tag based functionalities like pdf:font, pdf:frame and pdf:template as deprecated

Version 3.0.15, 2008-03-13

- Added new package and namespace "ho". With pisa 3.1. we will move away form "sx"
- Added version testing (2.1) for Reportlab Toolkit (Diego Firmenich)
- Added new command <pdf:toc> for support of table of contents, stiling per CSS has not been implemented yet (Jean Baltus)
- Added simple barcode support via command <pdf:barcode> (Diego Firmenich)
- Added Python logging. Name of logger "ho.pisa" and "ho.css". Set debugging level in command line tool by using "-d" for debugging and "-w" for warnings
- Added complete support for CSS "font"
- Modified the version handling and setup system for pisa distributions (had to do with the import errors that where not thrown, reported by Schmitte)
- Updated documentation and added a CSS for HTML version
- Bugfix: CSS "background" URL handling was broken (Luis Bruno)
- Bugfix: CSS "border" now works more standard conform
- Bugfix for compatibility problems with Python 2.3 because of reversed() function
- Bugfix: No exception was thrown if a third party module was missing (Kai Schmitte)
- Bugfix: Changed HTML5 parser from HTMLParser to XHTMLParser so that the custom tags of the "pdf" namespace are handled like expected
- Bugfix: Switched from urllib to urllib2 because status errors (like 404) where not handled (Kees Hink)
- A lot of smaller bugfixes and testings

Version 3.0.14, 2008-02-13

- Added a sample for Unicode support in exotic languages like "farsi" using DejaSans font (Adam Hyde)
- Command line tool generation integrated into setup.py (Andreas Gabriel)
- Bugfix if no path had been set to pisaDocument()
- Bugfix for calculating @frame dimensions
- Bugfix: CSS comments like "//" where allowed (Andreas Gabriel)

Version 3.0.13, 2008-01-22

- Added a demo using cherrypy web server and kid
- Added a demo using django framework
- Modified test-background.html to work with CSS
- Added support for bold and italic TTF fonts to the @font-face CSS section (Robert Klep)
- Added support for bold and italic Postscript fonts to the @font-face CSS section
- The @-rules are not need a trailing space after ident any more (Robert Klep)
- Fixed the Windows standalone version to work
- Made the 'sx' folder more sharable by modifying __init__.py
- Changed font-weight so that only values starting with '400'are considered 'bold' (Robert Klep)
- Added "text-indent" style (Robert Klep)
- Added "-pdf-keep-with-next" style to avoid page break between certain elements (Robert Klep)
- Added "-pdf-outline", "-pdf-outline-level" and "-pdf-outline-open" styles to create PDF bookmarks. Per default this is defined for the tags H1 to H6 (Robert Klep)
- New option to overwrite the default CSS definitions of pisa
- New command line options --css
- New command line options --css-dump to get the default CSS definitions. A dump of the recent CSS default may also be found in test/default.css
- Fixed setup.py
- Added EGG installation file support

Version 3.0.12, 2008-01-09

- Moved SVN repository to Holtwick
- Modified copyright notes and links to ``http://www.htmltopdf.org``
- Added new table attributes "border", "bordercolor", "cellpadding"
- Added support for &nbsp;

Version 3.0.11, 2007-11-13

- New example for loading a page form the web via Python
- New example "test-invoice.html"
- Added support for "align" attribute to <td> and <th>
- Fixed that more than one static frame can use the same named element
- Added -pdf-next-page to specify next page template
- Added -pdf-frame-break: after, before
- Fixed bug for @page without declarations
- Added option for output of errors as PDF (e.g. useful in web applications)
- Set "producer" to "pisa"
- Set author, subject and keywords with <meta>

Version 3.0.10, 2007-11-02

- Fixed some problems with wrong @page and @frame definitions
- New property -pdf-frame-box
- Implemented a pre parser for CSS that cleans up the code with some regular expression, like stripping illegal url ``http://...``
- Improved online demo
- First release of binary Windows command line version or pisa
- Fixed some issues with named anchors
- Empty documents are now delivered correctly
- Fixed error on list types
- Fixed problem with debugging infos

Version 3.0.9, 2007-10-31

- Modified setup.py for Chesse Shop
- Added bdist_wininst to setup
- Moved w3c into sx package and added license text
- Modified simple.py demo script
- Clean up for first public release

Version 3.0.8, 2007-10-31

- Added <a name> and a bugfix for ReportLab anchors
- Added <a href>
- More documentation about fonts and new font aliases
- Fixed some bugs in tables
- <hr> now uses ReportLabs implementation
- Margin collapse by using spaceBefore and spaceAfter
- Renamed -pdf-page-size to size (CSS3)

Version 3.0.7, 2007-10-30

- Static frames in @frame
- Wrote layout section in documentation
- Updated the documentation CSS
- Renamed @box to @frame
- Added -pdf-page-size and -pdf-page-orientation
- Added @page and @box
- Fixed some problems with font definitions and Unicode
- Font "Times" does not exist, changed default to "Times-Roman"
- Margins, paddings and borders are only applied in display:block elements

Version 3.0.6, 2007-10-29

- Implemented @font-face
- "font-family" can now handle comma separated font names
- Implemented <pdf:font> for embedding TTF and PS fonts
- <link> looks for rel="stylesheet"
- Style "white-space" and support for PRE
- Nested lists and ordered lists, Style "list-style-type"
- Prepared parser for @page and @box

Version 3.0.5, 2007-10-25

- Initial implementation of @font-face
- Warnings are only shown if flag -w is set
- Relative @import implementations
- Workaround for styles beginning with asterics like "* font: small"
- Support for color=transparent (threw Exceptions before)
- For @import with now media, is now set media=all
- Fixed the .1 CSS parser problem
- Removed cssutils again because of problems with @import
- Ignore CDATA in style definitions
- New method c.debug and command line option --debug
- Better URL support
- CSS attributes may now start with hyphen for vendor specific styles e.g. "-pdf-page-break"
- Implemented @import
- Implemented @media
- Images are now recalculated to 96DPI too
- 1px = 1/96inch (96dpi) instead of 1px = 1pt = 1/72inch
- Added some new tests like test-css-media.html

Version 3.0.0

- Initial versions of pisa rewrite
