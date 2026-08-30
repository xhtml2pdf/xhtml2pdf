# Copyright 2010 Dirk Holtwick, holtwick.it
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import copy
import logging
import re
import xml.dom.minidom
from typing import NamedTuple
from xml.dom import Node

import html5lib
from html5lib import treebuilders
from reportlab.platypus.doctemplate import FrameBreak, NextPageTemplate
from reportlab.platypus.flowables import KeepInFrame, PageBreak

from xhtml2pdf.default import (
    BOOL,
    BOX,
    COLOR,
    FILE,
    FONT,
    INT,
    MUST,
    POS,
    SIZE,
    STRING,
    TAGS,
)
from xhtml2pdf.files import pisaTempFile
from xhtml2pdf.properties import (
    FRAG_BLOCK_GROUPS,
    LOOP_GROUPS,
    PROPERTY_NAMES,
    SUPPORTED_PROPERTIES,
    CSSAttrs,
    apply_uniform_groups,
)

# TODO: Why do we need to import these Tags here? They aren't uses in this file or any other file,
#  but if we don't import them, the tests fail. Very strange (fbernhart)
from xhtml2pdf.tables import (  # noqa: F401
    TableData,
    pisaTagTABLE,
    pisaTagTD,
    pisaTagTH,
    pisaTagTHEAD,
    pisaTagTR,
)
from xhtml2pdf.tags import (  # noqa: F401
    pisaTag,
    pisaTagA,
    pisaTagBODY,
    pisaTagBR,
    pisaTagCANVAS,
    pisaTagDIV,
    pisaTagFONT,
    pisaTagH1,
    pisaTagH2,
    pisaTagH3,
    pisaTagH4,
    pisaTagH5,
    pisaTagH6,
    pisaTagHR,
    pisaTagIMG,
    pisaTagINPUT,
    pisaTagLI,
    pisaTagMETA,
    pisaTagOL,
    pisaTagP,
    pisaTagPDFBARCODE,
    pisaTagPDFFONT,
    pisaTagPDFFRAME,
    pisaTagPDFLANGUAGE,
    pisaTagPDFNEXTFRAME,
    pisaTagPDFNEXTPAGE,
    pisaTagPDFNEXTTEMPLATE,
    pisaTagPDFPAGECOUNT,
    pisaTagPDFPAGENUMBER,
    pisaTagPDFSPACER,
    pisaTagPDFTEMPLATE,
    pisaTagPDFTOC,
    pisaTagSELECT,
    pisaTagSTYLE,
    pisaTagSUB,
    pisaTagSUP,
    pisaTagTEXTAREA,
    pisaTagTITLE,
    pisaTagUL,
)
from xhtml2pdf.util import (
    getAlign,
    getBox,
    getColor,
    getKeepInFrameMode,
    getPos,
    getSize,
    toList,
)
from xhtml2pdf.w3c import cssDOMElementInterface
from xhtml2pdf.w3c.css import CSSTerminalFunction
from xhtml2pdf.xhtml2pdf_reportlab import PmlLeftPageBreak, PmlRightPageBreak

log = logging.getLogger(__name__)

rxhttpstrip = re.compile(r"https?://[^/]+(.*)", re.MULTILINE | re.IGNORECASE)


class AttrContainer(dict):
    def __getattr__(self, name):
        try:
            return dict.__getattr__(self, name)
        except Exception:
            return self[name]


def pisaGetAttributes(c, tag, attributes):
    attrs = {}
    if attributes:
        for k, v in attributes.items():
            try:
                # XXX no Unicode! Reportlab fails with template names
                attrs[str(k)] = str(v)
            except Exception as e:  # noqa: PERF203
                log.debug(
                    "%s during string conversion for %s=%s", e, k, v, exc_info=True
                )
                attrs[k] = v

    nattrs = {}
    if tag in TAGS:
        block, adef = TAGS[tag]
        adef["id"] = STRING

        for k, v in adef.items():
            nattrs[k] = None
            # print k, v
            # defaults, wenn vorhanden
            if isinstance(v, tuple):
                if v[1] == MUST and k not in attrs:
                    log.warning(c.warning("Attribute '%s' must be set!", k))
                    nattrs[k] = None
                    continue
                nv = attrs.get(k, v[1])
                dfl = v[1]
                v = v[0]
            else:
                nv = attrs.get(k)
                dfl = None

            if nv is not None:
                if isinstance(v, list):
                    nv = nv.strip().lower()
                    if nv not in v:
                        # ~ raise PML_EXCEPTION, "attribute '%s' of wrong value, allowed is one of: %s" % (k, repr(v))
                        log.warning(
                            c.warning(
                                "Attribute '%s' of wrong value, allowed is one of: %s",
                                k,
                                repr(v),
                            )
                        )
                        nv = dfl

                elif v == BOOL:
                    nv = nv.strip().lower()
                    nv = nv in {"1", "y", "yes", "true", str(k)}

                elif v == SIZE:
                    try:
                        nv = getSize(nv)
                    except Exception:
                        log.warning(c.warning("Attribute '%s' expects a size value", k))

                elif v == BOX:
                    nv = getBox(nv, c.pageSize)

                elif v == POS:
                    nv = getPos(nv, c.pageSize)

                elif v == INT:
                    nv = int(nv)

                elif v == COLOR:
                    nv = getColor(nv)

                elif v == FILE:
                    nv = c.getFile(nv)

                elif v == FONT:
                    nv = c.getFontName(nv)

                nattrs[k] = nv

    return AttrContainer(nattrs)


#: Kept as an alias: this has always been a public name in this module, and a
#: caller may be importing it. The list itself lives in xhtml2pdf.properties,
#: where each property carries its group, its consumer and -- where the mapping
#: is uniform -- the frag attribute and converter that apply it.
attrNames = PROPERTY_NAMES


def warnUnsupportedProperties(rulesets) -> None:
    """
    Say once which declared properties this library will not act on.

    CSSCollect asks the cascade only for the names in attrNames, so anything
    else is parsed, cascaded, stored in the ruleset and then quietly ignored,
    with not even a debug line to say so. Naming them is the difference
    between "xhtml2pdf renders my CSS wrong" and "xhtml2pdf does not
    implement float".
    """
    declared: set[str] = set()
    for ruleset in rulesets:
        for declarations in ruleset.values():
            declared.update(declarations)

    unsupported = sorted(declared - SUPPORTED_PROPERTIES)
    if unsupported:
        log.warning(
            "Ignoring CSS properties xhtml2pdf does not implement: %s",
            ", ".join(unsupported),
        )


#: The CSS functions the rest of the library can actually read. `url()` never
#: reaches here as a function -- the parser hands it over as a plain string --
#: and getColor reads the arguments of rgb() and rgba() off the function
#: object. Everything else is a value nothing downstream can evaluate.
READABLE_CSS_FUNCTIONS: frozenset[str] = frozenset({"rgb", "rgba"})


def firstUnreadableFunction(value) -> CSSTerminalFunction | None:
    """Return the first CSS function in `value` this library cannot evaluate."""
    parts = value if isinstance(value, list | tuple) else (value,)
    return next(
        (
            part
            for part in parts
            if isinstance(part, CSSTerminalFunction)
            and part.name.lower() not in READABLE_CSS_FUNCTIONS
        ),
        None,
    )


def dropUnreadableFunctions(cssAttrs, dropped: set[str]) -> None:
    """
    Discard declarations whose value is a CSS function we cannot evaluate.

    A function reaches the cascade as a CSSTerminalFunction, which is neither a
    string nor a sequence, and every consumer in CSS2Frag treats the value as
    one or the other. `width: calc(100% - 20pt)` therefore raised TypeError and
    `background-image: linear-gradient(...)` AttributeError, each of them
    aborting the whole conversion -- for CSS that a browser renders without
    complaint and that this library would otherwise have ignored.

    Dropping the declaration puts those values back with everything else
    xhtml2pdf does not implement: ignored, and named once so the author knows
    which of their declarations did nothing.
    """
    unreadable = [
        (name, function)
        for name, value in cssAttrs.items()
        if (function := firstUnreadableFunction(value)) is not None
    ]
    for name, function in unreadable:
        del cssAttrs[name]
        dropped.add(f"{name}: {function.name}()")


def warnDroppedFunctions(dropped: set[str]) -> None:
    """Say once which declarations were dropped for holding a CSS function."""
    if dropped:
        log.warning(
            "Ignoring CSS declarations whose value xhtml2pdf cannot evaluate: %s",
            ", ".join(sorted(dropped)),
        )


def getCSSAttr(self, cssCascade, attrName, default=NotImplemented):
    if attrName in self.cssAttrs:
        return self.cssAttrs[attrName]

    try:
        result = cssCascade.findStyleFor(self.cssElement, attrName, default)
    except LookupError:
        result = None

    # XXX Workaround for inline styles
    try:
        style = self.cssStyle
    except Exception:
        style = self.cssStyle = cssCascade.parser.parseInline(
            self.cssElement.getStyleAttr() or ""
        )[0]
    if attrName in style:
        result = style[attrName]

    if result == "inherit":
        if hasattr(self.parentNode, "getCSSAttr"):
            result = self.parentNode.getCSSAttr(cssCascade, attrName, default)
        elif default is not NotImplemented:
            return default
        msg = f"Could not find inherited CSS attribute value for '{attrName}'"
        raise LookupError(msg)

    if result is not None:
        self.cssAttrs[attrName] = result
    return result


# TODO: Monkeypatching standard lib should go away.
xml.dom.minidom.Element.getCSSAttr = getCSSAttr  # type: ignore[attr-defined]

# Create an aliasing system.  Many sources use non-standard tags, because browsers allow
# them to.  This allows us to map a nonstandard name to the standard one.
nonStandardAttrNames = {"bgcolor": "background-color"}

#: What the type attribute of a list means in CSS. HTML's "disk" is CSS's
#: "disc", and the ordered forms name counter styles. The attribute was
#: declared in TAGS and parsed, and then nothing ever read it: only
#: list-style-type in a stylesheet did anything.
LIST_STYLE_TYPES: dict[str, dict[str, str]] = {
    "ol": {
        "1": "decimal",
        "a": "lower-alpha",
        "A": "upper-alpha",
        "i": "lower-roman",
        "I": "upper-roman",
    },
    "ul": {"circle": "circle", "disk": "disc", "square": "square"},
}


def mapNonStandardAttrs(c, node, attrList):
    for attr, standard in nonStandardAttrNames.items():
        if attr in attrList and standard not in c:
            c[standard] = attrList[attr]

    styles = LIST_STYLE_TYPES.get(node.tagName)
    # Only when it is written down: the attribute carries a default even when
    # the author left it out, and the default stylesheet always sets
    # list-style-type, so there is no telling a user agent rule from an author
    # one. A type that was actually typed wins.
    if styles and node.hasAttribute("type"):
        # From the DOM and not from attrList: an attribute declared as a list
        # of allowed values is lowercased when it is parsed, and the type of a
        # list is case sensitive -- "a" and "A" are different counters.
        style = styles.get(node.getAttribute("type").strip())
        if style:
            c["list-style-type"] = style

    return c


#: Pseudo-classes whose answer depends on where an element sits among its
#: siblings, or on what it contains. Two siblings with the same tag, class,
#: id and style can differ on these, so they must not share a cached result.
POSITIONAL_PSEUDO_CLASSES: frozenset[str] = frozenset(
    {
        "empty",
        "first-child",
        "first-of-type",
        "last-child",
        "last-of-type",
        "middle-child",
        "not-first-child",
        "not-last-child",
        "not-middle-child",
        "nth-child",
        "nth-last-child",
        "nth-last-of-type",
        "nth-of-type",
        "only-child",
        "only-of-type",
    }
)


def getPositionalTagNames(cssCascade) -> set[str]:
    """
    Tag names some rule selects by position, so their cache key needs one.

    Only a pseudo-class on the selector's own subject counts. In
    `ul li:first-child div` the constraint is on the li, and two div siblings
    under one li answer it the same way, so the div does not need a position
    in its key. "*" means every tag does.
    """
    names: set[str] = set()
    for ruleset in cssCascade.iterCSSRulesets():
        for selector in ruleset:
            qualifiers = getattr(selector, "qualifiers", ())
            if any(
                qualifier.isPseudo() and qualifier.name in POSITIONAL_PSEUDO_CLASSES
                for qualifier in qualifiers
            ):
                names.add(str(selector.name).lower())
    return names


def getElementPosition(node) -> int:
    """This element's 0-based position among its element siblings."""
    position = 0
    sibling = node.previousSibling
    while sibling is not None:
        if sibling.nodeType == sibling.ELEMENT_NODE:
            position += 1
        sibling = sibling.previousSibling
    return position


class CSSAttrCacheKey(NamedTuple):
    """
    What makes two elements resolve to the same CSS properties.

    A tuple rather than the "#"-joined string this used to be. That string was
    ambiguous: id="x" with style="color:#fff" built exactly the same key as
    id="x#color:" with style="fff", so two different elements shared one entry.
    A tuple has no separator to confuse.

    The parent is held as the node itself and not as id(node). Two nodes alive
    at once cannot share an id, but a freed node's id can be handed to a later
    one, and this cache used to outlive the document that filled it.
    """

    parent: object
    tag: str
    css_class: str
    css_id: str
    style: str
    #: Only for tags some rule selects by position; see getPositionalTagNames.
    position: int | None = None


def getCSSAttrCacheKey(node, positional_tags=frozenset()) -> CSSAttrCacheKey:
    _cl = _id = _st = ""
    for k, v in node.attributes.items():
        if k == "class":
            _cl = v
        elif k == "id":
            _id = v
        elif k == "style":
            _st = v

    tag = node.tagName.lower()

    # Where the element sits belongs in the key whenever a structural selector
    # asks. Without it every sibling was handed the first one's result:
    # li:nth-child(odd) coloured a whole list, td:empty coloured no cell, and
    # DEFAULT_CSS's own `ul li div:first-child` applied to every div. It is
    # left out otherwise because it makes the key unique per element, and with
    # it in unconditionally the largest fixture in testrender renders half
    # again as slowly.
    positional = tag in positional_tags or "*" in positional_tags

    return CSSAttrCacheKey(
        parent=node.parentNode,
        tag=tag,
        css_class=_cl,
        css_id=_id,
        style=_st,
        position=getElementPosition(node) if positional else None,
    )


def CSSCollect(node, c):
    if c.css:
        key = getCSSAttrCacheKey(node, c.cssPositionalTags)
        cached = c.cssAttrCache.get(key)
        if cached is not None:
            node.cssAttrs = cached
            return cached

        node.cssElement = cssDOMElementInterface.CSSDOMElementInterface(node)
        # getCSSAttr writes what it resolves straight into this mapping; the
        # loop's own return value was collected into a dict that nothing ever
        # read, which made the loop look like it built the result.
        node.cssAttrs = CSSAttrs()
        for cssAttrName in PROPERTY_NAMES:
            try:
                node.getCSSAttr(c.cssCascade, cssAttrName)
            except Exception as e:  # noqa: PERF203
                log.debug("%r during CSS attr '%s'", e, cssAttrName, exc_info=True)

        dropUnreadableFunctions(node.cssAttrs, c.cssDroppedFunctions)

        c.cssAttrCache[key] = node.cssAttrs
    return node.cssAttrs


def lower(sequence):
    if isinstance(sequence, str):
        return sequence.lower()
    return sequence[0].lower()


def CSS2Frag(c, kw, isBlock):
    # COLORS
    if "color" in c.cssAttr:
        c.frag.textColor = getColor(c.cssAttr["color"], "#000000")
    if "background-color" in c.cssAttr:
        c.frag.backColor = getColor(c.cssAttr["background-color"], "#ffffff")
        # FONT SIZE, STYLE, WEIGHT
    if "font-family" in c.cssAttr:
        c.frag.fontName = c.getFontName(c.cssAttr["font-family"])
    if "font-size" in c.cssAttr:
        # XXX inherit
        c.frag.fontSize = max(
            getSize("".join(c.cssAttr["font-size"]), c.frag.fontSize, c.baseFontSize),
            1.0,
        )
    if "line-height" in c.cssAttr:
        leading = "".join(c.cssAttr["line-height"])
        c.frag.leading = getSize(leading, c.frag.fontSize)
        c.frag.leadingSource = leading
    else:
        c.frag.leading = getSize(c.frag.leadingSource, c.frag.fontSize)
    if "letter-spacing" in c.cssAttr:
        c.frag.letterSpacing = c.cssAttr["letter-spacing"]
    if "word-spacing" in c.cssAttr:
        c.frag.wordSpacing = c.cssAttr["word-spacing"]
    if "text-transform" in c.cssAttr:
        c.frag.textTransform = lower(c.cssAttr["text-transform"])
    if "-pdf-line-spacing" in c.cssAttr:
        c.frag.leadingSpace = getSize("".join(c.cssAttr["-pdf-line-spacing"]))
        # print "line-spacing", c.cssAttr["-pdf-line-spacing"], c.frag.leading
    if "font-weight" in c.cssAttr:
        value = lower(c.cssAttr["font-weight"])
        if value in {"bold", "bolder", "500", "600", "700", "800", "900"}:
            c.frag.bold = 1
        else:
            c.frag.bold = 0
    for value in toList(c.cssAttr.get("text-decoration", "")):
        if "underline" in value:
            c.frag.underline = 1
        if "line-through" in value:
            c.frag.strike = 1
        if "none" in value:
            c.frag.underline = 0
            c.frag.strike = 0
    if "font-style" in c.cssAttr:
        value = lower(c.cssAttr["font-style"])
        if value in {"italic", "oblique"}:
            c.frag.italic = 1
        else:
            c.frag.italic = 0
    if "white-space" in c.cssAttr:
        # normal | pre | nowrap
        c.frag.whiteSpace = str(c.cssAttr["white-space"]).lower()
        # ALIGN & VALIGN
    if "text-align" in c.cssAttr:
        c.frag.alignment = getAlign(c.cssAttr["text-align"])
    if "vertical-align" in c.cssAttr:
        c.frag.vAlign = c.cssAttr["vertical-align"]
        # HEIGHT & WIDTH
    if "height" in c.cssAttr:
        try:
            # XXX Relative is not correct!
            c.frag.height = "".join(toList(c.cssAttr["height"]))
        except TypeError:
            # sequence item 0: expected string, tuple found
            c.frag.height = "".join(toList(c.cssAttr["height"][0]))
        if c.frag.height == "auto":
            c.frag.height = None
    if "width" in c.cssAttr:
        try:
            # XXX Relative is not correct!
            c.frag.width = "".join(toList(c.cssAttr["width"]))
        except TypeError:
            c.frag.width = "".join(toList(c.cssAttr["width"][0]))
        if c.frag.width == "auto":
            c.frag.width = None
        # ZOOM
    if "zoom" in c.cssAttr:
        # XXX Relative is not correct!
        zoom = "".join(toList(c.cssAttr["zoom"]))
        if zoom.endswith("%"):
            zoom = float(zoom[:-1]) / 100.0
        c.frag.zoom = float(zoom)
        # MARGINS & LIST INDENT, STYLE
    if isBlock:
        # Margins, indent, paddings and border widths, styles and colours: the
        # properties whose whole consumption is a mapping onto a frag
        # attribute through one converter. The pairs come from the registry
        # rather than being repeated here, so a border side cannot be
        # forgotten on one of the three lists and not the others.
        apply_uniform_groups(c.frag, c.cssAttr, FRAG_BLOCK_GROUPS)

        if "margin-left" in c.cssAttr:
            c.frag.bulletIndent = kw["margin-left"]  # For lists
            kw["margin-left"] += getSize(c.cssAttr["margin-left"], c.frag.fontSize)
            c.frag.leftIndent = kw["margin-left"]
        if "margin-right" in c.cssAttr:
            kw["margin-right"] += getSize(c.cssAttr["margin-right"], c.frag.fontSize)
            c.frag.rightIndent = kw["margin-right"]

        if "background-image" in c.cssAttr:
            # `none` is a keyword, not a filename.
            image = c.cssAttr["background-image"]
            c.frag.backgroundImage = (
                None if str(image).strip().lower() == "none" else c.getFile(image)
            )
        if "background-repeat" in c.cssAttr:
            c.frag.backgroundRepeat = lower(c.cssAttr["background-repeat"])
        if "background-position" in c.cssAttr:
            c.frag.backgroundPosition = " ".join(
                str(part) for part in toList(c.cssAttr["background-position"])
            )
        if "list-style-type" in c.cssAttr:
            c.frag.listStyleType = str(c.cssAttr["list-style-type"]).lower()
        if "list-style-image" in c.cssAttr:
            # `none` is a keyword, not a filename. It reaches here from the
            # list-style shorthand, which sets both type and image.
            image = c.cssAttr["list-style-image"]
            c.frag.listStyleImage = (
                None if str(image).strip().lower() == "none" else c.getFile(image)
            )


def pisaPreLoop(node, context, *, collect=False):
    """Collect all CSS definitions."""
    data = ""
    if node.nodeType == Node.TEXT_NODE and collect:
        data = node.data

    elif node.nodeType == Node.ELEMENT_NODE:
        name = node.tagName.lower()

        if name in {"style", "link"}:
            attr = pisaGetAttributes(context, name, node.attributes)
            media = [x.strip() for x in attr.media.lower().split(",") if x.strip()]

            if attr.get("type", "").lower() in {"", "text/css"} and (
                not media or "all" in media or "print" in media or "pdf" in media
            ):
                if name == "style":
                    for child in node.childNodes:
                        data += pisaPreLoop(child, context, collect=True)
                    context.addCSS(data)
                    return ""

                if name == "link" and attr.href and attr.rel.lower() == "stylesheet":
                    # print "CSS LINK", attr
                    context.addCSS(
                        '\n@import "{}" {};'.format(attr.href, ",".join(media))
                    )

    for child in node.childNodes:
        result = pisaPreLoop(child, context, collect=collect)
        if collect:
            data += result

    return data


def pisaLoop(node, context, path=None, **kw):
    if path is None:
        path = []

    # Initialize KW
    if not kw:
        kw = {"margin-top": 0, "margin-bottom": 0, "margin-left": 0, "margin-right": 0}
    else:
        kw = copy.copy(kw)

    # indent = len(path) * "  " # only used for debug print statements

    # TEXT
    if node.nodeType == Node.TEXT_NODE:
        # print indent, "#", repr(node.data) #, context.frag
        context.addFrag(node.data)
        # context.text.append(node.value)

    # ELEMENT
    elif node.nodeType == Node.ELEMENT_NODE:
        node.tagName = node.tagName.replace(":", "").lower()

        if node.tagName in {"style", "script"}:
            return

        path = [*copy.copy(path), node.tagName]

        # Prepare attributes
        attr = pisaGetAttributes(context, node.tagName, node.attributes)
        # log.debug(indent + "<%s %s>" % (node.tagName, attr) +
        # repr(node.attributes.items())) #, path

        # Calculate styles
        context.cssAttr = CSSCollect(node, context)
        context.cssAttr = mapNonStandardAttrs(context.cssAttr, node, attr)
        context.node = node

        # Block?
        PAGE_BREAK = 1
        PAGE_BREAK_RIGHT = 2
        PAGE_BREAK_LEFT = 3

        pageBreakAfter = False
        frameBreakAfter = False
        display = lower(context.cssAttr.get("display", "inline"))
        # print indent, node.tagName, display,
        # context.cssAttr.get("background-color", None), attr
        isBlock = display == "block"

        if isBlock:
            context.addPara()

            # Page break by CSS
            if "-pdf-next-page" in context.cssAttr:
                context.addStory(
                    NextPageTemplate(str(context.cssAttr["-pdf-next-page"]))
                )
            if (
                "-pdf-page-break" in context.cssAttr
                and str(context.cssAttr["-pdf-page-break"]).lower() == "before"
            ):
                context.addStory(PageBreak())
            if "-pdf-frame-break" in context.cssAttr:
                if str(context.cssAttr["-pdf-frame-break"]).lower() == "before":
                    context.addStory(FrameBreak())
                if str(context.cssAttr["-pdf-frame-break"]).lower() == "after":
                    frameBreakAfter = True
            if "page-break-before" in context.cssAttr:
                if str(context.cssAttr["page-break-before"]).lower() == "always":
                    context.addStory(PageBreak())
                if str(context.cssAttr["page-break-before"]).lower() == "right":
                    context.addStory(PageBreak())
                    context.addStory(PmlRightPageBreak())
                if str(context.cssAttr["page-break-before"]).lower() == "left":
                    context.addStory(PageBreak())
                    context.addStory(PmlLeftPageBreak())
            if "page-break-after" in context.cssAttr:
                if str(context.cssAttr["page-break-after"]).lower() == "always":
                    pageBreakAfter = PAGE_BREAK
                if str(context.cssAttr["page-break-after"]).lower() == "right":
                    pageBreakAfter = PAGE_BREAK_RIGHT
                if str(context.cssAttr["page-break-after"]).lower() == "left":
                    pageBreakAfter = PAGE_BREAK_LEFT

        if display == "none":
            # print "none!"
            return

        # Translate CSS to frags

        # Save previous frag styles
        context.pushFrag()

        # Map styles to Reportlab fragment properties
        CSS2Frag(context, kw, isBlock=isBlock)

        # EXTRAS
        # -pdf-keep-with-next, -pdf-outline and -pdf-outline-open. Read here
        # and not in CSS2Frag because pisaContext.addTOC calls CSS2Frag
        # directly for the .pdftoclevelN styles, and a table of contents
        # should not pick up an outline flag from them.
        apply_uniform_groups(context.frag, context.cssAttr, LOOP_GROUPS)

        if "-pdf-outline-level" in context.cssAttr:
            context.frag.outlineLevel = int(context.cssAttr["-pdf-outline-level"])

        if "-pdf-word-wrap" in context.cssAttr:
            context.frag.wordWrap = context.cssAttr["-pdf-word-wrap"]

        # handle keep-in-frame
        keepInFrameMode = None
        keepInFrameMaxWidth = 0
        keepInFrameMaxHeight = 0
        if "-pdf-keep-in-frame-mode" in context.cssAttr:
            keepInFrameMode = getKeepInFrameMode(
                context.cssAttr["-pdf-keep-in-frame-mode"]
            )

        if "-pdf-keep-in-frame-max-width" in context.cssAttr:
            keepInFrameMaxWidth = getSize(
                "".join(context.cssAttr["-pdf-keep-in-frame-max-width"])
            )
        if "-pdf-keep-in-frame-max-height" in context.cssAttr:
            keepInFrameMaxHeight = getSize(
                "".join(context.cssAttr["-pdf-keep-in-frame-max-height"])
            )

        # BEGIN tag
        klass = globals().get("pisaTag%s" % node.tagName.replace(":", "").upper(), None)
        obj = None

        # Static block
        elementId = attr.get("id", None)
        staticFrame = context.frameStatic.get(elementId, None)
        if staticFrame:
            context.frag.insideStaticFrame += 1
            oldStory = context.swapStory()

        # ignore nested keep-in-frames, tables have their own KIF handling
        keepInFrame = keepInFrameMode is not None and context.keepInFrameIndex is None
        if keepInFrame:
            # keep track of current story index, so we can wrap everythink
            # added after this point in a KeepInFrame. This has to come after
            # the story swap above: an element that is itself the content of a
            # static frame starts a story of its own, and an index taken from
            # the story it interrupted would cut the frame's content in the
            # wrong place.
            context.keepInFrameIndex = len(context.story)

        # Tag specific operations
        if klass is not None:
            obj = klass(node, attr)
            obj.start(context)

        # Visit child nodes
        context.fragBlock = fragBlock = copy.copy(context.frag)
        for nnode in node.childNodes:
            pisaLoop(nnode, context, path, **kw)
        context.fragBlock = fragBlock

        # END tag
        if obj:
            obj.end(context)

        # Block?
        if isBlock:
            context.addPara()

            # XXX Buggy!

            # Page break by CSS
            if pageBreakAfter:
                context.addStory(PageBreak())
                if pageBreakAfter == PAGE_BREAK_RIGHT:
                    context.addStory(PmlRightPageBreak())
                if pageBreakAfter == PAGE_BREAK_LEFT:
                    context.addStory(PmlLeftPageBreak())
            if frameBreakAfter:
                context.addStory(FrameBreak())

        if keepInFrame:
            # get all content added after start of -pdf-keep-in-frame and wrap
            # it in a KeepInFrame
            substory = context.story[context.keepInFrameIndex :]
            context.story = context.story[: context.keepInFrameIndex]
            context.story.append(
                KeepInFrame(
                    content=substory,
                    maxWidth=keepInFrameMaxWidth,
                    maxHeight=keepInFrameMaxHeight,
                    mode=keepInFrameMode,
                )
            )
            # mode wasn't being used; it is necessary for tables or images at
            # end of page.
            context.keepInFrameIndex = None

        # Static block, END
        if staticFrame:
            context.addPara()
            for frame in staticFrame:
                frame.pisaStaticStory = context.story
            context.swapStory(oldStory)
            context.frag.insideStaticFrame -= 1

        # context.debug(1, indent, "</%s>" % (node.tagName))

        # Reset frag style
        context.pullFrag()

    # Unknown or not handled
    else:
        # context.debug(1, indent, "???", node, node.nodeType, repr(node))
        # Loop over children
        for child in node.childNodes:
            pisaLoop(child, context, path, **kw)


def pisaParser(
    src,
    context,
    default_css="",
    xhtml=False,  # noqa: FBT002
    encoding="utf8",
    xml_output=None,
):
    """
    - Parse HTML and get miniDOM
    - Extract CSS information, add default CSS, parse CSS
    - Handle the document DOM itself and build reportlab story
    - Return Context object.
    """
    if xhtml:
        log.warning("xhtml parameter will be removed on next release 0.2.8")
        # TODO: XHTMLParser doesn't seem to exist...
        parser = html5lib.XHTMLParser(tree=treebuilders.getTreeBuilder("dom"))
    else:
        parser = html5lib.HTMLParser(tree=treebuilders.getTreeBuilder("dom"))
    parser_kwargs = {}
    if isinstance(src, str):
        # If an encoding was provided, do not change it.
        if not encoding:
            encoding = "utf-8"
        src = src.encode(encoding)
        src = pisaTempFile(src, capacity=context.capacity)
        # To pass the encoding used to convert the text_type src to binary_type
        # on to html5lib's parser to ensure proper decoding
        parser_kwargs["transport_encoding"] = encoding

    # # Test for the restrictions of html5lib
    # if encoding:
    #     # Workaround for html5lib<0.11.1
    #     if hasattr(inputstream, "isValidEncoding"):
    #         if encoding.strip().lower() == "utf8":
    #             encoding = "utf-8"
    #         if not inputstream.isValidEncoding(encoding):
    #             log.error("%r is not a valid encoding e.g. 'utf8' is not valid but 'utf-8' is!", encoding)
    #     else:
    #         if inputstream.codecName(encoding) is None:
    #             log.error("%r is not a valid encoding", encoding)
    document = parser.parse(src, **parser_kwargs)  # encoding=encoding)

    if xml_output:
        xml_output.write(document.toprettyxml(encoding=encoding))

    if default_css:
        context.addDefaultCSS(default_css)

    pisaPreLoop(document, context)
    context.parseCSS()
    pisaLoop(document, context)
    # After the walk, not before: an inline style="" reaches the cascade only
    # while its element is being visited, so the set is not complete until now.
    warnDroppedFunctions(context.cssDroppedFunctions)
    return context


# Shortcuts

HTML2PDF = pisaParser


def XHTML2PDF(*a, **kw):
    kw["xhtml"] = True
    return HTML2PDF(*a, **kw)


XML2PDF = XHTML2PDF
