"""
What the performance tools render.

The fixtures under testrender/data/source are documents the project already
renders in its own comparison suite, so a number measured against them refers
to markup someone cared about. The synthetic documents hold everything
constant except one dimension -- nodes, rules, distinct style keys -- which is
what makes a growth curve readable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from xhtml2pdf.config.resources import ResourceAccessPolicy

ROOT = Path(__file__).resolve().parent.parent.parent

#: Some fixtures load fonts from manual_test/font on purpose, which is outside
#: their own directory and so outside what the default resource policy lets a
#: document read. testrender/testrender.py names the same directory for the
#: same reason; naming it here keeps the rest of the policy in force.
FONT_ROOT = ROOT / "manual_test" / "font"

_SOURCE = ROOT / "testrender" / "data" / "source"
_SAMPLES = ROOT / "tests" / "samples"

#: Chosen to spread across what dominates the profile: text volume, tables,
#: lists and their positional selectors, selector matching, and a document
#: whose cost is almost entirely font work inside reportlab.
FIXTURES: tuple[Path, ...] = (
    _SOURCE / "css-selectors.html",
    _SOURCE / "test-list.html",
    _SOURCE / "list-blocks.html",
    _SOURCE / "test-tables.html",
    _SOURCE / "test-table-css.html",
    _SOURCE / "test-letter.html",
    _SOURCE / "test-keep-in-frame.html",
    _SOURCE / "test-keep-with-next.html",
    _SOURCE / "test-loremipsum.html",
    _SOURCE / "flex-cards.html",
    _SOURCE / "inline-block-badges.html",
    _SAMPLES / "utf8.html",
)


@dataclass(frozen=True)
class Document:
    """One thing to render, and what it needs to render it."""

    name: str
    source: bytes
    #: What relative URLs in the document resolve against. Empty for synthetic
    #: documents, which reference nothing outside themselves.
    path: str
    base_dir: Path | None

    def policy(self) -> ResourceAccessPolicy | None:
        if self.base_dir is None:
            return None
        return ResourceAccessPolicy(base_dir=self.base_dir, extra_roots=(FONT_ROOT,))


def fixture(path: Path) -> Document:
    return Document(
        name=path.name,
        source=path.read_bytes(),
        path=str(path),
        base_dir=path.resolve().parent,
    )


def fixtures(names: list[str] | None = None) -> list[Document]:
    """The real documents, or the subset whose file name contains one of names."""
    chosen = FIXTURES
    if names:
        chosen = tuple(p for p in chosen if any(n in p.name for n in names))
    return [fixture(p) for p in chosen if p.exists()]


def synthetic(nodes: int, rules: int, *, distinct: bool) -> Document:
    """
    A document of `nodes` paragraphs against a stylesheet of `rules` classes.

    With distinct=False every class repeats, so CSSCollect's cssAttrCache
    answers most nodes and what is measured is the cached path. With
    distinct=True each node carries a class of its own and every node pays the
    full cascade -- the case that shows how the cost grows with the size of
    the stylesheet.
    """
    css = "\n".join(
        f".c{i} {{ color: #0{i % 10}0{i % 10}00; margin-left: {i % 5}px; }}"
        for i in range(rules)
    )
    span = max(rules, 1)
    body = "\n".join(
        f'<p class="c{i if distinct else i % span}">Lorem ipsum dolor sit amet {i}</p>'
        for i in range(nodes)
    )
    html = f"<html><head><style>{css}</style></head><body>{body}</body></html>"
    kind = "distinct" if distinct else "shared"
    return Document(
        name=f"synth-{nodes}n-{rules}r-{kind}",
        source=html.encode(),
        path="",
        base_dir=None,
    )


#: The scaling ladder. Nodes and rules grow together, each node with a class of
#: its own, so a linear scan of the stylesheet shows up as a quadratic curve.
SCALING: tuple[tuple[int, int], ...] = ((100, 100), (200, 200), (400, 400), (800, 800))


def scaling() -> list[Document]:
    return [synthetic(n, r, distinct=True) for n, r in SCALING]


def devnull():
    return open(os.devnull, "wb")


_IMAGES = _SOURCE / "img"

_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip."
)


def _document(name: str, html: str, base_dir: Path | None = None) -> Document:
    return Document(
        name=name,
        source=html.encode(),
        path=str(base_dir / "synthetic.html") if base_dir else "",
        base_dir=base_dir,
    )


def large_text(paragraphs: int) -> Document:
    """Plain paragraphs, a few inline runs each: what memory costs per node."""
    body = "\n".join(
        f"<p>{i}. {_LOREM} <b>bold</b> and <i>italic</i> text.</p>"
        for i in range(paragraphs)
    )
    return _document(f"large-text-{paragraphs}", f"<html><body>{body}</body></html>")


def large_table(rows: int) -> Document:
    """One table of `rows` rows and five columns, repeating its header (#208)."""
    head = "<tr>" + "".join(f"<th>Column {c}</th>" for c in range(5)) + "</tr>"
    body = "\n".join(
        "<tr>" + "".join(f"<td>r{r} c{c} value</td>" for c in range(5)) + "</tr>"
        for r in range(rows)
    )
    css = "table { -pdf-keep-in-frame-mode: shrink } td, th { border: 1px solid #999; padding: 2px }"
    html = (
        f"<html><head><style>{css}</style></head><body>"
        f'<table repeat="1"><thead>{head}</thead><tbody>{body}</tbody></table>'
        "</body></html>"
    )
    return _document(f"large-table-{rows}", html)


def large_pages(pages: int) -> Document:
    """`pages` pages of text under a static header and footer (C2)."""
    css = """
    @page { size: a4; margin: 3cm 2cm;
      @frame header { -pdf-frame-content: hdr; top: 1cm; height: 1.5cm; left: 2cm; right: 2cm }
      @frame footer { -pdf-frame-content: ftr; bottom: 1cm; height: 1cm; left: 2cm; right: 2cm }
    }
    """
    header = '<div id="hdr"><b>Company name</b> - quarterly report</div>'
    footer = '<div id="ftr">Page <pdf:pagenumber> of <pdf:pagecount></div>'
    body = "\n".join(
        f"<h2>Section {i}</h2>" + f"<p>{_LOREM}</p>" * 6 + "<pdf:nextpage />"
        for i in range(pages)
    )
    html = f"<html><head><style>{css}</style></head><body>{header}{footer}{body}</body></html>"
    return _document(f"large-pages-{pages}", html)


def large_images(count: int) -> Document:
    """The same two images referenced `count` times each (C3, C4)."""
    body = "\n".join(
        f'<p>Item {i} <img src="denker.png" width="40"> <img src="test_logo.jpg" width="60"></p>'
        for i in range(count)
    )
    return _document(
        f"large-images-{count}", f"<html><body>{body}</body></html>", _IMAGES
    )


def large(names: list[str] | None = None) -> list[Document]:
    """The documents that grow until they hurt: memory and the long tail."""
    docs = [
        *(large_text(n) for n in (1000, 3000, 10000)),
        *(large_table(n) for n in (256, 1024, 4096)),
        large_pages(200),
        large_images(200),
    ]
    if names:
        docs = [d for d in docs if any(n in d.name for n in names)]
    return docs
