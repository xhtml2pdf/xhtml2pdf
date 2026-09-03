"""
The CSS properties xhtml2pdf reads, and how.

This is the whitelist CSSCollect walks. A property that is not here is parsed
by the CSS engine, resolved through the cascade, stored in the ruleset -- and
then never looked at, because nothing ever asks the cascade for it. That is a
silent failure in both directions, and it has cost this library real bugs:
-pdf-keep-in-frame-max-width was read in pisaLoop but never listed here, so its
branch was unreachable; -pdf-outline-open was listed but its mapping was
commented out; and the reference documentation drifted far enough to list
"colordisplay", two properties run together, for years.

The list used to be a whitespace-separated string. Making each property a row
with its group, its consumer and -- where the mapping is uniform -- the frag
attribute and converter that apply it means the whitelist and the code that
acts on it cannot drift apart: the uniform mappings are generated from here
rather than repeated as literal tuples.

`frag` set means "the registry applies this one", through transform_attrs.
`frag` unset means the property has a hand-written branch, because its
consumption is not a plain mapping: font-weight is a binary flag,
text-decoration lights two flags from a list, margin-left accumulates into the
running indent as well as writing to the frag, display decides isBlock, and the
page-break properties emit flowables rather than touching the frag at all.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple

from xhtml2pdf.util import getBool, getColor, getSize, transform_attrs

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ The registry
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#: Where a property is read. The two differ in more than tidiness: pisaContext
#: .addTOC calls CSS2Frag directly for the .pdftoclevelN styles without going
#: through pisaLoop, so a property moved between them changes what a table of
#: contents picks up.
FRAG = "frag"  # xhtml2pdf.parser.CSS2Frag
LOOP = "loop"  # xhtml2pdf.parser.pisaLoop


def as_declared(value):
    """Converter for a property stored exactly as the stylesheet wrote it."""
    return value


class CSSProperty(NamedTuple):
    name: str
    group: str
    consumer: str = FRAG
    #: Frag attribute this writes to, when the registry applies it.
    frag: str | None = None
    #: Converter called as convert(value) or convert(value, font_size).
    convert: Callable | None = None
    #: Pass the current font size to the converter, for em and % lengths.
    relative_to_font_size: bool = False
    #: Only read inside CSS2Frag's `if isBlock:` sections.
    block_only: bool = False
    note: str = ""


CSS_PROPERTIES: tuple[CSSProperty, ...] = (
    # ~ text ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CSSProperty("color", "text", note="textColor, via getColor with a default"),
    CSSProperty("font-family", "text", note="resolved through pisaContext.getFontName"),
    CSSProperty(
        "font-size", "text", note="relative to the parent size, floored at 1pt"
    ),
    CSSProperty("font-weight", "text", note="binary: bold from bold/bolder/500-900"),
    CSSProperty("font-style", "text", note="binary: italic from italic/oblique"),
    CSSProperty("text-decoration", "text", note="lights underline and strike"),
    CSSProperty("line-height", "text", note="also recomputed when absent"),
    CSSProperty("letter-spacing", "text", note="kept raw, resolved at draw time"),
    CSSProperty("word-spacing", "text", note="kept raw, resolved at draw time"),
    CSSProperty("text-transform", "text", note="uppercase/lowercase/capitalize"),
    CSSProperty("text-align", "text", note="alignment, via getAlign"),
    CSSProperty("vertical-align", "text", note="table cells and inline images"),
    CSSProperty("white-space", "text", note="pre, pre-wrap, pre-line, nowrap"),
    CSSProperty(
        "text-indent",
        "text",
        frag="firstLineIndent",
        convert=getSize,
        relative_to_font_size=True,
        block_only=True,
    ),
    # ~ background ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CSSProperty("background-color", "background", note="backColor"),
    CSSProperty("background-image", "background", note="resolved to a file object"),
    CSSProperty("background-repeat", "background"),
    CSSProperty("background-position", "background"),
    # ~ box ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CSSProperty("display", "box", consumer=LOOP, note="block or none; decides isBlock"),
    CSSProperty("margin-left", "box", note="accumulates into the running indent"),
    CSSProperty("margin-right", "box", note="accumulates into the running indent"),
    CSSProperty(
        "margin-top",
        "box",
        frag="spaceBefore",
        convert=getSize,
        relative_to_font_size=True,
        block_only=True,
    ),
    CSSProperty(
        "margin-bottom",
        "box",
        frag="spaceAfter",
        convert=getSize,
        relative_to_font_size=True,
        block_only=True,
    ),
    CSSProperty("width", "box", note="images, table cells and barcodes only"),
    CSSProperty("height", "box", note="images, table cells and barcodes only"),
    CSSProperty("zoom", "box", note="not CSS; scales images"),
)

#: padding-* and the twelve border-* properties, which differ only by side.
CSS_PROPERTIES += tuple(
    CSSProperty(
        f"padding-{side.lower()}",
        "box",
        frag=f"padding{side}",
        convert=getSize,
        relative_to_font_size=True,
        block_only=True,
    )
    for side in ("Left", "Right", "Top", "Bottom")
)

CSS_PROPERTIES += tuple(
    prop
    for side in ("Top", "Bottom", "Left", "Right")
    for prop in (
        CSSProperty(
            f"border-{side.lower()}-color",
            "box",
            frag=f"border{side}Color",
            convert=getColor,
            block_only=True,
        ),
        CSSProperty(
            f"border-{side.lower()}-style",
            "box",
            frag=f"border{side}Style",
            convert=as_declared,
            block_only=True,
        ),
        CSSProperty(
            f"border-{side.lower()}-width",
            "box",
            frag=f"border{side}Width",
            convert=getSize,
            relative_to_font_size=True,
            block_only=True,
        ),
    )
)

CSS_PROPERTIES += (
    # ~ lists ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CSSProperty("list-style-type", "list", note="marker glyph or counter style"),
    CSSProperty("list-style-image", "list", note="resolved to a file object"),
    # ~ pagination ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CSSProperty("page-break-before", "page", consumer=LOOP, note="emits a flowable"),
    CSSProperty("page-break-after", "page", consumer=LOOP, note="emits a flowable"),
    # ~ proprietary ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CSSProperty("-pdf-page-break", "pdf", consumer=LOOP, note="before only"),
    CSSProperty("-pdf-frame-break", "pdf", consumer=LOOP),
    CSSProperty("-pdf-next-page", "pdf", consumer=LOOP, note="names a page template"),
    CSSProperty(
        "-pdf-keep-with-next",
        "pdf",
        consumer=LOOP,
        frag="keepWithNext",
        convert=getBool,
    ),
    CSSProperty("-pdf-outline", "pdf", consumer=LOOP, frag="outline", convert=getBool),
    CSSProperty(
        "-pdf-outline-open", "pdf", consumer=LOOP, frag="outlineOpen", convert=getBool
    ),
    CSSProperty("-pdf-outline-level", "pdf", consumer=LOOP, note="an int, unguarded"),
    CSSProperty("-pdf-line-spacing", "pdf", note="leadingSpace, added to the leading"),
    CSSProperty(
        "-pdf-keep-in-frame-mode",
        "pdf",
        consumer=LOOP,
        note="also read in tables.py, and from an @frame rule in context.py",
    ),
    CSSProperty("-pdf-keep-in-frame-max-width", "pdf", consumer=LOOP),
    CSSProperty("-pdf-keep-in-frame-max-height", "pdf", consumer=LOOP),
    CSSProperty("-pdf-word-wrap", "pdf", consumer=LOOP, note="CJK"),
)


#: What CSSCollect asks the cascade for, in registry order.
PROPERTY_NAMES: tuple[str, ...] = tuple(prop.name for prop in CSS_PROPERTIES)

#: Membership test for the same. A shorthand is expanded before it gets this
#: far, so only the names it expands into appear.
SUPPORTED_PROPERTIES: frozenset[str] = frozenset(PROPERTY_NAMES)

PROPERTIES_BY_NAME: dict[str, CSSProperty] = {
    prop.name: prop for prop in CSS_PROPERTIES
}


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ The uniform mappings, grouped for transform_attrs
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class UniformGroup(NamedTuple):
    """One transform_attrs call: a converter and the pairs it applies."""

    convert: Callable
    relative_to_font_size: bool
    pairs: tuple[tuple[str, str], ...]


def _build_groups(consumer: str, *, block_only: bool) -> tuple[UniformGroup, ...]:
    """
    Collect the registry-driven properties into one group per converter.

    transform_attrs applies each pair independently, so properties that share a
    converter can share a call whatever order they are in. That folds what used
    to be three separate calls for margins, paddings and border widths -- all
    getSize against the font size -- into one.
    """
    grouped: dict[tuple[Callable, bool], list[tuple[str, str]]] = {}
    for prop in CSS_PROPERTIES:
        if prop.frag is None or prop.convert is None or prop.consumer != consumer:
            continue
        if prop.block_only != block_only:
            continue
        key = (prop.convert, prop.relative_to_font_size)
        grouped.setdefault(key, []).append((prop.frag, prop.name))

    return tuple(
        UniformGroup(convert, relative, tuple(pairs))
        for (convert, relative), pairs in grouped.items()
    )


#: Applied by CSS2Frag inside its `if isBlock:` section.
FRAG_BLOCK_GROUPS: tuple[UniformGroup, ...] = _build_groups(FRAG, block_only=True)

#: Applied by pisaLoop, for every element rather than blocks alone.
LOOP_GROUPS: tuple[UniformGroup, ...] = _build_groups(LOOP, block_only=False)


def apply_uniform_groups(frag, css_attrs, groups: tuple[UniformGroup, ...]) -> None:
    """Apply every registry-driven mapping in `groups` to `frag`."""
    for group in groups:
        transform_attrs(
            frag,
            group.pairs,
            css_attrs,
            group.convert,
            extras=frag.fontSize if group.relative_to_font_size else None,
        )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ The properties collected for one element
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#: Names already reported, so one unregistered property does not fill the log
#: with a line per element.
_unregistered_seen: set[str] = set()


class CSSAttrs(dict):
    # A dict subclass rather than UserDict on purpose: getCSSAttr writes into
    # this mapping once per property per element, and UserDict would put a
    # Python-level __setitem__ in front of every one of those.
    """
    The CSS properties collected for one element, by CSSCollect.

    Asking about a name that is not in the registry is a bug in the caller
    rather than a missing declaration: CSSCollect only ever fills in
    registered names, so the answer is always "absent" and the code that asked
    quietly does nothing. That is precisely how -pdf-keep-in-frame-max-width
    stayed unreachable -- the branch was written, the `in` test said False, and
    nothing anywhere said why. Every lookup is checked so that the next one
    says so out loud.
    """

    @staticmethod
    def _check(key) -> None:
        if key in SUPPORTED_PROPERTIES or key in _unregistered_seen:
            return
        _unregistered_seen.add(key)
        log.warning(
            "CSS property %r is read but not registered in xhtml2pdf.properties, "
            "so CSSCollect never collects it and the code reading it can never "
            "fire",
            key,
        )

    def __contains__(self, key) -> bool:
        self._check(key)
        return super().__contains__(key)

    def __getitem__(self, key):
        self._check(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._check(key)
        return super().get(key, default)
