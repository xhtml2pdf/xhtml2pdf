"""
OpenType (CFF) and WOFF fonts, made into TrueType for ReportLab.

ReportLab embeds TrueType outlines only: it refuses an OpenType font whose
glyphs are PostScript (CFF) outlines, and it cannot read the WOFF and WOFF2
wrappers at all. fontTools reads all three. The CFF outlines are redrawn as
TrueType quadratic curves, within one font unit of the original (a
thousandth of the em, invisible in print), and the font is handed to
ReportLab as an ordinary TrueType file, which embeds it as a subset.

fontTools is the ``fonts`` extra (``pip install 'xhtml2pdf[fonts]'``), and
WOFF2 also needs brotli, which the extra installs. A TrueType font in an
``.otf`` file needs neither: it goes to ReportLab as it is.
"""

from __future__ import annotations

import hashlib
import io
from collections import OrderedDict

from xhtml2pdf.config.resources import RenderLimitError, check_deadline

#: The sfnt versions ReportLab reads as they are.
TRUETYPE_SIGNATURES: frozenset[bytes] = frozenset({b"\x00\x01\x00\x00", b"true"})

#: The file signatures of the formats this module converts.
CONVERTED_SIGNATURES: frozenset[bytes] = frozenset({b"OTTO", b"wOFF", b"wOF2"})

#: How far, in font units, a converted curve may stray from the original.
MAX_ERROR = 1.0

#: Converted fonts kept for the next document that names the same file.
CACHE_SIZE = 16

#: How many glyphs are converted between two checks of the render budget.
DEADLINE_STEP = 256

_cache: OrderedDict[str, bytes] = OrderedDict()

EXTRA_HINT = "pip install 'xhtml2pdf[fonts]'"


class FontConversionError(ValueError):
    """A font file that cannot be made into TrueType."""


def needs_conversion(data: bytes) -> bool:
    """Whether `data` is a font ReportLab cannot read without conversion."""
    return data[:4] in CONVERTED_SIGNATURES


def to_truetype(data: bytes) -> bytes:
    """Return `data`, an OpenType, WOFF or WOFF2 font, as a TrueType font."""
    if data[:4] in TRUETYPE_SIGNATURES:
        return data
    key = hashlib.sha256(data).hexdigest()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    converted = _convert(data)
    _cache[key] = converted
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return converted


def _convert(data: bytes) -> bytes:
    try:
        from fontTools.ttLib import TTFont
    except ImportError as e:
        msg = (
            "OpenType (CFF), WOFF and WOFF2 fonts need fontTools, which is not"
            f" installed: {EXTRA_HINT}"
        )
        raise ImportError(msg) from e

    # fontTools reads a table when it is first used, so a damaged font can
    # fail anywhere from here to save(). The modification time is kept, so
    # the same font always converts to the same bytes.
    try:
        font = TTFont(io.BytesIO(data), recalcTimestamp=False)
        font.flavor = None
        _truetype_outlines(font)
        out = io.BytesIO()
        font.save(out)
    except ImportError as e:
        # fontTools imports brotli only when it meets a WOFF2 file.
        msg = f"WOFF2 fonts need brotli, which is not installed: {EXTRA_HINT}"
        raise ImportError(msg) from e
    except (FontConversionError, RenderLimitError):
        raise
    except Exception as e:
        msg = f"not a font fontTools can read: {e!r}"
        raise FontConversionError(msg) from e
    return out.getvalue()


def _truetype_outlines(font) -> None:
    """Give `font` TrueType outlines, converting its CFF ones if it has them."""
    outlines = next((tag for tag in ("CFF ", "CFF2") if tag in font), None)
    if outlines is not None:
        _cff_to_glyf(font, outlines)
    elif "glyf" not in font:
        msg = "the font has no outlines (neither glyf nor CFF)"
        raise FontConversionError(msg)


def _cff_to_glyf(font, outlines: str) -> None:
    """Replace the PostScript outlines of `font` with TrueType ones."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable

    order = font.getGlyphOrder()
    # A variable CFF2 font is drawn at its default instance.
    glyph_set = font.getGlyphSet()
    glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = {}
    for index, name in enumerate(order):
        if index % DEADLINE_STEP == 0:
            check_deadline()
        pen = TTGlyphPen(glyph_set)
        # PostScript contours run counter-clockwise, TrueType ones clockwise.
        glyph_set[name].draw(Cu2QuPen(pen, MAX_ERROR, reverse_direction=True))
        glyf[name] = pen.glyph()
    font["glyf"] = glyf
    font["loca"] = newTable("loca")
    font["head"].glyphDataFormat = 0

    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    for attribute in (
        "maxTwilightPoints",
        "maxStorage",
        "maxFunctionDefs",
        "maxInstructionDefs",
        "maxStackElements",
        "maxSizeOfInstructions",
        "maxComponentElements",
    ):
        setattr(maxp, attribute, 0)

    # TrueType keeps glyph names in post format 2; CFF holds them itself.
    post = font["post"]
    post.formatType = 2.0
    post.extraNames = []
    post.mapping = {}
    post.glyphOrder = order

    for tag in (outlines, "VORG", "HVAR", "VVAR", "MVAR", "fvar", "avar", "STAT"):
        if tag in font:
            del font[tag]
    font.sfntVersion = "\x00\x01\x00\x00"
