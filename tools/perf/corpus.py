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
