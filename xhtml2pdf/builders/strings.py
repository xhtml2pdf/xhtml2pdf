"""
Named strings of CSS Generated Content for Paged Media: string-set and string().

``h1 { string-set: chapter content() }`` sets the string ``chapter`` to the
heading's text, and ``@top-center { content: string(chapter) }`` shows it in
the page margin: a running header. An element's strings are worked out when
it is read and handed to the next paragraph made, and recorded with the page
that paragraph lands on as it is drawn. The margin boxes are drawn after a
page's flow, so a page's own assignments are known when its boxes are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xhtml2pdf.w3c.css import CSSString, CSSTerminalFunction
from xhtml2pdf.w3c.generated_content import (
    AttrItem,
    CounterItem,
    _function_item,
    _unescape,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

#: What string() takes when it names no other: the first assignment on the
#: page, or the value the page started with.
POLICIES = frozenset({"first", "start", "last", "first-except"})


def _text_content(node) -> str:
    """The element's text, its white space collapsed as a line's would be."""
    parts: list[str] = []

    def walk(n) -> None:
        for child in n.childNodes:
            if child.nodeType == child.TEXT_NODE:
                parts.append(child.data)
            elif child.nodeType == child.ELEMENT_NODE:
                walk(child)

    walk(node)
    return " ".join("".join(parts).split())


def _content_text(function: CSSTerminalFunction, node) -> str:
    params = function.params if isinstance(function.params, list | tuple) else []
    which = next((str(p).strip().lower() for p in params if str(p).strip()), "text")
    text = _text_content(node)
    if which == "first-letter":
        return text[:1]
    if which in {"before", "after"}:
        # The text of ::before and ::after is not kept with the element.
        return ""
    return text


def string_set_values(value, node, counters) -> list[tuple[str, str]]:
    """
    (name, text) for each string a string-set value sets on `node`.

    The parser hands the value over without its commas; a bare identifier
    starts a new name, and the strings and functions after it are its value.
    """
    parts = value if isinstance(value, list | tuple) else [value]
    result: list[tuple[str, list[str]]] = []
    for part in parts:
        if isinstance(part, CSSString):
            if result:
                result[-1][1].append(_unescape(str(part)))
        elif isinstance(part, CSSTerminalFunction):
            if not result:
                continue
            if part.name.lower() == "content":
                result[-1][1].append(_content_text(part, node))
                continue
            item = _function_item(part)
            if isinstance(item, AttrItem):
                result[-1][1].append(node.getAttribute(item.name) or "")
            elif isinstance(item, CounterItem):
                result[-1][1].append(counters.text([item], node))
        else:
            name = str(part).strip()
            if name and name.lower() != "none":
                result.append((name, []))
    return [(name, "".join(texts)) for name, texts in result]


def string_on_page(doc, name: str, policy: str = "first") -> str:
    """
    The value of the named string on the page `doc` is drawing.

    first: the first assignment on the page, else the value the page began
    with; start: the value the page began with, else the first on it; last:
    the last on the page, else the one it began with; first-except: nothing
    on a page that assigns it, the value it began with on any other.
    """
    page = doc.page
    sets: Iterable[tuple[int, str, str]] = getattr(doc, "stringSets", ())
    before = [value for p, n, value in sets if n == name and p < page]
    here = [value for p, n, value in sets if n == name and p == page]
    entry = before[-1] if before else ""
    if policy == "last":
        return here[-1] if here else entry
    if policy == "start":
        return entry if before else (here[0] if here else "")
    if policy == "first-except":
        return "" if here else entry
    return here[0] if here else entry
