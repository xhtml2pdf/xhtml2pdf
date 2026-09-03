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

import contextlib
import logging
import re
from copy import copy
from io import BytesIO
from typing import Any, ClassVar

import arabic_reshaper
import reportlab.pdfbase._cidfontdata
from bidi import get_display
from reportlab.lib.colors import Color, toColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.rl_config import register_reset

import xhtml2pdf.default

log = logging.getLogger(__name__)

rgb_re = re.compile(
    r"^.*?rgb[a]?[(]([0-9]+).*?([0-9]+).*?([0-9]+)(?:.*?(?:[01]\.(?:[0-9]+)))?[)].*?[ ]*$"
)

#: The number in one argument of a colour function. A percentage argument
#: reaches CSSTerminalFunction as the stringified tuple "('50', '%')", because
#: that class turns any argument which is not already a str into one, so the
#: number is found rather than parsed off a known shape.
color_arg_re = re.compile(r"-?\d*\.?\d+")

# =========================================================================
# Memoize decorator
# =========================================================================


class Memoized:
    """
    A kwargs-aware memoizer, better than the one in python :).

    Don't pass in too large kwargs, since this turns them into a tuple of
    tuples. Also, avoid mutable types (as usual for memoizers)

    What this does is to create a dictionary of {(*parameters):return value},
    and uses it as a cache for subsequent calls to the same method.
    It is especially useful for functions that don't rely on external variables
    and that are called often. It's a perfect match for our getSize etc...

    The cache is bounded and evicts in FIFO order. Keys are derived from CSS
    values taken straight out of the rendered document, so an unbounded cache
    grows without limit in a long-running server process.

    ``functools.lru_cache`` is not a substitute here: the ``TypeError`` fallback
    below (unhashable arguments, e.g. a list ``pagesize``) is load-bearing, and
    ``lru_cache`` raises instead.
    """

    #: Maximum number of memoized results kept per decorated function.
    DEFAULT_MAXSIZE: int = 1000

    #: Every instance, so the whole memoization layer can be dropped at once.
    _instances: ClassVar[list[Memoized]] = []

    def __init__(self, func, maxsize: int | None = None) -> None:
        self.cache: dict = {}
        self.maxsize: int = self.DEFAULT_MAXSIZE if maxsize is None else maxsize
        self.func = func
        self.__doc__ = self.func.__doc__  # To avoid great confusion
        self.__name__ = self.func.__name__  # This also avoids great confusion
        Memoized._instances.append(self)
        # NB: must be a bound method of a real object -- reportlab >= 4.5.1
        # wraps the callback in a WeakMethod, which rejects builtins such as
        # dict.clear. Older versions store a plain weakref, which would expire
        # immediately on a temporary bound method, so keep a strong reference.
        self._reset_callback = self.clear
        register_reset(self._reset_callback)

    def clear(self) -> None:
        self.cache.clear()

    def __call__(self, *args, **kwargs):
        # Make sure the following line is not actually slower than what you're
        # trying to memoize
        args_plus = tuple(kwargs.items())
        key = (args, args_plus)
        try:
            if key not in self.cache:
                res = self.func(*args, **kwargs)
                if self.maxsize and len(self.cache) >= self.maxsize:
                    # dicts are insertion-ordered, so this is FIFO eviction
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = res
            return self.cache[key]
        except TypeError:
            # happens if any of the parameters is a list
            return self.func(*args, **kwargs)


def reset_caches() -> None:
    """Drop every memoized result. Called at the end of each render."""
    for memoized in Memoized._instances:
        memoized.clear()


def toList(value: Any, *, cast_tuple: bool = True) -> list:
    cls: tuple[type, ...] = (list, tuple) if cast_tuple else (list,)
    return list(value) if isinstance(value, cls) else [value]  # type: ignore[call-overload]


def transform_attrs(obj, keys, container, func, extras=None):
    """
    Allows to apply one function to set of keys checking if key is in container,
    also transform ccs key to report lab keys.

    extras = Are extra params for func, it will be call like func(*[param1, param2])

    obj = frag
    keys = [(reportlab, css), ... ]
    container = cssAttr
    """
    cpextras = extras

    for reportlab_key, css in keys:
        extras = cpextras
        if extras is None:
            extras = []
        elif not isinstance(extras, list):
            extras = [extras]
        if css in container:
            extras.insert(0, container[css])
            setattr(obj, reportlab_key, func(*extras))


def copy_attrs(obj1, obj2, attrs):
    """
    Allows copy a list of attributes from object2 to object1.
    Useful for copy ccs attributes to fragment.
    """
    for attr in attrs:
        value = getattr(obj2, attr) if hasattr(obj2, attr) else None
        if value is None and isinstance(obj2, dict) and attr in obj2:
            value = obj2[attr]
        setattr(obj1, attr, value)


def set_value(obj, attrs, value, *, do_copy=False):
    """Allows set the same value to a list of attributes."""
    for attr in attrs:
        if do_copy:
            value = copy(value)
        setattr(obj, attr, value)


def _clamp01(number: float) -> float:
    """Keep a colour channel inside the 0..1 the PDF format allows."""
    return min(max(number, 0.0), 1.0)


def _colorComponent(param, maximum: float) -> float:
    """One argument of rgb()/rgba(), as a fraction of its maximum."""
    text = str(param)
    match = color_arg_re.search(text)
    if match is None:
        msg = f"not a colour component: {text!r}"
        raise ValueError(msg)
    number = float(match.group())
    return number / 100.0 if "%" in text else number / maximum


def _rgbFunctionColor(function, default):
    """
    Read an rgb()/rgba() the parser handed over as a function object.

    Going through str() and a regular expression, as this used to, reads the
    channels off the object's *repr*: for `rgba(10, 200, 10, 1)` that is
    "<css function: rgba(10, 200, 10, 1)>", and the pattern -- written for
    `rgb(` -- matched from the "a" onwards and took the alpha as the blue
    channel. The arguments are right there on the object, so they are read
    from there.
    """
    channels, rest = function.params[:3], function.params[3:]
    try:
        red, green, blue = (_colorComponent(arg, 255.0) for arg in channels)
        alpha = _colorComponent(rest[0], 1.0) if rest else 1.0
    except (ValueError, IndexError):
        log.warning("Cannot read the colour %r", function)
        return default
    return Color(_clamp01(red), _clamp01(green), _clamp01(blue), alpha=_clamp01(alpha))


@Memoized
def getColor(value, default=None):
    """
    Convert to color value.
    This returns a Color object instance from a text bit.
    Mitigation for ReDoS attack applied by limiting input length and validating input.
    """
    original = value
    if value is None:
        return None
    if isinstance(value, Color):
        return value

    # Imported here and not at module scope: xhtml2pdf.w3c.css reaches this
    # module through cssParser, so importing it from the top would be circular.
    from xhtml2pdf.w3c.css import CSSTerminalFunction

    if isinstance(value, CSSTerminalFunction) and value.name.lower() in {"rgb", "rgba"}:
        return _rgbFunctionColor(value, default)

    value = str(value).strip().lower()

    # Limit the length of the value to prevent excessive input causing ReDoS
    if len(value) > 100:  # Set a reasonable length limit to avoid extreme inputs
        return default

    if value in {"transparent", "none"}:
        return default
    if value in COLOR_BY_NAME:
        return COLOR_BY_NAME[value]
    if value.startswith("#") and len(value) == 4:
        value = "#" + value[1] + value[1] + value[2] + value[2] + value[3] + value[3]
    elif rgb_re.match(value):
        # Use match instead of search to ensure proper regex usage and limit to valid patterns
        try:
            r, g, b = (int(x) for x in rgb_re.match(value).groups())
            value = f"#{r:02x}{g:02x}{b:02x}"
        except ValueError:
            pass
    else:
        # Shrug
        pass

    try:
        return toColor(value, default)  # Calling the reportlab function
    except ValueError:
        # reportlab raises rather than handing back the default it was given.
        # A colour nobody can read is worth a line in the log; it is not worth
        # abandoning the document.
        log.warning("Cannot read the colour %r, using %r", original, default)
        return default


def apply_text_transform(text: str, transform) -> str:
    """
    CSS 2.1 16.5 text-transform.

    capitalize is applied per word rather than per typographic word boundary,
    and a word split across two fragments -- by a nested <b>, say -- has each
    half capitalised. Neither matters for the usual case of a whole phrase.
    """
    transform = str(transform).lower()
    if transform == "uppercase":
        return text.upper()
    if transform == "lowercase":
        return text.lower()
    if transform == "capitalize":
        return re.sub(r"\b[a-z]", lambda m: m.group(0).upper(), text)
    return text


def getBorderStyle(value, default=None):
    if value and (str(value).lower() not in {"none", "hidden"}):
        return value
    return default


def getBorderWidth(style, width) -> float:
    """
    The width a border actually occupies in the box.

    CSS 2.1 8.5.3: `border-style: none` forces the computed border width to
    zero whatever border-width says. It is not only that nothing is drawn --
    the box is that much smaller. DEFAULT_CSS gives every element
    `border: 1px none`, so treating the declared width as occupied added 2pt
    of height and 2pt of width to every block on the page.
    """
    if not width or not getBorderStyle(style):
        return 0
    return width


#: On/off lengths of a dashed or dotted border, as multiples of its width.
#: Measured off Chromium through testrender/browsercompare.py rather than
#: guessed: a 5px dashed border rasterises to a 15px dash and an 8px gap at
#: 150dpi, and a 2px dotted one to a 3px dot and a 4px gap.
BORDER_DASH_PATTERNS: dict[str, tuple[float, float]] = {
    "dashed": (2.0, 1.0),
    "dotted": (1.0, 1.0),
}


def _is_double(style: str, width) -> bool:
    """
    Whether a border should be drawn as CSS 2.1's two lines with a gap.

    Below three units there is nothing to divide into three bands, so a
    double border that thin stays a single line, as browsers draw it.
    """
    return style == "double" and isinstance(width, int | float) and width >= 3


def getBorderDash(style, width: float) -> list[float] | None:
    """
    Dash array for a border style, or None when the line is continuous.

    A dash is proportional to the border's width, which is why the pattern
    cannot be a constant: a 1pt dotted border and a 6pt one are the same
    figure at different scales.
    """
    pattern = BORDER_DASH_PATTERNS.get(str(style).lower())
    if not pattern or not isinstance(width, int | float) or not width:
        return None
    return [max(part * width, 0.1) for part in pattern]


def getBorderTableLine(
    style, width: float
) -> tuple[float, str, list[float] | None, None, int, float]:
    """
    Trailing arguments of a ReportLab LINE* table command for a border style.

    Returns (weight, cap, dashes, join, count, space). A table border is not
    stroked by xhtml2pdf but described to ReportLab, so the style has to be
    expressed in those terms: a dash array for dashed and dotted, and for
    double the `count` parallel lines ReportLab can draw, narrowed to a third
    of the declared width and set two thirds apart so the three bands add up
    to the width that was asked for.
    """
    style = str(style).lower()
    if _is_double(style, width):
        band = width / 3.0
        return (band, "squared", None, None, 2, 2 * band)
    return (width, "squared", getBorderDash(style, width), None, 1, 0)


def drawBorderLine(
    canvas, bstyle, width: float, color, x1: float, y1: float, x2: float, y2: float
) -> None:
    """
    Draw one edge of a box, honouring its border-style.

    Every caller used to stroke a plain line whatever the style said, so
    dashed, dotted and double all came out solid. The style is still only
    consulted for the shape of the line: groove, ridge, inset and outset need
    two shades of the declared colour and are drawn solid for now.
    """
    if not width or not getBorderStyle(bstyle) or color is None:
        return

    style = str(bstyle).lower()
    canvas.saveState()
    canvas.setStrokeColor(color)

    # CSS 2.1 8.5.3: double is two solid lines with a gap, and the three
    # together are the declared width. Below 3 units there is nothing to
    # split, so it stays a single line.
    if _is_double(style, width):
        band = width / 3.0
        canvas.setLineWidth(band)
        if y1 == y2:
            canvas.line(x1, y1 - band, x2, y2 - band)
            canvas.line(x1, y1 + band, x2, y2 + band)
        else:
            canvas.line(x1 - band, y1, x2 - band, y2)
            canvas.line(x1 + band, y1, x2 + band, y2)
        canvas.restoreState()
        return

    canvas.setLineWidth(width)
    dash = getBorderDash(style, width)
    if dash:
        canvas.setDash(dash)
    canvas.line(x1, y1, x2, y2)
    canvas.restoreState()


MM: float = cm / 10.0
DPI96: float = 1.0 / 96.0 * inch

ABSOLUTE_SIZE_TABLE: dict[str, float] = {
    "1": 50.0 / 100.0,
    "xx-small": 50.0 / 100.0,
    "x-small": 50.0 / 100.0,
    "2": 75.0 / 100.0,
    "small": 75.0 / 100.0,
    "3": 1.0,
    "medium": 1.0,
    "4": 125.0 / 100.0,
    "large": 125.0 / 100.0,
    "5": 150.0 / 100.0,
    "x-large": 150.0 / 100.0,
    "6": 175.0 / 100.0,
    "xx-large": 175.0 / 100.0,
    "7": 200.0 / 100.0,
    "xxx-large": 200.0 / 100.0,
}

RELATIVE_SIZE_TABLE: dict[str, float] = {
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

MIN_FONT_SIZE: float = 1.0

#: Base for relative lengths in @page and @frame. There is no element in scope
#: at that point to inherit a font size from, so CSS resolves em, ex and % in
#: the page context against the initial font size, which DEFAULT_CSS sets with
#: html { font-size: 10px }.
DEFAULT_FONT_SIZE: float = 10.0 * DPI96


@Memoized
def getSize(
    value: str | float | list | tuple,
    relative=0,
    base: int | None = None,
    default: float = 0.0,
) -> float:
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
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if isinstance(value, tuple | list):
            value = "".join(value)
        value = str(value).strip().lower().replace(",", ".")
        if value.endswith("cm"):
            return float(value[:-2].strip()) * cm
        if value.endswith("mm"):
            return float(value[:-2].strip()) * MM  # 1MM = 0.1cm
        if value.endswith("in"):
            return float(value[:-2].strip()) * inch  # 1pt == 1/72inch
        if value.endswith("pt"):
            return float(value[:-2].strip())
        if value.endswith("pc"):
            return float(value[:-2].strip()) * 12.0  # 1pc == 12pt
        if value.endswith("px"):
            # XXX W3C says, use 96pdi
            # http://www.w3.org/TR/CSS21/syndata.html#length-units
            return float(value[:-2].strip()) * DPI96
        if value in {"none", "0", "0.0", "auto"}:
            return 0.0
        if relative:
            if value.endswith("rem"):  # XXX
                # 1rem = 1 * fontSize
                return float(value[:-3].strip()) * relative
            if value.endswith("em"):  # XXX
                # 1em = 1 * fontSize
                return float(value[:-2].strip()) * relative
            if value.endswith("ex"):  # XXX
                # 1ex = 1/2 fontSize
                return float(value[:-2].strip()) * (relative / 2.0)
            if value.endswith("%"):
                # 1% = (fontSize * 1) / 100
                return (relative * float(value[:-1].strip())) / 100.0
            if value in {"normal", "inherit"}:
                return relative
            if value in RELATIVE_SIZE_TABLE:
                if base:
                    return max(MIN_FONT_SIZE, base * RELATIVE_SIZE_TABLE[value])
                return max(MIN_FONT_SIZE, relative * RELATIVE_SIZE_TABLE[value])
            if value in ABSOLUTE_SIZE_TABLE:
                if base:
                    return max(MIN_FONT_SIZE, base * ABSOLUTE_SIZE_TABLE[value])
                return max(MIN_FONT_SIZE, relative * ABSOLUTE_SIZE_TABLE[value])
            return max(MIN_FONT_SIZE, relative * float(value))
        try:
            value = float(value)
        except ValueError:
            log.warning("getSize: Not a float %r", value)
            return default  # value = 0
        return max(0, value)
    except Exception as exc:
        # One line at warning level, the traceback at debug. A stylesheet with
        # a handful of lengths this function cannot read -- a calc(), say --
        # used to bury the log under a ten-line traceback for each one, which
        # made the warnings that mattered impossible to find.
        log.warning(
            "getSize: cannot read %r, using %r (%s)",
            original,
            default,
            type(exc).__name__,
        )
        log.debug("getSize %r %r", original, relative, exc_info=True)
        return default


@Memoized
def getCoords(x, y, w, h, pagesize):
    """
    As a stupid programmer I like to use the upper left
    corner of the document as the 0,0 coords therefore
    we need to do some fancy calculations.
    """
    # ~ print pagesize
    ax, ay = pagesize
    if x < 0:
        x = ax + x
    if y < 0:
        y = ay + y
    if w is not None and h is not None:
        if w <= 0:
            w = ax - x + w
        if h <= 0:
            h = ay - y + h
        return x, (ay - y - h), w, h
    return x, (ay - y)


@Memoized
def getBox(box, pagesize):
    """
    Parse sizes by corners in the form:
    <X-Left> <Y-Upper> <Width> <Height>
    The last to values with negative values are interpreted as offsets form
    the right and lower border.
    """
    box = str(box).split()
    if len(box) != 4:
        msg = "box not defined right way"
        raise RuntimeError(msg)
    x, y, w, h = (getSize(pos) for pos in box)
    return getCoords(x, y, w, h, pagesize)


#: Keywords background-position accepts, as a fraction of the free space.
BACKGROUND_POSITION_KEYWORDS: dict[str, float] = {
    "left": 0.0,
    "top": 0.0,
    "center": 0.5,
    "middle": 0.5,
    "right": 1.0,
    "bottom": 1.0,
}


def getBackgroundOffset(value, free: float, font_size: float) -> float:
    """
    One axis of background-position, in points from the box's near edge.

    CSS 2.1 14.2.1: a percentage places the same point of the image against
    the same point of the box, so 100% is not "one box away" but "flush with
    the far edge" -- which is why it is a fraction of the space left over
    rather than of the box.
    """
    text = str(value).strip().lower()
    if text in BACKGROUND_POSITION_KEYWORDS:
        return free * BACKGROUND_POSITION_KEYWORDS[text]
    if text.endswith("%"):
        try:
            return free * float(text[:-1]) / 100.0
        except ValueError:
            return 0.0
    return getSize(text, font_size)


#: ImageReaders, keyed by the file they were built from. A background is
#: painted once per paragraph and a tiled one is drawn many times over, so
#: decoding the file each time would be paid on every page.
_background_image_readers: dict[str, object] = {}


def getBackgroundImageReader(file_object):
    """An ImageReader for a background image file, or None if unusable."""
    if file_object is None or file_object.notFound():
        return None

    key = str(file_object.uri)
    if key in _background_image_readers:
        return _background_image_readers[key]

    from reportlab.lib.utils import ImageReader

    try:
        data = file_object.getData()
        reader = ImageReader(BytesIO(data)) if data else None
    except Exception:
        log.warning("Could not read background image %r", key, exc_info=True)
        reader = None

    _background_image_readers[key] = reader
    return reader


def getBackgroundImageSize(reader) -> tuple[float, float]:
    """The image's natural size in points, reading its pixels at 96dpi."""
    try:
        width, height = reader.getSize()
    except Exception:
        return (0.0, 0.0)
    return (width * DPI96, height * DPI96)


def drawBackgroundImage(
    canvas,
    reader,
    x: float,
    y: float,
    width: float,
    height: float,
    natural: tuple[float, float],
    repeat: str = "repeat",
    position: str = "0% 0%",
    font_size: float = DEFAULT_FONT_SIZE,
) -> None:
    """
    Paint a CSS background image into a box, clipped to it.

    Only what CSS 2.1 14.2 describes: the image at its natural size, placed by
    background-position and tiled along whichever axes background-repeat
    allows. No background-size, so nothing is ever scaled.
    """
    image_width, image_height = natural
    if image_width <= 0 or image_height <= 0:
        return

    repeat = str(repeat).strip().lower()
    tile_x = repeat in {"repeat", "repeat-x"}
    tile_y = repeat in {"repeat", "repeat-y"}

    parts = str(position).strip().lower().split()
    if not parts:
        parts = ["0%"]
    if len(parts) == 1:
        # CSS 2.1: a single value sets the horizontal position and centres
        # the other axis.
        parts = [parts[0], "center"]

    offset_x = getBackgroundOffset(parts[0], width - image_width, font_size)
    # The PDF origin is the bottom-left corner and CSS measures from the top,
    # so the vertical offset is taken from the top edge and turned around.
    offset_y = getBackgroundOffset(parts[1], height - image_height, font_size)

    start_x = x + offset_x
    start_y = y + height - image_height - offset_y

    # A tiled axis has to start left of, or above, the box so the run of tiles
    # covers it from the edge rather than from the placed image.
    if tile_x:
        while start_x > x:
            start_x -= image_width
    if tile_y:
        while start_y + image_height < y + height:
            start_y += image_height

    canvas.saveState()
    path = canvas.beginPath()
    path.rect(x, y, width, height)
    canvas.clipPath(path, stroke=0, fill=0)

    tile_y_position = start_y
    while True:
        tile_x_position = start_x
        while True:
            canvas.drawImage(
                reader,
                tile_x_position,
                tile_y_position,
                image_width,
                image_height,
                mask="auto",
            )
            if not tile_x:
                break
            tile_x_position += image_width
            if tile_x_position >= x + width:
                break
        if not tile_y:
            break
        tile_y_position -= image_height
        if tile_y_position + image_height <= y:
            break

    canvas.restoreState()


def getFrameDimensions(
    data, page_width: float, page_height: float, font_size: float = DEFAULT_FONT_SIZE
) -> tuple[float, float, float, float]:
    """
    Calculate dimensions of a frame.

    Returns left, top, width and height of the frame in points.

    font_size is the base for relative lengths. Without it `@page { margin:
    2em }` resolved to nothing at all: getSize returns its default for a
    relative unit when it is given no base, so the margin silently became 0.
    """

    def size(value, percent_of: float) -> float:
        """
        Resolve one length of the page box.

        A percentage here is a fraction of the page, per CSS 2.1 10.2 and
        10.5: the page box is the containing block. getSize would read it
        against the font size instead, which is the right answer for a font
        size and the wrong one for geometry.
        """
        if isinstance(value, list | tuple):
            value = "".join(value)
        if isinstance(value, str) and value.strip().endswith("%"):
            try:
                return float(value.strip()[:-1]) * percent_of / 100.0
            except ValueError:
                log.warning("Not a percentage: %r", value)
                return 0.0
        return getSize(value, font_size)

    def horizontal(value) -> float:
        return size(value, page_width)

    def vertical(value) -> float:
        return size(value, page_height)

    box = data.get("-pdf-frame-box", [])
    if len(box) == 4:
        # left, top, width, height
        return (
            horizontal(box[0]),
            vertical(box[1]),
            horizontal(box[2]),
            vertical(box[3]),
        )
    # Margins are folded in before the declared size is honoured, not after.
    # The frame is derived from the four edge offsets below, so a size has to
    # be turned into the offset it implies; doing that first and then adding
    # the margin would push the opposite edge and leave a frame that is
    # margin-narrower than what was asked for.
    top = vertical(data.get("top", 0)) + vertical(data.get("margin-top", 0))
    left = horizontal(data.get("left", 0)) + horizontal(data.get("margin-left", 0))
    bottom = vertical(data.get("bottom", 0)) + vertical(data.get("margin-bottom", 0))
    right = horizontal(data.get("right", 0)) + horizontal(data.get("margin-right", 0))

    # A declared height fixes one edge relative to the other. Which edge moves
    # depends on which one was given: with `bottom` the frame grows upwards,
    # otherwise it grows down from `top`, whose default of 0 is what makes
    # `@page { height: 6cm }` mean a 6cm area at the top of the page rather
    # than -- as it did before -- the whole page.
    if "height" in data:
        height = vertical(data["height"])
        if "bottom" in data and "top" not in data:
            top = page_height - (bottom + height)
        else:
            bottom = page_height - (top + height)
    if "width" in data:
        width = horizontal(data["width"])
        if "right" in data and "left" not in data:
            left = page_width - (right + width)
        else:
            right = page_width - (left + width)

    width = page_width - (left + right)
    height = page_height - (top + bottom)
    return left, top, width, height


@Memoized
def getPos(position, pagesize):
    """Pair of coordinates."""
    position = str(position).split()
    if len(position) != 2:
        msg = "position not defined right way"
        raise RuntimeError(msg)
    x, y = (getSize(pos) for pos in position)
    return getCoords(x, y, None, None, pagesize)


def getBool(s):
    """Is it a boolean?."""
    return str(s).lower() in {"y", "yes", "1", "true"}


def getFloat(s):
    with contextlib.suppress(Exception):
        return float(s)


#: The modes reportlab's KeepInFrame understands. "shrink" is the fallback
#: everywhere xhtml2pdf reads one, because keeping the content is the least
#: surprising answer to content that is a little too big for its box.
KEEP_IN_FRAME_MODES: frozenset[str] = frozenset(
    {"shrink", "error", "overflow", "truncate"}
)


def getKeepInFrameMode(value, default: str = "shrink") -> str:
    """
    Read a -pdf-keep-in-frame-mode declaration.

    Anything reportlab would not recognise falls back to ``default`` rather
    than reaching KeepInFrame, which raises on an unknown mode.
    """
    mode = str(value).strip().lower()
    return mode if mode in KEEP_IN_FRAME_MODES else default


ALIGNMENTS = {
    "left": TA_LEFT,
    "center": TA_CENTER,
    "middle": TA_CENTER,
    "right": TA_RIGHT,
    "justify": TA_JUSTIFY,
}


def getAlign(value, default=TA_LEFT):
    return ALIGNMENTS.get(str(value).lower(), default)


_rx_datauri = re.compile(
    r"^data:(?P<mime>[a-z]+/[a-z]+);base64,(?P<data>.*)$", re.MULTILINE | re.DOTALL
)

COLOR_BY_NAME = {
    "activeborder": Color(212, 208, 200),
    "activecaption": Color(10, 36, 106),
    "aliceblue": Color(0.941176, 0.972549, 1),
    "antiquewhite": Color(0.980392, 0.921569, 0.843137),
    "appworkspace": Color(128, 128, 128),
    "aqua": Color(0, 1, 1),
    "aquamarine": Color(0.498039, 1, 0.831373),
    "azure": Color(0.941176, 1, 1),
    "background": Color(58, 110, 165),
    "beige": Color(0.960784, 0.960784, 0.862745),
    "bisque": Color(1, 0.894118, 0.768627),
    "black": Color(0, 0, 0),
    "blanchedalmond": Color(1, 0.921569, 0.803922),
    "blue": Color(0, 0, 1),
    "blueviolet": Color(0.541176, 0.168627, 0.886275),
    "brown": Color(0.647059, 0.164706, 0.164706),
    "burlywood": Color(0.870588, 0.721569, 0.529412),
    "buttonface": Color(212, 208, 200),
    "buttonhighlight": Color(255, 255, 255),
    "buttonshadow": Color(128, 128, 128),
    "buttontext": Color(0, 0, 0),
    "cadetblue": Color(0.372549, 0.619608, 0.627451),
    "captiontext": Color(255, 255, 255),
    "chartreuse": Color(0.498039, 1, 0),
    "chocolate": Color(0.823529, 0.411765, 0.117647),
    "coral": Color(1, 0.498039, 0.313725),
    "cornflowerblue": Color(0.392157, 0.584314, 0.929412),
    "cornsilk": Color(1, 0.972549, 0.862745),
    "crimson": Color(0.862745, 0.078431, 0.235294),
    "cyan": Color(0, 1, 1),
    "darkblue": Color(0, 0, 0.545098),
    "darkcyan": Color(0, 0.545098, 0.545098),
    "darkgoldenrod": Color(0.721569, 0.52549, 0.043137),
    "darkgray": Color(0.662745, 0.662745, 0.662745),
    "darkgreen": Color(0, 0.392157, 0),
    "darkgrey": Color(0.662745, 0.662745, 0.662745),
    "darkkhaki": Color(0.741176, 0.717647, 0.419608),
    "darkmagenta": Color(0.545098, 0, 0.545098),
    "darkolivegreen": Color(0.333333, 0.419608, 0.184314),
    "darkorange": Color(1, 0.54902, 0),
    "darkorchid": Color(0.6, 0.196078, 0.8),
    "darkred": Color(0.545098, 0, 0),
    "darksalmon": Color(0.913725, 0.588235, 0.478431),
    "darkseagreen": Color(0.560784, 0.737255, 0.560784),
    "darkslateblue": Color(0.282353, 0.239216, 0.545098),
    "darkslategray": Color(0.184314, 0.309804, 0.309804),
    "darkslategrey": Color(0.184314, 0.309804, 0.309804),
    "darkturquoise": Color(0, 0.807843, 0.819608),
    "darkviolet": Color(0.580392, 0, 0.827451),
    "deeppink": Color(1, 0.078431, 0.576471),
    "deepskyblue": Color(0, 0.74902, 1),
    "dimgray": Color(0.411765, 0.411765, 0.411765),
    "dimgrey": Color(0.411765, 0.411765, 0.411765),
    "dodgerblue": Color(0.117647, 0.564706, 1),
    "firebrick": Color(0.698039, 0.133333, 0.133333),
    "floralwhite": Color(1, 0.980392, 0.941176),
    "forestgreen": Color(0.133333, 0.545098, 0.133333),
    "fuchsia": Color(1, 0, 1),
    "gainsboro": Color(0.862745, 0.862745, 0.862745),
    "ghostwhite": Color(0.972549, 0.972549, 1),
    "gold": Color(1, 0.843137, 0),
    "goldenrod": Color(0.854902, 0.647059, 0.12549),
    "gray": Color(0.501961, 0.501961, 0.501961),
    "graytext": Color(128, 128, 128),
    "green": Color(0, 0.501961, 0),
    "greenyellow": Color(0.678431, 1, 0.184314),
    "grey": Color(0.501961, 0.501961, 0.501961),
    "highlight": Color(10, 36, 106),
    "highlighttext": Color(255, 255, 255),
    "honeydew": Color(0.941176, 1, 0.941176),
    "hotpink": Color(1, 0.411765, 0.705882),
    "inactiveborder": Color(212, 208, 200),
    "inactivecaption": Color(128, 128, 128),
    "inactivecaptiontext": Color(212, 208, 200),
    "indianred": Color(0.803922, 0.360784, 0.360784),
    "indigo": Color(0.294118, 0, 0.509804),
    "infobackground": Color(255, 255, 225),
    "infotext": Color(0, 0, 0),
    "ivory": Color(1, 1, 0.941176),
    "khaki": Color(0.941176, 0.901961, 0.54902),
    "lavender": Color(0.901961, 0.901961, 0.980392),
    "lavenderblush": Color(1, 0.941176, 0.960784),
    "lawngreen": Color(0.486275, 0.988235, 0),
    "lemonchiffon": Color(1, 0.980392, 0.803922),
    "lightblue": Color(0.678431, 0.847059, 0.901961),
    "lightcoral": Color(0.941176, 0.501961, 0.501961),
    "lightcyan": Color(0.878431, 1, 1),
    "lightgoldenrodyellow": Color(0.980392, 0.980392, 0.823529),
    "lightgray": Color(0.827451, 0.827451, 0.827451),
    "lightgreen": Color(0.564706, 0.933333, 0.564706),
    "lightgrey": Color(0.827451, 0.827451, 0.827451),
    "lightpink": Color(1, 0.713725, 0.756863),
    "lightsalmon": Color(1, 0.627451, 0.478431),
    "lightseagreen": Color(0.12549, 0.698039, 0.666667),
    "lightskyblue": Color(0.529412, 0.807843, 0.980392),
    "lightslategray": Color(0.466667, 0.533333, 0.6),
    "lightslategrey": Color(0.466667, 0.533333, 0.6),
    "lightsteelblue": Color(0.690196, 0.768627, 0.870588),
    "lightyellow": Color(1, 1, 0.878431),
    "lime": Color(0, 1, 0),
    "limegreen": Color(0.196078, 0.803922, 0.196078),
    "linen": Color(0.980392, 0.941176, 0.901961),
    "magenta": Color(1, 0, 1),
    "maroon": Color(0.501961, 0, 0),
    "mediumaquamarine": Color(0.4, 0.803922, 0.666667),
    "mediumblue": Color(0, 0, 0.803922),
    "mediumorchid": Color(0.729412, 0.333333, 0.827451),
    "mediumpurple": Color(0.576471, 0.439216, 0.858824),
    "mediumseagreen": Color(0.235294, 0.701961, 0.443137),
    "mediumslateblue": Color(0.482353, 0.407843, 0.933333),
    "mediumspringgreen": Color(0, 0.980392, 0.603922),
    "mediumturquoise": Color(0.282353, 0.819608, 0.8),
    "mediumvioletred": Color(0.780392, 0.082353, 0.521569),
    "menu": Color(212, 208, 200),
    "menutext": Color(0, 0, 0),
    "midnightblue": Color(0.098039, 0.098039, 0.439216),
    "mintcream": Color(0.960784, 1, 0.980392),
    "mistyrose": Color(1, 0.894118, 0.882353),
    "moccasin": Color(1, 0.894118, 0.709804),
    "navajowhite": Color(1, 0.870588, 0.678431),
    "navy": Color(0, 0, 0.501961),
    "oldlace": Color(0.992157, 0.960784, 0.901961),
    "olive": Color(0.501961, 0.501961, 0),
    "olivedrab": Color(0.419608, 0.556863, 0.137255),
    "orange": Color(1, 0.647059, 0),
    "orangered": Color(1, 0.270588, 0),
    "orchid": Color(0.854902, 0.439216, 0.839216),
    "palegoldenrod": Color(0.933333, 0.909804, 0.666667),
    "palegreen": Color(0.596078, 0.984314, 0.596078),
    "paleturquoise": Color(0.686275, 0.933333, 0.933333),
    "palevioletred": Color(0.858824, 0.439216, 0.576471),
    "papayawhip": Color(1, 0.937255, 0.835294),
    "peachpuff": Color(1, 0.854902, 0.72549),
    "peru": Color(0.803922, 0.521569, 0.247059),
    "pink": Color(1, 0.752941, 0.796078),
    "plum": Color(0.866667, 0.627451, 0.866667),
    "powderblue": Color(0.690196, 0.878431, 0.901961),
    "purple": Color(0.501961, 0, 0.501961),
    "red": Color(1, 0, 0),
    "rosybrown": Color(0.737255, 0.560784, 0.560784),
    "royalblue": Color(0.254902, 0.411765, 0.882353),
    "saddlebrown": Color(0.545098, 0.270588, 0.07451),
    "salmon": Color(0.980392, 0.501961, 0.447059),
    "sandybrown": Color(0.956863, 0.643137, 0.376471),
    "scrollbar": Color(212, 208, 200),
    "seagreen": Color(0.180392, 0.545098, 0.341176),
    "seashell": Color(1, 0.960784, 0.933333),
    "sienna": Color(0.627451, 0.321569, 0.176471),
    "silver": Color(0.752941, 0.752941, 0.752941),
    "skyblue": Color(0.529412, 0.807843, 0.921569),
    "slateblue": Color(0.415686, 0.352941, 0.803922),
    "slategray": Color(0.439216, 0.501961, 0.564706),
    "slategrey": Color(0.439216, 0.501961, 0.564706),
    "snow": Color(1, 0.980392, 0.980392),
    "springgreen": Color(0, 1, 0.498039),
    "steelblue": Color(0.27451, 0.509804, 0.705882),
    "tan": Color(0.823529, 0.705882, 0.54902),
    "teal": Color(0, 0.501961, 0.501961),
    "thistle": Color(0.847059, 0.74902, 0.847059),
    "threeddarkshadow": Color(64, 64, 64),
    "threedface": Color(212, 208, 200),
    "threedhighlight": Color(255, 255, 255),
    "threedlightshadow": Color(212, 208, 200),
    "threedshadow": Color(128, 128, 128),
    "tomato": Color(1, 0.388235, 0.278431),
    "turquoise": Color(0.25098, 0.878431, 0.815686),
    "violet": Color(0.933333, 0.509804, 0.933333),
    "wheat": Color(0.960784, 0.870588, 0.701961),
    "white": Color(1, 1, 1),
    "whitesmoke": Color(0.960784, 0.960784, 0.960784),
    "window": Color(255, 255, 255),
    "windowframe": Color(0, 0, 0),
    "windowtext": Color(0, 0, 0),
    "yellow": Color(1, 1, 0),
    "yellowgreen": Color(0.603922, 0.803922, 0.196078),
}


def get_default_asian_font():
    lower_font_list = []
    upper_font_list = []

    font_dict = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
    fonts = font_dict.keys()

    for font in fonts:
        upper_font_list.append(font)
        lower_font_list.append(font.lower())
    return {lower_font_list[i]: upper_font_list[i] for i in range(len(lower_font_list))}


def set_asian_fonts(fontname):
    font_dict = copy(reportlab.pdfbase._cidfontdata.defaultUnicodeEncodings)
    fonts = font_dict.keys()
    if fontname in fonts:
        pdfmetrics.registerFont(UnicodeCIDFont(fontname))


def detect_language(name):
    asian_language_list = xhtml2pdf.default.DEFAULT_LANGUAGE_LIST
    if name in asian_language_list:
        return name
    return None


def arabic_format(text, language):
    # Note: right now all of the languages are treated the same way.
    # But maybe in the future we have to for example implement something
    # for "hebrew" that isn't used in "arabic"
    if detect_language(language) in {
        "arabic",
        "hebrew",
        "persian",
        "urdu",
        "pashto",
        "sindhi",
    }:
        ar = arabic_reshaper.reshape(text)
        return get_display(ar)
    return None


def frag_text_language_check(context, frag_text):
    if hasattr(context, "language"):
        language = context.language
        detect_language_result = arabic_format(frag_text, language)
        if detect_language_result:
            return detect_language_result
        return None
    return None


class ImageWarning(Exception):  # noqa: N818
    pass
