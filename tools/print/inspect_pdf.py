"""
Report what a print shop's preflight looks at in a PDF.

    python tools/print/inspect_pdf.py document.pdf [--min-ppi 300]

For each page: the page boxes, the colour operators its content uses, every
image with its colour space and the resolution it is drawn at, and the fonts
it uses with whether each is embedded. For the document: the PDF version and
the PDF/X markers (output intent, XMP metadata, the Info keys).

This is an inspection aid, not a PDF/X validator.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

import pypdf
from pypdf.generic import ContentStream, IndirectObject

#: Content-stream operators that set a colour, by the colour space they imply.
COLOR_OPERATORS = {
    "rg": "DeviceRGB",
    "RG": "DeviceRGB",
    "k": "DeviceCMYK",
    "K": "DeviceCMYK",
    "g": "DeviceGray",
    "G": "DeviceGray",
    "cs": "named",
    "CS": "named",
}


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
class PageReport:
    number: int
    boxes: dict[str, list[float]]
    colors: Counter = field(default_factory=Counter)
    images: list[ImageUse] = field(default_factory=list)
    fonts: dict[str, bool] = field(default_factory=dict)
    fonts_drawn: set[str] = field(default_factory=set)
    transparency: bool = False


def _resolve(obj):
    return obj.get_object() if isinstance(obj, IndirectObject) else obj


def _color_space_name(cs) -> str:
    cs = _resolve(cs)
    if cs is None:
        return "-"
    if isinstance(cs, list):
        head = str(cs[0])
        if head == "/ICCBased":
            n = _resolve(cs[1]).get("/N")
            return f"ICCBased(N={n})"
        if head in {"/Indexed", "/Separation", "/DeviceN"}:
            return (
                head[1:]
                + "("
                + _color_space_name(cs[1] if head == "/Indexed" else cs[2])
                + ")"
            )
        return head[1:]
    return str(cs).lstrip("/")


def _font_embedded(font) -> bool:
    font = _resolve(font)
    if font.get("/Subtype") == "/Type3":
        return True
    if font.get("/Subtype") == "/Type0":
        font = _resolve(_resolve(font["/DescendantFonts"])[0])
    desc = _resolve(font.get("/FontDescriptor"))
    if desc is None:
        return False
    return any(key in desc for key in ("/FontFile", "/FontFile2", "/FontFile3"))


def _multiply(a, b):
    return [
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    ]


def _walk(content, resources, ctm, report: PageReport, reader, depth=0) -> None:
    """Follow a content stream, recording colours, images, fonts and forms."""
    resources = _resolve(resources) or {}
    xobjects = _resolve(resources.get("/XObject")) or {}
    fonts = _resolve(resources.get("/Font")) or {}
    base_names = {}
    for name, font in fonts.items():
        base = str(_resolve(font).get("/BaseFont", name)).lstrip("/")
        base_names[name] = base
        report.fonts[base] = _font_embedded(font)
    for gs in (_resolve(resources.get("/ExtGState")) or {}).values():
        gs = _resolve(gs)
        if gs.get("/SMask", "/None") != "/None" or any(
            float(gs.get(key, 1)) < 1 for key in ("/ca", "/CA")
        ):
            report.transparency = True

    stack = []
    current_font = None
    for operands, operator in ContentStream(content, reader).operations:
        op = operator.decode("latin-1")
        if op == "q":
            stack.append(ctm)
        elif op == "Q" and stack:
            ctm = stack.pop()
        elif op == "cm":
            ctm = _multiply([float(x) for x in operands], ctm)
        elif op == "Tf":
            current_font = base_names.get(operands[0], str(operands[0]))
        elif op in {"Tj", "TJ", "'", '"'} and current_font:
            report.fonts_drawn.add(current_font)
        elif op in COLOR_OPERATORS:
            kind = COLOR_OPERATORS[op]
            if kind == "named":
                kind = str(operands[0]).lstrip("/")
            report.colors[kind] += 1
        elif op == "Do":
            xobj = _resolve(xobjects.get(operands[0]))
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
                        color_space=_color_space_name(xobj.get("/ColorSpace")),
                        filters=str(filters).lstrip("/"),
                        drawn_w=math.hypot(ctm[0], ctm[1]),
                        drawn_h=math.hypot(ctm[2], ctm[3]),
                    )
                )
            elif xobj.get("/Subtype") == "/Form" and depth < 20:
                matrix = [float(x) for x in xobj.get("/Matrix", [1, 0, 0, 1, 0, 0])]
                _walk(
                    xobj,
                    xobj.get("/Resources", resources),
                    _multiply(matrix, ctm),
                    report,
                    reader,
                    depth + 1,
                )


def inspect(path: str) -> tuple[dict, list[PageReport]]:
    reader = pypdf.PdfReader(path)
    with open(path, "rb") as fh:
        header = fh.read(16)
    version = re.match(rb"%PDF-(\d\.\d)", header)
    root = reader.trailer["/Root"]
    info = reader.trailer.get("/Info")
    info = _resolve(info) or {}
    intents = []
    for intent in _resolve(root.get("/OutputIntents")) or []:
        intent = _resolve(intent)
        profile = _resolve(intent.get("/DestOutputProfile"))
        intents.append(
            {
                "S": str(intent.get("/S")),
                "condition": str(intent.get("/OutputConditionIdentifier")),
                "profile N": profile.get("/N") if profile is not None else None,
            }
        )
    metadata = _resolve(root.get("/Metadata"))
    xmp = metadata.get_data().decode("utf-8", "replace") if metadata is not None else ""
    pdfx_xmp = re.search(r"GTS_PDFXVersion[>=\"']+([^<\"']+)", xmp)
    doc = {
        "version": version.group(1).decode() if version else "?",
        "pages": len(reader.pages),
        "output intents": intents,
        "XMP": bool(xmp),
        "XMP GTS_PDFXVersion": pdfx_xmp.group(1) if pdfx_xmp else None,
        "Info GTS_PDFXVersion": info.get("/GTS_PDFXVersion"),
        "Info Trapped": info.get("/Trapped"),
        "ID": "/ID" in reader.trailer,
        "encrypted": reader.is_encrypted,
    }

    pages = []
    for number, page in enumerate(reader.pages, 1):
        boxes = {}
        for box in ("/MediaBox", "/CropBox", "/BleedBox", "/TrimBox", "/ArtBox"):
            if box in page:
                boxes[box[1:]] = [round(float(v), 2) for v in page[box]]
        report = PageReport(number, boxes)
        default_cs = (
            _resolve((_resolve(page.get("/Resources")) or {}).get("/ColorSpace")) or {}
        )
        for key in ("/DefaultRGB", "/DefaultGray", "/DefaultCMYK"):
            if key in default_cs:
                report.colors[key[1:] + " set"] += 0
        contents = page.get_contents()
        if contents is not None:
            _walk(contents, page.get("/Resources"), [1, 0, 0, 1, 0, 0], report, reader)
        pages.append(report)
    return doc, pages


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("pdf")
    parser.add_argument("--min-ppi", type=float, default=300)
    args = parser.parse_args(argv)

    doc, pages = inspect(args.pdf)
    print(f"{args.pdf}: PDF {doc['version']}, {doc['pages']} pages")
    for key, value in doc.items():
        if key not in {"version", "pages"}:
            print(f"  {key}: {value}")

    problems: Counter[str] = Counter()
    for page in pages:
        print(f"\npage {page.number}")
        for box, value in page.boxes.items():
            print(f"  {box:9} {value}")
        if "TrimBox" not in page.boxes and "ArtBox" not in page.boxes:
            problems["pages without TrimBox"] += 1
        colors = ", ".join(
            f"{k}x{v}" if v else k for k, v in sorted(page.colors.items())
        )
        print(f"  colours   {colors or '-'}")
        if page.colors.get("DeviceRGB"):
            problems["pages with DeviceRGB colour"] += 1
        if page.transparency:
            print("  transparency used")
            problems["pages with transparency"] += 1
        for image in page.images:
            low = image.ppi < args.min_ppi
            print(
                f"  image     {image.width}x{image.height} {image.color_space}"
                f" [{image.filters}] drawn {image.drawn_w:.1f}x{image.drawn_h:.1f}pt"
                f" = {image.ppi:.0f} ppi{'  << LOW' if low else ''}"
            )
            if low:
                problems[f"images under {args.min_ppi:.0f} ppi"] += 1
            if image.color_space.startswith("DeviceRGB"):
                problems["RGB images"] += 1
        for name, embedded in sorted(page.fonts.items()):
            use = "draws text" if name in page.fonts_drawn else "referenced only"
            flag = "" if embedded else "  << NOT EMBEDDED"
            print(f"  font      {name} ({use}){flag}")
            if not embedded:
                problems[f"font {name} not embedded"] += 1

    print("\nsummary")
    if not problems:
        print("  nothing to report")
    for problem, count in problems.items():
        print(f"  {problem}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
