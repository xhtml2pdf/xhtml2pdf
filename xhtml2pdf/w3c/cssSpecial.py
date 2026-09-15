"""
Helper for complex CSS definitions like font, margin, padding and border
Optimized for use with PISA.

Copyright 2010 Dirk Holtwick, holtwick.it

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# ruff: file-ignore[invalid-module-name]

import logging
import re

from xhtml2pdf.util import toList

log = logging.getLogger(__name__)


_styleTable = {"normal": "", "italic": "", "oblique": ""}

_variantTable = {"normal": None, "small-caps": None}

_weightTable = {
    "light": 300,
    "lighter": 300,  # fake relativness for now
    "normal": 400,
    "bold": 700,
    "bolder": 700,  # fake relativness for now
    "100": 100,
    "200": 200,
    "300": 300,
    "400": 400,
    "500": 500,
    "600": 600,
    "700": 700,
    "800": 800,
    "900": 900,
    # wx.LIGHT: 300,
    # wx.NORMAL: 400,
    # wx.BOLD: 700,
}

# _absSizeTable = {
#    "xx-small" : 3./5.,
#    "x-small": 3./4.,
#    "small": 8./9.,
#    "medium": 1./1.,
#    "large": 6./5.,
#    "x-large": 3./2.,
#    "xx-large": 2./1.,
#    "xxx-large": 3./1.,
#    "larger": 1.25,      # XXX Not totally CSS conform:
#    "smaller": 0.75,     # http://www.w3.org/TR/CSS21/fonts.html#propdef-font-size
#    }

_borderStyleTable = {
    "none": 0,
    "hidden": 0,
    "dotted": 1,
    "dashed": 1,
    "solid": 1,
    "double": 1,
    "groove": 1,
    "ridge": 1,
    "inset": 1,
    "outset": 1,
}

#: CSS 2.1 12.6.2, plus the CSS 3 aliases xhtml2pdf's marker table accepts.
_listStyleTypeTable = {
    "disc",
    "circle",
    "square",
    "decimal",
    "decimal-leading-zero",
    "lower-roman",
    "upper-roman",
    "lower-greek",
    "lower-latin",
    "upper-latin",
    "lower-alpha",
    "upper-alpha",
    "hebrew",
    "georgian",
    "armenian",
    "cjk-ideographic",
    "hiragana",
    "katakana",
    "hiragana-iroha",
    "katakana-iroha",
}

_listStylePositionTable = {"inside", "outside"}


_backgroundRepeatTable = {"repeat", "repeat-x", "repeat-y", "no-repeat"}
_backgroundAttachmentTable = {"scroll", "fixed", "local"}
_backgroundPositionTable = {"left", "right", "top", "bottom", "center", "middle"}

_lengthPattern = re.compile(r"^[+-]?\d*\.?\d+(%|em|ex|rem|px|pt|pc|cm|mm|in)?$")
_numberPattern = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")

_flexDirectionTable = {"row", "row-reverse", "column", "column-reverse"}
_flexWrapTable = {"nowrap", "wrap", "wrap-reverse"}


def _isLength(text: str) -> bool:
    return bool(_lengthPattern.match(text))


def _isNumber(part) -> bool:
    """A bare <number>: the parser hands those over as strings, "1" or "1.5"."""
    return isinstance(part, str) and bool(_numberPattern.match(part))


def _joinPart(part) -> str:
    """One shorthand part as a string; the parser splits "10px" into a pair."""
    if isinstance(part, tuple | list):
        return "".join(str(piece) for piece in part)
    return str(part)


def getNextPart(parts):
    return parts.pop(0) if parts else None


def isSize(value):
    return value and (isinstance(value, tuple) or value == "0")


def splitBorder(parts):
    """
    The order of the elements seems to be of no importance:

    http://www.w3.org/TR/CSS21/box.html#border-shorthand-properties
    """
    width = style = color = None

    if len(parts) > 3:
        log.warning("To many elements for border style %r", parts)

    for part in parts:
        # Width
        if isSize(part):
            width = part

        # Style
        elif hasattr(part, "lower") and part.lower() in _borderStyleTable:
            style = part

        # Color
        else:
            color = part

    # log.debug("Border styles: %r -> %r ", copy_parts, (width, style, color))

    return (width, style, color)


def expandBackground(parts, last):
    """
    Expand the background shorthand.

    [<'background-color'> || <'background-image'> || <'background-repeat'> ||
     <'background-attachment'> || <'background-position'>] | inherit

    Every part used to be thrown away but one: the first was read as an image
    if it contained a dot and as a colour otherwise, so
    `background: #fcaf3e url(x.png) no-repeat` set the colour and lost both
    the image and the repeat.

    The parser has already unwrapped url(), so an image is a bare string by
    the time it arrives and cannot be told from a colour name by syntax alone;
    the dot-or-data: guess is still how they are separated, only now it is the
    last resort rather than the first test.
    """
    expanded = []
    position = []
    for part in parts:
        text = _joinPart(part)
        lowered = text.lower()
        if lowered in _backgroundRepeatTable:
            expanded.append(("background-repeat", text, last))
        elif lowered in _backgroundAttachmentTable:
            # Nothing consumes background-attachment; a PDF page does not
            # scroll. Recognised so it is not mistaken for a colour, then
            # dropped.
            continue
        elif lowered in _backgroundPositionTable or _isLength(lowered):
            position.append(text)
        elif ("." in text) or ("data:" in lowered) or lowered == "none":
            expanded.append(("background-image", text, last))
        else:
            expanded.append(("background-color", text, last))

    if position:
        expanded.append(("background-position", " ".join(position), last))
    return expanded


def expandListStyle(parts, last):
    """
    Expand the list-style shorthand.

    [ <'list-style-type'> || <'list-style-position'> || <'list-style-image'> ]

    Not expanded at all before this, so the whole shorthand was dropped:
    `list-style: none`, the usual way to ask for a list without markers, did
    nothing whatsoever.
    """
    expanded = []
    for part in parts:
        text = str(part).strip().lower()
        if text == "none":
            # CSS 2.1 12.6.2: ambiguous between type and image, and sets both.
            expanded += [
                ("list-style-type", part, last),
                ("list-style-image", part, last),
            ]
        elif text in _listStylePositionTable:
            expanded.append(("list-style-position", part, last))
        elif text in _listStyleTypeTable:
            expanded.append(("list-style-type", part, last))
        else:
            expanded.append(("list-style-image", part, last))
    return expanded


def expandFlex(parts, last):
    """
    flex: none | auto | initial | [ <flex-grow> <flex-shrink>? || <flex-basis> ]

    The parts the shorthand leaves out are not the longhands' own initial
    values: a bare number sets flex-basis to 0, not auto, and a bare basis
    sets flex-grow to 1. That is what makes three cards with `flex: 1` come
    out equal instead of proportional to their text, and it is the error
    everyone makes the first time (css-flexbox-1, 7.1.1).

    None means the declaration is not a form this understands; the caller
    keeps it as written, and it is reported as unsupported like any other.
    """
    if len(parts) == 1 and isinstance(parts[0], str):
        keyword = parts[0].lower()
        if keyword == "none":
            grow, shrink, basis = "0", "0", "auto"
        elif keyword == "auto":
            grow, shrink, basis = "1", "1", "auto"
        elif keyword == "initial":
            grow, shrink, basis = "0", "1", "auto"
        else:
            keyword = None
        if keyword is not None:
            return [
                ("flex-grow", grow, last),
                ("flex-shrink", shrink, last),
                ("flex-basis", basis, last),
            ]

    grow, shrink, basis = "1", "1", "0"
    numbers = [part for part in parts if _isNumber(part)]
    others = [part for part in parts if not _isNumber(part)]
    # A unitless 0 is a length wherever a length is allowed, so `flex: 1 1 0`
    # is three numbers of which the last is the basis.
    if len(numbers) == 3 and numbers[2] == "0" and not others:
        others = [numbers.pop()]
    if len(numbers) > 2 or len(others) > 1 or not parts:
        log.warning("flex: %r is not a form xhtml2pdf understands", parts)
        return None
    if numbers:
        grow = numbers[0]
    if len(numbers) == 2:
        shrink = numbers[1]
    if others:
        basis = others[0]
    return [
        ("flex-grow", grow, last),
        ("flex-shrink", shrink, last),
        ("flex-basis", basis, last),
    ]


def expandFlexFlow(parts, last):
    """flex-flow: <flex-direction> || <flex-wrap>, in either order."""
    expanded = []
    for part in parts:
        if part in _flexDirectionTable:
            expanded.append(("flex-direction", part, last))
        elif part in _flexWrapTable:
            expanded.append(("flex-wrap", part, last))
        else:
            log.warning("flex-flow: %r is not a direction or a wrap", part)
            return None
    return expanded


def expandGap(parts, last):
    """gap: <row-gap> <column-gap>?; one value serves both."""
    if len(parts) == 1:
        row = column = parts[0]
    elif len(parts) == 2:
        row, column = parts
    else:
        log.warning("gap: %r takes one or two values", parts)
        return None
    return [("row-gap", row, last), ("column-gap", column, last)]


def parseSpecialRules(declarations, debug=0):
    # print selectors, declarations
    # CSS MODIFY!
    dd = []

    for d in declarations:
        if debug:
            log.debug("CSS special  IN: %r", d)

        name, parts, last = d
        parts = toList(parts, cast_tuple=False)

        # FONT
        if name == "font":
            # [ [ <'font-style'> || <'font-variant'> || <'font-weight'> ]? <'font-size'> [ / <'line-height'> ]? <'font-family'> ] | inherit
            part = getNextPart(parts)
            # Style
            if part and part in _styleTable:
                dd.append(("font-style", part, last))
                part = getNextPart(parts)
                # Variant
            if part and part in _variantTable:
                dd.append(("font-variant", part, last))
                part = getNextPart(parts)
                # Weight
            if part and part in _weightTable:
                dd.append(("font-weight", part, last))
                part = getNextPart(parts)
                # Size and Line Height
            if isinstance(part, tuple) and len(part) == 3:
                fontSize, slash, lineHeight = part
                assert slash == "/"
                dd.extend(
                    (("font-size", fontSize, last), ("line-height", lineHeight, last))
                )
            else:
                dd.append(("font-size", part, last))
                # Face/ Family
            #
            # "font-face" is not a property, and nothing reads it: CSSCollect
            # only asks for the names in attrNames. So `font: 12px Arial` set
            # the size and dropped the family on the floor.
            dd.append(("font-family", parts, last))

        # BACKGROUND
        elif name == "background":
            dd.extend(expandBackground(parts, last))

        # LIST-STYLE
        elif name == "list-style":
            dd.extend(expandListStyle(parts, last))

        # FLEX, FLEX-FLOW, GAP
        elif name in {"flex", "flex-flow", "gap"}:
            expand = {"flex": expandFlex, "flex-flow": expandFlexFlow, "gap": expandGap}
            expanded = expand[name](parts, last)
            if expanded is None:
                dd.append(d)
            else:
                dd.extend(expanded)

        # TODO: We should definitely outsource the "if len() ==" part into a separate function!
        # Because we're repeating the same if-elif-else statement for MARGIN, PADDING,
        # BORDER-WIDTH, BORDER-COLOR and BORDER-STYLE. That's pretty messy. (fbernhart)
        # MARGIN
        elif name == "margin":
            if len(parts) == 1:
                top = bottom = left = right = parts[0]
            elif len(parts) == 2:
                top = bottom = parts[0]
                left = right = parts[1]
            elif len(parts) == 3:
                top = parts[0]
                left = right = parts[1]
                bottom = parts[2]
            elif len(parts) == 4:
                top = parts[0]
                right = parts[1]
                bottom = parts[2]
                left = parts[3]
            else:
                continue
            dd.extend(
                (
                    ("margin-left", left, last),
                    ("margin-right", right, last),
                    ("margin-top", top, last),
                    ("margin-bottom", bottom, last),
                )
            )

        # PADDING
        elif name == "padding":
            if len(parts) == 1:
                top = bottom = left = right = parts[0]
            elif len(parts) == 2:
                top = bottom = parts[0]
                left = right = parts[1]
            elif len(parts) == 3:
                top = parts[0]
                left = right = parts[1]
                bottom = parts[2]
            elif len(parts) == 4:
                top = parts[0]
                right = parts[1]
                bottom = parts[2]
                left = parts[3]
            else:
                continue
            dd.extend(
                (
                    ("padding-left", left, last),
                    ("padding-right", right, last),
                    ("padding-top", top, last),
                    ("padding-bottom", bottom, last),
                )
            )

        # BORDER WIDTH
        elif name == "border-width":
            if len(parts) == 1:
                top = bottom = left = right = parts[0]
            elif len(parts) == 2:
                top = bottom = parts[0]
                left = right = parts[1]
            elif len(parts) == 3:
                top = parts[0]
                left = right = parts[1]
                bottom = parts[2]
            elif len(parts) == 4:
                top = parts[0]
                right = parts[1]
                bottom = parts[2]
                left = parts[3]
            else:
                continue
            dd.extend(
                (
                    ("border-left-width", left, last),
                    ("border-right-width", right, last),
                    ("border-top-width", top, last),
                    ("border-bottom-width", bottom, last),
                )
            )

        # BORDER COLOR
        elif name == "border-color":
            if len(parts) == 1:
                top = bottom = left = right = parts[0]
            elif len(parts) == 2:
                top = bottom = parts[0]
                left = right = parts[1]
            elif len(parts) == 3:
                top = parts[0]
                left = right = parts[1]
                bottom = parts[2]
            elif len(parts) == 4:
                top = parts[0]
                right = parts[1]
                bottom = parts[2]
                left = parts[3]
            else:
                continue
            dd.extend(
                (
                    ("border-left-color", left, last),
                    ("border-right-color", right, last),
                    ("border-top-color", top, last),
                    ("border-bottom-color", bottom, last),
                )
            )

        # BORDER STYLE
        elif name == "border-style":
            if len(parts) == 1:
                top = bottom = left = right = parts[0]
            elif len(parts) == 2:
                top = bottom = parts[0]
                left = right = parts[1]
            elif len(parts) == 3:
                top = parts[0]
                left = right = parts[1]
                bottom = parts[2]
            elif len(parts) == 4:
                top = parts[0]
                right = parts[1]
                bottom = parts[2]
                left = parts[3]
            else:
                continue
            dd.extend(
                (
                    ("border-left-style", left, last),
                    ("border-right-style", right, last),
                    ("border-top-style", top, last),
                    ("border-bottom-style", bottom, last),
                )
            )

        # BORDER
        elif name == "border":
            width, style, color = splitBorder(parts)
            if width is not None:
                dd.extend(
                    (
                        ("border-left-width", width, last),
                        ("border-right-width", width, last),
                        ("border-top-width", width, last),
                        ("border-bottom-width", width, last),
                    )
                )
            if style is not None:
                dd.extend(
                    (
                        ("border-left-style", style, last),
                        ("border-right-style", style, last),
                        ("border-top-style", style, last),
                        ("border-bottom-style", style, last),
                    )
                )
            if color is not None:
                dd.extend(
                    (
                        ("border-left-color", color, last),
                        ("border-right-color", color, last),
                        ("border-top-color", color, last),
                        ("border-bottom-color", color, last),
                    )
                )

        # BORDER TOP, BOTTOM, LEFT, RIGHT
        elif name in {"border-top", "border-bottom", "border-left", "border-right"}:
            direction = name[7:]
            width, style, color = splitBorder(parts)
            # print direction, width
            if width is not None:
                dd.append(("border-" + direction + "-width", width, last))
            if style is not None:
                dd.append(("border-" + direction + "-style", style, last))
            if color is not None:
                dd.append(("border-" + direction + "-color", color, last))

        # REST
        else:
            dd.append(d)

    if debug and dd:
        log.debug("CSS special OUT:\n%s", "\n".join([repr(d) for d in dd]))

    if 0:  # declarations!=dd:
        print("###", declarations)
        print("#->", dd)
        # CSS MODIFY! END
    return dd


# import re
# _rxhttp = re.compile(r"url\([\'\"]?http\:\/\/[^\/]", re.IGNORECASE|re.DOTALL)


def cleanupCSS(src):
    # src = _rxhttp.sub('url(', src)
    return src
