"""
CSS custom properties and var() (CSS Custom Properties for Cascading
Variables 1).

A declaration whose value holds var() cannot be parsed into terms when the
stylesheet is read: what it means depends on the element it applies to, whose
custom properties are only known once the cascade has reached it. The parser
keeps such a value as its source text, a CSSPendingValue, and a custom property
as a CSSCustomValue. parser.CSSCollect substitutes the element's custom
properties into the text and parses what comes out as if it had been written
that way.

A shorthand holding var() cannot be split into its longhands either, as the
split depends on the values. Each longhand it would set is declared with the
whole pending shorthand instead, so that the cascade still sees one
declaration per longhand in the order they were written; substitution parses
the shorthand and keeps the longhand it is for.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class CSSCustomValue(str):
    """The value of a custom property, `--name: value`, as written."""

    __slots__ = ()


class CSSPendingValue(str):
    """
    A value that holds var(), as written, waiting for an element.

    `shorthand` is the shorthand it was written as, when it stands for one of
    that shorthand's longhands.
    """

    __slots__ = ("shorthand", "source")
    shorthand: str | None
    source: str | None

    def __new__(  # noqa: PYI034
        cls, text: str, shorthand: str | None = None, source: str | None = None
    ) -> CSSPendingValue:
        value = super().__new__(cls, text)
        value.shorthand = shorthand
        #: The stylesheet it was written in, for a warning about it later.
        value.source = source
        return value

    def __repr__(self) -> str:
        return f"<CSS pending var(): {str(self)!r}>"


#: The longhands each shorthand that parseSpecialRules expands can set.
SHORTHAND_LONGHANDS: dict[str, tuple[str, ...]] = {
    "margin": tuple(f"margin-{side}" for side in ("top", "right", "bottom", "left")),
    "padding": tuple(f"padding-{side}" for side in ("top", "right", "bottom", "left")),
    **{
        f"border-{part}": tuple(
            f"border-{side}-{part}" for side in ("top", "right", "bottom", "left")
        )
        for part in ("width", "style", "color")
    },
    "border": tuple(
        f"border-{side}-{part}"
        for side in ("top", "right", "bottom", "left")
        for part in ("width", "style", "color")
    ),
    **{
        f"border-{side}": tuple(
            f"border-{side}-{part}" for part in ("width", "style", "color")
        )
        for side in ("top", "right", "bottom", "left")
    },
    "border-radius": tuple(
        f"border-{corner}-radius"
        for corner in ("top-left", "top-right", "bottom-right", "bottom-left")
    ),
    "font": ("font-style", "font-weight", "font-size", "line-height", "font-family"),
    "background": (
        "background-color",
        "background-image",
        "background-repeat",
        "background-position",
    ),
    "list-style": ("list-style-type", "list-style-image", "list-style-position"),
    "flex": ("flex-grow", "flex-shrink", "flex-basis"),
    "flex-flow": ("flex-direction", "flex-wrap"),
    "gap": ("row-gap", "column-gap"),
}

_VAR = re.compile(r"\bvar\s*\(", re.IGNORECASE)


class InvalidVarError(ValueError):
    """A var() that names nothing and has no fallback, or a cycle."""


def _closingParen(text: str, start: int) -> int:
    """Index of the ")" that closes the "(" just before start, or -1."""
    depth = 1
    quote = None
    i = start
    while i < len(text):
        char = text[i]
        if quote:
            if char == "\\":
                i += 1
            elif char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if not depth:
                return i
        i += 1
    return -1


def hasVar(text: str) -> bool:
    return _VAR.search(text) is not None


def substitute(
    text: str, lookup: Callable[[str], str | None], _seen: frozenset[str] = frozenset()
) -> str:
    """
    Text with every var() replaced, recursively, by what lookup gives for the
    custom property it names, or by its fallback.

    Raises InvalidVarError for a var() that resolves to nothing, or that reaches a
    custom property already being substituted: a cycle makes every property
    in it invalid.
    """
    out: list[str] = []
    pos = 0
    for match in _VAR.finditer(text):
        if match.start() < pos:
            continue  # inside a var() already replaced
        end = _closingParen(text, match.end())
        if end < 0:
            msg = f"unclosed var() in {text!r}"
            raise InvalidVarError(msg)
        name, comma, fallback = text[match.end() : end].partition(",")
        name = name.strip()
        if not name.startswith("--"):
            msg = f"var() names {name!r}, not a custom property"
            raise InvalidVarError(msg)
        if name in _seen:
            msg = f"{name} depends on itself"
            raise InvalidVarError(msg)
        value = lookup(name)
        if value is not None:
            try:
                value = substitute(value, lookup, _seen | {name})
            except InvalidVarError:
                # A property that is itself invalid -- in a cycle, say --
                # falls back like one that is not there.
                if not comma:
                    raise
                value = None
        if value is None:
            if not comma:
                msg = f"{name} is not defined"
                raise InvalidVarError(msg)
            value = substitute(fallback.strip(), lookup, _seen)
        out.extend((text[pos : match.start()], value))
        pos = end + 1
    out.append(text[pos:])
    return "".join(out)


def substituteFrom(text: str, properties: Mapping[str, str]) -> str:
    """substitute() against a plain mapping of custom properties."""
    return substitute(text, properties.get)
