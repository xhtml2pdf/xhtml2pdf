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

import logging
import re
import sys
from copy import copy

import arabic_reshaper
import reportlab
import reportlab.pdfbase._cidfontdata
from bidi.algorithm import get_display
from reportlab.lib.colors import Color, toColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

import xhtml2pdf.default

rgb_re = re.compile(
    r"^.*?rgb[a]?[(]([0-9]+).*?([0-9]+).*?([0-9]+)(?:.*?(?:[01]\.(?:[0-9]+)))?[)].*?[ ]*$")

log = logging.getLogger("xhtml2pdf")

import pypdf
from reportlab.graphics import renderPM
from reportlab.graphics import renderSVG

#=========================================================================
# Memoize decorator
#=========================================================================


class memoized(object):

    """
    A kwargs-aware memoizer, better than the one in python :)

    Don't pass in too large kwargs, since this turns them into a tuple of
    tuples. Also, avoid mutable types (as usual for memoizers)

    What this does is to create a dictionnary of {(*parameters):return value},
    and uses it as a cache for subsequent calls to the same method.
    It is especially useful for functions that don't rely on external variables
    and that are called often. It's a perfect match for our getSize etc...
    """

    def __init__(self, func):
        self.cache = {}
        self.func = func
        self.__doc__ = self.func.__doc__  # To avoid great confusion
        self.__name__ = self.func.__name__  # This also avoids great confusion

    def __call__(self, *args, **kwargs):
        # Make sure the following line is not actually slower than what you're
        # trying to memoize
        args_plus = tuple(kwargs.items())
        key = (args, args_plus)
        try:
            if key not in self.cache:
                res = self.func(*args, **kwargs)
                self.cache[key] = res
            return self.cache[key]
        except TypeError:
            # happens if any of the parameters is a list
            return self.func(*args, **kwargs)


def ErrorMsg():
    """
    Helper to get a nice traceback as string
    """
    import traceback

    limit = None
    _type, value, tb = sys.exc_info()
    _list = traceback.format_tb(tb, limit) + \
        traceback.format_exception_only(_type, value)
    return "Traceback (innermost last):\n" + "%-20s %s" % (
        " ".join(_list[:-1]),
        _list[-1])


def toList(value):
    if type(value) not in (list, tuple):
        return [value]
    return list(value)


def transform_attrs(obj, keys, container, func, extras=None):
    """
    Allows to apply one function to set of keys cheching if key is in container,
    also trasform ccs key to report lab keys.

    extras = Are extra params for func, it will be call like func(*[param1, param2])

    obj = frag
    keys = [(reportlab, css), ... ]
    container = cssAttr
    """
    cpextras = extras

    for reportlab, css in keys:
        extras = cpextras
        if extras is None:
            extras = []
        elif not isinstance(extras, list):
            extras = [extras]
        if css in container:
            extras.insert(0, container[css])
            setattr(obj,
                    reportlab,
                    func(*extras)
                    )


def copy_attrs(obj1, obj2, attrs):
    """
    Allows copy a list of attributes from object2 to object1.
    Useful for copy ccs attributes to fragment
    """
    for attr in attrs:
        value = getattr(obj2, attr) if hasattr(obj2, attr) else None
        if value is None and isinstance(obj2, dict) and attr in obj2:
            value = obj2[attr]
        setattr(obj1, attr, value)


def set_value(obj, attrs, value, _copy=False):
    """
    Allows set the same value to a list of attributes
    """
    for attr in attrs:
        if _copy:
            value = copy(value)
        setattr(obj, attr, value)


@memoized
def getColor(value, default=None):
    """
    Convert to color value.
    This returns a Color object instance from a text bit.
    """
    if value is None:
        return
    if isinstance(value, Color):
        return value
    value = str(value).strip().lower()
    if value == "transparent" or value == "none":
        return default
    if value in COLOR_BY_NAME:
        return COLOR_BY_NAME[value]
    if value.startswith("#") and len(value) == 4:
        value = "#" + value[1] + value[1] + \
            value[2] + value[2] + value[3] + value[3]
    elif rgb_re.search(value):
        # e.g., value = "<css function: rgb(153, 51, 153)>", go figure:
        r, g, b = [int(x) for x in rgb_re.search(value).groups()]
        value = "#%02x%02x%02x" % (r, g, b)
    else:
        # Shrug
        pass

    return toColor(value, default)  # Calling the reportlab function


def getBorderStyle(value, default=None):
    if value and (str(value).lower() not in ("none", "hidden")):
        return value
    return default


mm = cm / 10.0
dpi96 = (1.0 / 96.0 * inch)

_absoluteSizeTable = {
    "1": 50.0 / 100.0,
    "xx-small": 50.0 / 100.0,
    "x-small": 50.0 / 100.0,
    "2": 75.0 / 100.0,
    "small": 75.0 / 100.0,
    "3": 100.0 / 100.0,
    "medium": 100.0 / 100.0,
    "4": 125.0 / 100.0,
    "large": 125.0 / 100.0,
    "5": 150.0 / 100.0,
    "x-large": 150.0 / 100.0,
    "6": 175.0 / 100.0,
    "xx-large": 175.0 / 100.0,
    "7": 200.0 / 100.0,
    "xxx-large": 200.0 / 100.0,
}

_relativeSizeTable = {
    "larger": 1.25,
    "smaller": 0.75,
    "+4": 200.0 / 100.0,
    "+3": 175.0 / 100.0,
    "+2": 150.0 / 100.0,
    "+1": 125.0 / 100.0,
    "-1": 75.0 / 100.0,
    "-2": 50.0 / 100.0,
    "-3": 25.0 / 100.0,
}

MIN_FONT_SIZE = 1.0


@memoized
def getSize(value, relative=0, base=None, default=0.0):
    """
    Converts strings to standard sizes.
    That is the function taking a string of CSS size ('12pt', '1cm' and so on)
    and converts it into a float in a standard unit (in our case, points).

    >>> getSize('12pt')
    12.0
    >>> getSize('1cm')
    28.346456692913385
    """
    try:
        original = value
        if value is None:
            return relative
        elif type(value) is float:
            return value
        elif isinstance(value, int):
            return float(value)
        elif type(value) in (tuple, list):
            value = "".join(value)
        value = str(value).strip().lower().replace(",", ".")
        if value[-2:] == 'cm':
            return float(value[:-2].strip()) * cm
        elif value[-2:] == 'mm':
            return float(value[:-2].strip()) * mm  # 1mm = 0.1cm
        elif value[-2:] == 'in':
            return float(value[:-2].strip()) * inch  # 1pt == 1/72inch
        elif value[-2:] == 'pt':
            return float(value[:-2].strip())
        elif value[-2:] == 'pc':
            return float(value[:-2].strip()) * 12.0  # 1pc == 12pt
        elif value[-2:] == 'px':
            # XXX W3C says, use 96pdi
            # http://www.w3.org/TR/CSS21/syndata.html#length-units
            return float(value[:-2].strip()) * dpi96
        elif value in ("none", "0", '0.0', "auto"):
            return 0.0
        elif relative:
            if value[-3:] == 'rem':  # XXX
                # 1rem = 1 * fontSize
                return float(value[:-3].strip()) * relative
            elif value[-2:] == 'em':  # XXX
                # 1em = 1 * fontSize
                return float(value[:-2].strip()) * relative
            elif value[-2:] == 'ex':  # XXX
                # 1ex = 1/2 fontSize
                return float(value[:-2].strip()) * (relative / 2.0)
            elif value[-1:] == '%':
                # 1% = (fontSize * 1) / 100
                return (relative * float(value[:-1].strip())) / 100.0
            elif value in ("normal", "inherit"):
                return relative
            elif value in _relativeSizeTable:
                if base:
                    return max(MIN_FONT_SIZE, base * _relativeSizeTable[value])
                return max(MIN_FONT_SIZE, relative * _relativeSizeTable[value])
            elif value in _absoluteSizeTable:
                if base:
                    return max(MIN_FONT_SIZE, base * _absoluteSizeTable[value])
                return max(MIN_FONT_SIZE, relative * _absoluteSizeTable[value])
            else:
                return max(MIN_FONT_SIZE, relative * float(value))
        try:
            value = float(value)
        except ValueError:
            log.warning("getSize: Not a float %r", value)
            return default  # value = 0
        return max(0, value)
    except Exception:
        log.warning("getSize %r %r", original, relative, exc_info=1)
        return default


@memoized
def getCoords(x, y, w, h, pagesize):
    """
    As a stupid programmer I like to use the upper left
    corner of the document as the 0,0 coords therefore
    we need to do some fancy calculations
    """
    #~ print pagesize
    ax, ay = pagesize
    if x < 0:
        x = ax + x
    if y < 0:
        y = ay + y
    if w is not None and h is not None:
        if w <= 0:
            w = (ax - x + w)
        if h <= 0:
            h = (ay - y + h)
        return x, (ay - y - h), w, h
    return x, (ay - y)


@memoized
def getBox(box, pagesize):
    """
    Parse sizes by corners in the form:
    <X-Left> <Y-Upper> <Width> <Height>
    The last to values with negative values are interpreted as offsets form
    the right and lower border.
    """
    box = str(box).split()
    if len(box) != 4:
        raise Exception("box not defined right way")
    x, y, w, h = [getSize(pos) for pos in box]
    return getCoords(x, y, w, h, pagesize)


def getFrameDimensions(data, page_width, page_height):
    """Calculate dimensions of a frame

    Returns left, top, width and height of the frame in points.
    """
    box = data.get("-pdf-frame-box", [])
    if len(box) == 4:
        return [getSize(x) for x in box]
    top = getSize(data.get("top", 0))
    left = getSize(data.get("left", 0))
    bottom = getSize(data.get("bottom", 0))
    right = getSize(data.get("right", 0))
    if "height" in data:
        height = getSize(data["height"])
        if "top" in data:
            top = getSize(data["top"])
            bottom = page_height - (top + height)
        elif "bottom" in data:
            bottom = getSize(data["bottom"])
            top = page_height - (bottom + height)
    if "width" in data:
        width = getSize(data["width"])
        if "left" in data:
            left = getSize(data["left"])
            right = page_width - (left + width)
        elif "right" in data:
            right = getSize(data["right"])
            left = page_width - (right + width)
    top += getSize(data.get("margin-top", 0))
    left += getSize(data.get("margin-left", 0))
    bottom += getSize(data.get("margin-bottom", 0))
    right += getSize(data.get("margin-right", 0))

    width = page_width - (left + right)
    height = page_height - (top + bottom)
    return left, top, width, height


@memoized
def getPos(position, pagesize):
    """
    Pair of coordinates
    """
    position = str(position).split()
    if len(position) != 2:
        raise Exception("position not defined right way")
    x, y = [getSize(pos) for pos in position]
    return getCoords(x, y, None, None, pagesize)


def getBool(s):
    " Is it a boolean? "
    return str(s).lower() in ("y", "yes", "1", "true")

def getFloat(s):
    try:
        s = float(s)
    except:
        pass
    return s

_uid = 0


def getUID():
    " Unique ID "
    global _uid
    _uid += 1
    return str(_uid)


_alignments = {
    "left": TA_LEFT,
    "center": TA_CENTER,
    "middle": TA_CENTER,
    "right": TA_RIGHT,
    "justify": TA_JUSTIFY,
}


def getAlign(value, default=TA_LEFT):
    return _alignments.get(str(value).lower(), default)



_rx_datauri = re.compile(
    "^data:(?P<mime>[a-z]+/[a-z]+);base64,(?P<data>.*)$", re.M | re.DOTALL)

COLOR_BY_NAME = {
    'activeborder': Color(212, 208, 200),
    'activecaption': Color(10, 36, 106),
    'aliceblue': Color(.941176, .972549, 1),
    'antiquewhite': Color(.980392, .921569, .843137),
    'appworkspace': Color(128, 128, 128),
    'aqua': Color(0, 1, 1),
    'aquamarine': Color(.498039, 1, .831373),
    'azure': Color(.941176, 1, 1),
    'background': Color(58, 110, 165),
    'beige': Color(.960784, .960784, .862745),
    'bisque': Color(1, .894118, .768627),
    'black': Color(0, 0, 0),
    'blanchedalmond': Color(1, .921569, .803922),
    'blue': Color(0, 0, 1),
    'blueviolet': Color(.541176, .168627, .886275),
    'brown': Color(.647059, .164706, .164706),
    'burlywood': Color(.870588, .721569, .529412),
    'buttonface': Color(212, 208, 200),
    'buttonhighlight': Color(255, 255, 255),
    'buttonshadow': Color(128, 128, 128),
    'buttontext': Color(0, 0, 0),
    'cadetblue': Color(.372549, .619608, .627451),
    'captiontext': Color(255, 255, 255),
    'chartreuse': Color(.498039, 1, 0),
    'chocolate': Color(.823529, .411765, .117647),
    'coral': Color(1, .498039, .313725),
    'cornflowerblue': Color(.392157, .584314, .929412),
    'cornsilk': Color(1, .972549, .862745),
    'crimson': Color(.862745, .078431, .235294),
    'cyan': Color(0, 1, 1),
    'darkblue': Color(0, 0, .545098),
    'darkcyan': Color(0, .545098, .545098),
    'darkgoldenrod': Color(.721569, .52549, .043137),
    'darkgray': Color(.662745, .662745, .662745),
    'darkgreen': Color(0, .392157, 0),
    'darkgrey': Color(.662745, .662745, .662745),
    'darkkhaki': Color(.741176, .717647, .419608),
    'darkmagenta': Color(.545098, 0, .545098),
    'darkolivegreen': Color(.333333, .419608, .184314),
    'darkorange': Color(1, .54902, 0),
    'darkorchid': Color(.6, .196078, .8),
    'darkred': Color(.545098, 0, 0),
    'darksalmon': Color(.913725, .588235, .478431),
    'darkseagreen': Color(.560784, .737255, .560784),
    'darkslateblue': Color(.282353, .239216, .545098),
    'darkslategray': Color(.184314, .309804, .309804),
    'darkslategrey': Color(.184314, .309804, .309804),
    'darkturquoise': Color(0, .807843, .819608),
    'darkviolet': Color(.580392, 0, .827451),
    'deeppink': Color(1, .078431, .576471),
    'deepskyblue': Color(0, .74902, 1),
    'dimgray': Color(.411765, .411765, .411765),
    'dimgrey': Color(.411765, .411765, .411765),
    'dodgerblue': Color(.117647, .564706, 1),
    'firebrick': Color(.698039, .133333, .133333),
    'floralwhite': Color(1, .980392, .941176),
    'forestgreen': Color(.133333, .545098, .133333),
    'fuchsia': Color(1, 0, 1),
    'gainsboro': Color(.862745, .862745, .862745),
    'ghostwhite': Color(.972549, .972549, 1),
    'gold': Color(1, .843137, 0),
    'goldenrod': Color(.854902, .647059, .12549),
    'gray': Color(.501961, .501961, .501961),
    'graytext': Color(128, 128, 128),
    'green': Color(0, .501961, 0),
    'greenyellow': Color(.678431, 1, .184314),
    'grey': Color(.501961, .501961, .501961),
    'highlight': Color(10, 36, 106),
    'highlighttext': Color(255, 255, 255),
    'honeydew': Color(.941176, 1, .941176),
    'hotpink': Color(1, .411765, .705882),
    'inactiveborder': Color(212, 208, 200),
    'inactivecaption': Color(128, 128, 128),
    'inactivecaptiontext': Color(212, 208, 200),
    'indianred': Color(.803922, .360784, .360784),
    'indigo': Color(.294118, 0, .509804),
    'infobackground': Color(255, 255, 225),
    'infotext': Color(0, 0, 0),
    'ivory': Color(1, 1, .941176),
    'khaki': Color(.941176, .901961, .54902),
    'lavender': Color(.901961, .901961, .980392),
    'lavenderblush': Color(1, .941176, .960784),
    'lawngreen': Color(.486275, .988235, 0),
    'lemonchiffon': Color(1, .980392, .803922),
    'lightblue': Color(.678431, .847059, .901961),
    'lightcoral': Color(.941176, .501961, .501961),
    'lightcyan': Color(.878431, 1, 1),
    'lightgoldenrodyellow': Color(.980392, .980392, .823529),
    'lightgray': Color(.827451, .827451, .827451),
    'lightgreen': Color(.564706, .933333, .564706),
    'lightgrey': Color(.827451, .827451, .827451),
    'lightpink': Color(1, .713725, .756863),
    'lightsalmon': Color(1, .627451, .478431),
    'lightseagreen': Color(.12549, .698039, .666667),
    'lightskyblue': Color(.529412, .807843, .980392),
    'lightslategray': Color(.466667, .533333, .6),
    'lightslategrey': Color(.466667, .533333, .6),
    'lightsteelblue': Color(.690196, .768627, .870588),
    'lightyellow': Color(1, 1, .878431),
    'lime': Color(0, 1, 0),
    'limegreen': Color(.196078, .803922, .196078),
    'linen': Color(.980392, .941176, .901961),
    'magenta': Color(1, 0, 1),
    'maroon': Color(.501961, 0, 0),
    'mediumaquamarine': Color(.4, .803922, .666667),
    'mediumblue': Color(0, 0, .803922),
    'mediumorchid': Color(.729412, .333333, .827451),
    'mediumpurple': Color(.576471, .439216, .858824),
    'mediumseagreen': Color(.235294, .701961, .443137),
    'mediumslateblue': Color(.482353, .407843, .933333),
    'mediumspringgreen': Color(0, .980392, .603922),
    'mediumturquoise': Color(.282353, .819608, .8),
    'mediumvioletred': Color(.780392, .082353, .521569),
    'menu': Color(212, 208, 200),
    'menutext': Color(0, 0, 0),
    'midnightblue': Color(.098039, .098039, .439216),
    'mintcream': Color(.960784, 1, .980392),
    'mistyrose': Color(1, .894118, .882353),
    'moccasin': Color(1, .894118, .709804),
    'navajowhite': Color(1, .870588, .678431),
    'navy': Color(0, 0, .501961),
    'oldlace': Color(.992157, .960784, .901961),
    'olive': Color(.501961, .501961, 0),
    'olivedrab': Color(.419608, .556863, .137255),
    'orange': Color(1, .647059, 0),
    'orangered': Color(1, .270588, 0),
    'orchid': Color(.854902, .439216, .839216),
    'palegoldenrod': Color(.933333, .909804, .666667),
    'palegreen': Color(.596078, .984314, .596078),
    'paleturquoise': Color(.686275, .933333, .933333),
    'palevioletred': Color(.858824, .439216, .576471),
    'papayawhip': Color(1, .937255, .835294),
    'peachpuff': Color(1, .854902, .72549),
    'peru': Color(.803922, .521569, .247059),
    'pink': Color(1, .752941, .796078),
    'plum': Color(.866667, .627451, .866667),
    'powderblue': Color(.690196, .878431, .901961),
    'purple': Color(.501961, 0, .501961),
    'red': Color(1, 0, 0),
    'rosybrown': Color(.737255, .560784, .560784),
    'royalblue': Color(.254902, .411765, .882353),
    'saddlebrown': Color(.545098, .270588, .07451),
    'salmon': Color(.980392, .501961, .447059),
    'sandybrown': Color(.956863, .643137, .376471),
    'scrollbar': Color(212, 208, 200),
    'seagreen': Color(.180392, .545098, .341176),
    'seashell': Color(1, .960784, .933333),
    'sienna': Color(.627451, .321569, .176471),
    'silver': Color(.752941, .752941, .752941),
    'skyblue': Color(.529412, .807843, .921569),
    'slateblue': Color(.415686, .352941, .803922),
    'slategray': Color(.439216, .501961, .564706),
    'slategrey': Color(.439216, .501961, .564706),
    'snow': Color(1, .980392, .980392),
    'springgreen': Color(0, 1, .498039),
    'steelblue': Color(.27451, .509804, .705882),
    'tan': Color(.823529, .705882, .54902),
    'teal': Color(0, .501961, .501961),
    'thistle': Color(.847059, .74902, .847059),
    'threeddarkshadow': Color(64, 64, 64),
    'threedface': Color(212, 208, 200),
    'threedhighlight': Color(255, 255, 255),
    'threedlightshadow': Color(212, 208, 200),
    'threedshadow': Color(128, 128, 128),
    'tomato': Color(1, .388235, .278431),
    'turquoise': Color(.25098, .878431, .815686),
    'violet': Color(.933333, .509804, .933333),
    'wheat': Color(.960784, .870588, .701961),
    'white': Color(1, 1, 1),
    'whitesmoke': Color(.960784, .960784, .960784),
    'window': Color(255, 255, 255),
    'windowframe': Color(0, 0, 0),
    'windowtext': Color(0, 0, 0),
    'yellow': Color(1, 1, 0),
    'yellowgreen': Color(.603922, .803922, .196078)
}


def get_default_asian_font():
    lower_font_list = []
    upper_font_list = []

    font_dict = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
    fonts = font_dict.keys()

    for font in fonts:
        upper_font_list.append(font)
        lower_font_list.append(font.lower())
    default_asian_font = {lower_font_list[i]: upper_font_list[i] for i in range(len(lower_font_list))}

    return default_asian_font


def set_asian_fonts(fontname):
    font_dict = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
    fonts = font_dict.keys()
    if fontname in fonts:
        pdfmetrics.registerFont(UnicodeCIDFont(fontname))


def detect_language(name):
    asian_language_list = xhtml2pdf.default.DEFAULT_LANGUAGE_LIST
    if name in asian_language_list:
        return name


def arabic_format(text, language):
    # Note: right now all of the languages are treated the same way.
    # But maybe in the future we have to for example implement something
    # for "hebrew" that isn't used in "arabic"
    if detect_language(language) in ('arabic', 'hebrew', 'persian', 'urdu', 'pashto', 'sindhi'):
        ar = arabic_reshaper.reshape(text)
        return get_display(ar)
    else:
        return None


def frag_text_language_check(context, frag_text):
    if hasattr(context, 'language'):
        language = context.__getattribute__('language')
        detect_language_result = arabic_format(frag_text, language)
        if detect_language_result:
            return detect_language_result
