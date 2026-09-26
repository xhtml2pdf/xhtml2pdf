# Copyright (C) 2002-2004  TechGame Networks, LLC.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the BSD style License as found in the
# LICENSE file included with this distribution.
#
# Modified by Dirk Holtwick <holtwick@web.de>, 2007-2008

# ruff: file-ignore[invalid-module-name]
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from xhtml2pdf.w3c import css

if TYPE_CHECKING:
    from collections.abc import Callable

    from typing_extensions import Self

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~ Definitions
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

_flatten_params = css._flatten_params
_parse_nth = css._parse_nth
_matches_nth = css._matches_nth

#: Elements the form-state pseudo-classes (:disabled, :enabled) apply to.
_FORM_CONTROLS = frozenset(
    {"button", "input", "select", "textarea", "option", "optgroup", "fieldset"}
)
#: The <input> types a user types text into: :read-write and
#: :placeholder-shown apply to these.
_TEXT_INPUTS = frozenset(
    {
        "text", "search", "url", "tel", "email", "password", "number",
        "date", "month", "week", "time", "datetime-local",
    }
)  # fmt: skip


def _inputType(node) -> str:
    return (node.getAttribute("type") or "text").lower()


def _isDisabled(node) -> bool:
    """HTML's "actually disabled": its own disabled, or a disabled container's."""
    if node.tagName.lower() not in _FORM_CONTROLS:
        return False
    current = node
    while current is not None and current.nodeType == current.ELEMENT_NODE:
        if current.hasAttribute("disabled") and (
            current is node
            or current.tagName.lower() in {"fieldset", "optgroup", "select"}
        ):
            return True
        current = current.parentNode
    return False


def _isChecked(node) -> bool:
    tag = node.tagName.lower()
    if tag == "input":
        return _inputType(node) in {"checkbox", "radio"} and node.hasAttribute(
            "checked"
        )
    return tag == "option" and node.hasAttribute("selected")


def _isReadWrite(node) -> bool:
    tag = node.tagName.lower()
    if tag not in {"input", "textarea"} or (
        tag == "input" and _inputType(node) not in _TEXT_INPUTS
    ):
        return False
    return not node.hasAttribute("readonly") and not _isDisabled(node)


def _isPlaceholderShown(node) -> bool:
    tag = node.tagName.lower()
    if not node.hasAttribute("placeholder"):
        return False
    if tag == "input":
        return _inputType(node) in _TEXT_INPUTS and not node.getAttribute("value")
    if tag == "textarea":
        return not any(
            child.nodeType == child.TEXT_NODE and child.data
            for child in node.childNodes
        )
    return False


def _inheritedAttr(node, names) -> str | None:
    """The first of names set on node or its nearest ancestor that sets one."""
    current = node
    while current is not None and current.nodeType == current.ELEMENT_NODE:
        for name in names:
            if current.hasAttribute(name):
                return current.getAttribute(name)
        current = current.parentNode
    return None


def _matchesLang(self, params) -> bool:
    """
    :lang(): the element's language, from its own lang or xml:lang or its
    nearest ancestor's, is one asked for or begins with it and a "-".
    Case does not matter; "*" matches any language that is set.
    """
    lang = _inheritedAttr(self.domElement, ("lang", "xml:lang"))
    if not lang:
        return False
    lang = lang.lower()
    # Each language arrives as its own parameter: ("en-GB", "fr").
    wanted = [_flatten_params([param]).strip("'\"") for param in params]
    return any(
        language in {"*", lang} or lang.startswith(language + "-")
        for language in wanted
        if language
    )


def _matchesDir(self, params) -> bool:
    """
    :dir(): the direction dir sets on the element or its nearest ancestor
    with a dir of ltr or rtl, and ltr without one. dir="auto" takes the
    direction of the text, which is not worked out here: it matches neither.
    """
    current = self.domElement
    direction = "ltr"
    while current is not None and current.nodeType == current.ELEMENT_NODE:
        value = (current.getAttribute("dir") or "").lower()
        if value in {"ltr", "rtl", "auto"}:
            direction = value
            break
        current = current.parentNode
    return direction == _flatten_params(params)


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
        # Selectors 4. :scope is the root, except in the arguments of a
        # :has(), where it is the element the :has() qualifies.
        "scope": lambda self: (
            css._scope.get() is self.domElement
            if css._scope.get() is not None
            else self._pseudoStateHandlerLookup["root"](self)
        ),
        "link": lambda self: (
            self.domElement.tagName.lower() in {"a", "area"}
            and self.domElement.hasAttribute("href")
        ),
        "any-link": lambda self: self._pseudoStateHandlerLookup["link"](self),
        "checked": lambda self: _isChecked(self.domElement),
        # In a document that is never interacted with, what is checked is
        # what was checked to begin with.
        "default": lambda self: _isChecked(self.domElement),
        "disabled": lambda self: _isDisabled(self.domElement),
        "enabled": lambda self: (
            self.domElement.tagName.lower() in _FORM_CONTROLS
            and not _isDisabled(self.domElement)
        ),
        "required": lambda self: (
            self.domElement.tagName.lower() in {"input", "select", "textarea"}
            and self.domElement.hasAttribute("required")
        ),
        "optional": lambda self: (
            self.domElement.tagName.lower() in {"input", "select", "textarea"}
            and not self.domElement.hasAttribute("required")
        ),
        "read-write": lambda self: _isReadWrite(self.domElement),
        "read-only": lambda self: not _isReadWrite(self.domElement),
        "placeholder-shown": lambda self: _isPlaceholderShown(self.domElement),
    }

    #: Pseudo-classes that take a plain argument: a language, a direction.
    _pseudoArgumentHandlerLookup: ClassVar[dict[str, Callable]] = {
        "lang": _matchesLang,
        "dir": _matchesDir,
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

        argument = self._pseudoArgumentHandlerLookup.get(name)
        if argument is not None:
            return argument(self, params)

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
