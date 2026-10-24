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
import re
import sys
from collections import Counter

import pypdf

from xhtml2pdf.builders.preflight import PRINT_PPI, PageReport, resolve, scan


def inspect(path: str) -> tuple[dict, list[PageReport]]:
    reader = pypdf.PdfReader(path)
    with open(path, "rb") as fh:
        header = fh.read(16)
    version = re.match(rb"%PDF-(\d\.\d)", header)
    root = reader.trailer["/Root"]
    info = reader.trailer.get("/Info")
    info = resolve(info) or {}
    intents = []
    for intent in resolve(root.get("/OutputIntents")) or []:
        intent = resolve(intent)
        profile = resolve(intent.get("/DestOutputProfile"))
        intents.append(
            {
                "S": str(intent.get("/S")),
                "condition": str(intent.get("/OutputConditionIdentifier")),
                "profile N": profile.get("/N") if profile is not None else None,
            }
        )
    metadata = resolve(root.get("/Metadata"))
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

    return doc, scan(reader)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("pdf")
    parser.add_argument("--min-ppi", type=float, default=PRINT_PPI)
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
        managed_rgb = "DefaultRGB" in page.default_spaces
        if page.default_spaces:
            print(f"  defaults  {', '.join(sorted(page.default_spaces))}")
        if page.colors.get("DeviceRGB") and not managed_rgb:
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
            if image.color_space.startswith("DeviceRGB") and not managed_rgb:
                problems["RGB images"] += 1
        for font in sorted(page.fonts.values(), key=lambda font: font.name):
            use = "draws text" if font.drawn else "referenced only"
            flag = "" if font.embedded else "  << NOT EMBEDDED"
            print(f"  font      {font.name} ({use}){flag}")
            if not font.embedded:
                problems[f"font {font.name} not embedded"] += 1

    print("\nsummary")
    if not problems:
        print("  nothing to report")
    for problem, count in problems.items():
        print(f"  {problem}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
