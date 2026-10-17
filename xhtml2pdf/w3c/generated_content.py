"""
CSS generated content: what ::before and ::after say, and the counters in it.

CSS 2.1 12.2 to 12.4 and CSS Lists 3. The ``content`` of a pseudo-element is
read into a list of items (strings, ``counter()``, ``counters()``,
``attr()``), and the text of that list is worked out when the element is
reached in the walk of the document, against the counters as they stand
there.
"""

from __future__ import annotations

import logging
import re
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING

from xhtml2pdf.w3c.css import CSSString, CSSTerminalFunction

if TYPE_CHECKING:
    from xml.dom.minidom import Element, Node

log = logging.getLogger(__name__)

roman_numeral_map: tuple[tuple[int, str], ...] = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


def int_to_roman(i: int) -> str:
    result: list[str] = []
    for integer, numeral in roman_numeral_map:
        count: int = int(i / integer)
        result.append(numeral * count)
        i -= integer * count
    return "".join(result)


#: CSS 2.1 lower-greek: the 24 letters of the alphabet, with no final sigma.
greek_alphabet: str = "αβγδεζηθικλμνξοπρστυφχψω"

_LATIN = string.ascii_lowercase


def _alphabetic(n: int, letters: str) -> str:
    """CSS Counter Styles' alphabetic system: a, b, ..., z, aa, ab, ..."""
    text = ""
    while n > 0:
        n -= 1
        text = letters[n % len(letters)] + text
        n //= len(letters)
    return text


#: The counter styles with a glyph rather than a number.
_SYMBOLS = {"disc": "•", "circle": "◦", "square": "▪", "none": ""}


def format_counter(n: int, style: str = "decimal") -> str:
    """
    `n` written in the counter style `style`.

    A value outside a style's range -- below 1 for the letters, outside 1 to
    3999 for roman numerals -- is written in decimal, as CSS Counter Styles
    says. A style this does not know is decimal too.
    """
    style = style.lower()
    if style in _SYMBOLS:
        return _SYMBOLS[style]
    if style == "decimal-leading-zero":
        return f"{n:02d}" if n >= 0 else f"-{-n:02d}"
    if style in {"lower-roman", "upper-roman"} and 0 < n < 4000:
        roman = int_to_roman(n)
        return roman.lower() if style == "lower-roman" else roman
    if n > 0:
        if style in {"lower-alpha", "lower-latin"}:
            return _alphabetic(n, _LATIN)
        if style in {"upper-alpha", "upper-latin"}:
            return _alphabetic(n, _LATIN).upper()
        if style == "lower-greek":
            return _alphabetic(n, greek_alphabet)
    return str(n)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ content
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dataclass(frozen=True)
class CounterItem:
    """counter(name, style), or counters(name, separator, style)."""

    name: str
    style: str = "decimal"
    #: None for counter(): only the innermost value.
    separator: str | None = None


@dataclass(frozen=True)
class AttrItem:
    """attr(name): the value of that attribute of the element, or nothing."""

    name: str


ContentItem = str | CounterItem | AttrItem

#: A CSS escape in a string: a backslash and up to six hex digits, with the
#: one white space that may end them, or a backslash and any other character.
_ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6})[ \t\n]?|\\(.)", re.DOTALL)


def _unescape(text: str) -> str:
    r"""The text of a CSS string, "\2014" and "\A" read as the characters."""

    def char(match: re.Match) -> str:
        if match.group(1) is not None:
            code = int(match.group(1), 16)
            return chr(code) if 0 < code <= 0x10FFFF else "�"
        return match.group(2)

    return _ESCAPE.sub(char, text)


def _function_item(function: CSSTerminalFunction) -> ContentItem | None:
    name = function.name.lower()
    params = [str(param).strip() for param in function.params if str(param).strip()]
    if name == "counter" and 1 <= len(params) <= 2:
        return CounterItem(params[0], *params[1:])
    if name == "counters" and 2 <= len(params) <= 3:
        return CounterItem(
            params[0],
            params[2] if len(params) == 3 else "decimal",
            _unescape(params[1]),
        )
    if name == "attr" and len(params) == 1:
        return AttrItem(params[0])
    return None


def parse_content(value) -> list[ContentItem] | None:
    """
    The items of a ``content`` value, or None when it generates nothing.

    ``none`` and ``normal`` generate nothing, and neither does a value with
    nothing in it this can draw. A part this cannot draw -- ``open-quote``,
    an image -- is left out with a warning, and the rest still drawn.
    """
    parts = value if isinstance(value, list | tuple) else [value]
    items: list[ContentItem] = []
    for part in parts:
        if isinstance(part, CSSString):
            items.append(_unescape(str(part)))
        elif isinstance(part, CSSTerminalFunction):
            item = _function_item(part)
            if item is None:
                log.warning("Ignoring %r in content: it is not drawn", part)
            else:
                items.append(item)
        elif str(part).strip().lower() in {"none", "normal", ""}:
            if len(parts) == 1:
                return None
        else:
            log.warning("Ignoring %r in content: it is not drawn", str(part))
    return items or None


def parse_counter_list(value, default: int) -> list[tuple[str, int]]:
    """
    The (name, value) pairs of counter-reset or counter-increment.

    ``h2``, ``h2 0 h3``, ``none``. A name with no number after it takes
    `default`: 0 for a reset, 1 for an increment.
    """
    parts = value if isinstance(value, list | tuple) else [value]
    words = [str(part).strip() for part in parts if str(part).strip()]
    pairs: list[tuple[str, int]] = []
    for word in words:
        try:
            number = int(float(word))
        except ValueError:
            if word.lower() != "none":
                pairs.append((word, default))
            continue
        if pairs:
            pairs[-1] = (pairs[-1][0], number)
    return pairs


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ counters
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class Counters:
    """
    The counters in scope at the point of the walk of the document.

    CSS 2.1 12.4.1: a counter-reset on an element starts a new instance of
    the counter, in scope for that element, its following siblings and all
    their descendants. One of the same name reset by a following sibling
    takes over the instance rather than nesting another one inside it. So
    each name has a stack of instances, each one tied to its scope -- the
    parent of the element that reset it, or the element itself for its
    ::before and ::after -- and leaving that node ends them.
    """

    def __init__(self) -> None:
        #: name -> [[value, the node whose children it covers], ...]
        self._instances: dict[str, list[list]] = {}

    def reset(self, scope: Node, name: str, value: int) -> None:
        stack = self._instances.setdefault(name, [])
        if stack and stack[-1][1] is scope:
            stack[-1][0] = value
        else:
            stack.append([value, scope])

    def increment(self, scope: Node, name: str, by: int) -> None:
        stack = self._instances.get(name)
        if not stack:
            # Incrementing a counter no one reset resets it on the spot.
            self.reset(scope, name, 0)
            stack = self._instances[name]
        stack[-1][0] += by

    def apply(self, scope: Node, attrs) -> None:
        """An element's counter-reset, then its counter-increment."""
        if "counter-reset" in attrs:
            for name, value in parse_counter_list(attrs["counter-reset"], 0):
                self.reset(scope, name, value)
        if "counter-increment" in attrs:
            for name, value in parse_counter_list(attrs["counter-increment"], 1):
                self.increment(scope, name, value)

    def leave(self, node: Node) -> None:
        """End the instances `node` held in scope: its children's."""
        for stack in self._instances.values():
            while stack and stack[-1][1] is node:
                stack.pop()

    def values(self, name: str) -> list[int]:
        """Every instance of `name` in scope, outermost first."""
        return [value for value, _scope in self._instances.get(name, [])]

    def text(self, items: list[ContentItem], element: Element) -> str:
        """The text `items` stand for in a pseudo-element of `element`."""
        out: list[str] = []
        for item in items:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, AttrItem):
                if element.hasAttribute(item.name):
                    out.append(element.getAttribute(item.name))
            else:
                values = self.values(item.name)
                if not values:
                    # A counter used where none is in scope is created there
                    # at 0 (CSS 2.1 12.4).
                    self.reset(element, item.name, 0)
                    values = [0]
                if item.separator is None:
                    out.append(format_counter(values[-1], item.style))
                else:
                    out.append(
                        item.separator.join(
                            format_counter(value, item.style) for value in values
                        )
                    )
        return "".join(out)
