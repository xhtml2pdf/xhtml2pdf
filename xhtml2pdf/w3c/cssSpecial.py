# -*- coding: utf-8 -*-

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


__reversion__ = "$Revision: 20 $"
__author__ = "$Author: holtwick $"
__date__ = "$Date: 2007-10-09 12:58:24 +0200 (Di, 09 Okt 2007) $"

"""
Helper for complex CSS definitons like font, margin, padding and border
Optimized for use with PISA
"""

import types
import logging


log = logging.getLogger("ho.css")


def toList(value):
    if type(value) != types.ListType:
        return [value]
    return value


_styleTable = {
    "normal": "",
    "italic": "",
    "oblique": "",
}

_variantTable = {
    "normal": None,
    "small-caps": None,
}

_weightTable = {
    "light": 300,
    "lighter": 300, # fake relativness for now
    "normal": 400,
    "bold": 700,
    "bolder": 700, # fake relativness for now

    "100": 100,
    "200": 200,
    "300": 300,
    "400": 400,
    "500": 500,
    "600": 600,
    "700": 700,
    "800": 800,
    "900": 900,

    #wx.LIGHT: 300,
    #wx.NORMAL: 400,
    #wx.BOLD: 700,
}

#_absSizeTable = {
#    "xx-small" : 3./5.,
#    "x-small": 3./4.,
#    "small": 8./9.,
#    "medium": 1./1.,
#    "large": 6./5.,
#    "x-large": 3./2.,
#    "xx-large": 2./1.,
#    "xxx-large": 3./1.,
#    "larger": 1.25,      # XXX Not totaly CSS conform:
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

'''
_relSizeTable = {
    'pt':
        # pt: absolute point size
        # Note: this is 1/72th of an inch
        (lambda value, pt: value),
    'px':
        # px: pixels, relative to the viewing device
        # Note: approximate at the size of a pt
        (lambda value, pt: value),
    'ex':
        # ex: proportional to the 'x-height' of the parent font
        # Note: can't seem to dervie this value from wx.Font methods,
        # so we'll approximate by calling it 1/2 a pt
        (lambda value, pt: 2 * value),
    'pc':
        # pc: 12:1 pica:point size
        # Note: this is 1/6th of an inch
        (lambda value, pt: 12*value),
    'in':
        # in: 72 inches per point
        (lambda value, pt: 72*value),
    'cm':
        # in: 72 inches per point, 2.54 cm per inch
        (lambda value, pt,_r=72./2.54: _r*value),
    'mm':
        # in: 72 inches per point, 25.4 mm per inch
        (lambda value, pt,_r=72./25.4: _r*value),
    '%':
        # %: percentage of the parent's pointSize
        (lambda value, pt: 0.01 * pt * value),
    'em':
        # em: proportional to the 'font-size' of the parent font
        (lambda value, pt: pt * value),
    }
'''


def getNextPart(parts):
    if parts:
        part = parts.pop(0)
    else:
        part = None
    return part


def isSize(value):
    return value and ((type(value) is types.TupleType) or value == "0")


def splitBorder(parts):
    """
    The order of the elements seems to be of no importance:

    http://www.w3.org/TR/CSS21/box.html#border-shorthand-properties
    """

    width = style = color = None
    copy_parts = parts[:]
    # part = getNextPart(parts)

    if len(parts) > 3:
        log.warn("To many elements for border style %r", parts)

    for part in parts:
        # Width
        if isSize(part):
            width = part
            # part = getNextPart(parts)

        # Style
        elif hasattr(part, 'lower') and part.lower() in _borderStyleTable:
            style = part
            # part = getNextPart(parts)

        # Color
        else:
            color = part

    # log.debug("Border styles: %r -> %r ", copy_parts, (width, style, color))

    return (width, style, color)


def parseSpecialRules(declarations, debug=0):
    # print selectors, declarations
    # CSS MODIFY!
    dd = []

    for d in declarations:

        if debug:
            log.debug("CSS special  IN: %r", d)

        name, parts, last = d
        oparts = parts
        parts = toList(parts)

        # FONT
        if name == "font":
            # [ [ <'font-style'> || <'font-variant'> || <'font-weight'> ]? <'font-size'> [ / <'line-height'> ]? <'font-family'> ] | inherit
            ddlen = len(dd)
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
                assert slash == '/'
                dd.append(("font-size", fontSize, last))
                dd.append(("line-height", lineHeight, last))
            else:
                dd.append(("font-size", part, last))
                # Face/ Family
            dd.append(("font-face", parts, last))

        # BACKGROUND
        elif name == "background":
            # [<'background-color'> || <'background-image'> || <'background-repeat'> || <'background-attachment'> || <'background-position'>] | inherit

            # XXX We do not receive url() and parts list, so we go for a dirty work arround
            part = getNextPart(parts) or oparts
            if part:

                if hasattr(part, '__iter__') and (type("." in part) or ("data:" in part)):
                    dd.append(("background-image", part, last))
                else:
                    dd.append(("background-color", part, last))

            if 0:
                part = getNextPart(parts) or oparts
                print ("~", part, parts, oparts, declarations)
                # Color
                if part and (not part.startswith("url")):
                    dd.append(("background-color", part, last))
                    part = getNextPart(parts)
                    # Background
                if part:
                    dd.append(("background-image", part, last))
                    # XXX Incomplete! Error in url()!

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
            dd.append(("margin-left", left, last))
            dd.append(("margin-right", right, last))
            dd.append(("margin-top", top, last))
            dd.append(("margin-bottom", bottom, last))

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
            dd.append(("padding-left", left, last))
            dd.append(("padding-right", right, last))
            dd.append(("padding-top", top, last))
            dd.append(("padding-bottom", bottom, last))

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
            dd.append(("border-left-width", left, last))
            dd.append(("border-right-width", right, last))
            dd.append(("border-top-width", top, last))
            dd.append(("border-bottom-width", bottom, last))

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
            dd.append(("border-left-color", left, last))
            dd.append(("border-right-color", right, last))
            dd.append(("border-top-color", top, last))
            dd.append(("border-bottom-color", bottom, last))

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
            dd.append(("border-left-style", left, last))
            dd.append(("border-right-style", right, last))
            dd.append(("border-top-style", top, last))
            dd.append(("border-bottom-style", bottom, last))

        # BORDER
        elif name == "border":
            width, style, color = splitBorder(parts)
            if width is not None:
                dd.append(("border-left-width", width, last))
                dd.append(("border-right-width", width, last))
                dd.append(("border-top-width", width, last))
                dd.append(("border-bottom-width", width, last))
            if style is not None:
                dd.append(("border-left-style", style, last))
                dd.append(("border-right-style", style, last))
                dd.append(("border-top-style", style, last))
                dd.append(("border-bottom-style", style, last))
            if color is not None:
                dd.append(("border-left-color", color, last))
                dd.append(("border-right-color", color, last))
                dd.append(("border-top-color", color, last))
                dd.append(("border-bottom-color", color, last))

        # BORDER TOP, BOTTOM, LEFT, RIGHT
        elif name in ("border-top", "border-bottom", "border-left", "border-right"):
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

    if 0: #declarations!=dd:
        print ("###", declarations)
        print ("#->", dd)
        # CSS MODIFY! END
    return dd


#import re
#_rxhttp = re.compile(r"url\([\'\"]?http\:\/\/[^\/]", re.IGNORECASE|re.DOTALL)

def cleanupCSS(src):
    # src = _rxhttp.sub('url(', src)
    return src
