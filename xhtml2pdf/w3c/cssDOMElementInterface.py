# Copyright (C) 2002-2004  TechGame Networks, LLC.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the BSD style License as found in the
# LICENSE file included with this distribution.
#
# Modified by Dirk Holtwick <holtwick@web.de>, 2007-2008

# ruff: file-ignore[invalid-module-name]
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from xhtml2pdf.w3c import css

if TYPE_CHECKING:
    from collections.abc import Callable

    from typing_extensions import Self

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ Definitions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#: an+b, the argument of :nth-child() and its relatives. CSS Selectors 3 6.6.5.
_NTH_PATTERN = re.compile(r"^(?:([+-]?\d*)n)?\s*([+-]?\s*\d+)?$")


def _flatten_params(params) -> str:
    """
    The argument of a functional pseudo-class, as one string.

    The parser hands it over already broken into terms, and how it breaks it
    depends on the spelling: "odd" arrives as ("odd",), "2n+1" as
    (("2", "n"), "+", "1"), "-n + 3" as ("-n", "+", "3"). Reassembling and
    matching one pattern is steadier than reading each of those shapes.
    """
    parts = []
    for param in params:
        if isinstance(param, tuple | list):
            parts.append(_flatten_params(param))
        else:
            parts.append(str(param))
    return "".join(parts).replace(" ", "").lower()


def _parse_nth(params) -> tuple[int, int] | None:
    """Turn an an+b argument into (a, b), or None if it is not one."""
    text = _flatten_params(params)
    if text == "odd":
        return (2, 1)
    if text == "even":
        return (2, 0)

    match = _NTH_PATTERN.match(text)
    if not match or not text:
        return None
    coefficient, constant = match.groups()
    if coefficient is None:
        # A plain number: b on its own, matching one position.
        return (0, int(constant)) if constant else None
    if coefficient in {"", "+"}:
        a = 1
    elif coefficient == "-":
        a = -1
    else:
        a = int(coefficient)
    return (a, int(constant) if constant else 0)


def _matches_nth(index: int, a: int, b: int) -> bool:
    """Whether a 1-based position satisfies an+b for some whole n >= 0."""
    if a == 0:
        return index == b
    offset = index - b
    return offset % a == 0 and offset // a >= 0


class CSSDOMElementInterface(css.CSSElementInterfaceAbstract):
    """An implementation of css.CSSElementInterfaceAbstract for xml.dom Element Nodes."""

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ~ Constants / Variables / Etc.
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    style = None
    #: The node this wraps. Assigned in __init__, declared here so the
    #: pseudo-class handlers below can be read on their own.
    domElement: Any

    #: The not-* and middle-child forms are xhtml2pdf's own, not CSS, and
    #: DEFAULT_CSS uses them; the rest are the standard structural
    #: pseudo-classes. Anything not here still parses and simply never
    #: matches, which is what :hover and ::before should do in a PDF.
    _pseudoStateHandlerLookup: ClassVar[dict[str, Callable[[Self], bool]]] = {
        "first-child": lambda self: not bool(self.getPreviousSibling()),
        "not-first-child": lambda self: bool(self.getPreviousSibling()),
        "last-child": lambda self: not bool(self.getNextSibling()),
        "not-last-child": lambda self: bool(self.getNextSibling()),
        "middle-child": lambda self: not bool(self.getPreviousSibling())
        and not bool(self.getNextSibling()),
        "not-middle-child": lambda self: bool(self.getPreviousSibling())
        or bool(self.getNextSibling()),
        "only-child": lambda self: self._countSiblings(same_type=False) == 1,
        "only-of-type": lambda self: self._countSiblings(same_type=True) == 1,
        "first-of-type": lambda self: self._indexAmongSiblings(same_type=True) == 1,
        "last-of-type": lambda self: (
            self._indexAmongSiblings(same_type=True)
            == self._countSiblings(same_type=True)
        ),
        "empty": lambda self: not any(
            child.nodeType in {child.ELEMENT_NODE, child.TEXT_NODE}
            and (child.nodeType == child.ELEMENT_NODE or child.data.strip())
            for child in self.domElement.childNodes
        ),
        "root": lambda self: (
            self.domElement.parentNode is None
            or self.domElement.parentNode.nodeType != self.domElement.ELEMENT_NODE
        ),
        # XXX 'first-line':
    }

    #: Pseudo-classes that take an an+b argument.
    _pseudoFunctionHandlerLookup: ClassVar[dict[str, Callable]] = {
        "nth-child": lambda self, a, b: _matches_nth(
            self._indexAmongSiblings(same_type=False), a, b
        ),
        "nth-of-type": lambda self, a, b: _matches_nth(
            self._indexAmongSiblings(same_type=True), a, b
        ),
        "nth-last-child": lambda self, a, b: _matches_nth(
            self._countSiblings(same_type=False)
            - self._indexAmongSiblings(same_type=False)
            + 1,
            a,
            b,
        ),
        "nth-last-of-type": lambda self, a, b: _matches_nth(
            self._countSiblings(same_type=True)
            - self._indexAmongSiblings(same_type=True)
            + 1,
            a,
            b,
        ),
    }

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # ~ Definitions
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(self, domElement, cssParser=None) -> None:
        self.domElement = domElement
        # print self.domElement.attributes
        if cssParser is not None:
            self.onCSSParserVisit(cssParser)

    def onCSSParserVisit(self, cssParser):
        styleSrc = self.getStyleAttr()
        if styleSrc:
            style = cssParser.parseInline(styleSrc)
            self.setInlineStyle(style)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def matchesNode(self, namespace_tagName):
        namespace, tagName = namespace_tagName
        if tagName not in {"*", self.domElement.tagName}:
            return False
        if namespace in {None, "", "*"}:
            # matches any namespace
            return True
        # full compare
        return namespace == self.domElement.namespaceURI

    def getAttr(self, name, default=NotImplemented):
        attr_value = self.domElement.attributes.get(name)
        if attr_value is not None:
            return attr_value.value
        return default

    def getIdAttr(self):
        return self.getAttr("id", "")

    def getClassAttr(self):
        return self.getAttr("class", "")

    def getStyleAttr(self):
        return self.getAttr("style", None)

    def _siblingElements(self, *, same_type: bool):
        """Every element child of this element's parent, in document order."""
        parent = self.domElement.parentNode
        children = parent.childNodes if parent is not None else [self.domElement]
        elements = [child for child in children if child.nodeType == child.ELEMENT_NODE]
        if same_type:
            tag = self.domElement.tagName
            elements = [child for child in elements if child.tagName == tag]
        return elements

    def _indexAmongSiblings(self, *, same_type: bool) -> int:
        """This element's 1-based position among its siblings, as CSS counts."""
        elements = self._siblingElements(same_type=same_type)
        try:
            return elements.index(self.domElement) + 1
        except ValueError:
            return 1

    def _countSiblings(self, *, same_type: bool) -> int:
        return len(self._siblingElements(same_type=same_type))

    def inPseudoState(self, name, params=()):
        handler = self._pseudoStateHandlerLookup.get(name)
        if handler is not None:
            return handler(self)

        function = self._pseudoFunctionHandlerLookup.get(name)
        if function is None:
            return False
        nth = _parse_nth(params)
        if nth is None:
            return False
        return function(self, *nth)

    def iterXMLParents(self, *, includeSelf=False):
        klass = type(self)
        current = self.domElement
        if not includeSelf:
            current = current.parentNode
        while (current is not None) and (current.nodeType == current.ELEMENT_NODE):
            yield klass(current)
            current = current.parentNode

    def getPreviousSibling(self):
        """
        The element before this one, wrapped like iterXMLParents' results.

        It used to come back as a bare DOM node, which is why the adjacent
        combinator never worked: css.py handed it straight to
        CSSSelectorBase.matches, which reads element.domElement and raised
        AttributeError into the blanket handler in parser.py.
        """
        sibling = self.domElement.previousSibling
        while sibling:
            if sibling.nodeType == sibling.ELEMENT_NODE:
                return type(self)(sibling)
            sibling = sibling.previousSibling
        return None

    def getNextSibling(self):
        sibling = self.domElement.nextSibling
        while sibling:
            if sibling.nodeType == sibling.ELEMENT_NODE:
                return type(self)(sibling)
            sibling = sibling.nextSibling
        return None

    def iterPrecedingSiblings(self):
        """Every element before this one under the same parent, nearest first."""
        klass = type(self)
        sibling = self.domElement.previousSibling
        while sibling:
            if sibling.nodeType == sibling.ELEMENT_NODE:
                yield klass(sibling)
            sibling = sibling.previousSibling

    def getInlineStyle(self):
        return self.style

    def setInlineStyle(self, style):
        self.style = style
