"""
What a print shop's preflight looks at in a finished PDF.

`scan` follows the content of every page, and of the forms it draws, and
records the images with the resolution each is drawn at, the fonts with
whether each is embedded and whether it draws any text, the colour
operators, and the use of transparency. `warn` logs what a print job should
know about; `drop_idle_fonts` takes out the fonts that are named in a content
stream without ever drawing a glyph.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field

from pypdf.generic import ContentStream, EncodedStreamObject, IndirectObject, NameObject

log = logging.getLogger(__name__)

#: The resolution below which an image looks soft in offset print.
PRINT_PPI: float = 300.0

#: Content-stream operators that set a colour, by the colour space they imply.
COLOR_OPERATORS: dict[str, str] = {
    "rg": "DeviceRGB",
    "RG": "DeviceRGB",
    "k": "DeviceCMYK",
    "K": "DeviceCMYK",
    "g": "DeviceGray",
    "G": "DeviceGray",
    "cs": "named",
    "CS": "named",
}

TEXT_SHOWING: frozenset[str] = frozenset({"Tj", "TJ", "'", '"'})

#: How deep forms drawing forms are followed.
MAX_FORM_DEPTH = 20

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass
class ImageUse:
    name: str
    width: int
    height: int
    color_space: str
    filters: str
    drawn_w: float
    drawn_h: float

    @property
    def ppi(self) -> float:
        """Resolution along the less dense axis, in pixels per inch."""
        if not self.drawn_w or not self.drawn_h:
            return math.inf
        return min(self.width / self.drawn_w, self.height / self.drawn_h) * 72


@dataclass
class FontUse:
    name: str
    embedded: bool
    drawn: bool = False


@dataclass
class PageReport:
    number: int
    boxes: dict[str, list[float]] = field(default_factory=dict)
    colors: Counter = field(default_factory=Counter)
    images: list[ImageUse] = field(default_factory=list)
    #: Keyed by the font dictionary's object, so that two resource names for
    #: one font count once.
    fonts: dict[object, FontUse] = field(default_factory=dict)
    transparency: bool = False
    #: The default colour spaces the page sets: DefaultRGB, DefaultGray...
    default_spaces: set[str] = field(default_factory=set)


def resolve(obj):
    return obj.get_object() if isinstance(obj, IndirectObject) else obj


def replace_stream_data(stream, data: bytes) -> None:
    """
    Give a stream object new data, Flate-encoded whatever its filters were.

    pypdf rewrites only a stream whose sole filter is FlateDecode, and
    reportlab writes its forms through ASCII85Decode as well.
    """
    if isinstance(stream, EncodedStreamObject):
        stream.get_data()
        stream[NameObject("/Filter")] = NameObject("/FlateDecode")
        stream.pop("/DecodeParms", None)
    stream.set_data(data)


def font_key(ref) -> object:
    """The identity of a font dictionary, from its reference in /Font."""
    if isinstance(ref, IndirectObject):
        return ("ref", ref.idnum, ref.generation)
    return ("direct", id(ref))


def color_space_name(cs) -> str:
    cs = resolve(cs)
    if cs is None:
        return "-"
    if isinstance(cs, list):
        head = str(cs[0])
        if head == "/ICCBased":
            return f"ICCBased(N={resolve(cs[1]).get('/N')})"
        if head in {"/Indexed", "/Separation", "/DeviceN"}:
            base = cs[1] if head == "/Indexed" else cs[2]
            return f"{head[1:]}({color_space_name(base)})"
        return head[1:]
    return str(cs).lstrip("/")


def font_embedded(font) -> bool:
    font = resolve(font)
    if font.get("/Subtype") == "/Type3":
        return True
    if font.get("/Subtype") == "/Type0":
        font = resolve(resolve(font["/DescendantFonts"])[0])
    descriptor = resolve(font.get("/FontDescriptor"))
    if descriptor is None:
        return False
    return any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))


def _multiply(a, b) -> tuple[float, ...]:
    return (
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    )


def _walk(content, resources, ctm, report: PageReport, pdf, depth: int = 0) -> None:
    """Follow one content stream, recording colours, images, fonts and forms."""
    resources = resolve(resources) or {}
    xobjects = resolve(resources.get("/XObject")) or {}
    fonts = resolve(resources.get("/Font")) or {}
    keys = {}
    for name, ref in fonts.items():
        key = font_key(ref)
        keys[name] = key
        if key not in report.fonts:
            base = str(resolve(ref).get("/BaseFont", name)).lstrip("/")
            report.fonts[key] = FontUse(base, font_embedded(ref))
    for state in (resolve(resources.get("/ExtGState")) or {}).values():
        state = resolve(state)
        if state.get("/SMask", "/None") != "/None" or any(
            float(state.get(key, 1)) < 1 for key in ("/ca", "/CA")
        ):
            report.transparency = True

    # The font is part of the graphics state, so q and Q save and restore it.
    stack: list[tuple[tuple[float, ...], object]] = []
    font = None
    for operands, operator in ContentStream(content, pdf).operations:
        op = operator.decode("latin-1")
        if op == "q":
            stack.append((ctm, font))
        elif op == "Q" and stack:
            ctm, font = stack.pop()
        elif op == "cm":
            ctm = _multiply([float(x) for x in operands], ctm)
        elif op == "Tf":
            font = keys.get(operands[0])
        elif op in TEXT_SHOWING and font in report.fonts:
            report.fonts[font].drawn = True
        elif op in COLOR_OPERATORS:
            kind = COLOR_OPERATORS[op]
            if kind == "named":
                kind = str(operands[0]).lstrip("/")
            report.colors[kind] += 1
        elif op == "Do":
            xobj = resolve(xobjects.get(operands[0]))
            if xobj is None:
                continue
            if xobj.get("/SMask") is not None:
                report.transparency = True
            if xobj.get("/Subtype") == "/Image":
                filters = xobj.get("/Filter", "")
                if isinstance(filters, list):
                    filters = ",".join(str(f).lstrip("/") for f in filters)
                report.images.append(
                    ImageUse(
                        name=str(operands[0]),
                        width=int(xobj["/Width"]),
                        height=int(xobj["/Height"]),
                        color_space=color_space_name(xobj.get("/ColorSpace")),
                        filters=str(filters).lstrip("/"),
                        drawn_w=math.hypot(ctm[0], ctm[1]),
                        drawn_h=math.hypot(ctm[2], ctm[3]),
                    )
                )
            elif xobj.get("/Subtype") == "/Form" and depth < MAX_FORM_DEPTH:
                matrix = [float(x) for x in xobj.get("/Matrix", IDENTITY)]
                _walk(
                    xobj,
                    xobj.get("/Resources", resources),
                    _multiply(matrix, ctm),
                    report,
                    pdf,
                    depth + 1,
                )


def scan(pdf) -> list[PageReport]:
    """Scan every page of a pypdf reader or writer."""
    reports = []
    for number, page in enumerate(pdf.pages, 1):
        report = PageReport(number)
        for box in ("/MediaBox", "/CropBox", "/BleedBox", "/TrimBox", "/ArtBox"):
            if box in page:
                report.boxes[box[1:]] = [round(float(v), 2) for v in page[box]]
        resources = resolve(page.get("/Resources")) or {}
        spaces = resolve(resources.get("/ColorSpace")) or {}
        report.default_spaces = {
            name.lstrip("/") for name in spaces if name.startswith("/Default")
        }
        contents = page.get_contents()
        if contents is not None:
            _walk(contents, resources, IDENTITY, report, pdf)
        reports.append(report)
    return reports


def unembedded_text_fonts(reports: list[PageReport]) -> list[str]:
    """The fonts that draw text without being embedded, by name."""
    return sorted(
        {
            font.name
            for report in reports
            for font in report.fonts.values()
            if font.drawn and not font.embedded
        }
    )


def warn(reports: list[PageReport], min_ppi: float = PRINT_PPI) -> None:
    """Log the images too coarse for print and the fonts left out of the file."""
    seen = set()
    for report in reports:
        for image in report.images:
            if image.ppi >= min_ppi or image.name in seen:
                continue
            seen.add(image.name)
            log.warning(
                "An image of %dx%d pixels is drawn at %.0f ppi on page %d; print"
                " wants %.0f ppi, which at that size takes %dx%d pixels.",
                image.width,
                image.height,
                image.ppi,
                report.number,
                min_ppi,
                math.ceil(image.drawn_w / 72 * min_ppi),
                math.ceil(image.drawn_h / 72 * min_ppi),
            )
    fonts = unembedded_text_fonts(reports)
    if fonts:
        log.warning(
            "Text is set in fonts that are not embedded in the PDF: %s. The"
            " printer substitutes its own. Embed a face with @font-face.",
            ", ".join(fonts),
        )


def _drop_tf(content, resources, idle: set, pdf, forms: list, depth: int = 0):
    """
    Remove the Tf operators of `content` that select an idle font.

    No glyph is drawn while an idle font is current, so dropping the operator
    that makes it current leaves every glyph drawn with the font it had.
    The resources of the forms it draws are added to `forms`, for their fonts
    to be taken out once every stream is rewritten. Returns the rewritten
    stream, or None when nothing changed.
    """
    resources = resolve(resources) or {}
    fonts = resolve(resources.get("/Font")) or {}
    idle_names = {name for name, ref in fonts.items() if font_key(ref) in idle}
    for xobj in (resolve(resources.get("/XObject")) or {}).values():
        xobj = resolve(xobj)
        if xobj.get("/Subtype") == "/Form" and depth < MAX_FORM_DEPTH:
            rewritten = _drop_tf(
                xobj, xobj.get("/Resources", resources), idle, pdf, forms, depth + 1
            )
            if rewritten is not None:
                replace_stream_data(xobj, rewritten.get_data())
            forms.append(xobj.get("/Resources"))
    if not idle_names:
        return None
    stream = ContentStream(content, pdf)
    kept = [
        (operands, operator)
        for operands, operator in stream.operations
        if not (operator == b"Tf" and operands and operands[0] in idle_names)
    ]
    if len(kept) == len(stream.operations):
        return None
    stream.operations = kept
    return stream


def _drop_font_resources(resources, idle: set) -> None:
    fonts = resolve((resolve(resources) or {}).get("/Font"))
    if not fonts:
        return
    for name in [name for name, ref in fonts.items() if font_key(ref) in idle]:
        del fonts[NameObject(name)]


def drop_idle_fonts(writer) -> list[str]:
    """
    Take out the fonts that are never embedded and never draw a glyph.

    reportlab selects its initial font, Helvetica, at the top of every page,
    and a drawing selects a font before it knows whether it has text; a
    preflight reports each of those as a font missing from the file. Returns
    the names of the fonts taken out.
    """
    reports = scan(writer)
    fonts: dict[object, FontUse] = {}
    for report in reports:
        for key, font in report.fonts.items():
            if key in fonts:
                fonts[key].drawn |= font.drawn
            else:
                fonts[key] = FontUse(font.name, font.embedded, font.drawn)
    idle = {key for key, font in fonts.items() if not font.embedded and not font.drawn}
    if not idle:
        return []
    # Pages share reportlab's /Font dictionary, so fonts leave the resources
    # only after every content stream has been rewritten.
    resources: list = []
    for page in writer.pages:
        contents = page.get_contents()
        if contents is not None:
            rewritten = _drop_tf(
                contents, page.get("/Resources"), idle, writer, resources
            )
            if rewritten is not None:
                page.replace_contents(rewritten)
        resources.append(page.get("/Resources"))
    for found in resources:
        _drop_font_resources(found, idle)
    return sorted({fonts[key].name for key in idle})
