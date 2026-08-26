"""
Build the demonstration PDFs the documentation embeds.

Every page that describes output the library produces ends with a
demonstration: an HTML source under ``_static/html_samples``, converted to PDF
by xhtml2pdf itself while the documentation is being built, and embedded at the
foot of the page.

The point is that the demonstrations cannot drift from the library. They are
rendered by the very version being documented, so a feature that stops working
shows up as a broken demonstration rather than as prose that quietly stopped
being true. A conversion error fails the documentation build for the same
reason.

A demonstration belongs to a page by its filename: ``quickstart.html`` is the
demonstration for ``quickstart.rst`` and ``guide-fonts.html`` for
``guide/fonts.rst``. A page may have several, distinguished by a ``--`` suffix
-- ``graphics--pie.html``, ``graphics--doughnut.html`` -- shown in the order
their names sort.

Each page carries ``.. include:: /_generated/<slug>.rst`` at the end, under a
heading of its own. The generated fragment has no heading: heading levels in
reStructuredText are per-document, decided by the order the underline
characters first appear, so a heading here would land at a different depth in
each page that included it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from reportlab.lib.pdfencrypt import StandardEncryption

from xhtml2pdf import pisa


class Demo(NamedTuple):
    """How one page's demonstration is presented and produced."""

    caption: str
    #: Passed to CreatePDF. Only the encryption page needs one, because
    #: encryption is an argument to the converter rather than something the
    #: HTML can ask for.
    encrypt: Any = None


#: Documentation pages that end with a demonstration, in reading order, each
#: with the caption shown above its PDF. A page absent from here simply has no
#: demonstration; pages that describe how to contribute, or list what changed,
#: have no output to show.
DEMO_PAGES: dict[str, Demo] = {
    "quickstart": Demo("The smallest document that produces a PDF."),
    "format_html": Demo("Pages, frames and static content, over several pages."),
    "reference": Demo("The layout features this page describes, a page each."),
    "reference/html": Demo("The CSS properties and selectors this page lists."),
    "guide/fonts": Demo("The base-14 faces and their aliases, CJK, and RTL."),
    "graphics": Demo("Each chart type the canvas understands."),
    "watermarks": Demo("A background image and a background PDF."),
    "encryption_and_signatures": Demo(
        "Encrypted, with printing and modification withheld. The user password"
        " is empty, so it opens without one -- an owner password alone"
        " restricts what a reader may do.",
        # Restrict permissions rather than demand a password: a PDF that asks
        # for one cannot be read in the frame below.
        encrypt=StandardEncryption("", ownerPassword="owner", canPrint=0, canModify=0),
    ),
    "advanced-usage": Demo(
        "Relative references resolved through a link_callback, as this page"
        " describes -- these very pages build it with one."
    ),
}

SOURCE_DIR = Path("_static/html_samples")
PDF_DIR = Path("_static/pdf_samples")
GENERATED_DIR = Path("_generated")


class DemoError(RuntimeError):
    """A demonstration could not be converted."""


def slug_for(page: str) -> str:
    """``guide/fonts`` -> ``guide-fonts``, the demo's filename stem."""
    return page.replace("/", "-")


def static_prefix(page: str) -> str:
    """
    How to reach the source root from ``page``'s own output directory.

    pdfembed drops its ``src`` straight into an ``<iframe>``, so the path is
    resolved against the page rather than against the project, and a page one
    directory down needs to climb back out.
    """
    return "../" * page.count("/")


def link_callback(uri: str, _rel: str) -> str:
    """Resolve a demo's own relative asset references."""
    return str((SOURCE_DIR / uri).absolute().resolve())


def convert_to_pdf_file(
    inputfile, outputfile, link_callback=None, encrypt=None, signature=None
):
    with (
        open(outputfile, "wb") as arch,
        open(inputfile, encoding="utf-8", errors="ignore") as source,
    ):
        return pisa.CreatePDF(
            source,
            arch,
            encrypt=encrypt,
            link_callback=link_callback,
            signature=signature,
            show_error_as_pdf=True,
        )


def demos_for(page: str) -> list[Path]:
    """The demonstration sources belonging to ``page``, in display order."""
    stem = slug_for(page)
    return sorted(
        [*SOURCE_DIR.glob(f"{stem}.html"), *SOURCE_DIR.glob(f"{stem}--*.html")]
    )


def render_demo(source: Path, demo: Demo) -> Path:
    """Convert one demonstration, returning the PDF it wrote."""
    pdf = PDF_DIR / (source.stem + ".pdf")
    context = convert_to_pdf_file(
        source, pdf, link_callback=link_callback, encrypt=demo.encrypt
    )
    if context.err:
        msg = (
            f"{source} did not convert: {context.err} error(s). The "
            f"documentation describes a feature its own demonstration cannot "
            f"use."
        )
        raise DemoError(msg)
    return pdf


def fragment_for(page: str, caption: str, pdfs: list[tuple[Path, Path]]) -> str:
    """The reStructuredText embedded at the foot of ``page``."""
    prefix = static_prefix(page)
    parts = [caption, ""]
    for source, pdf in pdfs:
        parts += [
            f".. literalinclude:: /{SOURCE_DIR}/{source.name}",
            "   :language: html",
            f"   :caption: {source.name}",
            "",
            (
                f":pdfembed:`src:{prefix}{PDF_DIR}/{pdf.name}, "
                f"height:600, width:600, align:middle`"
            ),
            "",
        ]
    return "\n".join(parts)


def build_resources() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    index = [
        "Examples",
        "################",
        "",
        "Every demonstration in this documentation, gathered in one place. Each",
        "is rendered by xhtml2pdf while these pages are built, and each is",
        "explained by the page it links to.",
        "",
    ]

    for page, demo in DEMO_PAGES.items():
        sources = demos_for(page)
        if not sources:
            msg = (
                f"No demonstration source for {page!r}: expected "
                f"{SOURCE_DIR}/{slug_for(page)}.html"
            )
            raise DemoError(msg)

        rendered = [(source, render_demo(source, demo)) for source in sources]
        fragment = fragment_for(page, demo.caption, rendered)
        (GENERATED_DIR / f"{slug_for(page)}.rst").write_text(fragment, encoding="utf-8")

        index += [f":doc:`{page}`", "-" * (len(page) + 8), "", demo.caption, ""]
        for _source, pdf in rendered:
            index += [
                (
                    f":pdfembed:`src:{PDF_DIR}/{pdf.name}, "
                    f"height:400, width:600, align:middle`"
                ),
                "",
            ]

    Path("examples.rst").write_text("\n".join(index), encoding="utf-8")


if __name__ == "__main__":
    build_resources()
